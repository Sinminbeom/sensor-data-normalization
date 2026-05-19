"""NormalizerManager — 정규화 daemon 프로세스.

daemon 시작 시 별도 프로세스 진입 → 영구 실행. 매 action() 마다:
  1. Redis queue poll (listener 합성)
  2. 메시지가 자기 receiver 대상이면 cycle 진입:
     - 파일 수집 → device 필터 → StorageFile 들을 shared_job_queue 에 push
     - worker 들이 IPC queue 로 보내는 WorkerMessage (PairPutMessage / JobDoneMessage)
       를 drain 하면서 PairBuckets / JobProgressTracker (manager 단독 owner) 업데이트.
       매칭된 pair 는 즉시 merge + upload.
     - cycle 끝의 PairBuckets 잔여 sweep + upload
     - Slack notify (notifier 합성)

cycle 컨텍스트(request_id/date/vehicle_id/selected_device)는 cycle 동안만 살아 있는
**instance field** 로 보유 (ClassVar 안티패턴 아님).
"""

import os
import time
from typing import ClassVar, cast

from python_library.logger.app_logger import AppLogger
from python_library.process.queue_process import QueueProcessing
from python_library.storage.s3.s3_storage_factory import S3StorageFactory
from python_library.storage.s3.s3_storage_info_factory import S3StorageInfoFactory
from python_library.storage.storage import IStorage
from python_library.storage.storage_file import StorageFile

from config.project_config import ProjectConfig
from listener.normalization_request_listener import (
    NormalizationRequestListener,
)
from notification.log_notifier import LogNotifier
from notification.notification_sender import INotificationSender
from pcap.local_pcap_splitter import LocalPcapSplitter
from pcap.pcap_filename_parser import PcapFilenameParser
from pcap.splitter import IPcapSplitter
from pcap.unprocessed_pcap import UnprocessedPcap
from process_state.job_progress import JobProgressTracker
from process_state.pair_buckets import PairBuckets
from protocol.job_done import JobDoneMessage
from protocol.message import abMessage
from protocol.normalization_request import NormalizationRequest
from protocol.pair_put import PairPutMessage
from protocol.protocol_meta import ProtocolMeta
from sensor_category.enum_sensor import E_SENSOR_TYPE
from sensor_category.sensor_registry import SensorRegistry


class NormalizerManager(QueueProcessing):
    PROCESS_NAME: ClassVar[str] = "NORMALIZER_MANAGER"
    _POLL_TIMEOUT_SEC = 1.0
    _DRAIN_IDLE_SLEEP_SEC = 0.01

    def __init__(self) -> None:
        super().__init__(name=NormalizerManager.PROCESS_NAME)
        self._process_name = NormalizerManager.PROCESS_NAME
        # 모든 의존성은 자식 안의 on_init 에서 명시 setup (fork-inherit 의존 없음).
        # __init__ 에선 pickle 가능한 metadata 만 보유 (spawn 호환).
        self._storage: IStorage | None = None
        self._splitter: IPcapSplitter | None = None
        self._listener: NormalizationRequestListener | None = None
        self._notifier: INotificationSender | None = None
        # manager 단독 owner — worker 는 IPC queue 메시지로만 업데이트 (#27).
        self._pair_buckets: PairBuckets | None = None
        self._progress: JobProgressTracker | None = None

    # ---------- lifecycle ----------

    def run(self) -> None:
        # 자식 프로세스 진입 직후 1회. QueueProcessing.run() 의 while 루프를 그대로
        # 유지하면서 on_init 만 앞에 추가.
        self.on_init()
        try:
            while not self.is_stop():
                self.action()
        except Exception as e:
            raise e

    def on_init(self) -> None:
        ProjectConfig.set_config(ProjectConfig.DEFAULT_CONFIG_PATH)
        # AppLogger 는 Singleton — 자식 프로세스 안에서 set_config 후 첫 `AppLogger.instance()`
        # 호출 시점에 logging.conf 가 fileConfig 로 적용. NAME 을 process 별로 박아
        # 로그에서 어떤 프로세스 출력인지 식별 가능.
        AppLogger.set_config(
            ProjectConfig.DEFAULT_LOGGING_CONFIG_PATH,
            f"{ProjectConfig.LOGGER_BASE_NAME}.{self._process_name}",
        )

        SensorRegistry.instance().register()

        self._pair_buckets = PairBuckets()
        self._progress = JobProgressTracker()

        self._storage = self._build_storage()
        self._storage.connect()
        self._splitter = LocalPcapSplitter()

        self._listener = NormalizationRequestListener()
        # 개발 단계 기본값: 로그만. Slack 발송으로 전환하려면
        # notification.slack_webhook_notifier.SlackWebhookNotifier 로 교체.
        self._notifier = LogNotifier()

        AppLogger.instance().info(
            f"pid={os.getpid()} || {self._process_name} init "
            f"(workers={ProjectConfig.instance().worker_count})"
        )

    def action(self) -> None:
        assert self._listener is not None
        request = self._listener.poll(timeout_sec=NormalizerManager._POLL_TIMEOUT_SEC)
        if request is None:
            return

        self._handle_request(request)

    # ---------- cycle ----------

    def _handle_request(self, request: NormalizationRequest) -> None:
        assert self._notifier is not None
        assert self._progress is not None
        selected_device = (
            request.selected_device or ProjectConfig.instance().selected_device
        )
        summary = (
            f"date={request.date} "
            f"vehicle_id={request.vehicle_id or 'ALL'} "
            f"selected_device={selected_device}"
        )
        AppLogger.instance().info(f"[{request.request_id}] start | {summary}")
        try:
            self._run_cycle(request, selected_device)
        except Exception as e:
            AppLogger.instance().exception(f"[{request.request_id}] pipeline failed")
            self._notifier.notify_failure(request.request_id, summary, repr(e))
            return

        succeeded = self._progress.success_count()
        failed = self._progress.failure_count()
        total = succeeded + failed
        if failed > 0:
            AppLogger.instance().error(
                f"[{request.request_id}] partial failure: {failed}/{total} job(s) failed"
            )
            self._notifier.notify_failure(
                request.request_id,
                summary,
                error=f"partial failure: {failed}/{total} job(s) failed",
            )
            return
        AppLogger.instance().info(
            f"[{request.request_id}] done | {succeeded}/{total} job(s) succeeded"
        )
        self._notifier.notify_success(request.request_id, summary)

    def _run_cycle(self, request: NormalizationRequest, selected_device: str) -> None:
        assert self._pair_buckets is not None
        assert self._progress is not None
        file_list = self._collect_file_list(request.date, request.vehicle_id)
        jobs = self._filter_by_device(file_list, selected_device)

        # 새 cycle 시작 시 PairBuckets 잔여 초기화 (이전 cycle 의 unmatched 가 남아
        # 있으면 안 됨 — cycle 끝의 _upload_unpaired 가 sweep 하지만 안전망).
        self._pair_buckets = PairBuckets()
        self._progress.begin_cycle(len(jobs))
        for file_obj in jobs:
            self.push_shared_job_queue(file_obj)

        self._drain_worker_messages()
        self._upload_unpaired(self._pair_buckets.pop_all_remaining())

    def _drain_worker_messages(self) -> None:
        """progress.is_done 이 될 때까지 자기 mailbox 에서 메시지를 받아 처리."""
        assert self._progress is not None
        while not self._progress.is_done():
            if self.is_stop():
                return
            body = self.pop_shared_queue(self._process_name)
            if body is None:
                time.sleep(NormalizerManager._DRAIN_IDLE_SLEEP_SEC)
                continue
            self._dispatch_message(
                cast(abMessage, ProtocolMeta.instance().decode_body(body))
            )

    def _dispatch_message(self, msg: abMessage) -> None:
        assert self._pair_buckets is not None
        assert self._progress is not None
        if isinstance(msg, JobDoneMessage):
            self._progress.mark_one_done(success=msg.success)
            return
        if isinstance(msg, PairPutMessage):
            paired = self._pair_buckets.put(msg.pair_key, msg.item)
            if paired is not None:
                self._merge_pair(paired)
            return
        raise ValueError(f"unexpected message: {type(msg).__name__}")

    # ---------- pair merge (manager owner) ----------

    def _merge_pair(self, paired_list: list[UnprocessedPcap]) -> None:
        assert self._storage is not None
        assert self._splitter is not None
        pcap_files = [item.src_path for item in paired_list]
        out_file_path = paired_list[0].out_file_path
        prefix_path = paired_list[0].prefix_path

        self._splitter.merge_pcap_files(pcap_files, out_file_path)
        self._storage.upload(out_file_path, prefix_path)

        if os.path.isfile(out_file_path):
            os.remove(out_file_path)
        for f in pcap_files:
            if os.path.isfile(f):
                os.remove(f)

    # ---------- file collection ----------

    def _collect_file_list(
        self, date_folder: str, vehicle_id: str
    ) -> list[StorageFile]:
        assert self._storage is not None
        raw_root = ProjectConfig.instance().get_raw_storage_full_path()
        process_folder = f"{raw_root}/{date_folder}"

        if not self._storage.is_exists(process_folder):
            AppLogger.instance().error(f"path not exists: {process_folder}")
            return []

        all_files = [
            f for f in self._storage.get_file_list(process_folder) if not f.is_dir()
        ]
        if vehicle_id:
            return [f for f in all_files if vehicle_id in f.get_file_path()]
        return all_files

    def _filter_by_device(
        self, file_list: list[StorageFile], selected_device: str
    ) -> list[StorageFile]:
        filtered: list[StorageFile] = []
        for file_obj in file_list:
            file_name = file_obj.get_file_name()
            if "temp" in file_name:
                continue

            if selected_device == E_SENSOR_TYPE.ALL:
                filtered.append(file_obj)
                continue

            parts = PcapFilenameParser.parse(file_name)
            sensor_type = SensorRegistry.instance().get_sensor_type(
                parts.module_name.upper()
            )

            if selected_device.upper() == sensor_type:
                filtered.append(file_obj)
                continue

            if selected_device.lower() in file_name:
                filtered.append(file_obj)
        return filtered

    # ---------- final upload ----------

    def _upload_unpaired(self, unpaired: list[list[UnprocessedPcap]]) -> None:
        assert self._storage is not None
        for bucket in unpaired:
            head = bucket[0]
            src_path = os.path.abspath(head.src_path)
            self._storage.upload(src_path, head.prefix_path)
            AppLogger.instance().info(f"unPairedPcap={src_path}")
            if os.path.isfile(src_path):
                os.remove(src_path)

    # ---------- helpers ----------

    def _build_storage(self) -> IStorage:
        return S3StorageFactory(S3StorageInfoFactory()).create_storage()
