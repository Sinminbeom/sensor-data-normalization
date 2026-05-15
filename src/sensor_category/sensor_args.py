"""센서 인자(타입+모듈명) DTO.

원본 매핑 (swm → 신규):
- App/Category/cSensorArgs.py::cSensorArgs → SensorArgs
- 속성 sensor_type/sensor_name은 swm과 동일 명칭 유지
- getSensorType()/getSensorName() → @dataclass 필드 sensor_type / sensor_name

구조 변경:
- swm: IDTO 상속 + getter / @property 혼용.
- 신규: sensor-data-replayer의 @dataclass(frozen=True) 표준.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SensorArgs:
    sensor_type: str
    sensor_name: str
