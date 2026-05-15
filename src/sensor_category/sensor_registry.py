"""센서 모듈명 → SensorArgs(type, name) 매핑 레지스트리 싱글톤.

원본 매핑 (swm → 신규):
- App/Category/eSensor.py::EC_SENSOR (싱글톤) → SensorRegistry
- Register()           → register()
- GetSensorArgs(name)  → get_sensor_args(name)
- 추가: has_sensor(name)
구조 변경: enum 정의(E_LIDAR/E_CAMERA/E_GNSS)는 sensor_category.enum_sensor로 분리하고,
이 클래스는 등록·조회만 담당하도록 책임 축소.
"""

from python_library.singleton.singleton import Singleton

from sensor_category.enum_sensor import E_CAMERA, E_GNSS, E_LIDAR, E_SENSOR_TYPE
from sensor_category.sensor_args import SensorArgs


class SensorRegistry(Singleton):
    def __init__(self) -> None:
        super().__init__()
        self._args_by_name: dict[str, SensorArgs] = {}
        self._registered = False

    def register(self) -> None:
        if self._registered:
            return

        for name in self._iter_enum_values(E_LIDAR):
            self._args_by_name[name] = SensorArgs(E_SENSOR_TYPE.LIDAR, name)
        for name in self._iter_enum_values(E_CAMERA):
            self._args_by_name[name] = SensorArgs(E_SENSOR_TYPE.CAMERA, name)
        for name in self._iter_enum_values(E_GNSS):
            self._args_by_name[name] = SensorArgs(E_SENSOR_TYPE.GNSS, name)

        self._registered = True

    def get_sensor_args(self, sensor_name: str) -> SensorArgs:
        return self._args_by_name[sensor_name]

    def has_sensor(self, sensor_name: str) -> bool:
        return sensor_name in self._args_by_name

    @staticmethod
    def _iter_enum_values(enum_cls: type) -> list[str]:
        return [
            value
            for key, value in vars(enum_cls).items()
            if not key.startswith("_") and isinstance(value, str)
        ]
