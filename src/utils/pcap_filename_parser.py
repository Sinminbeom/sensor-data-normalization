"""split PCAP 파일명 파서.

원본 매핑 (swm → 신규):
- utils/Utils.py::Utils.GetSplitPcapFileName(name)
    → PcapFilenameParser.parse(pcap_file_name) -> PcapFilenameParts
  반환을 tuple (moduleName, date, hours, minutes)에서 @dataclass로 변경.
  second(SS) 필드 추가 — swm 원본은 storageHandler 내부에서 별도 추출하던 값을 통합.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PcapFilenameParts:
    module_name: str
    date: str  # YYYYMMDD
    hours: str  # HH
    minutes: str  # MM
    second: str = ""  # SS (분 단위 파싱 시 빈 문자열)


class PcapFilenameParser:
    @staticmethod
    def parse(pcap_file_name: str) -> PcapFilenameParts:
        """split PCAP 파일명에서 module/date/hours/minutes/second를 추출.

        예: AT128_ROOF_FRONT_202401301045.pcap
             → module=AT128_ROOF_FRONT, date=20240130, hours=10, minutes=45
        """
        base_name = pcap_file_name.split(".")[-2]
        tail = base_name.split("_")[-1]
        module_name = base_name.replace(f"_{tail}", "")

        date = tail[:8]
        hours = tail[8:10]
        minutes = tail[10:12]
        second = tail[12:14] if len(tail) >= 14 else ""

        return PcapFilenameParts(
            module_name=module_name,
            date=date,
            hours=hours,
            minutes=minutes,
            second=second,
        )
