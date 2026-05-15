from __future__ import annotations

from abc import ABC, abstractmethod


class abPcapBody(ABC):
    """PCAP 패킷 body 추상 base — link-type/protocol별 구현은 body/ 하위.

    공유 구현은 IpHeader/UdpHeader/TcpFlags helper로 composition.
    본 base는 attribute 인터페이스 + parse/payload 강제만 담당.
    """

    data: bytes
    protocol: int
    link_type: int
    source_ip: str
    destination_ip: str
    length: int
    checksum: int

    @abstractmethod
    def parse(self, data: bytes) -> abPcapBody: ...

    @property
    @abstractmethod
    def payload(self) -> bytes: ...
