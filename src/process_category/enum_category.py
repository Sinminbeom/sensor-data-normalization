"""프로세스 카테고리 enum."""

from python_library.define.enum import IENUM

from app.communication.process.consumer.consumer_process import RequestConsumerProcess
from app.communication.process.notifier.notifier_process import NotifierProcess
from app.normalizer.process.manager.manager import NormalizerManager
from app.normalizer.process.module.module import NormalizerModule


class E_CATE_META_ELE(IENUM):
    NAME = 0
    LAMBDA = 1


class E_CATE(IENUM):
    NORMALIZER = "NORMALIZER"
    COMMUNICATION = "COMMUNICATION"

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

    class E_COMMUNICATION(IENUM):
        COMMON = "COMMON"

        class E_COMMON(IENUM):
            REQUEST_CONSUMER = "REQUEST_CONSUMER"
            E_REQUEST_CONSUMER = (
                REQUEST_CONSUMER,
                lambda _app_name, _process_name: RequestConsumerProcess(
                    _app_name, _process_name
                ),
            )
            NOTIFIER = "NOTIFIER"
            E_NOTIFIER = (
                NOTIFIER,
                lambda _app_name, _process_name: NotifierProcess(
                    _app_name, _process_name
                ),
            )
