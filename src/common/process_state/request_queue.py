"""RequestQueue — RequestConsumerProcess(Redis poll) → main 으로 request 전달."""

from multiprocessing import Manager
from typing import Any

from python_library.singleton.singleton import Singleton

from common.protocol.normalization_request import NormalizationRequest


class RequestQueue(Singleton):
    def __init__(self) -> None:
        super().__init__()
        manager = Manager()
        self._queue: Any = manager.Queue()

    def push(self, request: NormalizationRequest) -> None:
        # pydantic 모델은 pickle 가능. 단순 push.
        self._queue.put(request)

    def pop(self, timeout_sec: float = 1.0) -> NormalizationRequest | None:
        try:
            return self._queue.get(timeout=timeout_sec)
        except Exception:
            return None
