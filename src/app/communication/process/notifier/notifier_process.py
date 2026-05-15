"""NotifierProcess — NotificationQueue pop → Slack 발송.

영구 daemon process. main 사이클 완료/실패 시 NotificationQueue.push(envelope).
"""

import logging

from python_library.process.process import abProcessing

from common.notification.slack_webhook_notifier import SlackWebhookNotifier
from common.process_state.notification_queue import NotificationQueue
from config.project_config import ProjectConfig


class NotifierProcess(abProcessing):
    def __init__(self, app_name: str, process_name: str):
        super().__init__(name=process_name)
        self._app_name = app_name
        self._process_name = process_name
        self._logger = logging.getLogger(
            f"{ProjectConfig.LOGGER_BASE_NAME}.{process_name}"
        )
        self._notification_queue = NotificationQueue.instance()
        self._notifier: SlackWebhookNotifier | None = None
        self._initialized = False

    def on_init(self) -> None:
        # requests.Session 같은 자원이 있다면 fork 후 별도 인스턴스 생성.
        self._notifier = SlackWebhookNotifier()
        self._initialized = True
        self._logger.info(f"notifier process started: {self._process_name}")

    def action(self) -> None:
        if not self._initialized:
            self.on_init()
        assert self._notifier is not None
        envelope = self._notification_queue.pop(timeout_sec=1.0)
        if envelope is None:
            return
        if envelope.success:
            self._notifier.notify_success(envelope.request_id, envelope.summary)
        else:
            self._notifier.notify_failure(
                envelope.request_id, envelope.summary, envelope.error
            )
