"""PAIR_PUT — worker→manager: HEAD/TAIL 조각을 pair bucket 에 누적 요청 (#27)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from pcap.unprocessed_pcap import UnprocessedPcap
from protocol.message import abMessage
from protocol.protocol_meta import E_PROTOCOL_ID


@dataclass(frozen=True, kw_only=True)
class PairPutMessage(abMessage):
    protocol_id: str = E_PROTOCOL_ID.WORKER_PAIR_PUT.value
    pair_key: str
    item: UnprocessedPcap

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_body: str) -> PairPutMessage:
        data = json.loads(json_body)
        data["item"] = UnprocessedPcap(**data["item"])
        return cls(**data)
