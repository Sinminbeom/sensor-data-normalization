"""프로세스 카테고리 enum.

원본 매핑 (swm → 신규):
- swm에는 카테고리 enum 자체가 없다 (main에서 replayerPreProcesser·storageHandler 직접 생성).
- sensor-data-replayer 의 E_CATE 패턴(STREAMER/DOWNLOADER 등)을 따라 E_CATE.NORMALIZER 추가.
- 두 단계 구성:
    E_CATE.NORMALIZER.COMMON.NORMALIZER_MANAGER  — replayerPreProcesser 역할 (오케스트레이터)
    E_CATE.NORMALIZER.MODULE.NORMALIZER_MODULE   — storageHandler 역할 (워커 N개)
"""

from python_library.define.enum import IENUM

from app.normalizer.process.manager.manager import NormalizerManager
from app.normalizer.process.module.module import NormalizerModule


class E_CATE_META_ELE(IENUM):
    NAME = 0
    LAMBDA = 1


class E_CATE(IENUM):
    NORMALIZER = "NORMALIZER"

    class E_NORMALIZER(IENUM):
        COMMON = "COMMON"
        MODULE = "MODULE"

        class E_COMMON(IENUM):
            NORMALIZER_MANAGER = "NORMALIZER_MANAGER"
            E_NORMALIZER_MANAGER = (
                NORMALIZER_MANAGER,
                lambda _app_name, _process_name: NormalizerManager(
                    _app_name, _process_name
                ),
            )

        class E_MODULE(IENUM):
            NORMALIZER_MODULE = "NORMALIZER_MODULE"
            E_NORMALIZER_MODULE = (
                NORMALIZER_MODULE,
                lambda _app_name, _process_name: NormalizerModule(
                    _app_name, _process_name
                ),
            )
