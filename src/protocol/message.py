from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Self


class IMessage(ABC):
    @abstractmethod
    def to_json(self) -> str: ...

    @classmethod
    @abstractmethod
    def from_json(cls, json_body: str) -> Self: ...


@dataclass(frozen=True, kw_only=True)
class abMessage(IMessage):
    protocol_id: str
    sender: str
    receiver: str
