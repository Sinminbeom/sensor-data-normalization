"""PCAP split 결과의 패킷 위치 enum.

원본 매핑 (swm → 신규):
- App/cDefine.py::ePacketPosition → E_PACKET_POSITION
- 위치 분류: HEAD (1초 경계 시작 조각) / MID (완전한 1초) / TAIL (1초 경계 끝 조각)
- splitter 의 output(SplitedPcap.position)에 부착되며, worker 에서 MID 만 즉시 업로드,
  HEAD/TAIL 은 pair_buckets 로 보낸다.
"""

from enum import IntEnum


class E_PACKET_POSITION(IntEnum):
    HEAD = 0
    MID = 1
    TAIL = 2
