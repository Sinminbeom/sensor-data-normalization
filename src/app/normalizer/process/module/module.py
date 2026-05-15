"""NormalizerModule — PCAP 다운로드/분할/업로드 모듈 프로세스 (워커)."""

import json
import logging
import os
import time

import requests
from python_library.process.queue_process import QueueProcessing
from python_library.storage.s3.s3_storage_factory import S3StorageFactory
from python_library.storage.s3.s3_storage_info_factory import S3StorageInfoFactory
from python_library.storage.storage import IStorage, StorageFile

from common.process_state.module_status import ModuleStatusTracker
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
        self._status_tracker = ModuleStatusTracker.instance()
        self._storage: IStorage | None = None
        self._splitter: IPcapSplitter | None = None
        self._initialized = False

    # ---------- lifecycle ----------

    def on_init(self) -> None:
        self._status_tracker.register(self._process_name)
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
        try:
            file_obj = self.pop_shared_job_queue()
            if file_obj is None:
                if self.size_shared_job_queue() == 0:
                    self._logger.info(f"pid={os.getpid()} || {self._process_name} exit")
                    self._status_tracker.mark_finished(self._process_name)
                    self._storage.disconnect()
                    self.stop()
                    return
                time.sleep(0.02)
                return

            self._process_file(file_obj)
            time.sleep(0.02)
        except Exception as e:
            self._logger.error(f"pid={os.getpid()} || errMsg={e}")
            try:
                self._storage.disconnect()
            finally:
                self._status_tracker.mark_finished(self._process_name)
                self._post_error(e)
                self.stop()

    # ---------- job (jobQueue → download → split → upload) ----------

    def _process_file(self, file_obj: StorageFile) -> None:
        file_path = file_obj.get_file_path()
        file_name = file_obj.get_file_name()
        # path 의 마지막 segment 가 vehicle_id 라는 도메인 컨벤션
        # (`{cache_root}/{date_folder}/{vehicle_id}/{file_name}`).
        vehicle_id = file_path.split("/")[-1]

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
        self._storage.download(f"{file_path}/{file_name}", download_dst_path)

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
        parts = PcapFilenameParser.parse(file_name)
        module_type = self._get_module_type(parts.module_name).lower()
        base = self._config.get_storage_full_path()
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

    def _post_error(self, err: Exception) -> None:
        url = (
            f"{self._config.rest_base_url}/error/{self._config.project_name}"
            f"/{self._process_name}"
        )
        try:
            requests.post(
                url,
                data=json.dumps({"message": str(err)}),
                headers={"Content-Type": "application/json; charset=utf-8"},
                timeout=5,
            )
        except Exception:
            self._logger.exception("error report failed")
