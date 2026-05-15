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
        REDIS = "REDIS"
        NOTIFICATION = "NOTIFICATION"
        SELECTED_DEVICE = "SELECTED_DEVICE"

    class E_CATE_ELE_COMMON(IENUM):
        PROJECT_NAME = "PROJECT_NAME"
        CHANNEL_NAME = "CHANNEL_NAME"

    class E_CATE_ELE_STORAGE(IENUM):
        ROOT = "ROOT"
        PREFIX = "PREFIX"

    class E_CATE_ELE_NORMALIZER(IENUM):
        WORKER_COUNT = "WORKER_COUNT"

    class E_CATE_ELE_REDIS(IENUM):
        HOST = "HOST"
        PORT = "PORT"
        CHANNEL_NAME = "CHANNEL_NAME"
        RECEIVER = "RECEIVER"

    class E_CATE_ELE_NOTIFICATION(IENUM):
        WEBHOOK_URL = "WEBHOOK_URL"
        DEFAULT_CHANNEL = "DEFAULT_CHANNEL"

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

        self.redis_host = self.get_config(
            ProjectConfig.E_CATE_TYPE.REDIS, ProjectConfig.E_CATE_ELE_REDIS.HOST
        )
        self.redis_port = int(
            self.get_config(
                ProjectConfig.E_CATE_TYPE.REDIS, ProjectConfig.E_CATE_ELE_REDIS.PORT
            )
        )
        self.redis_channel_name = self.get_config(
            ProjectConfig.E_CATE_TYPE.REDIS,
            ProjectConfig.E_CATE_ELE_REDIS.CHANNEL_NAME,
        )
        self.redis_receiver = self.get_config(
            ProjectConfig.E_CATE_TYPE.REDIS,
            ProjectConfig.E_CATE_ELE_REDIS.RECEIVER,
        )

        self.notification_webhook_url = self.get_config(
            ProjectConfig.E_CATE_TYPE.NOTIFICATION,
            ProjectConfig.E_CATE_ELE_NOTIFICATION.WEBHOOK_URL,
        )
        self.notification_default_channel = self.get_config(
            ProjectConfig.E_CATE_TYPE.NOTIFICATION,
            ProjectConfig.E_CATE_ELE_NOTIFICATION.DEFAULT_CHANNEL,
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
