# sensor-data-normalization

PCAP 기반 센서 데이터 정규화 파이프라인.

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
│   │   └── normalizer/process/
│   │       ├── manager/manager.py       # NormalizerManager (QueueProcessing, 파일 수집·잔여 sweep)
│   │       └── module/module.py         # NormalizerModule (QueueProcessing, 다운로드/분할/업로드)
│   ├── common/process_state/
│   │   ├── pair_buckets.py              # HEAD/TAIL 쌍 누적 (cross-process 공유)
│   │   └── module_status.py             # 모듈 종료 추적 (cross-process 공유)
│   ├── process_category/
│   │   ├── enum_category.py             # E_CATE.NORMALIZER
│   │   └── process_category.py          # register_normalizer (워커 N 동적 push)
│   ├── sensor_category/
│   │   ├── enum_sensor.py               # E_SENSOR_TYPE, E_LIDAR, E_CAMERA, E_GNSS
│   │   └── sensor_registry.py           # SensorRegistry 싱글톤 (모듈명 → sensor_type)
│   ├── config/
│   │   └── project_config.py            # ProjectConfig (AppConfig 상속)
│   ├── pcap/                            # replayer src/pcaps/ 차용 + 응용 추가
│   │   ├── headers/{file_header,packet_header}.py     # 24B FileHeader / 16B PacketHeader (time_stamp)
│   │   ├── body/{ethernet,linux_sll*,ip_header,pcap_body*}.py  # protocol layer parse
│   │   ├── reader/{single,multi}.py     # PcapReader (file/packet header + body parse)
│   │   ├── {packet,pool,time_info,constants}.py
│   │   ├── packet_position.py           # E_PACKET_POSITION (HEAD/MID/TAIL)
│   │   ├── splitter.py                  # IPcapSplitter / SplitedPcap / SplitOutcome
│   │   ├── local_pcap_splitter.py       # LocalPcapSplitter (1초 split + merge, raw bytes 기반)
│   │   ├── pcap_filename_parser.py      # PcapFilenameParser (파일명 → module/date/hours/minutes)
│   │   └── unprocessed_pcap.py          # @dataclass(frozen=True) UnprocessedPcap
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

## 동시성 모델

multi-process 채택. 벤치마크(`scripts/bench_io_vs_cpu.py`) 결과 합성 IO+CPU 워크로드에서
process가 thread 대비 모든 worker count(1/2/4/8)에서 동등 또는 우세 (Python 표준
파일 IO가 의외로 GIL-bound이기 때문). 워커 결선·종료는 `python_library.MultiProcessManager`
의 자동 결선(`set_shared_job_queue` / `set_shared_queue` / `join`)을 그대로 사용.
