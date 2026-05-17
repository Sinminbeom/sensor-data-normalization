"""sensor-data-normalization 진입점."""

import logging.config
import multiprocessing
import time

from app.app_object import MultiProcessManagerAppFromCate
from common.process_state.job_progress import JobProgressTracker
from common.process_state.pair_buckets import PairBuckets
from config.project_config import ProjectConfig
from process_category.enum_category import E_CATE
from process_category.process_category import ProcessCategory


class Normalizer(MultiProcessManagerAppFromCate):
    def __init__(self, *_cate):
        super().__init__(E_CATE.NORMALIZER, *_cate)

    def init(self) -> None:
        self.get_multi_process_manager().start()

    def on_run(self) -> None:
        time.sleep(0.005)


def main() -> None:
    # Python 3.14 부터 multiprocessing 기본 start_method 가 'spawn'. 본 프로젝트는
    # 부모에서 instance() 호출 후 자식이 fork 로 class-level state 를 inherit 하는
    # 패턴 (PairBuckets / JobProgressTracker / ProjectConfig / SensorRegistry) 에
    # 의존하므로 fork 로 명시 (Linux 서버 환경 가정).
    multiprocessing.set_start_method("fork", force=True)

    ProjectConfig.set_config(ProjectConfig.DEFAULT_CONFIG_PATH)
    logging.config.fileConfig(
        ProjectConfig.DEFAULT_LOGGING_CONFIG_PATH, disable_existing_loggers=False
    )

    # cross-process singleton 은 부모에서 먼저 instance() → fork 시 자식이 inherit.
    PairBuckets.instance()
    JobProgressTracker.instance()

    config = ProjectConfig.instance()
    ProcessCategory.instance().set_worker_count(config.worker_count)
    ProcessCategory.instance().register_normalizer()

    app = Normalizer(E_CATE.NORMALIZER)
    app.init()
    app.run()


if __name__ == "__main__":
    main()
