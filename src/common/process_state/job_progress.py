"""사이클 완료 감지 + 성공/실패 카운터 싱글톤.

Manager 가 cycle 시작 시 `begin_cycle(total)` 로 잔여/성공/실패 리셋, Module 이 매 job
처리 후 `mark_one_done(success=)` 호출. Manager 는 `is_done()` 폴링 후 `success_count`
/ `failure_count` 로 cycle 결과 분기.
"""

from multiprocessing import Manager
from typing import Any

from python_library.singleton.singleton import Singleton


class JobProgressTracker(Singleton):
    _REMAINING = "remaining"
    _SUCCESS = "success"
    _FAILURE = "failure"

    def __init__(self) -> None:
        super().__init__()
        manager = Manager()
        # multiprocessing.Manager 의 proxy 객체는 정확한 generic 타입 명시 불가 → Any.
        self._state: Any = manager.dict()
        self._lock: Any = manager.Lock()
        self._state[JobProgressTracker._REMAINING] = 0
        self._state[JobProgressTracker._SUCCESS] = 0
        self._state[JobProgressTracker._FAILURE] = 0

    def begin_cycle(self, total: int) -> None:
        with self._lock:
            self._state[JobProgressTracker._REMAINING] = total
            self._state[JobProgressTracker._SUCCESS] = 0
            self._state[JobProgressTracker._FAILURE] = 0

    def mark_one_done(self, success: bool) -> None:
        with self._lock:
            self._state[JobProgressTracker._REMAINING] = (
                self._state[JobProgressTracker._REMAINING] - 1
            )
            if success:
                self._state[JobProgressTracker._SUCCESS] = (
                    self._state[JobProgressTracker._SUCCESS] + 1
                )
            else:
                self._state[JobProgressTracker._FAILURE] = (
                    self._state[JobProgressTracker._FAILURE] + 1
                )

    def is_done(self) -> bool:
        return self._state[JobProgressTracker._REMAINING] <= 0

    def success_count(self) -> int:
        return self._state[JobProgressTracker._SUCCESS]

    def failure_count(self) -> int:
        return self._state[JobProgressTracker._FAILURE]
