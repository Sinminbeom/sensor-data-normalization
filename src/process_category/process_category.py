"""ProcessCategory — 카테고리 트리 등록."""

from collections.abc import Callable

from python_library.category.app_category import AppCategory
from python_library.category.category_action import CategoryAction
from python_library.category.category_component import ICategoryComponent
from python_library.category.category_group import CategoryGroup
from python_library.process.queue_process import IQueueProcess

from process_category.enum_category import E_CATE, E_CATE_META_ELE

# (name, factory) — factory(app_name, process_name) → 워커/매니저 프로세스 인스턴스.
# E_CATE_META_ELE 의 [NAME=0, LAMBDA=1] 와 정렬.
CategoryEntry = tuple[str, Callable[[str, str], IQueueProcess]]


class ProcessCategory(AppCategory):
    DEFAULT_WORKER_COUNT = 1

    def __init__(self) -> None:
        super().__init__()
        self._worker_count = ProcessCategory.DEFAULT_WORKER_COUNT

    def set_worker_count(self, worker_count: int) -> None:
        self._worker_count = max(1, worker_count)

    def register_category(self) -> None:
        self.cate_reg_queue[E_CATE.NORMALIZER] = lambda: self.register_normalizer()

    def register_normalizer(self) -> None:
        normalizer = CategoryGroup()

        common = CategoryGroup()
        common.push(
            E_CATE.E_NORMALIZER.E_COMMON.E_NORMALIZER_MANAGER[E_CATE_META_ELE.NAME],
            CategoryAction(
                E_CATE.E_NORMALIZER.E_COMMON.E_NORMALIZER_MANAGER[
                    E_CATE_META_ELE.LAMBDA
                ]
            ),
        )

        module = CategoryGroup()
        base = E_CATE.E_NORMALIZER.E_MODULE.E_NORMALIZER_MODULE[E_CATE_META_ELE.NAME]
        for idx in range(self._worker_count):
            module.push(
                f"{base}_{idx}",
                CategoryAction(
                    E_CATE.E_NORMALIZER.E_MODULE.E_NORMALIZER_MODULE[
                        E_CATE_META_ELE.LAMBDA
                    ]
                ),
            )

        normalizer.push(E_CATE.E_NORMALIZER.COMMON, common)
        normalizer.push(E_CATE.E_NORMALIZER.MODULE, module)
        self.cate_queue[E_CATE.NORMALIZER] = normalizer

    def get_process_list_category(self, *cate: str) -> list[CategoryEntry]:
        """E_CATE.NORMALIZER 같은 root 카테고리 키로부터 (name, factory) 튜플 리스트 추출.

        MultiProcessManagerAppFromCate 가 factory(_app_name, _process_name)으로 프로세스
        인스턴스를 만들 때 사용. 튜플 인덱스 [NAME=0, LAMBDA=1] 는 E_CATE_META_ELE 와 정렬.
        """
        if not cate:
            return []
        root = self.cate_queue.get(cate[0])
        if root is None:
            return []
        result: list[CategoryEntry] = []
        self._walk_actions(root, result)
        return result

    def _walk_actions(
        self, component: ICategoryComponent, result: list[CategoryEntry]
    ) -> None:
        if not isinstance(component, CategoryGroup):
            return
        for name, child in component._children.items():
            if isinstance(child, CategoryAction):
                result.append((name, child.action))
            else:
                self._walk_actions(child, result)
