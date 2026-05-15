"""RequestConsumerProcess — Redis Pub/Sub poll → RequestQueue push.

영구 daemon process. 매 사이클 main 이 RequestQueue.pop() 으로 한 건씩 받음.
"""

import logging
import time

from python_library.process.process import abProcessing

from common.event_bus.listener.normalization_request_listener import (
    NormalizationRequestListener,
)
from common.process_state.request_queue import RequestQueue
from config.project_config import ProjectConfig


class RequestConsumerProcess(abProcessing):
    def __init__(self, app_name: str, process_name: str):
        super().__init__(name=process_name)
        self._app_name = app_name
        self._process_name = process_name
        self._logger = logging.getLogger(
            f"{ProjectConfig.LOGGER_BASE_NAME}.{process_name}"
        )
        self._request_queue = RequestQueue.instance()
        self._consumer: NormalizationRequestListener | None = None
        self._initialized = False

    def on_init(self) -> None:
        # NormalizationRequestListener 가 redis.StrictRedis 연결 → fork 후 자식 process 안에서
        # 별도 연결 가져야 fork-safe.
        self._consumer = NormalizationRequestListener()
        self._initialized = True
        self._logger.info(f"consumer process started: {self._process_name}")

    def action(self) -> None:
        if not self._initialized:
            self.on_init()
        assert self._consumer is not None
        try:
            request = self._consumer.poll(timeout_sec=1.0)
            if request is not None:
                self._request_queue.push(request)
        except Exception as e:
            self._logger.exception(f"consumer poll failed: {e}")
            time.sleep(0.5)
