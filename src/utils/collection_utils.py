"""dict 보조 유틸.

원본 매핑 (swm → 신규):
- App/Common/CollectionUtils.py::DictExtends      → CollectionUtils.dict_extend
- App/Common/CollectionUtils.py::DictIsContainKey → CollectionUtils.dict_contains_key
- App/Common/CollectionUtils.py::DictGetValue     → CollectionUtils.dict_get_value
"""

from collections.abc import Hashable
from typing import Any


class CollectionUtils:
    @staticmethod
    def dict_extend(target: dict[Hashable, list], key: Hashable, value: Any) -> None:
        target.setdefault(key, []).append(value)

    @staticmethod
    def dict_contains_key(source: dict, key: Hashable) -> bool:
        return key in source

    @staticmethod
    def dict_get_value(source: dict, key: Hashable, default: Any = None) -> Any:
        return source.get(key, default)
