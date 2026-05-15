"""PCAP 1초 분할기 추상화."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from pcap.packet_position import E_PACKET_POSITION


@dataclass(frozen=True)
class SplitedPcap:
    save_path: str
    module_name: str
    date: str
    hours: str
    minutes: str
    second: str
    position: E_PACKET_POSITION

    def to_string(self) -> str:
        return (
            f"SplitedPcap(path={self.save_path}, module={self.module_name}, "
            f"ts={self.date}{self.hours}{self.minutes}{self.second}, pos={self.position.name})"
        )


@dataclass(frozen=True)
class SplitOutcome:
    processed: list[SplitedPcap]
    unprocessed: list[SplitedPcap]


class IPcapSplitter(ABC):
    @abstractmethod
    def split_once(self, src_file: str, out_template: str) -> SplitOutcome: ...

    @abstractmethod
    def merge_pcap_files(self, pcap_files: list[str], out_file_path: str) -> None: ...
