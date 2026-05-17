"""사이클 완료 감지용 카운터 싱글톤.

Manager 가 cycle 시작 시 `begin_cycle(total)` 로 잔여 job 수 세팅, Module 이 매 job
처리 후 `mark_one_done()` 호출. Manager 는 `is_done()` 폴링으로 cycle 종료 판단.
"""

from multiprocessing import Manager
from typing import Any

from python_library.singleton.singleton import Singleton


class JobProgressTracker(Singleton):
    _REMAINING_KEY = "remaining"

    def __init__(self) -> None:
        super().__init__()
        manager = Manager()
        # multiprocessing.Manager 의 proxy 객체는 정확한 generic 타입 명시 불가 → Any.
        self._state: Any = manager.dict()
        self._lock: Any = manager.Lock()
        self._state[JobProgressTracker._REMAINING_KEY] = 0

    def begin_cycle(self, total: int) -> None:
        with self._lock:
            self._state[JobProgressTracker._REMAINING_KEY] = total

    def mark_one_done(self) -> None:
        with self._lock:
            self._state[JobProgressTracker._REMAINING_KEY] = (
                self._state[JobProgressTracker._REMAINING_KEY] - 1
            )

    def is_done(self) -> bool:
        return self._state[JobProgressTracker._REMAINING_KEY] <= 0
