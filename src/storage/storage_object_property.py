"""원본 스토리지(예: Hadoop)에서 받은 객체의 경로/이름 정보 DTO.

원본 매핑 (swm → 신규):
- App/cStorageObjectPropertyDTO.py::cStorageObjectPropertyDTO → StorageObjectProperty
- GetFilePath()/GetFileName()  → @dataclass 필드 file_path / file_name
- GetVehicleId()               → @property vehicle_id (path 마지막 세그먼트)
- GetDownloadSrcPath()          → @property download_src_path

구조 변경:
- swm은 IDTO 추상 상속 + getter 메서드 패턴.
- 신규는 sensor-data-replayer의 @dataclass(frozen=True) 표준을 따라
  불변 DTO로 단순화. 파생 값은 @property로 노출.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StorageObjectProperty:
    file_path: str
    file_name: str

    @property
    def vehicle_id(self) -> str:
        return self.file_path.split("/")[-1]

    @property
    def download_src_path(self) -> str:
        return f"{self.file_path}/{self.file_name}"
