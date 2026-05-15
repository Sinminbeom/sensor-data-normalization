"""ProcessCategory — 카테고리 트리 등록.

원본 매핑 (swm → 신규):
- swm은 main에서 storageHandler N개를 AppendWithShardPairQueue로 직접 append.
- 신규는 sensor-data-replayer의 ProcessCategory 패턴을 따라 cate_queue 트리로 등록.
- 매니저 1 + 모듈 N 구성. 모듈 수(swm argv processSize)는 set_worker_count(N).
"""

from python_library.category.app_category import AppCategory
from python_library.category.category_action import CategoryAction
from python_library.category.category_component import ICategoryComponent
from python_library.category.category_group import CategoryGroup

from process_category.enum_category import E_CATE, E_CATE_META_ELE


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

    def get_process_list_category(self, *cate: str) -> list[tuple]:
        """E_CATE.NORMALIZER 같은 root 카테고리 키로부터 (name, lambda) 튜플 리스트 추출.

        MultiProcessManagerAppFromCate 가 lambda(_app_name, _process_name)으로 프로세스
        인스턴스를 만들 때 사용. 튜플 인덱스 [NAME=0, LAMBDA=1] 는 E_CATE_META_ELE 와 정렬.
        """
        if not cate:
            return []
        root = self.cate_queue.get(cate[0])
        if root is None:
            return []
        result: list[tuple] = []
        self._walk_actions(root, result)
        return result

    def _walk_actions(self, component: ICategoryComponent, result: list[tuple]) -> None:
        if not isinstance(component, CategoryGroup):
            return
        for name, child in component._children.items():
            if isinstance(child, CategoryAction):
                result.append((name, child.action))
            else:
                self._walk_actions(child, result)
