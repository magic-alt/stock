"""
Download Qlib dataset via built-in helper.
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download Qlib dataset.")
    parser.add_argument("--target-dir", required=True, help="Target directory for qlib data")
    parser.add_argument("--name", default="qlib_data", help="Dataset name: qlib_data or qlib_data_simple")
    parser.add_argument("--region", default="cn", help="Region: cn/us")
    parser.add_argument("--interval", default="1d", help="Interval: 1d or 1min")
    parser.add_argument("--version", default=None, help="Dataset version (e.g., v2)")
    parser.add_argument("--exists-skip", action="store_true", help="Skip if data already exists")
    return parser.parse_args()


def main() -> None:
    try:
        from qlib.tests.data import GetData
    except Exception as exc:
        raise ImportError("Qlib is required to download datasets. Install pyqlib first.") from exc

    args = parse_args()
    getter = GetData(delete_zip_file=True)
    getter.qlib_data(
        name=args.name,
        target_dir=args.target_dir,
        version=args.version,
        interval=args.interval,
        region=args.region,
        delete_old=True,
        exists_skip=args.exists_skip,
    )


if __name__ == "__main__":
    main()
