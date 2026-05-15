from __future__ import annotations

import threading
from collections import deque

from pcap.packet import PcapPacket


class PcapPool:
    """PcapPacket producer-consumer buffer.

    Reader thread가 append, Sender thread가 pop_front — deque 기반.
    max_size 설정 시 가득 차면 append=False 반환 (호출자가 wait 결정).
    """

    def __init__(self, max_size: int | None = None) -> None:
        self._packets: deque[PcapPacket] = deque()
        self._max_size: int | None = max_size
        self._lock = threading.Lock()

    def append(self, packet: PcapPacket) -> bool:
        """가득 차면 False — 호출자가 sleep+retry. 성공 시 True."""
        with self._lock:
            if self._max_size is not None and len(self._packets) >= self._max_size:
                return False
            self._packets.append(packet)
            return True

    def pop_front(self) -> PcapPacket | None:
        """비어있으면 None — 호출자가 sleep+retry."""
        with self._lock:
            if not self._packets:
                return None
            return self._packets.popleft()

    def peek_front(self) -> PcapPacket | None:
        with self._lock:
            return self._packets[0] if self._packets else None

    def clear(self) -> None:
        """Pool 비움 — seek 시 사용."""
        with self._lock:
            self._packets.clear()

    def get(self, index: int) -> PcapPacket:
        """index access — PcapReader.head_packet 등에서 사용."""
        with self._lock:
            return self._packets[index]

    @property
    def packets(self) -> list[PcapPacket]:
        """전체 packet 스냅샷 — read-only iteration용."""
        with self._lock:
            return list(self._packets)

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._packets)

    @property
    def is_full(self) -> bool:
        if self._max_size is None:
            return False
        with self._lock:
            return len(self._packets) >= self._max_size

    @property
    def is_empty(self) -> bool:
        with self._lock:
            return len(self._packets) == 0

    def println(self) -> None:
        # replayer 원본 PcapReader.println() 이 호출하지만 PcapPool 본체에 정의가 없어 stub 추가.
        # 향후 python-library 통합 시점에 replayer 와 함께 정리.
        with self._lock:
            for i, packet in enumerate(self._packets):
                print(f"[{i}] {packet}")
