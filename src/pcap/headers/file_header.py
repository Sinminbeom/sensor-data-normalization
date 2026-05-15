from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO


@dataclass(frozen=True)
class FileHeader:
    """PCAP 파일 24바이트 헤더."""

    magic: bytes  # uint, 0xA1B2C3D4
    major: int  # ushort
    minor: int  # ushort
    gmt_to_local: int  # uint
    timestamp: int  # uint
    max_caplen: int  # uint
    link_type: int  # uint

    @classmethod
    def from_file(cls, file_point: BinaryIO) -> FileHeader:
        magic = file_point.read(4)
        major = int.from_bytes(file_point.read(2), "little")
        minor = int.from_bytes(file_point.read(2), "little")
        gmt_to_local = int.from_bytes(file_point.read(4), "little")
        timestamp = int.from_bytes(file_point.read(4), "little")
        max_caplen = int.from_bytes(file_point.read(4), "little")
        link_type = int.from_bytes(file_point.read(4), "little")
        return cls(magic, major, minor, gmt_to_local, timestamp, max_caplen, link_type)
