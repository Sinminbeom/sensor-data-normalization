"""1초 단위 split 후 짝(HEAD/TAIL)을 이루지 못한 PCAP 조각 DTO.

원본 매핑 (swm → 신규):
- App/cUnProcessedPcapDTO.py::cUnProcessedPcapDTO → UnprocessedPcap
- GetSrcPath/GetOutFilePath/GetPrefixPath → @dataclass 필드 src_path / out_file_path / prefix_path

구조 변경:
- swm: IDTO 상속 + getter 메서드.
- 신규: sensor-data-replayer의 @dataclass(frozen=True) 표준.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class UnprocessedPcap:
    src_path: str
    out_file_path: str
    prefix_path: str
