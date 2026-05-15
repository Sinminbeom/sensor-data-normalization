from __future__ import annotations

from pcap.reader.single import FilterFn, PcapReader


class MultiPcapReader:
    """여러 .pcap 파일을 순차 read하면서 첫 파일 첫 패킷 시각을 기준점으로 보존.

    Streamer가 여러 sensor의 .pcap을 동기화 재생할 때 활용.
    """

    def __init__(self) -> None:
        self._world_first_time: float | None = None

    def reset(self) -> None:
        self._world_first_time = None

    @property
    def world_first_time(self) -> float | None:
        return self._world_first_time

    def read(
        self, pcap_file_path: str, filter_fn: FilterFn | None = None
    ) -> PcapReader:
        reader = PcapReader(filter_fn)
        reader.read(pcap_file_path, self._world_first_time)

        if self._world_first_time is None and reader.head_packet is not None:
            self._world_first_time = reader.head_packet.time.time_stamp

        return reader
