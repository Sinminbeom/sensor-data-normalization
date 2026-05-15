from __future__ import annotations

from typing import BinaryIO, ClassVar

from pcap.body.ethernet import TcpEthernet, UdpEthernet
from pcap.body.linux_sll import TcpLinuxSll, UdpLinuxSll
from pcap.body.linux_sll_v2 import TcpLinuxSllV2, UdpLinuxSllV2
from pcap.body.pcap_body import abPcapBody
from pcap.constants import E_LINK_TYPE, E_PROTOCOL


class PcapBodyFactory:
    """(link_type, protocol) → body 클래스 dispatch + bytes parse 진입점."""

    # (link_type, protocol) → body 클래스 매핑
    _BODY_TABLE: ClassVar[dict[tuple[int, int], type[abPcapBody]]] = {
        (E_LINK_TYPE.ETHERNET, E_PROTOCOL.UDP): UdpEthernet,
        (E_LINK_TYPE.ETHERNET, E_PROTOCOL.TCP): TcpEthernet,
        (E_LINK_TYPE.LINUX_SLL, E_PROTOCOL.UDP): UdpLinuxSll,
        (E_LINK_TYPE.LINUX_SLL, E_PROTOCOL.TCP): TcpLinuxSll,
        (E_LINK_TYPE.LINUX_SLL_V2, E_PROTOCOL.UDP): UdpLinuxSllV2,
        (E_LINK_TYPE.LINUX_SLL_V2, E_PROTOCOL.TCP): TcpLinuxSllV2,
    }

    # link-type별 protocol byte offset (data[offset:offset+1])
    _PROTOCOL_OFFSET: ClassVar[dict[int, int]] = {
        E_LINK_TYPE.ETHERNET: 23,
        E_LINK_TYPE.LINUX_SLL: 25,
        E_LINK_TYPE.LINUX_SLL_V2: 29,
    }

    @classmethod
    def register(
        cls, link_type: int, protocol: int, body_cls: type[abPcapBody]
    ) -> None:
        """확장 — 새 link-type/protocol 조합에 대한 body 클래스 등록."""
        cls._BODY_TABLE[(link_type, protocol)] = body_cls

    @classmethod
    def parse(
        cls, link_type: int, pak_len: int, file_point: BinaryIO
    ) -> abPcapBody | None:
        """파일 포인터에서 pak_len 바이트 읽어 link_type/protocol에 맞는 body 인스턴스 반환."""
        if pak_len <= 0:
            return None

        data = file_point.read(pak_len)
        if not data:
            return None

        protocol = cls._detect_protocol(link_type, data)
        body_cls = cls._BODY_TABLE.get((link_type, protocol))
        if body_cls is None:
            # TCP가 기본 fallback — 원본과 동일 동작 (UDP 외엔 TCP)
            body_cls = cls._BODY_TABLE.get((link_type, E_PROTOCOL.TCP))
        if body_cls is None:
            return None

        body = body_cls()
        body.parse(data)
        return body

    @classmethod
    def _detect_protocol(cls, link_type: int, data: bytes) -> int:
        offset = cls._PROTOCOL_OFFSET[link_type]
        return int.from_bytes(data[offset : offset + 1], "little")
