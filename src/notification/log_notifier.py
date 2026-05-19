"""개발용 알림 구현 — 외부 발송 없이 logger 로 완료/실패만 기록."""

from python_library.logger.app_logger import AppLogger

from notification.notification_sender import INotificationSender


class LogNotifier(INotificationSender):
    """완료/실패를 INFO/ERROR 로그로만 남긴다. 개발 단계 기본값."""

    def notify_success(self, request_id: str, summary: str) -> None:
        AppLogger.instance().info(f"[NOTIFY_SUCCESS] {request_id} | {summary}")

    def notify_failure(self, request_id: str, summary: str, error: str) -> None:
        AppLogger.instance().error(
            f"[NOTIFY_FAILURE] {request_id} | {summary} | {error}"
        )
