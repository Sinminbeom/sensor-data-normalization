"""사이클 완료 감지 + 성공/실패 카운터.

설계 (#27):
- manager 프로세스 단일 owner. worker 는 IPC queue 메시지로 JobDoneMessage 송신,
  manager 가 자기 cycle 루프에서 drain 하여 본 객체 업데이트.
- 단일 thread (manager main loop) 만 호출하므로 lock 불필요.
"""


class JobProgressTracker:
    def __init__(self) -> None:
        self._remaining: int = 0
        self._success: int = 0
        self._failure: int = 0

    def begin_cycle(self, total: int) -> None:
        self._remaining = total
        self._success = 0
        self._failure = 0

    def mark_one_done(self, success: bool) -> None:
        self._remaining -= 1
        if success:
            self._success += 1
        else:
            self._failure += 1

    def is_done(self) -> bool:
        return self._remaining <= 0

    def success_count(self) -> int:
        return self._success

    def failure_count(self) -> int:
        return self._failure
