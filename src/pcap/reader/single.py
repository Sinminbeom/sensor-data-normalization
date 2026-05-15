from __future__ import annotations

from collections.abc import Callable

from pcap.body.pcap_body import abPcapBody
from pcap.body.pcap_body_factory import PcapBodyFactory
from pcap.headers.file_header import FileHeader
from pcap.headers.packet_header import PacketHeader
from pcap.packet import PcapPacket
from pcap.pool import PcapPool
from pcap.time_info import TimeCalculator

FilterFn = Callable[[PacketHeader, abPcapBody], bool]


class PcapReader:
    """단일 .pcap 파일 reader — file/packet header + body parse + pool 누적."""

    def __init__(self, filter_fn: FilterFn | None = None) -> None:
        self._filter_fn: FilterFn | None = filter_fn
        self._file_header: FileHeader | None = None
        self._pool: PcapPool = PcapPool()

    @property
    def pool(self) -> PcapPool:
        return self._pool

    @property
    def file_header(self) -> FileHeader | None:
        return self._file_header

    @property
    def head_packet(self) -> PcapPacket | None:
        if self._pool.size == 0:
            return None
        return self._pool.get(0)

    @property
    def pool_size(self) -> int:
        return self._pool.size

    def _is_filtering(self, header: PacketHeader, body: abPcapBody) -> bool:
        if self._filter_fn is None:
            return False
        return self._filter_fn(header, body)

    def read(
        self, pcap_file_path: str, world_first_time: float | None = None
    ) -> PcapReader:
        packet_index = 1
        first_time: float | None = None
        previous_time: float | None = None

        with open(pcap_file_path, "rb") as f:
            self._file_header = FileHeader.from_file(f)

            while True:
                packet_header = PacketHeader.from_file(f)
                if packet_header is None:
                    break

                body = PcapBodyFactory.parse(
                    self._file_header.link_type, packet_header.packlen, f
                )
                if body is None:
                    break

                time = TimeCalculator.calculate(
                    time_stamp=packet_header.time_stamp,
                    previous_time=previous_time,
                    first_time=first_time,
                    world_first_time=world_first_time,
                )

                if not self._is_filtering(packet_header, body):
                    self._pool.append(
                        PcapPacket(packet_index, packet_header, body, time)
                    )
                    packet_index += 1

                previous_time = packet_header.time_stamp
                if first_time is None:
                    first_time = packet_header.time_stamp

        return self

    def println(self) -> None:
        self._pool.println()
