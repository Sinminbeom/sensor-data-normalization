"""PCAP split 결과의 패킷 위치 enum."""

from enum import IntEnum


class E_PACKET_POSITION(IntEnum):
    HEAD = 0
    MID = 1
    TAIL = 2
