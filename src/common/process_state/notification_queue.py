"""NotificationQueue — main 사이클 완료 후 NotifierProcess 로 Slack 메시지 전달."""

from dataclasses import dataclass
from multiprocessing import Manager
from typing import Any

from python_library.singleton.singleton import Singleton


@dataclass(frozen=True)
class NotificationEnvelope:
    request_id: str
    summary: str
    success: bool
    error: str = ""


class NotificationQueue(Singleton):
    def __init__(self) -> None:
        super().__init__()
        manager = Manager()
        self._queue: Any = manager.Queue()

    def push(self, envelope: NotificationEnvelope) -> None:
        self._queue.put(envelope)

    def pop(self, timeout_sec: float = 1.0) -> NotificationEnvelope | None:
        try:
            return self._queue.get(timeout=timeout_sec)
        except Exception:
            return None
