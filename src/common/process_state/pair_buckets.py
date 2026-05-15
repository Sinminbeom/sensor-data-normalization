"""HEAD/TAIL 쌍 누적 버킷 (pair_key → 조각 리스트).

설계:
- multiprocessing.Manager().dict() + Lock 으로 워커 프로세스 간 공유.
- put(pair_key, item) 호출 후 같은 key의 누적이 2개 도달하면 그 리스트를 반환
  (워커가 즉시 merge 가능). 끝까지 짝 못 맞춘 잔여는 pop_all_remaining 으로 sweep.
"""

from multiprocessing import Manager
from typing import Any

from python_library.singleton.singleton import Singleton


class PairBuckets(Singleton):
    def __init__(self) -> None:
        super().__init__()
        manager = Manager()
        # multiprocessing.Manager 의 proxy 객체는 정확한 generic 타입을 명시할 수 없어 Any 사용.
        self._buckets: Any = manager.dict()
        self._lock: Any = manager.Lock()

    def put(self, pair_key: str, item: Any) -> list[Any] | None:
        with self._lock:
            bucket = self._buckets.get(pair_key, [])
            bucket.append(item)
            if len(bucket) >= 2:
                del self._buckets[pair_key]
                return list(bucket)
            self._buckets[pair_key] = bucket
            return None

    def pop_all_remaining(self) -> list[list[Any]]:
        with self._lock:
            remaining = [list(v) for v in self._buckets.values()]
            self._buckets.clear()
            return remaining
