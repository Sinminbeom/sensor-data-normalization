"""정규화 요청 envelope (Redis pub/sub message body).

외부 시스템(Slack 명령/REST/CLI)이 Redis pub/sub 채널에 PUBLISH 하는 message 의
정형 schema. abMessage 를 상속해 protocol_id / sender / receiver 공통 헤더 보유.
도메인 검증(date 형식 등)은 메시지 인스턴스가 아닌 boundary(listener) 책임 —
메시지 dataclass 는 단순 DTO.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Self

from protocol.message import abMessage
from protocol.protocol_meta import E_PROTOCOL_ID
from protocol.request_id import RequestIdGenerator


@dataclass(frozen=True, kw_only=True)
class NormalizationRequest(abMessage):
    protocol_id: str = E_PROTOCOL_ID.NORMALIZATION_REQUEST.value
    sender: str = "CLIENT"
    request_id: str = field(default_factory=RequestIdGenerator.next)
    date: str = ""
    vehicle_id: str = ""
    selected_device: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_body: str) -> Self:
        return cls(**json.loads(json_body))
