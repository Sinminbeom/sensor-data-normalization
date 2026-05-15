"""Redis Pub/Sub consumer — 정규화 요청 수신.

SUBSCRIBE 한 채널에서 message 받아 NormalizationRequest 로 parse 후 receiver 필터링.
sensor-data-replayer 의 ImdgListener 패턴 차용 (pubsub.get_message 기반 non-blocking poll).
"""

import logging
from typing import Any, cast

import redis
from redis.client import PubSub, Redis

from common.protocol.normalization_request import NormalizationRequest
from config.project_config import ProjectConfig


class NormalizationRequestListener:
    """Redis Pub/Sub 기반 message poller.

    poll() 호출마다 최대 1건 message 반환. None 이면 timeout 또는 receiver 불일치.
    XACK 같은 ack 단계 없음 (pub/sub 의 특성).
    """

    def __init__(self) -> None:
        config = ProjectConfig.instance()
        self._logger = logging.getLogger(ProjectConfig.LOGGER_BASE_NAME)
        self._channel_name: str = config.redis_channel_name
        self._receiver: str = config.redis_receiver

        self._redis: Redis = redis.StrictRedis(
            host=config.redis_host, port=config.redis_port
        )
        self._pubsub: PubSub = self._redis.pubsub(ignore_subscribe_messages=True)
        self._pubsub.subscribe(self._channel_name)
        self._logger.info(
            f"subscribed to {self._channel_name} as receiver={self._receiver}"
        )

    def poll(self, timeout_sec: float = 1.0) -> NormalizationRequest | None:
        raw = cast(
            dict[str, Any] | None,
            self._pubsub.get_message(timeout=timeout_sec),
        )
        if raw is None or raw.get("type") != "message":
            return None

        body = raw.get("data")
        if not isinstance(body, (bytes, str)):
            return None

        try:
            request = NormalizationRequest.model_validate_json(body)
        except Exception as e:
            self._logger.error(f"failed to parse request envelope: {e}")
            return None

        if request.receiver != self._receiver:
            # 다른 service 대상 메시지 — skip.
            return None

        return request

    def close(self) -> None:
        try:
            self._pubsub.unsubscribe(self._channel_name)
            self._pubsub.close()
        except Exception:
            self._logger.exception("pubsub close failed")
