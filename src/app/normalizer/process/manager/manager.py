"""NormalizerManager — 정규화 파이프라인 오케스트레이터 프로세스.

책임:
1. 입력 캐시 스토리지에서 파일 목록 수집 → push_shared_job_queue 로 jobQueue 적재
2. ModuleStatusTracker 로 모든 모듈 종료 감지 → 잔여 미페어 sweep + 업로드
3. 런타임 컨텍스트(request_id/date_folder/vehicle_id/selected_device) 는 ClassVar로
   보유 (daemon main 에서 configure 호출, fork 시 자식 프로세스가 inherit)
"""

import logging
import os
import time
from typing import ClassVar

from python_library.process.queue_process import QueueProcessing
from python_library.storage.s3.s3_storage_factory import S3StorageFactory
from python_library.storage.s3.s3_storage_info_factory import S3StorageInfoFactory
from python_library.storage.storage import IStorage
from python_library.storage.storage_file import StorageFile

from common.process_state.module_status import ModuleStatusTracker
from common.process_state.pair_buckets import PairBuckets
from config.project_config import ProjectConfig
from pcap.pcap_filename_parser import PcapFilenameParser
from pcap.unprocessed_pcap import UnprocessedPcap
from sensor_category.enum_sensor import E_SENSOR_TYPE
from sensor_category.sensor_registry import SensorRegistry


class NormalizerManager(QueueProcessing):
    _REQUEST_ID: ClassVar[str] = ""
    _DATE_FOLDER: ClassVar[str] = ""
    _VEHICLE_ID: ClassVar[str] = ""
    _SELECTED_DEVICE: ClassVar[str] = ""

    def __init__(self, app_name: str, process_name: str):
        super().__init__(name=process_name)
        self._app_name = app_name
        self._process_name = process_name
        self._logger = logging.getLogger(
            f"{ProjectConfig.LOGGER_BASE_NAME}.{process_name}"
        )
        # 싱글톤은 fork 전 부모 프로세스에서 즉시 instance() 호출 →
        # 자식이 inherit (Manager() proxy 포함).
        self._config = ProjectConfig.instance()
        self._pair_buckets = PairBuckets.instance()
        self._status_tracker = ModuleStatusTracker.instance()
        self._storage: IStorage | None = None
        self._expected_modules = 0
        self._initialized = False

    @classmethod
    def configure(
        cls,
        request_id: str,
        date_folder: str,
        vehicle_id: str,
        selected_device: str,
    ) -> None:
        """daemon main()에서 호출. fork된 자식 프로세스가 ClassVar로 inherit."""
        cls._REQUEST_ID = request_id
        cls._DATE_FOLDER = date_folder
        cls._VEHICLE_ID = vehicle_id
        cls._SELECTED_DEVICE = selected_device

    # ---------- lifecycle ----------

    def on_init(self) -> None:
        self._expected_modules = self._config.worker_count

        SensorRegistry.instance().register()

        self._storage = self._build_storage()
        self._storage.connect()

        file_list = self._collect_file_list()
        self._enqueue_jobs_by_device_filter(
            file_list, NormalizerManager._SELECTED_DEVICE
        )

        self._initialized = True
        self._logger.info(
            f"pid={os.getpid()} || manager init (request_id={NormalizerManager._REQUEST_ID})"
        )

    def action(self) -> None:
        if not self._initialized:
            self.on_init()

        assert self._storage is not None
        try:
            self._logger.info(
                f"pid={os.getpid()} || size_shared_job_queue={self.size_shared_job_queue()}"
            )

            if self._status_tracker.all_finished(self._expected_modules):
                self._logger.info(f"pid={os.getpid()} || all modules finished")
                self._upload_unpaired(self._pair_buckets.pop_all_remaining())
                self._storage.disconnect()
                self.stop()
                return

            time.sleep(0.1)
        except Exception as e:
            self._logger.exception(f"pid={os.getpid()} || manager errMsg={e}")
            try:
                self._storage.disconnect()
            finally:
                self.stop()

    # ---------- file collection ----------

    def _collect_file_list(self) -> list[StorageFile]:
        assert self._storage is not None
        cache_root = self._config.get_cache_storage_full_path()
        process_folder = f"{cache_root}/{NormalizerManager._DATE_FOLDER}"

        if not self._storage.is_exists(process_folder):
            self._logger.error(f"path not exists: {process_folder}")
            self._storage.disconnect()
            self.stop()
            return []

        all_files = [
            f for f in self._storage.get_file_list(process_folder) if not f.is_dir()
        ]
        if NormalizerManager._VEHICLE_ID:
            return [
                f
                for f in all_files
                if NormalizerManager._VEHICLE_ID in f.get_file_path()
            ]
        return all_files

    def _enqueue_jobs_by_device_filter(
        self, file_list: list[StorageFile], selected_device: str
    ) -> None:
        for file_obj in file_list:
            file_name = file_obj.get_file_name()
            if "temp" in file_name:
                continue

            if selected_device == E_SENSOR_TYPE.ALL:
                self.push_shared_job_queue(file_obj)
                continue

            parts = PcapFilenameParser.parse(file_name)
            sensor_type = SensorRegistry.instance().get_sensor_type(
                parts.module_name.upper()
            )

            if selected_device.upper() == sensor_type:
                self.push_shared_job_queue(file_obj)
                continue

            if selected_device.lower() in file_name:
                self.push_shared_job_queue(file_obj)

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
