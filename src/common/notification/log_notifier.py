"""개발용 알림 구현 — 외부 발송 없이 logger 로 완료/실패만 기록."""

import logging

from common.notification.notification_sender import INotificationSender
from config.project_config import ProjectConfig


class LogNotifier(INotificationSender):
    """완료/실패를 INFO/ERROR 로그로만 남긴다. 개발 단계 기본값."""

    def __init__(self) -> None:
        self._logger = logging.getLogger(ProjectConfig.LOGGER_BASE_NAME)

    def notify_success(self, request_id: str, summary: str) -> None:
        self._logger.info(f"[NOTIFY_SUCCESS] {request_id} | {summary}")

    def notify_failure(self, request_id: str, summary: str, error: str) -> None:
        self._logger.error(f"[NOTIFY_FAILURE] {request_id} | {summary} | {error}")
