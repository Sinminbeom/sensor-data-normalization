"""모듈 프로세스 종료 추적용 싱글톤.

원본 매핑 (swm → 신규):
- App/cPairQueueMultiProcessor.py 의 process status 통보 부분만 분리
    → ModuleStatusTracker (별도 객체. PairBuckets 와 분리: 단일 책임)
- swm의 eSubProcessStatus.END → ModuleStatusTracker.END_TOKEN
- 매니저(NormalizerManager) 가 expected_count 와 비교해 모든 모듈 종료 여부 판정.
"""

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
