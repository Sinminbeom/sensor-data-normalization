"""앱 베이스 클래스."""

from abc import ABC, abstractmethod

from python_library.process.multi_process_manager import MultiProcessManager
from python_library.process.queue_process import IQueueProcess

from process_category.enum_category import E_CATE_META_ELE
from process_category.process_category import ProcessCategory


class IApp(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def init(self):
        pass

    @abstractmethod
    def on_run(self):
        pass

    def run(self):
        try:
            while True:
                self.on_run()
        except Exception as e:
            raise e


class abApp(IApp):
    def __init__(self):
        super().__init__()

    def init(self):
        pass

    def on_run(self):
        pass


class MultiProcessManagerApp(abApp):
    def __init__(self, app_name: str):
        super().__init__()
        self._app_name = app_name
        self._multi_process_manager = MultiProcessManager()

    def add_process(self, process: IQueueProcess) -> None:
        self._multi_process_manager.append(process)

    def get_multi_process_manager(self) -> MultiProcessManager:
        return self._multi_process_manager

    def get_app_name(self) -> str:
        return self._app_name

    def init(self):
        pass

    def on_run(self):
        pass


class MultiProcessManagerAppFromCate(MultiProcessManagerApp):
    def __init__(self, app_name: str, *_cate):
        category_list = ProcessCategory.instance().get_process_list_category(*_cate)
        super().__init__(app_name)
        self._append_process_category(category_list)

    def _append_process_category(self, category_list) -> None:
        for process_factory in category_list:
            self.add_process(
                process_factory[E_CATE_META_ELE.LAMBDA](
                    self.get_app_name(), process_factory[E_CATE_META_ELE.NAME]
                )
            )

    def init(self):
        pass

    def on_run(self):
        pass
