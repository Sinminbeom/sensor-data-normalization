"""protocol_id enum + ProtocolEntry registry (#27).

`common/protocol/` 의 모든 메시지 클래스는 본 ProtocolMeta 에 한 번 등록되어
어디서든 동일한 path 로 디코딩/인스턴스화된다. Singleton 이라
`ProtocolMeta.instance()` 첫 호출 시 `__init__` 에서 모든 메시지 자동 register.

E_PROTOCOL_ID:
  모든 protocol_id 를 모아두는 enum — single source of truth. 각 메시지
  dataclass 의 `protocol_id` instance field default 가 enum.value 를 참조.

ProtocolEntry:
  protocol_id 별로 decoder + factory 를 묶음 (replayer 의 ProtocolEntry 단순화).
  - decoder(json_body) -> message
  - factory(**kwargs) -> message  (각 메시지의 payload signature 는 메시지마다 다름)

두 가지 디코딩 path:
  - `get_decoder(protocol_id)(json_body)` — 외부에서 protocol_id 를 이미 아는 경우
    (예: NormalizationRequestListener — Redis 큐 한 채널 = 한 메시지 타입).
  - `decode_body(json_body)` — body 안에 `protocol_id` 필드가 박혀 있는 경우
    (abMessage 상속 메시지. worker IPC). envelope 불필요.

새 메시지 추가 시 E_PROTOCOL_ID + 메시지 클래스 + `_register_protocols` 한 줄.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from python_library.singleton.singleton import Singleton

from protocol.message import IMessage

_DecoderFn = Callable[[str], IMessage]
_FactoryFn = Callable[..., IMessage]


class E_PROTOCOL_ID(Enum):
    NORMALIZATION_REQUEST = "NORMALIZATION_REQUEST"
    WORKER_PAIR_PUT = "WORKER_PAIR_PUT"
    WORKER_JOB_DONE = "WORKER_JOB_DONE"


@dataclass(frozen=True)
class ProtocolEntry:
    decoder: _DecoderFn
    factory: _FactoryFn


class ProtocolMeta(Singleton):
    def __init__(self) -> None:
        super().__init__()
        self._entries: dict[str, ProtocolEntry] = {}
        self._register_protocols()

    def _register_protocols(self) -> None:
        # 사이클 회피용 lazy import.
        from protocol.job_done import JobDoneMessage
        from protocol.normalization_request import NormalizationRequest
        from protocol.pair_put import PairPutMessage

        self._register(
            E_PROTOCOL_ID.NORMALIZATION_REQUEST.value,
            decoder=NormalizationRequest.from_json,
            factory=NormalizationRequest,
        )
        self._register(
            E_PROTOCOL_ID.WORKER_PAIR_PUT.value,
            decoder=PairPutMessage.from_json,
            factory=PairPutMessage,
        )
        self._register(
            E_PROTOCOL_ID.WORKER_JOB_DONE.value,
            decoder=JobDoneMessage.from_json,
            factory=JobDoneMessage,
        )

    def _register(
        self, protocol_id: str, *, decoder: _DecoderFn, factory: _FactoryFn
    ) -> None:
        if protocol_id in self._entries:
            raise KeyError(f"Protocol already registered: {protocol_id}")
        self._entries[protocol_id] = ProtocolEntry(decoder=decoder, factory=factory)

    def get_decoder(self, protocol_id: str) -> _DecoderFn:
        return self._entries[protocol_id].decoder

    def get_factory(self, protocol_id: str) -> _FactoryFn:
        return self._entries[protocol_id].factory

    def decode_body(self, json_body: str) -> IMessage:
        """abMessage 계열 — body 안의 `protocol_id` 필드로 dispatch."""
        protocol_id = json.loads(json_body).get("protocol_id")
        if protocol_id is None:
            raise ValueError("missing protocol_id in message body")
        return self._entries[protocol_id].decoder(json_body)
