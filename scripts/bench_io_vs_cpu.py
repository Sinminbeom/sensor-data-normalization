"""Thread vs Process 벤치마크 (정규화 파이프라인 워크로드 합성판).

워커 단위 작업(swm storageHandler 한 사이클 흉내):
  1) 입력 파일 read (디스크 IO)
  2) bytes scan / xor 누적 (PCAP parse + position 분류 흉내, CPU)
  3) split write 3개 (디스크 IO)
  4) network sleep (다운로드/업로드 latency 흉내)
  5) upload write 3개 (디스크 IO)
  6) merge: split 결과 2개 read + concat + write (디스크 IO + CPU)

매트릭스: WORKER_COUNT × MODE(thread|process). 각 셀에서 전체 wallclock 측정.

표준 라이브러리만 사용 (의존성 없음). 본 스크립트는 일회성 측정용이며
프로젝트 코드에 import 되지 않는다.
"""

from __future__ import annotations

import argparse
import multiprocessing
import os
import queue as stdqueue
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BenchConfig:
    file_count: int = 32
    file_size_mb: int = 16
    network_sleep_ms: int = 50  # ↑ 일수록 IO 비중 ↑ (다운로드/업로드 latency 흉내)
    cpu_passes: int = 1  # ↑ 일수록 CPU 비중 ↑ (전체 파일을 몇 번 훑을지)


def prepare_files(base_dir: Path, cfg: BenchConfig) -> list[Path]:
    src_dir = base_dir / "in"
    src_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    payload = os.urandom(cfg.file_size_mb * 1024 * 1024)
    for i in range(cfg.file_count):
        p = src_dir / f"pcap_{i:04d}.bin"
        p.write_bytes(payload)
        paths.append(p)
    return paths


def process_one_file(
    src_path: Path, work_dir: Path, worker_id: str, cfg: BenchConfig
) -> None:
    """워커 1회 작업 — IO 70~80% + CPU 20~30% 가정의 합성 워크로드."""
    out_dir = work_dir / worker_id
    out_dir.mkdir(parents=True, exist_ok=True)

    data = src_path.read_bytes()

    # 고정 stride(4KB)로 sample. cpu_passes 만큼 반복 → 값이 클수록 CPU 비중 ↑.
    checksum = 0
    sample_stride = 4096
    for _ in range(cfg.cpu_passes):
        for i in range(0, len(data), sample_stride):
            checksum ^= data[i]

    split_files: list[Path] = []
    third = len(data) // 3
    for i, chunk in enumerate(
        (data[:third], data[third : 2 * third], data[2 * third :])
    ):
        p = out_dir / f"{src_path.stem}_split_{i}.bin"
        p.write_bytes(chunk)
        split_files.append(p)

    time.sleep(cfg.network_sleep_ms / 1000.0)

    for sp in split_files:
        up = out_dir / f"{sp.stem}.upload"
        up.write_bytes(sp.read_bytes())

    merge_data = b"".join(sp.read_bytes() for sp in split_files[:2])
    merge_out = out_dir / f"{src_path.stem}_merged.bin"
    merge_out.write_bytes(merge_data)

    _ = checksum


def thread_worker(
    job_q: stdqueue.Queue, work_dir: Path, worker_id: str, cfg: BenchConfig
) -> None:
    while True:
        try:
            path = job_q.get_nowait()
        except stdqueue.Empty:
            return
        process_one_file(path, work_dir, worker_id, cfg)


def process_worker(
    job_q: multiprocessing.Queue, work_dir: str, worker_id: str, cfg: BenchConfig
) -> None:
    work = Path(work_dir)
    while True:
        try:
            path_str = job_q.get_nowait()
        except Exception:
            return
        process_one_file(Path(path_str), work, worker_id, cfg)


def run_threads(files: list[Path], work_dir: Path, worker_count: int, cfg: BenchConfig) -> float:
    job_q: stdqueue.Queue = stdqueue.Queue()
    for p in files:
        job_q.put(p)

    threads = [
        threading.Thread(
            target=thread_worker,
            args=(job_q, work_dir, f"t{i}", cfg),
            daemon=True,
        )
        for i in range(worker_count)
    ]

    start = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return time.perf_counter() - start


def run_processes(files: list[Path], work_dir: Path, worker_count: int, cfg: BenchConfig) -> float:
    ctx = multiprocessing.get_context("fork")
    job_q: multiprocessing.Queue = ctx.Queue()
    for p in files:
        job_q.put(str(p))

    procs = [
        ctx.Process(
            target=process_worker,
            args=(job_q, str(work_dir), f"p{i}", cfg),
            daemon=True,
        )
        for i in range(worker_count)
    ]

    start = time.perf_counter()
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    return time.perf_counter() - start


class BenchRunner:
    @staticmethod
    def run(cfg: BenchConfig, worker_counts: list[int]) -> None:
        print(
            f"config: files={cfg.file_count}, size={cfg.file_size_mb}MB, "
            f"sleep={cfg.network_sleep_ms}ms, cpu_passes={cfg.cpu_passes}"
        )
        print()
        print(f"{'workers':>8} | {'thread (s)':>11} | {'process (s)':>12} | {'thread tput':>12} | {'process tput':>13}")
        print("-" * 72)

        with tempfile.TemporaryDirectory(prefix="bench_io_") as base:
            base_dir = Path(base)
            files = prepare_files(base_dir, cfg)

            for wc in worker_counts:
                t_work = base_dir / f"thread_w{wc}"
                p_work = base_dir / f"process_w{wc}"
                t_work.mkdir(exist_ok=True)
                p_work.mkdir(exist_ok=True)

                t_elapsed = run_threads(files, t_work, wc, cfg)
                shutil.rmtree(t_work, ignore_errors=True)
                t_work.mkdir()

                p_elapsed = run_processes(files, p_work, wc, cfg)
                shutil.rmtree(p_work, ignore_errors=True)

                t_tput = cfg.file_count / t_elapsed
                p_tput = cfg.file_count / p_elapsed
                print(
                    f"{wc:>8} | {t_elapsed:>11.2f} | {p_elapsed:>12.2f} | "
                    f"{t_tput:>10.2f}/s | {p_tput:>11.2f}/s"
                )


def main() -> None:
    parser = argparse.ArgumentParser(description="thread vs process bench")
    parser.add_argument("--files", type=int, default=32)
    parser.add_argument("--size-mb", type=int, default=16)
    parser.add_argument("--sleep-ms", type=int, default=50)
    parser.add_argument("--cpu-passes", type=int, default=1)
    parser.add_argument("--workers", type=str, default="1,2,4,8")
    args = parser.parse_args()

    cfg = BenchConfig(
        file_count=args.files,
        file_size_mb=args.size_mb,
        network_sleep_ms=args.sleep_ms,
        cpu_passes=args.cpu_passes,
    )
    worker_counts = [int(x) for x in args.workers.split(",")]
    BenchRunner.run(cfg, worker_counts)


if __name__ == "__main__":
    main()
