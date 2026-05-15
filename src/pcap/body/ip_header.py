from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IpHeader:
    """공통 IP 헤더 정보 — link-layer offset만 다르고 IP 헤더 구조는 동일.

    base_offset: link-layer header 끝 위치 (Ethernet=14, LinuxSll=16, LinuxSllV2=20)
    """

    protocol: int
    source_ip: str
    destination_ip: str

    @classmethod
    def parse(cls, data: bytes, base_offset: int) -> IpHeader:
        # IP 헤더 구조 — base_offset부터:
        # +9: protocol (1 byte)
        # +12: src IP (4 bytes)
        # +16: dst IP (4 bytes)
        protocol = int.from_bytes(data[base_offset + 9 : base_offset + 10], "little")
        src_bytes = data[base_offset + 12 : base_offset + 16]
        dst_bytes = data[base_offset + 16 : base_offset + 20]
        return cls(
            protocol=protocol,
            source_ip=".".join(map(str, src_bytes)),
            destination_ip=".".join(map(str, dst_bytes)),
        )


@dataclass(frozen=True)
class UdpHeader:
    """UDP 헤더 — IP 헤더 끝 +6/+8 위치의 length/checksum."""

    length: int
    checksum: int

    @classmethod
    def parse(cls, data: bytes, ip_end_offset: int) -> UdpHeader:
        length = int.from_bytes(data[ip_end_offset + 4 : ip_end_offset + 6], "little")
        checksum = int.from_bytes(data[ip_end_offset + 6 : ip_end_offset + 8], "little")
        return cls(length=length, checksum=checksum)


@dataclass(frozen=True)
class TcpFlags:
    """TCP flags — ack/psh."""

    ack: int
    psh: int

    @classmethod
    def parse(cls, data: bytes, flags_offset: int, ack_and_psh_mask: int) -> TcpFlags:
        flag_bytes = data[flags_offset : flags_offset + 2]
        ack_and_psh = int.from_bytes(flag_bytes[1:], "little") & ack_and_psh_mask
        return cls(
            ack=(ack_and_psh >> 3) & 1,
            psh=(ack_and_psh >> 4) & 1,
        )
