from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import BinaryIO


@dataclass(frozen=True)
class PacketHeader:
    """PCAP 패킷별 16바이트 헤더 — captime/caputime/caplen/packlen."""

    captime: int  # uint, second
    caputime: int  # uint, microsecond
    caplen: int  # uint
    packlen: int  # uint

    @classmethod
    def from_file(cls, file_point: BinaryIO) -> PacketHeader | None:
        binary = file_point.read(4)
        if not binary:
            return None
        captime = int.from_bytes(binary, "little")
        caputime = int.from_bytes(file_point.read(4), "little")
        caplen = int.from_bytes(file_point.read(4), "little")
        packlen = int.from_bytes(file_point.read(4), "little")
        return cls(captime, caputime, caplen, packlen)

    @property
    def time_stamp(self) -> float:
        return self.captime + self.caputime / 1e6

    @property
    def time_str(self) -> str:
        return datetime.datetime.fromtimestamp(self.time_stamp).strftime(
            "%Y-%m-%d %H:%M:%S.%f"
        )
