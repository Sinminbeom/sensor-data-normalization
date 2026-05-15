# sensor-data-normalization

PCAP 기반 센서 데이터 정규화 파이프라인. python-library를 의존성으로 사용하며,
[sensor-data-replayer](https://github.com/Sinminbeom/sensor-data-replayer) 와 동일한
코드 스타일(Python 3.11+, uv + hatchling, src layout, `MultiProcessManagerAppFromCate`
패턴)을 따른다.

## 빌드 / 실행

```sh
uv sync
uv run python src/normalizer_app.py \
    --build-num <build> \
    --date <YYYYMMDD> \
    --vehicle-id <VEHICLE-NNN> \
    --process-size <N>
```

`--process-size`를 생략하면 `conf/application.conf` 의 `[NORMALIZER].WORKER_COUNT` 값을 사용한다.

## 디렉토리 구조

```
sensor-data-normalization/
├── conf/
│   ├── application.conf
│   └── logging.conf
├── src/
│   ├── normalizer_app.py                # 진입점
│   ├── app/
│   │   ├── app_object.py                # IApp / abApp / MultiProcessManagerApp[FromCate]
│   │   └── normalizer/
│   │       ├── queue/
│   │       │   ├── pair_buckets.py      # HEAD/TAIL 쌍 누적 (jobQueue는 python_library가 자동 결선)
│   │       │   └── module_status.py     # 모듈 종료 추적 (매니저가 polling)
│   │       └── process/
│   │           ├── manager/manager.py   # NormalizerManager (QueueProcessing, 파일 수집·잔여 sweep)
│   │           └── module/module.py     # NormalizerModule (QueueProcessing, 다운로드/분할/업로드)
│   ├── process_category/
│   │   ├── enum_category.py             # E_CATE.NORMALIZER
│   │   └── process_category.py          # register_normalizer (워커 N 동적 push)
│   ├── sensor_category/
│   │   ├── enum_sensor.py               # E_SENSOR_TYPE, E_LIDAR, E_CAMERA, E_GNSS
│   │   ├── sensor.py                    # 센서 타입별 모듈 목록 (mutable)
│   │   ├── sensor_args.py               # @dataclass(frozen=True) SensorArgs
│   │   └── sensor_registry.py           # SensorRegistry 싱글톤 (모듈명 → SensorArgs)
│   ├── config/
│   │   └── project_config.py            # ProjectConfig (AppConfig 상속)
│   ├── pcap/
│   │   ├── packet_position.py           # E_PACKET_POSITION (HEAD/MID/TAIL)
│   │   ├── splitter.py                  # IPcapSplitter / SplitedPcap / SplitOutcome
│   │   └── unprocessed_pcap.py          # @dataclass(frozen=True) UnprocessedPcap
│   ├── storage/
│   │   └── storage_object_property.py   # @dataclass(frozen=True) StorageObjectProperty
│   └── utils/                           # collection_utils, pcap_filename_parser
└── pyproject.toml
```

## 데이터 흐름

1. `main()` → argv 파싱 → `NormalizerManager.configure(build_num, date, vehicle_id)` (ClassVar)
2. `ProjectConfig.set_config()` + `logging.fileConfig()` → `ProcessCategory.register_category()` 가
   매니저 1 + 모듈 N 카테고리 등록
3. `Normalizer(MultiProcessManagerAppFromCate)` 의 `MultiProcessManager` 가 shared_job_queue
   와 모듈별 shared_queue 를 alloc, 자식 프로세스 append 시 자동 결선
4. `NormalizerManager.on_init()` (별도 프로세스):
   - storage connect, SensorRegistry 등록
   - 입력 캐시에서 파일 목록 수집 → `push_shared_job_queue(file)` 로 jobQueue 적재
5. `NormalizerModule.action()` (모듈 N개, `QueueProcessing` 루프):
   - `ModuleStatusTracker.register(name)` (on_init 1회)
   - `pop_shared_job_queue()` → 파일 1개 → 다운로드 → 1초 split
   - MID 패킷은 즉시 업로드, HEAD/TAIL은 `PairBuckets.put(pair_key, item)` (짝 도달 시 자동 merge & upload)
   - jobQueue 비면 `ModuleStatusTracker.mark_finished(name)` + `stop()`
6. `NormalizerManager.action()`:
   - `ModuleStatusTracker.all_finished(expected_count)` polling
   - 모든 모듈 종료되면 `PairBuckets.pop_all_remaining()` 잔여 sweep → 업로드 → disconnect → stop

## 차량 식별자 명명 규칙

차량 식별자는 `VEHICLE-NNN`(예: `VEHICLE-001`) 형식. 외부 입력(`--vehicle-id`,
S3 객체 경로 등)에서 이 형식을 기대한다. 코드 안에 하드코딩된 차량 식별자는
존재하지 않는다.

## 스토리지 백엔드

본 Task 범위에서는 스토리지 추상화(`python_library.storage.IStorage`)만 결선되어
있고, 구체 구현(LocalStorage / S3) 결선은 후속 작업으로 분리. `Normalizer` 와
`NormalizerWorker` 의 `_build_storage()` 가 현재 `NotImplementedError` 를 던지는
이유다.

## 동시성 모델

multi-process 채택. 벤치마크(`scripts/bench_io_vs_cpu.py`) 결과 합성 IO+CPU 워크로드에서
process가 thread 대비 모든 worker count(1/2/4/8)에서 동등 또는 우세 (Python 표준
파일 IO가 의외로 GIL-bound이기 때문). 워커 결선·종료는 `python_library.MultiProcessManager`
의 자동 결선(`set_shared_job_queue` / `set_shared_queue` / `join`)을 그대로 사용.

## swm 원본과의 매핑

각 파일 상단의 모듈 docstring에 swm 원본 파일·심볼 매핑이 명시되어 있다.
주요 매핑 요약:

| swm 원본 | 신규 |
| --- | --- |
| `sensor-data-normalization.py` | `src/normalizer_app.py` (얇은 `Normalizer` wrapper) |
| `pcapNormalization/replayerPreProcesser.py` | `src/app/normalizer/process/manager/manager.py` (`QueueProcessing` 상속) |
| `pcapNormalization/storageHandler.py` | `src/app/normalizer/process/module/module.py` (`QueueProcessing` 상속) |
| `App/cPairQueueMultiProcessor.py` 의 jobQueue | `python_library.MultiProcessManager.shared_job_queue` (자동 결선) |
| `App/cPairQueueMultiProcessor.py` 의 pairQueue | `src/app/normalizer/queue/pair_buckets.py` |
| swm 의 `eSubProcessStatus` 통보 | `src/app/normalizer/queue/module_status.py` |
| `App/Category/eSensor.py` (enum) | `src/sensor_category/enum_sensor.py` |
| `App/Category/eSensor.py::EC_SENSOR` (싱글톤) | `src/sensor_category/sensor_registry.py` |
| `App/Category/cSensorArgs.py` | `src/sensor_category/sensor_args.py` |
| `App/Category/cSensorDTO.py` | `src/sensor_category/sensor.py` |
| `App/cStorageObjectPropertyDTO.py` | `src/storage/storage_object_property.py` |
| `App/cUnProcessedPcapDTO.py` | `src/pcap/unprocessed_pcap.py` |
| `App/cDefine.py::ePacketPosition` | `src/pcap/packet_position.py::E_PACKET_POSITION` |
| `Configure/ConfigureManager` | `src/config/project_config.py` |
| `utils/Utils.py::Utils.GetSplitPcapFileName` | `src/utils/pcap_filename_parser.py::PcapFilenameParser.parse` |
