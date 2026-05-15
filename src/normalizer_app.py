"""sensor-data-normalization 진입점.

sensor-data-replayer 의 streamer_app.py / downloader_app.py 와 동일 구조.

"""

import argparse
import logging.config
import time

from app.app_object import MultiProcessManagerAppFromCate
from app.normalizer.process.manager.manager import NormalizerManager
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
    parser = argparse.ArgumentParser(description="sensor-data-normalization")
    parser.add_argument("--build-num", required=True)
    parser.add_argument("--date", required=True, help="처리 대상 날짜 폴더 (YYYYMMDD)")
    parser.add_argument("--vehicle-id", default="", help="VEHICLE-NNN. 비우면 전체.")
    parser.add_argument(
        "--process-size",
        type=int,
        default=0,
        help="모듈 수. 0이면 conf [NORMALIZER].WORKER_COUNT 사용.",
    )
    args = parser.parse_args()

    ProjectConfig.set_config(ProjectConfig.DEFAULT_CONFIG_PATH)
    logging.config.fileConfig(
        ProjectConfig.DEFAULT_LOGGING_CONFIG_PATH, disable_existing_loggers=False
    )

    config = ProjectConfig.instance()
    worker_count = args.process_size if args.process_size > 0 else config.worker_count

    NormalizerManager.configure(
        build_num=args.build_num,
        date_folder=args.date,
        vehicle_id=args.vehicle_id,
    )

    ProcessCategory.instance().set_worker_count(worker_count)
    ProcessCategory.instance().register_category()

    app = Normalizer(E_CATE.NORMALIZER)
    app.init()
    app.run()


if __name__ == "__main__":
    main()
