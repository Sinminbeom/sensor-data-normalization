"""정규화 요청 envelope (Redis pub/sub message body).

외부 시스템(Slack 명령/REST/CLI)이 Redis pub/sub 채널에 PUBLISH 하는 message 의 정형 schema.
회사 컨벤션상 외부 I/O 는 pydantic.
"""

from pydantic import BaseModel, Field

from common.protocol.request_id import RequestIdGenerator


class NormalizationRequest(BaseModel):
    """Redis pub/sub message body.

    fields:
        request_id: 요청 고유 ID. publisher 가 생략하면 listener parse 시점에
                    `req-YYYYMMDD-HHMMSS-{uuid8}` 형식으로 자동 발급.
        receiver: 메시지 대상 식별자. daemon 의 conf RECEIVER 와 일치할 때만 처리.
                  여러 종류의 service 가 같은 채널을 listen할 때 라우팅 키 역할.
        date: 처리 대상 날짜 폴더 (YYYYMMDD)
        vehicle_id: VEHICLE-NNN. 빈 문자열이면 해당 날짜의 모든 vehicle 처리
        selected_device: ALL | LIDAR | CAMERA | GNSS | 단일 모듈명 (생략 시 conf 값)
        notify_channel: Slack 알림 채널 (생략 시 conf 의 DEFAULT_CHANNEL)
    """

    request_id: str = Field(default_factory=RequestIdGenerator.next)
    receiver: str
    date: str = Field(..., min_length=8, max_length=8, pattern=r"^\d{8}$")
    vehicle_id: str = ""
    selected_device: str | None = None
    notify_channel: str | None = None
