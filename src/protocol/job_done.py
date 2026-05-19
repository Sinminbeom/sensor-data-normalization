"""JOB_DONE — worker→manager: 한 job 처리 완료 (성공/실패) 보고 (#27)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from protocol.message import abMessage
from protocol.protocol_meta import E_PROTOCOL_ID


@dataclass(frozen=True, kw_only=True)
class JobDoneMessage(abMessage):
    protocol_id: str = E_PROTOCOL_ID.WORKER_JOB_DONE.value
    success: bool

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_body: str) -> JobDoneMessage:
        return cls(**json.loads(json_body))
