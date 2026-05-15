"""PCAP 1초 분할기 추상화.

원본 매핑 (swm → 신규):
- PCap/cSplitsPcaps2.cSplitsPcaps (외부 라이브러리)            → IPcapSplitter (추상)
- PCap/cSplitedPcaps.cSplitedPcaps (split 결과 단일 조각)      → SplitedPcap (dataclass)
- SplitsOnce(src, out_template, lock)                          → split_once(...)
- MergePcapFiles(file_list, out_path)                          → @classmethod merge_pcap_files(...)
- cSplitedPcaps.GetProcessedPcaps/GetUnProcessedPacps           → SplitOutcome.processed/unprocessed
- cSplitedPcaps.GetPosition/GetModuleName/GetDate/...           → @property로 정렬
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

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
    def split_once(
        self, src_file: str, out_template: str, lock: Any
    ) -> SplitOutcome: ...

    @classmethod
    @abstractmethod
    def merge_pcap_files(cls, pcap_files: list[str], out_file_path: str) -> None: ...
