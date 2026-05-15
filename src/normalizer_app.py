"""sensor-data-normalization 진입점.

흐름:
1. Communication app (RequestConsumerProcess + NotifierProcess) 영구 fork
2. main loop: RequestQueue.pop() 으로 Redis 메시지 1건 받음
3. request_id 발급 → NormalizerManager.configure
4. Normalizer app (manager + module N) 사이클별 fork → 자식 join 까지 wait
5. 완료/실패 → NotificationQueue.push → NotifierProcess 가 Slack 발송
6. 다음 요청 대기 (SIGTERM/SIGINT 시 graceful shutdown)
"""

import logging
import logging.config
import signal
import time
from types import FrameType

from app.app_object import MultiProcessManagerAppFromCate
from app.normalizer.process.manager.manager import NormalizerManager
from common.process_state.notification_queue import (
    NotificationEnvelope,
    NotificationQueue,
)
from common.process_state.request_queue import RequestQueue
from common.protocol.request_id import RequestIdGenerator
from config.project_config import ProjectConfig
from process_category.enum_category import E_CATE
from process_category.process_category import ProcessCategory


class Communication(MultiProcessManagerAppFromCate):
    def __init__(self, *_cate):
        super().__init__(E_CATE.COMMUNICATION, *_cate)

    def init(self) -> None:
        self.get_multi_process_manager().start()

    def on_run(self) -> None:
        time.sleep(0.005)


class Normalizer(MultiProcessManagerAppFromCate):
    def __init__(self, *_cate):
        super().__init__(E_CATE.NORMALIZER, *_cate)

    def init(self) -> None:
        self.get_multi_process_manager().start()

    def run(self) -> None:
        # 한 사이클 = 자식들이 jobQueue 소진 후 stop. MultiProcessManager join 까지 wait.
        mpm = self.get_multi_process_manager()
        while mpm.is_running():
            time.sleep(0.5)

    def on_run(self) -> None:
        pass


def main() -> None:
    ProjectConfig.set_config(ProjectConfig.DEFAULT_CONFIG_PATH)
    logging.config.fileConfig(
        ProjectConfig.DEFAULT_LOGGING_CONFIG_PATH, disable_existing_loggers=False
    )
    logger = logging.getLogger(ProjectConfig.LOGGER_BASE_NAME)
    config = ProjectConfig.instance()

    # Queue singleton 을 부모 프로세스에서 먼저 instance() → fork 시 자식이 inherit.
    request_queue = RequestQueue.instance()
    notification_queue = NotificationQueue.instance()

    ProcessCategory.instance().register_category()

    communication = Communication(E_CATE.COMMUNICATION)
    communication.init()
    logger.info("communication processes started (consumer + notifier)")

    stopping = False

    def _shutdown(_signum: int, _frame: FrameType | None) -> None:
        nonlocal stopping
        logger.info("stop signal received, finishing current cycle then exit")
        stopping = True

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    logger.info("daemon started")
    while not stopping:
        request = request_queue.pop(timeout_sec=1.0)
        if request is None:
            continue

        request_id = RequestIdGenerator.next()
        summary = (
            f"date={request.date} vehicle_id={request.vehicle_id or 'ALL'} "
            f"selected_device={request.selected_device or '(conf)'}"
        )
        logger.info(f"[{request_id}] start | {summary}")

        try:
            NormalizerManager.configure(
                request_id=request_id,
                date_folder=request.date,
                vehicle_id=request.vehicle_id,
                selected_device=request.selected_device or config.selected_device,
            )
            ProcessCategory.instance().set_worker_count(config.worker_count)
            ProcessCategory.instance().register_normalizer()

            app = Normalizer(E_CATE.NORMALIZER)
            app.init()
            app.run()

            notification_queue.push(
                NotificationEnvelope(
                    request_id=request_id, summary=summary, success=True
                )
            )
            logger.info(f"[{request_id}] done")
        except Exception as e:
            logger.exception(f"[{request_id}] pipeline failed")
            notification_queue.push(
                NotificationEnvelope(
                    request_id=request_id,
                    summary=summary,
                    success=False,
                    error=repr(e),
                )
            )

    logger.info("daemon stopped")


if __name__ == "__main__":
    main()
