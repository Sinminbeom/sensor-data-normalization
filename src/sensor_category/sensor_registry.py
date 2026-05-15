"""센서 모듈명 → 센서 타입 매핑 레지스트리 싱글톤."""

from python_library.singleton.singleton import Singleton

from sensor_category.enum_sensor import E_CAMERA, E_GNSS, E_LIDAR, E_SENSOR_TYPE


class SensorRegistry(Singleton):
    def __init__(self) -> None:
        super().__init__()
        self._type_by_name: dict[str, str] = {}
        self._registered = False

    def register(self) -> None:
        if self._registered:
            return

        for name in self._iter_enum_values(E_LIDAR):
            self._type_by_name[name] = E_SENSOR_TYPE.LIDAR
        for name in self._iter_enum_values(E_CAMERA):
            self._type_by_name[name] = E_SENSOR_TYPE.CAMERA
        for name in self._iter_enum_values(E_GNSS):
            self._type_by_name[name] = E_SENSOR_TYPE.GNSS

        self._registered = True

    def get_sensor_type(self, sensor_name: str) -> str:
        return self._type_by_name[sensor_name]

    def has_sensor(self, sensor_name: str) -> bool:
        return sensor_name in self._type_by_name

    @staticmethod
    def _iter_enum_values(enum_cls: type) -> list[str]:
        return [
            value
            for key, value in vars(enum_cls).items()
            if not key.startswith("_") and isinstance(value, str)
        ]
