"""NormalizerModule — PCAP 다운로드/분할/업로드 워커 프로세스.

daemon 시작 시 별도 프로세스 진입 → 영구 실행. shared_job_queue 에서
StorageFile 을 pop, 다운로드 → 1초 split → MID 업로드. HEAD/TAIL 은 manager 의 mailbox
로 PairPutMessage 송신. job 완료 시 JobDoneMessage 송신. cycle 컨텍스트는 파일 경로
에서 derive (vehicle_id 등) — cycle 별 상태 없음 (stateless worker).
"""

import os
import time
from typing import ClassVar

from python_library.logger.app_logger import AppLogger
from python_library.process.queue_process import QueueProcessing
from python_library.storage.s3.s3_storage_factory import S3StorageFactory
from python_library.storage.s3.s3_storage_info_factory import S3StorageInfoFactory
from python_library.storage.storage import IStorage, StorageFile

from app.normalizer.process.manager.manager import NormalizerManager
from config.project_config import ProjectConfig
from pcap.local_pcap_splitter import LocalPcapSplitter
from pcap.packet_position import E_PACKET_POSITION
from pcap.pcap_filename_parser import PcapFilenameParser
from pcap.splitter import IPcapSplitter, SplitedPcap, SplitOutcome
from pcap.unprocessed_pcap import UnprocessedPcap
from protocol.protocol_meta import E_PROTOCOL_ID, ProtocolMeta
from sensor_category.enum_sensor import E_SENSOR_TYPE
from sensor_category.sensor_registry import SensorRegistry


class NormalizerModule(QueueProcessing):
    _PROCESS_NAME_PREFIX: ClassVar[str] = "NORMALIZER_MODULE"
    _IDLE_SLEEP_SEC = 0.02

    def __init__(self, idx: int) -> None:
        process_name = f"{NormalizerModule._PROCESS_NAME_PREFIX}_{idx}"
        super().__init__(name=process_name)
        self._process_name = process_name
        # __init__ 에서 instance() 호출 없음 (fork-inherit 의존 없음). 모든 의존성은
        # on_init 에서 setup. attribute 는 pickle 가능한 None 으로 시작 (spawn 호환).
        self._storage: IStorage | None = None
        self._splitter: IPcapSplitter | None = None

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
        # 호출 시점에 logging.conf 가 fileConfig 로 적용.
        AppLogger.set_config(
            ProjectConfig.DEFAULT_LOGGING_CONFIG_PATH,
            f"{ProjectConfig.LOGGER_BASE_NAME}.{self._process_name}",
        )

        SensorRegistry.instance().register()

        self._storage = self._build_storage()
        self._storage.connect()
        self._splitter = self._build_splitter()

        AppLogger.instance().info(f"pid={os.getpid()} || {self._process_name} init")

    def action(self) -> None:
        file_obj = self.pop_shared_job_queue()
        if file_obj is None:
            time.sleep(NormalizerModule._IDLE_SLEEP_SEC)
            return

        success = True
        try:
            self._process_file(file_obj)
        except Exception as e:
            success = False
            AppLogger.instance().error(
                f"pid={os.getpid()} || file={file_obj.get_file_name()} errMsg={e}"
            )
        finally:
            self.push_shared_queue(
                NormalizerManager.PROCESS_NAME,
                ProtocolMeta.instance()
                .get_factory(E_PROTOCOL_ID.WORKER_JOB_DONE.value)(
                    sender=self._process_name,
                    receiver=NormalizerManager.PROCESS_NAME,
                    success=success,
                )
                .to_json(),
            )

    # ---------- job (jobQueue → download → split → upload) ----------

    def _process_file(self, file_obj: StorageFile) -> None:
        # file_path 는 파일 자체의 전체 경로 (S3 key 포함). 도메인 컨벤션은
        # `{raw_root}/{date_folder}/{VEHICLE_ID}/{file_name}` 이므로 vehicle_id 는
        # path 의 끝에서 두 번째 segment.
        file_path = file_obj.get_file_path()
        file_name = file_obj.get_file_name()
        vehicle_id = file_path.split("/")[-2]

        self._download(file_path, file_name, vehicle_id)
        outcome = self._split_pcap(file_name, vehicle_id)

        self._upload_processed(vehicle_id, outcome.processed)
        self._send_unprocessed_to_manager(vehicle_id, outcome.unprocessed)

        parts = PcapFilenameParser.parse(file_name)
        module_type = self._get_module_type(parts.module_name)
        if module_type in (E_SENSOR_TYPE.CAMERA, E_SENSOR_TYPE.GNSS):
            time.sleep(0.01)

    def _download(self, file_path: str, file_name: str, vehicle_id: str) -> None:
        assert self._storage is not None
        download_dst_path = self._build_download_dst_path(vehicle_id, file_name)
        # file_path 는 S3 src (파일 전체 경로), dst 는 로컬 디렉토리 + 파일명.
        self._storage.download(file_path, f"{download_dst_path}/{file_name}")

    def _split_pcap(self, file_name: str, vehicle_id: str) -> SplitOutcome:
        assert self._splitter is not None
        download_dst_path = self._build_download_dst_path(vehicle_id, file_name)
        split_src_file = f"{download_dst_path}/{file_name}"
        split_out_template = self._build_split_out_template(vehicle_id, file_name)

        outcome = self._splitter.split_once(split_src_file, split_out_template)

        if os.path.isfile(split_src_file):
            os.remove(split_src_file)

        return outcome

    def _upload_processed(self, vehicle_id: str, processed: list[SplitedPcap]) -> None:
        assert self._storage is not None
        for piece in processed:
            if piece.position != E_PACKET_POSITION.MID:
                continue

            src_path = os.path.abspath(piece.save_path)
            dst_dir = self._build_upload_dst_path(vehicle_id, piece)
            # dst 는 파일 path 여야 함 (boto3 upload_file 의 key 는 OBJECT 이름).
            # 디렉토리만 넘기면 그 디렉토리 자체가 S3 객체로 박힘.
            dst_path = f"{dst_dir}/{os.path.basename(piece.save_path)}"
            self._storage.upload(src_path, dst_path)

            if os.path.isfile(src_path):
                os.remove(src_path)

    # ---------- pair message (manager 단독 owner — worker 는 메시지 송신만) ----------

    def _send_unprocessed_to_manager(
        self, vehicle_id: str, unprocessed: list[SplitedPcap]
    ) -> None:
        for piece in unprocessed:
            if piece.position == E_PACKET_POSITION.MID:
                continue

            pair_key = self._build_pair_key(vehicle_id, piece)
            out_file_path = self._build_unpaired_out_path(vehicle_id, piece)
            # S3 dst 는 디렉토리 path + merge 결과 파일명 (boto3 upload_file 의 key 가
            # OBJECT 의 정확한 이름이므로 디렉토리만 넘기면 그 자체가 객체로 박힘).
            prefix_path = (
                f"{self._build_upload_dst_path(vehicle_id, piece)}/"
                f"{os.path.basename(out_file_path)}"
            )

            unprocessed_pcap = UnprocessedPcap(
                src_path=piece.save_path,
                out_file_path=out_file_path,
                prefix_path=prefix_path,
            )

            self.push_shared_queue(
                NormalizerManager.PROCESS_NAME,
                ProtocolMeta.instance()
                .get_factory(E_PROTOCOL_ID.WORKER_PAIR_PUT.value)(
                    sender=self._process_name,
                    receiver=NormalizerManager.PROCESS_NAME,
                    pair_key=pair_key,
                    item=unprocessed_pcap,
                )
                .to_json(),
            )

    # ---------- path builders ----------

    def _build_download_dst_path(self, vehicle_id: str, file_name: str) -> str:
        parts = PcapFilenameParser.parse(file_name)
        module_type = self._get_module_type(parts.module_name).lower()
        base = ProjectConfig.instance().get_cache_storage_full_path()
        path = (
            f"{base}/{vehicle_id}/{module_type}/{parts.module_name}/"
            f"{parts.date}/{parts.hours}/{parts.minutes}"
        )
        path = os.path.abspath(path)
        os.makedirs(path, exist_ok=True)
        return path

    def _build_split_out_template(self, vehicle_id: str, file_name: str) -> str:
        # splitter 는 로컬 파일을 출력 (LocalPcapSplitter). base 는 cache (로컬).
        # 파일명에 `_split_` 마커를 넣어 원본 다운로드 파일과 충돌 방지
        # (마지막 second 의 split 결과가 원본과 같은 이름을 가지면 자기 자신을 덮어쓰고
        #  _split_pcap 의 os.remove 가 split 결과를 삭제하는 버그).
        parts = PcapFilenameParser.parse(file_name)
        module_type = self._get_module_type(parts.module_name).lower()
        base = ProjectConfig.instance().get_cache_storage_full_path()
        return (
            f"{base}/{vehicle_id}/{module_type}/{parts.module_name}/"
            f"{parts.date}/{parts.hours}/{parts.minutes}/"
            f"{parts.module_name}_split_{{}}.pcap"
        )

    def _build_upload_dst_path(self, vehicle_id: str, piece: SplitedPcap) -> str:
        module_type = self._get_module_type(piece.module_name).lower()
        base = ProjectConfig.instance().get_storage_full_path()
        return (
            f"{base}/{vehicle_id}/{module_type}/{piece.module_name}/"
            f"{piece.date}/{piece.hours}/{piece.minutes}"
        )

    def _build_pair_key(self, vehicle_id: str, piece: SplitedPcap) -> str:
        return (
            f"{vehicle_id}/{piece.module_name}_"
            f"{piece.date}{piece.hours}{piece.minutes}{piece.second}"
        )

    def _build_unpaired_out_path(self, vehicle_id: str, piece: SplitedPcap) -> str:
        module_type = self._get_module_type(piece.module_name).lower()
        base = ProjectConfig.instance().get_unpaired_merge_full_path()
        dir_path = (
            f"{base}/{vehicle_id}/{module_type}/{piece.module_name}/"
            f"{piece.date}/{piece.hours}/{piece.minutes}"
        )
        file_name = (
            f"{piece.module_name}_"
            f"{piece.date}{piece.hours}{piece.minutes}{piece.second}.pcap"
        )
        return os.path.abspath(f"{dir_path}/{file_name}")

    # ---------- helpers ----------

    def _get_module_type(self, module_name: str) -> str:
        return SensorRegistry.instance().get_sensor_type(module_name.upper())

    def _build_storage(self) -> IStorage:
        # S3 표준 credential chain (환경변수 / ~/.aws/credentials / IAM role) 을 boto3 가 자동 인식.
        return S3StorageFactory(S3StorageInfoFactory()).create_storage()

    def _build_splitter(self) -> IPcapSplitter:
        return LocalPcapSplitter()
