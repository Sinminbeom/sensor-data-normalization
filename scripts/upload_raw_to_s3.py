"""replayer 의 raw PCAP 을 normalization 이 기대하는 S3 구조로 업로드 (dev/test 용).

replayer 구조 (예):
    data/raw/vehicle-001/am20_front_center_right_down/20260513/full_115344.pcap

normalization 기대 S3 구조:
    s3://{bucket}/{prefix}/{date}/{VEHICLE_ID}/{MODULE_NAME}_{YYYYMMDDHHMMSS}.pcap

PcapFilenameParser 의 입력 형식은 `{MODULE_NAME}_{YYYYMMDDHHMM[SS]}.pcap` 이므로 본
스크립트가 파일명을 재변환 후 업로드한다.

사용:
    python scripts/upload_raw_to_s3.py \\
        --source /home/shinminbeom/infra_glue/personal/sensor-data-replayer/data/raw \\
        --bucket oncx-dev-common-assets-bucket \\
        --prefix test/raw \\
        [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import boto3

DEFAULT_SOURCE = "/home/shinminbeom/infra_glue/personal/sensor-data-replayer/data/raw"
DEFAULT_BUCKET = "oncx-dev-common-assets-bucket"
DEFAULT_PREFIX = "test/raw"


class RawUploader:
    """replayer raw 트리를 walk → 파일명 재변환 → S3 업로드."""

    HHMMSS_RE = re.compile(r"(\d{6})")

    def __init__(self, source: Path, bucket: str, prefix: str, dry_run: bool) -> None:
        self._source = source.resolve()
        self._bucket = bucket
        self._prefix = prefix.strip("/")
        self._dry_run = dry_run
        self._client = None if dry_run else boto3.client("s3")

    def run(self) -> int:
        if not self._source.is_dir():
            raise SystemExit(f"source directory not found: {self._source}")

        uploaded = 0
        for pcap in sorted(self._source.rglob("*.pcap")):
            rel = pcap.relative_to(self._source)
            mapping = self._derive_mapping(rel)
            if mapping is None:
                print(f"skip: {rel}", file=sys.stderr)
                continue

            s3_key = mapping
            print(f"{pcap}  →  s3://{self._bucket}/{s3_key}")
            if not self._dry_run:
                assert self._client is not None
                self._client.upload_file(str(pcap), self._bucket, s3_key)
            uploaded += 1

        return uploaded

    def _derive_mapping(self, rel: Path) -> str | None:
        # 예상 path: {vehicle}/{module}/{date}/{file}.pcap (4 segments)
        if len(rel.parts) != 4:
            return None
        vehicle, module_lower, date, fname = rel.parts

        match = RawUploader.HHMMSS_RE.search(fname)
        if not match:
            return None
        hhmmss = match.group(1)

        module_upper = module_lower.upper()
        vehicle_upper = vehicle.upper()
        new_name = f"{module_upper}_{date}{hhmmss}.pcap"
        return f"{self._prefix}/{date}/{vehicle_upper}/{new_name}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    uploader = RawUploader(
        source=Path(args.source),
        bucket=args.bucket,
        prefix=args.prefix,
        dry_run=args.dry_run,
    )
    count = uploader.run()
    prefix_tag = "(dry-run) " if args.dry_run else ""
    print(f"{prefix_tag}uploaded {count} file(s)")


if __name__ == "__main__":
    main()
