from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TimeInfo:
    """패킷의 상대 시간 정보 — 모두 초 단위 float."""

    time_stamp: float  # 절대 epoch 시각
    offset_time: float  # 직전 패킷과의 차이
    accumulate_offset_time: float  # 같은 파일 첫 패킷 기준 누적
    world_accumulate_offset_time: float  # 멀티 파일 첫 패킷 기준 누적

    @property
    def time_stamp_ns(self) -> float:
        return self.time_stamp * 1_000_000_000

    @property
    def offset_time_ns(self) -> float:
        return self.offset_time * 1_000_000_000

    @property
    def accumulate_offset_time_ns(self) -> float:
        return self.accumulate_offset_time * 1_000_000_000

    @property
    def world_accumulate_offset_time_ns(self) -> float:
        return self.world_accumulate_offset_time * 1_000_000_000


class TimeCalculator:
    """이전 패킷·첫 패킷 reference로 TimeInfo를 계산하는 service."""

    @staticmethod
    def calculate(
        time_stamp: float,
        previous_time: float | None = None,
        first_time: float | None = None,
        world_first_time: float | None = None,
    ) -> TimeInfo:
        offset_time = 0.0 if previous_time is None else (time_stamp - previous_time)
        accumulate_offset_time = (
            0.0 if first_time is None else (time_stamp - first_time)
        )
        if world_first_time is None:
            world_accumulate_offset_time = accumulate_offset_time
        else:
            world_accumulate_offset_time = time_stamp - world_first_time
        return TimeInfo(
            time_stamp=time_stamp,
            offset_time=offset_time,
            accumulate_offset_time=accumulate_offset_time,
            world_accumulate_offset_time=world_accumulate_offset_time,
        )
