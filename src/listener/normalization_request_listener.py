"""Redis queue 기반 정규화 요청 수신 (LIST 자료형 + LPUSH/BRPOP 패턴).

외부 시스템이 LPUSH 한 메시지를 BRPOP 으로 blocking pop. Pub/Sub 와 달리 daemon 이
대기 중이 아닐 때 들어온 메시지도 queue 에 영속, 다음 BRPOP 에서 꺼낸다.
"""

import re
from typing import cast

import redis
from python_library.logger.app_logger import AppLogger
from redis.client import Redis

from config.project_config import ProjectConfig
from protocol.normalization_request import NormalizationRequest
from protocol.protocol_meta import E_PROTOCOL_ID, ProtocolMeta

_DATE_PATTERN = re.compile(r"\d{8}")


class NormalizationRequestListener:
    """Redis queue (LIST) 기반 message poller.

    poll() 호출마다 BRPOP 으로 최대 1건 message 반환. None 이면 timeout 또는 receiver
    불일치 (mismatched 메시지는 destructive pop 으로 사라짐 — single daemon 시나리오
    가정. 멀티 receiver 필요 시 queue 를 receiver 별로 분리할 것).
    """

    def __init__(self) -> None:
        config = ProjectConfig.instance()
        self._queue_name: str = config.redis_channel_name
        self._receiver: str = config.redis_receiver

        self._redis: Redis = redis.StrictRedis(
            host=config.redis_host, port=config.redis_port
        )
        AppLogger.instance().info(
            f"polling queue {self._queue_name} as receiver={self._receiver}"
        )

    def poll(self, timeout_sec: float = 1.0) -> NormalizationRequest | None:
        # BRPOP: timeout 이 int 단위. 0 이면 무한 대기 — 최소 1초 보장.
        # redis-py stub 이 Awaitable union 형태라 cast 로 sync 결과 명시.
        result = cast(
            tuple[bytes, bytes] | None,
            self._redis.brpop([self._queue_name], timeout=max(1, int(timeout_sec))),
        )
        if result is None:
            return None

        _, body = result  # (queue name bytes, value bytes)
        try:
            request = cast(
                NormalizationRequest,
                ProtocolMeta.instance().get_decoder(
                    E_PROTOCOL_ID.NORMALIZATION_REQUEST.value
                )(body.decode("utf-8")),
            )
        except Exception as e:
            AppLogger.instance().error(f"failed to parse request envelope: {e}")
            return None

        if request.receiver != self._receiver:
            AppLogger.instance().warning(
                f"dropping message: receiver={request.receiver} != {self._receiver}"
            )
            return None

        if not _DATE_PATTERN.fullmatch(request.date):
            AppLogger.instance().error(
                f"dropping message: invalid date format (expect YYYYMMDD): {request.date!r}"
            )
            return None

        return request

    def close(self) -> None:
        try:
            self._redis.close()
        except Exception:
            AppLogger.instance().exception("redis close failed")
