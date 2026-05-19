"""Slack Incoming Webhook 기반 알림."""

import json

import requests
from python_library.logger.app_logger import AppLogger

from config.project_config import ProjectConfig
from notification.notification_sender import INotificationSender


class SlackWebhookNotifier(INotificationSender):
    """Slack Incoming Webhook 으로 메시지 발송.

    `conf [NOTIFICATION].WEBHOOK_URL` 이 비어 있으면 발송 skip (개발 환경).
    """

    def __init__(self) -> None:
        config = ProjectConfig.instance()
        self._webhook_url: str = config.notification_webhook_url
        self._channel: str = config.notification_default_channel

    def notify_success(self, request_id: str, summary: str) -> None:
        text = f":white_check_mark: *{request_id}* 완료\n{summary}"
        self._post(text)

    def notify_failure(self, request_id: str, summary: str, error: str) -> None:
        text = f":x: *{request_id}* 실패\n{summary}\n```{error}```"
        self._post(text)

    def _post(self, text: str) -> None:
        if not self._webhook_url:
            AppLogger.instance().info(f"slack webhook empty, skip notify: {text}")
            return
        try:
            requests.post(
                self._webhook_url,
                data=json.dumps({"channel": self._channel, "text": text}),
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
        except Exception:
            AppLogger.instance().exception("slack webhook failed")
