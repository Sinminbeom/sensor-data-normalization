"""sensor-data-normalization 진입점."""

from python_library.process.multi_process_manager import MultiProcessManager

from app.normalizer.process.manager.manager import NormalizerManager
from app.normalizer.process.module.module import NormalizerModule
from config.project_config import ProjectConfig


def main() -> None:
    ProjectConfig.set_config(ProjectConfig.DEFAULT_CONFIG_PATH)
    config = ProjectConfig.instance()

    multi_process_manager = MultiProcessManager()
    multi_process_manager.append(NormalizerManager())
    for idx in range(config.worker_count):
        multi_process_manager.append(NormalizerModule(idx))

    # run() = 자식 프로세스 spawn + join 대기 (main thread 안에서 sync 실행).
    multi_process_manager.run()


if __name__ == "__main__":
    main()
