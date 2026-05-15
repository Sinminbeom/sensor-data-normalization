"""ProjectConfig — application.conf 값 접근."""

from python_library.configure.app_config import AppConfig
from python_library.define.enum import IENUM


class ProjectConfig(AppConfig):
    DEFAULT_CONFIG_PATH = "./conf/application.conf"
    DEFAULT_LOGGING_CONFIG_PATH = "./conf/logging.conf"
    LOGGER_BASE_NAME = "sensor-data-normalization"

    class E_CATE_TYPE(IENUM):
        COMMON = "COMMON"
        STORAGE = "STORAGE"
        STORAGE_CACHE = "STORAGE_CACHE"
        STORAGE_UNPAIRED_MERGE = "STORAGE_UNPAIRED_MERGE"
        NORMALIZER = "NORMALIZER"
        REST = "REST"
        SELECTED_DEVICE = "SELECTED_DEVICE"

    class E_CATE_ELE_COMMON(IENUM):
        PROJECT_NAME = "PROJECT_NAME"
        CHANNEL_NAME = "CHANNEL_NAME"

    class E_CATE_ELE_STORAGE(IENUM):
        ROOT = "ROOT"
        PREFIX = "PREFIX"

    class E_CATE_ELE_NORMALIZER(IENUM):
        WORKER_COUNT = "WORKER_COUNT"

    class E_CATE_ELE_REST(IENUM):
        BASE_URL = "BASE_URL"

    class E_CATE_ELE_SELECTED_DEVICE(IENUM):
        SELECTED = "SELECTED"

    def __init__(self) -> None:
        super().__init__()

        self.project_name = self.get_config(
            ProjectConfig.E_CATE_TYPE.COMMON,
            ProjectConfig.E_CATE_ELE_COMMON.PROJECT_NAME,
        )
        self.channel_name = self.get_config(
            ProjectConfig.E_CATE_TYPE.COMMON,
            ProjectConfig.E_CATE_ELE_COMMON.CHANNEL_NAME,
        )

        self.storage_root = self.get_config(
            ProjectConfig.E_CATE_TYPE.STORAGE, ProjectConfig.E_CATE_ELE_STORAGE.ROOT
        )
        self.storage_prefix = self.get_config(
            ProjectConfig.E_CATE_TYPE.STORAGE, ProjectConfig.E_CATE_ELE_STORAGE.PREFIX
        )
        self.cache_storage_root = self.get_config(
            ProjectConfig.E_CATE_TYPE.STORAGE_CACHE,
            ProjectConfig.E_CATE_ELE_STORAGE.ROOT,
        )
        self.cache_storage_prefix = self.get_config(
            ProjectConfig.E_CATE_TYPE.STORAGE_CACHE,
            ProjectConfig.E_CATE_ELE_STORAGE.PREFIX,
        )
        self.unpaired_merge_root = self.get_config(
            ProjectConfig.E_CATE_TYPE.STORAGE_UNPAIRED_MERGE,
            ProjectConfig.E_CATE_ELE_STORAGE.ROOT,
        )
        self.unpaired_merge_prefix = self.get_config(
            ProjectConfig.E_CATE_TYPE.STORAGE_UNPAIRED_MERGE,
            ProjectConfig.E_CATE_ELE_STORAGE.PREFIX,
        )

        self.worker_count = int(
            self.get_config(
                ProjectConfig.E_CATE_TYPE.NORMALIZER,
                ProjectConfig.E_CATE_ELE_NORMALIZER.WORKER_COUNT,
            )
        )

        self.rest_base_url = self.get_config(
            ProjectConfig.E_CATE_TYPE.REST, ProjectConfig.E_CATE_ELE_REST.BASE_URL
        )

        self.selected_device = self.get_config(
            ProjectConfig.E_CATE_TYPE.SELECTED_DEVICE,
            ProjectConfig.E_CATE_ELE_SELECTED_DEVICE.SELECTED,
        )

    def get_storage_full_path(self) -> str:
        return f"{self.storage_root}/{self.storage_prefix}"

    def get_cache_storage_full_path(self) -> str:
        return f"{self.cache_storage_root}/{self.cache_storage_prefix}"

    def get_unpaired_merge_full_path(self) -> str:
        return f"{self.unpaired_merge_root}/{self.unpaired_merge_prefix}"
