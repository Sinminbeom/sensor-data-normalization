"""LocalPcapSplitter — PacketHeader.time_stamp 기준 1초 단위 split + merge.

알고리즘:
- PCAP file = 24B FileHeader + (16B PacketHeader + caplen 바이트 payload) 반복
- PacketHeader.time_stamp(=captime + caputime/1e6) 의 정수 second 로 grouping
- 각 second 그룹마다 별도 .pcap 파일로 write (FileHeader + 그 그룹 패킷들)
- HEAD: 첫 second 그룹 (이전 file 과 이어질 가능성)
- TAIL: 마지막 second 그룹 (다음 file 과 이어질 가능성)
- MID : 중간 second 그룹 (완전한 1초)
"""

from __future__ import annotations

import os

from pcap.headers.packet_header import PacketHeader
from pcap.packet_position import E_PACKET_POSITION
from pcap.pcap_filename_parser import PcapFilenameParser
from pcap.splitter import IPcapSplitter, SplitedPcap, SplitOutcome


class LocalPcapSplitter(IPcapSplitter):
    PCAP_FILE_HEADER_SIZE = 24
    PCAP_PACKET_HEADER_SIZE = 16

    def split_once(self, src_file: str, out_template: str) -> SplitOutcome:
        file_name = os.path.basename(src_file)
        parts = PcapFilenameParser.parse(file_name)

        # 1) raw bytes 로 file header + 각 (packet header, payload) 묶음 수집.
        file_header_bytes, packet_records = self._read_pcap_records(src_file)

        # 2) second 단위 grouping (정수 초로 변환).
        groups: dict[int, list[tuple[PacketHeader, bytes, bytes]]] = {}
        for header, header_bytes, payload in packet_records:
            second = int(header.time_stamp)
            groups.setdefault(second, []).append((header, header_bytes, payload))

        if not groups:
            return SplitOutcome(processed=[], unprocessed=[])

        sorted_seconds = sorted(groups.keys())
        head_second = sorted_seconds[0]
        tail_second = sorted_seconds[-1]

        # 3) 각 second 그룹 → 별도 .pcap write.
        processed: list[SplitedPcap] = []
        unprocessed: list[SplitedPcap] = []

        for second in sorted_seconds:
            second_str = f"{second:02d}"[-2:]
            timestamp_label = f"{parts.date}{parts.hours}{parts.minutes}{second_str}"
            save_path = out_template.format(timestamp_label)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            self._write_pcap(save_path, file_header_bytes, groups[second])

            position = self._classify_position(second, head_second, tail_second)
            piece = SplitedPcap(
                save_path=save_path,
                module_name=parts.module_name,
                date=parts.date,
                hours=parts.hours,
                minutes=parts.minutes,
                second=second_str,
                position=position,
            )
            if position == E_PACKET_POSITION.MID:
                processed.append(piece)
            else:
                unprocessed.append(piece)

        return SplitOutcome(processed=processed, unprocessed=unprocessed)

    def merge_pcap_files(self, pcap_files: list[str], out_file_path: str) -> None:
        if not pcap_files:
            return
        os.makedirs(os.path.dirname(out_file_path), exist_ok=True)

        with open(pcap_files[0], "rb") as first:
            file_header_bytes = first.read(LocalPcapSplitter.PCAP_FILE_HEADER_SIZE)

        with open(out_file_path, "wb") as out:
            out.write(file_header_bytes)
            for pcap_file in pcap_files:
                with open(pcap_file, "rb") as src:
                    src.seek(LocalPcapSplitter.PCAP_FILE_HEADER_SIZE)
                    while True:
                        chunk = src.read(65536)
                        if not chunk:
                            break
                        out.write(chunk)

    # ---------- internals ----------

    def _read_pcap_records(
        self, src_file: str
    ) -> tuple[bytes, list[tuple[PacketHeader, bytes, bytes]]]:
        records: list[tuple[PacketHeader, bytes, bytes]] = []
        with open(src_file, "rb") as f:
            file_header_bytes = f.read(LocalPcapSplitter.PCAP_FILE_HEADER_SIZE)
            # FileHeader.from_file 은 file_point 를 처음부터 읽으므로 별도 BytesIO 로 parse.
            # 본 메서드에서는 bytes 만 쥐고 다음 packet 부터 직접 parse.
            while True:
                header_bytes = f.read(LocalPcapSplitter.PCAP_PACKET_HEADER_SIZE)
                if (
                    not header_bytes
                    or len(header_bytes) < LocalPcapSplitter.PCAP_PACKET_HEADER_SIZE
                ):
                    break
                header = PacketHeader(
                    captime=int.from_bytes(header_bytes[0:4], "little"),
                    caputime=int.from_bytes(header_bytes[4:8], "little"),
                    caplen=int.from_bytes(header_bytes[8:12], "little"),
                    packlen=int.from_bytes(header_bytes[12:16], "little"),
                )
                payload = f.read(header.caplen)
                if len(payload) < header.caplen:
                    break
                records.append((header, header_bytes, payload))
        return file_header_bytes, records

    def _write_pcap(
        self,
        save_path: str,
        file_header_bytes: bytes,
        records: list[tuple[PacketHeader, bytes, bytes]],
    ) -> None:
        with open(save_path, "wb") as out:
            out.write(file_header_bytes)
            for _header, header_bytes, payload in records:
                out.write(header_bytes)
                out.write(payload)

    def _classify_position(
        self, second: int, head_second: int, tail_second: int
    ) -> E_PACKET_POSITION:
        if second == head_second:
            return E_PACKET_POSITION.HEAD
        if second == tail_second:
            return E_PACKET_POSITION.TAIL
        return E_PACKET_POSITION.MID
