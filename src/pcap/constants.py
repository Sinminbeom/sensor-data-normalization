"""PCAP 파싱 상수 — module-level enum (상속 chain 사용 안 함)."""

from enum import IntEnum


class E_LINK_TYPE(IntEnum):
    ETHERNET = 1
    LINUX_SLL = 113
    LINUX_SLL_V2 = 276


class E_PROTOCOL(IntEnum):
    UDP = 17
    TCP = 6


class E_TCP_FLAG(IntEnum):
    ACK_AND_PSH = 24
