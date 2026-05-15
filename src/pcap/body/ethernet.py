from __future__ import annotations

from pcap.body.ip_header import IpHeader, TcpFlags, UdpHeader
from pcap.body.pcap_body import abPcapBody
from pcap.constants import E_LINK_TYPE, E_PROTOCOL, E_TCP_FLAG

# Ethernet link-layer header = 14 bytes
_LINK_HEADER_SIZE = 14
_IP_HEADER_SIZE = 20
_UDP_PAYLOAD_OFFSET = _LINK_HEADER_SIZE + _IP_HEADER_SIZE + 8  # 42
_TCP_PAYLOAD_OFFSET = (
    _LINK_HEADER_SIZE + _IP_HEADER_SIZE + 32
)  # 66 (TCP header 32 bytes incl options)


class UdpEthernet(abPcapBody):
    link_type: int = E_LINK_TYPE.ETHERNET
    protocol: int = E_PROTOCOL.UDP

    def __init__(self) -> None:
        self.data: bytes = b""
        self.source_ip: str = ""
        self.destination_ip: str = ""
        self.length: int = 0
        self.checksum: int = 0

    def parse(self, data: bytes) -> UdpEthernet:
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


class TcpEthernet(abPcapBody):
    link_type: int = E_LINK_TYPE.ETHERNET
    protocol: int = E_PROTOCOL.TCP

    def __init__(self) -> None:
        self.data: bytes = b""
        self.source_ip: str = ""
        self.destination_ip: str = ""
        self.length: int = 0
        self.checksum: int = 0
        self.ack: int = 0
        self.psh: int = 0

    def parse(self, data: bytes) -> TcpEthernet:
        self.data = data
        ip = IpHeader.parse(data, _LINK_HEADER_SIZE)
        flags = TcpFlags.parse(data, 46, E_TCP_FLAG.ACK_AND_PSH)

        self.protocol = ip.protocol
        self.source_ip = ip.source_ip
        self.destination_ip = ip.destination_ip
        self.length = int.from_bytes(self.data[57:58], "little")
        self.checksum = int.from_bytes(self.data[50:52], "little")
        self.ack = flags.ack
        self.psh = flags.psh
        return self

    @property
    def payload(self) -> bytes:
        return self.data[_TCP_PAYLOAD_OFFSET:]
