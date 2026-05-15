"""정규화 요청별 시퀀스 ID 발급기."""

import uuid
from datetime import UTC, datetime


class RequestIdGenerator:
    """request_id 발급 — `req-YYYYMMDD-HHMMSS-{uuid8}` 형식.

    외부 시스템이 별도 sequence DB 없이 호출 측에서 발급 가능.
    swm 의 buildNum argv 대체.
    """

    @staticmethod
    def next() -> str:
        now = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        uid = uuid.uuid4().hex[:8]
        return f"req-{now}-{uid}"
