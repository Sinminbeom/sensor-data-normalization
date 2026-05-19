"""HEAD/TAIL 쌍 누적 버킷 (pair_key → 조각 리스트).

설계 (#27):
- manager 프로세스 단일 owner. worker 는 IPC queue 메시지로 PairPutMessage 송신,
  manager 가 자기 cycle 루프에서 drain 하여 본 객체 업데이트.
- 단일 thread (manager main loop) 만 호출하므로 lock 불필요.
"""

from pcap.unprocessed_pcap import UnprocessedPcap


class PairBuckets:
    def __init__(self) -> None:
        self._buckets: dict[str, list[UnprocessedPcap]] = {}

    def put(self, pair_key: str, item: UnprocessedPcap) -> list[UnprocessedPcap] | None:
        bucket = self._buckets.get(pair_key, [])
        bucket.append(item)
        if len(bucket) >= 2:
            del self._buckets[pair_key]
            return list(bucket)
        self._buckets[pair_key] = bucket
        return None

    def pop_all_remaining(self) -> list[list[UnprocessedPcap]]:
        remaining = [list(v) for v in self._buckets.values()]
        self._buckets.clear()
        return remaining
