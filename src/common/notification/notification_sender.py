"""알림 발송 추상 인터페이스."""

from abc import ABC, abstractmethod


class INotificationSender(ABC):
    @abstractmethod
    def notify_success(self, request_id: str, summary: str) -> None: ...

    @abstractmethod
    def notify_failure(self, request_id: str, summary: str, error: str) -> None: ...
