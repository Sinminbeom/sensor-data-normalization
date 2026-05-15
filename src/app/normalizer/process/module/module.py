"""NormalizerModule — PCAP 다운로드/분할/업로드 모듈 프로세스 (워커).

원본 매핑 (swm → 신규):
- pcapNormalization/storageHandler.py::storageHandler(cShardPairQueueProcess)
    → NormalizerModule(QueueProcessing)
- sensor-data-replayer 의 app/<service>/process/module/module.py 위치·역할에 정렬.
  매니저(NormalizerManager) 와 모듈(NormalizerModule) 두 단계 패턴.
- 메서드 매핑:
    Init                                       → on_init() (action 첫 진입에서 1회)
    Running(process) 본체 (while isRunning)    → action() (QueueProcessing 루프)
    _download                                  → _download
    _splitPcap                                 → _split_pcap
    _upload                                    → _upload_processed
    _pushUnProcessedPcapsInShardPairQueue      → _push_unprocessed_to_pair_buckets
    _mergePcapFiles                            → _merge_pair
    _getDownloadDstPath                        → _build_download_dst_path
    _getSplitOutFileTemplate                   → _build_split_out_template
    _makeUploadDstPath                         → _build_upload_dst_path
    _makePairKey                               → _build_pair_key
    _makeOutFilePath                           → _build_unpaired_out_path
    _getModuleType                             → _get_module_type
    postError                                  → _post_error
- 외부 의존 변경:
    cHadoopStorage                            → python_library.storage.IStorage (LocalStorage)
    cSplitsPcaps/cSplitedPcaps                → pcap.splitter.IPcapSplitter / SplitedPcap (추상)
    ConfigureManager                          → ProjectConfig
    Log.Log                                   → python logging
    cShardPairQueueProcess (자체 큐 관리)      → QueueProcessing (python_library, shared_job_queue 자동 결선)
    SharedQueues (자체 정의)                   → 라이브러리 shared_job_queue + PairBuckets (pair 검출만 남김)
- 종료 신호:
    swm의 eSubProcessStatus.END 통보
        → ModuleStatusTracker.mark_finished(name) + self.stop()
"""

import json
import logging
import os
import time

import requests
from python_library.process.queue_process import QueueProcessing
from python_library.storage.storage import IStorage, StorageFile

from app.normalizer.queue.module_status import ModuleStatusTracker
from app.normalizer.queue.pair_buckets import PairBuckets
from config.project_config import ProjectConfig
from pcap.packet_position import E_PACKET_POSITION
from pcap.splitter import IPcapSplitter, SplitedPcap
from pcap.unprocessed_pcap import UnprocessedPcap
from sensor_category.enum_sensor import E_SENSOR_TYPE
from sensor_category.sensor_registry import SensorRegistry
from storage.storage_object_property import StorageObjectProperty
from utils.pcap_filename_parser import PcapFilenameParser


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

        # TODO: 구체 PcapSplitter 구현체 결합. 후속 작업에서 LocalPcapSplitter 등 주입.
        # self._splitter = LocalPcapSplitter()

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
        storage_obj = StorageObjectProperty(
            file_obj.get_file_path(), file_obj.get_file_name()
        )
        vehicle_id = storage_obj.vehicle_id

        self._download(storage_obj)
        outcome = self._split_pcap(storage_obj)

        self._upload_processed(vehicle_id, outcome.processed)
        self._push_unprocessed_to_pair_buckets(vehicle_id, outcome.unprocessed)

        parts = PcapFilenameParser.parse(storage_obj.file_name)
        module_type = self._get_module_type(parts.module_name)
        if module_type in (E_SENSOR_TYPE.CAMERA, E_SENSOR_TYPE.GNSS):
            time.sleep(0.01)

    def _download(self, storage_obj: StorageObjectProperty) -> None:
        assert self._storage is not None
        download_dst_path = self._build_download_dst_path(
            storage_obj.vehicle_id, storage_obj.file_name
        )
        self._storage.download(storage_obj.download_src_path, download_dst_path)

    def _split_pcap(self, storage_obj: StorageObjectProperty):
        assert self._splitter is not None
        file_name = storage_obj.file_name
        vehicle_id = storage_obj.vehicle_id

        download_dst_path = self._build_download_dst_path(vehicle_id, file_name)
        split_src_file = f"{download_dst_path}/{file_name}"
        split_out_template = self._build_split_out_template(vehicle_id, file_name)

        outcome = self._splitter.split_once(split_src_file, split_out_template, None)

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
        pcap_files = [item.src_path for item in paired_list]
        out_file_path = paired_list[0].out_file_path
        prefix_path = paired_list[0].prefix_path

        IPcapSplitter.merge_pcap_files(pcap_files, out_file_path)  # type: ignore[abstract]
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
        args = SensorRegistry.instance().get_sensor_args(module_name.upper())
        return args.sensor_type

    def _build_storage(self) -> IStorage:
        # NOTE: 후속 Task에서 LocalStorageFactory 결선.
        raise NotImplementedError(
            "LocalStorage 결선은 후속 Task. 본 Task는 IStorage 결합만 정렬."
        )

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
