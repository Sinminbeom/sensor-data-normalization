"""NormalizerModule — PCAP 다운로드/분할/업로드 워커 프로세스.

daemon 시작 시 한 번 fork → 영구 실행. shared_job_queue 에서 StorageFile 을 pop,
다운로드 → 1초 split → MID 업로드 → HEAD/TAIL 은 PairBuckets 누적. cycle 컨텍스트는
파일 경로에서 derive (vehicle_id 등) — cycle 별 상태 없음 (stateless worker).
"""

import logging
import os
import time

from python_library.process.queue_process import QueueProcessing
from python_library.storage.s3.s3_storage_factory import S3StorageFactory
from python_library.storage.s3.s3_storage_info_factory import S3StorageInfoFactory
from python_library.storage.storage import IStorage, StorageFile

from common.process_state.job_progress import JobProgressTracker
from common.process_state.pair_buckets import PairBuckets
from config.project_config import ProjectConfig
from pcap.local_pcap_splitter import LocalPcapSplitter
from pcap.packet_position import E_PACKET_POSITION
from pcap.pcap_filename_parser import PcapFilenameParser
from pcap.splitter import IPcapSplitter, SplitedPcap, SplitOutcome
from pcap.unprocessed_pcap import UnprocessedPcap
from sensor_category.enum_sensor import E_SENSOR_TYPE
from sensor_category.sensor_registry import SensorRegistry


class NormalizerModule(QueueProcessing):
    def __init__(self, app_name: str, process_name: str):
        super().__init__(name=process_name)
        self._app_name = app_name
        self._process_name = process_name
        self._logger = logging.getLogger(
            f"{ProjectConfig.LOGGER_BASE_NAME}.{process_name}"
        )
        # 싱글톤은 부모 프로세스에서 즉시 instance() 호출 → 자식이 inherit.
        self._config = ProjectConfig.instance()
        self._pair_buckets = PairBuckets.instance()
        self._progress = JobProgressTracker.instance()
        self._storage: IStorage | None = None
        self._splitter: IPcapSplitter | None = None
        self._initialized = False

    # ---------- lifecycle ----------

    def on_init(self) -> None:
        SensorRegistry.instance().register()

        self._storage = self._build_storage()
        self._storage.connect()

        self._splitter = self._build_splitter()

        self._initialized = True
        self._logger.info(f"pid={os.getpid()} || {self._process_name} init")

    def action(self) -> None:
        if not self._initialized:
            self.on_init()

        assert self._storage is not None
        file_obj = self.pop_shared_job_queue()
        if file_obj is None:
            time.sleep(0.02)
            return

        success = True
        try:
            self._process_file(file_obj)
        except Exception as e:
            success = False
            self._logger.error(
                f"pid={os.getpid()} || file={file_obj.get_file_name()} errMsg={e}"
            )
        finally:
            self._progress.mark_one_done(success=success)

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
        self._push_unprocessed_to_pair_buckets(vehicle_id, outcome.unprocessed)

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
            dst_path = self._build_upload_dst_path(vehicle_id, piece)
            self._storage.upload(src_path, dst_path)

            if os.path.isfile(src_path):
                os.remove(src_path)

    # ---------- pair bucket (HEAD/TAIL pair → merge → upload) ----------

    def _push_unprocessed_to_pair_buckets(
        self, vehicle_id: str, unprocessed: list[SplitedPcap]
    ) -> None:
        for piece in unprocessed:
            if piece.position == E_PACKET_POSITION.MID:
                continue

            pair_key = self._build_pair_key(vehicle_id, piece)
            out_file_path = self._build_unpaired_out_path(vehicle_id, piece)
            prefix_path = self._build_upload_dst_path(vehicle_id, piece)

            unprocessed_pcap = UnprocessedPcap(
                src_path=piece.save_path,
                out_file_path=out_file_path,
                prefix_path=prefix_path,
            )

            paired = self._pair_buckets.put(pair_key, unprocessed_pcap)
            if paired is not None:
                self._merge_pair(paired)

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

    # ---------- path builders ----------

    def _build_download_dst_path(self, vehicle_id: str, file_name: str) -> str:
        parts = PcapFilenameParser.parse(file_name)
        module_type = self._get_module_type(parts.module_name).lower()
        base = self._config.get_cache_storage_full_path()
        path = (
            f"{base}/{vehicle_id}/{module_type}/{parts.module_name}/"
            f"{parts.date}/{parts.hours}/{parts.minutes}"
        )
        path = os.path.abspath(path)
        os.makedirs(path, exist_ok=True)
        return path

    def _build_split_out_template(self, vehicle_id: str, file_name: str) -> str:
        # splitter 는 로컬 파일을 출력 (LocalPcapSplitter). base 는 cache (로컬). upload 시
        # 이 로컬 결과를 _build_upload_dst_path (S3) 로 올린다.
        parts = PcapFilenameParser.parse(file_name)
        module_type = self._get_module_type(parts.module_name).lower()
        base = self._config.get_cache_storage_full_path()
        return (
            f"{base}/{vehicle_id}/{module_type}/{parts.module_name}/"
            f"{parts.date}/{parts.hours}/{parts.minutes}/{parts.module_name}_{{}}.pcap"
        )

    def _build_upload_dst_path(self, vehicle_id: str, piece: SplitedPcap) -> str:
        module_type = self._get_module_type(piece.module_name).lower()
        base = self._config.get_storage_full_path()
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
        base = self._config.get_unpaired_merge_full_path()
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
