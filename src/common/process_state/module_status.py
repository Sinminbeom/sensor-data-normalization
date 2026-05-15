"""모듈 프로세스 종료 추적용 싱글톤."""

from multiprocessing import Manager
from typing import Any, ClassVar

from python_library.singleton.singleton import Singleton


class ModuleStatusTracker(Singleton):
    END_TOKEN: ClassVar[str] = "END"

    def __init__(self) -> None:
        super().__init__()
        manager = Manager()
        # multiprocessing.Manager proxy 는 generic 타입 명시 불가 → Any.
        self._status: Any = manager.dict()

    def register(self, module_name: str) -> None:
        self._status.setdefault(module_name, "")

    def mark_finished(self, module_name: str) -> None:
        self._status[module_name] = ModuleStatusTracker.END_TOKEN

    def all_finished(self, expected_count: int) -> bool:
        statuses = list(self._status.values())
        if len(statuses) < expected_count:
            return False
        return all(s == ModuleStatusTracker.END_TOKEN for s in statuses)
