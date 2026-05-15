from __future__ import annotations

from pcap.body.ip_header import IpHeader, TcpFlags, UdpHeader
from pcap.body.pcap_body import abPcapBody
from pcap.constants import E_LINK_TYPE, E_PROTOCOL, E_TCP_FLAG

# Linux SLL v2 link-layer header = 20 bytes
_LINK_HEADER_SIZE = 20
_IP_HEADER_SIZE = 20
_UDP_PAYLOAD_OFFSET = _LINK_HEADER_SIZE + _IP_HEADER_SIZE + 8  # 48
# 원본은 TCP linux_sll_v2도 link header 16 기반(_LINK_HEADER_SIZE=16) offset을 사용했음 — 동일 보존
_TCP_LINK_HEADER_SIZE_LEGACY = 16
_TCP_PAYLOAD_OFFSET = _TCP_LINK_HEADER_SIZE_LEGACY + _IP_HEADER_SIZE + 32  # 68


class UdpLinuxSllV2(abPcapBody):
    # 원본은 LINUX_SLL을 그대로 link_type으로 둠 — 동일 보존.
    link_type: int = E_LINK_TYPE.LINUX_SLL
    protocol: int = E_PROTOCOL.UDP

    def __init__(self) -> None:
        self.data: bytes = b""
        self.source_ip: str = ""
        self.destination_ip: str = ""
        self.length: int = 0
        self.checksum: int = 0

    def parse(self, data: bytes) -> UdpLinuxSllV2:
        self.data = data
        ip = IpHeader.parse(data, _LINK_HEADER_SIZE)
        udp = UdpHeader.parse(data, _LINK_HEADER_SIZE + _IP_HEADER_SIZE)

        self.protocol = ip.protocol
        self.source_ip = ip.source_ip
        self.destination_ip = ip.destination_ip
        self.length = udp.length
        self.checksum = udp.checksum
        return self

    @property
    def payload(self) -> bytes:
        return self.data[_UDP_PAYLOAD_OFFSET:]


class TcpLinuxSllV2(abPcapBody):
    link_type: int = E_LINK_TYPE.LINUX_SLL
    protocol: int = E_PROTOCOL.TCP

    def __init__(self) -> None:
        self.data: bytes = b""
        self.source_ip: str = ""
        self.destination_ip: str = ""
        self.length: int = 0
        self.checksum: int = 0
        self.ack: int = 0
        self.psh: int = 0

    def parse(self, data: bytes) -> TcpLinuxSllV2:
        self.data = data
        # 원본은 link header 16 기반 offset 사용 — 동일 보존.
        ip = IpHeader.parse(data, _TCP_LINK_HEADER_SIZE_LEGACY)
        flags = TcpFlags.parse(data, 52, E_TCP_FLAG.ACK_AND_PSH)

        self.protocol = ip.protocol
        self.source_ip = ip.source_ip
        self.destination_ip = ip.destination_ip
        self.length = int.from_bytes(self.data[63:64], "little")
        self.checksum = int.from_bytes(self.data[56:58], "little")
        self.ack = flags.ack
        self.psh = flags.psh
        return self

    @property
    def payload(self) -> bytes:
        return self.data[_TCP_PAYLOAD_OFFSET:]
