"""NormalizerManager — 정규화 daemon 프로세스.

daemon 시작 시 한 번 fork → 영구 실행. 매 action() 마다:
  1. Redis pub/sub 채널 poll (listener 합성)
  2. 메시지가 자기 receiver 대상이면 cycle 진입:
     - 파일 수집 → device 필터 → StorageFile 들을 shared_job_queue 에 push
     - JobProgressTracker 카운터로 NormalizerModule × N 의 완료 감지
     - PairBuckets 잔여 sweep
     - Slack notify (notifier 합성)

cycle 컨텍스트(request_id/date/vehicle_id/selected_device)는 cycle 동안만 살아 있는
**instance field** 로 보유 (ClassVar 안티패턴 아님).
"""

import logging
import os
import time

from python_library.process.queue_process import QueueProcessing
from python_library.storage.s3.s3_storage_factory import S3StorageFactory
from python_library.storage.s3.s3_storage_info_factory import S3StorageInfoFactory
from python_library.storage.storage import IStorage
from python_library.storage.storage_file import StorageFile

from common.event_bus.listener.normalization_request_listener import (
    NormalizationRequestListener,
)
from common.notification.log_notifier import LogNotifier
from common.notification.notification_sender import INotificationSender
from common.process_state.job_progress import JobProgressTracker
from common.process_state.pair_buckets import PairBuckets
from common.protocol.normalization_request import NormalizationRequest
from config.project_config import ProjectConfig
from pcap.pcap_filename_parser import PcapFilenameParser
from pcap.unprocessed_pcap import UnprocessedPcap
from sensor_category.enum_sensor import E_SENSOR_TYPE
from sensor_category.sensor_registry import SensorRegistry


class NormalizerManager(QueueProcessing):
    _POLL_TIMEOUT_SEC = 1.0
    _CYCLE_WAIT_INTERVAL_SEC = 0.1

    def __init__(self, app_name: str, process_name: str):
        super().__init__(name=process_name)
        self._app_name = app_name
        self._process_name = process_name
        self._logger = logging.getLogger(
            f"{ProjectConfig.LOGGER_BASE_NAME}.{process_name}"
        )
        # 싱글톤은 fork 전 부모 프로세스에서 즉시 instance() 호출 → 자식이 inherit.
        self._config = ProjectConfig.instance()
        self._pair_buckets = PairBuckets.instance()
        self._progress = JobProgressTracker.instance()

        # 합성 (composition) — listener / notifier / storage 는 자식 프로세스 안에서 초기화.
        self._storage: IStorage | None = None
        self._listener: NormalizationRequestListener | None = None
        self._notifier: INotificationSender | None = None
        self._initialized = False

    # ---------- lifecycle ----------

    def on_init(self) -> None:
        SensorRegistry.instance().register()

        self._storage = self._build_storage()
        self._storage.connect()

        self._listener = NormalizationRequestListener()
        # 개발 단계 기본값: 로그만. Slack 발송으로 전환하려면
        # common.notification.slack_webhook_notifier.SlackWebhookNotifier 로 교체.
        self._notifier = LogNotifier()

        self._initialized = True
        self._logger.info(
            f"pid={os.getpid()} || {self._process_name} init "
            f"(workers={self._config.worker_count})"
        )

    def action(self) -> None:
        if not self._initialized:
            self.on_init()

        assert self._listener is not None
        request = self._listener.poll(timeout_sec=NormalizerManager._POLL_TIMEOUT_SEC)
        if request is None:
            return

        self._handle_request(request)

    # ---------- cycle ----------

    def _handle_request(self, request: NormalizationRequest) -> None:
        assert self._notifier is not None
        selected_device = request.selected_device or self._config.selected_device
        summary = (
            f"date={request.date} "
            f"vehicle_id={request.vehicle_id or 'ALL'} "
            f"selected_device={selected_device}"
        )
        self._logger.info(f"[{request.request_id}] start | {summary}")
        try:
            self._run_cycle(request, selected_device)
        except Exception as e:
            self._logger.exception(f"[{request.request_id}] pipeline failed")
            self._notifier.notify_failure(request.request_id, summary, repr(e))
            return

        succeeded = self._progress.success_count()
        failed = self._progress.failure_count()
        total = succeeded + failed
        if failed > 0:
            self._logger.error(
                f"[{request.request_id}] partial failure: {failed}/{total} job(s) failed"
            )
            self._notifier.notify_failure(
                request.request_id,
                summary,
                error=f"partial failure: {failed}/{total} job(s) failed",
            )
            return
        self._logger.info(
            f"[{request.request_id}] done | {succeeded}/{total} job(s) succeeded"
        )
        self._notifier.notify_success(request.request_id, summary)

    def _run_cycle(
        self, request: NormalizationRequest, selected_device: str
    ) -> None:
        assert self._storage is not None
        file_list = self._collect_file_list(request.date, request.vehicle_id)
        jobs = self._filter_by_device(file_list, selected_device)

        self._progress.begin_cycle(len(jobs))
        for file_obj in jobs:
            self.push_shared_job_queue(file_obj)

        self._wait_for_completion()
        self._upload_unpaired(self._pair_buckets.pop_all_remaining())

    def _wait_for_completion(self) -> None:
        while not self._progress.is_done():
            if self.is_stop():
                return
            time.sleep(NormalizerManager._CYCLE_WAIT_INTERVAL_SEC)

    # ---------- file collection ----------

    def _collect_file_list(
        self, date_folder: str, vehicle_id: str
    ) -> list[StorageFile]:
        assert self._storage is not None
        raw_root = self._config.get_raw_storage_full_path()
        process_folder = f"{raw_root}/{date_folder}"

        if not self._storage.is_exists(process_folder):
            self._logger.error(f"path not exists: {process_folder}")
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
            self._logger.info(f"unPairedPcap={src_path}")
            if os.path.isfile(src_path):
                os.remove(src_path)

    # ---------- helpers ----------

    def _build_storage(self) -> IStorage:
        return S3StorageFactory(S3StorageInfoFactory()).create_storage()
