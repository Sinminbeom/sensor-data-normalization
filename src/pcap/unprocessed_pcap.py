"""1초 단위 split 후 짝(HEAD/TAIL)을 이루지 못한 PCAP 조각 DTO."""

from dataclasses import dataclass


@dataclass(frozen=True)
class UnprocessedPcap:
    src_path: str
    out_file_path: str
    prefix_path: str
