"""센서 타입별 모듈 목록 DTO.

원본 매핑 (swm → 신규):
- App/Category/cSensorDTO.py::cSensorDTO → Sensor
- GetSensorProtocolLists()                 → get_sensor_protocol_list()
  (반환 형식 동일: "<TYPE>/<NAME>" 문자열 리스트)

구조 변경:
- swm: IDTO 상속 + getter 메서드.
- 신규: @dataclass + default_factory(dict). mutable 컨테이너라 frozen=False.
"""

from dataclasses import dataclass, field


@dataclass
class Sensor:
    sensors_by_type: dict[str, list[str]] = field(default_factory=dict)

    def append(self, sensor_type: str, sensor_name: str) -> None:
        self.sensors_by_type.setdefault(sensor_type, []).append(sensor_name)

    def get_sensors(self, sensor_type: str) -> list[str]:
        return list(self.sensors_by_type.get(sensor_type, []))

    def get_sensor_protocol_list(self) -> list[str]:
        return [
            f"{sensor_type}/{name}"
            for sensor_type, names in self.sensors_by_type.items()
            for name in names
        ]
