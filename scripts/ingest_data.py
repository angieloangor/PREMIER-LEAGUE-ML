from __future__ import annotations

import argparse
from pathlib import Path

from src.data import download_base_datasets, existing_files_are_available


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate or download the raw project datasets.")
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Download the raw CSV files even if they are already present locally.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if existing_files_are_available() and not args.force_download:
        print("Raw datasets already available locally.")
        for path in sorted(Path("data").glob("*.csv")):
            print(f"- {path}")
        return

    print("Downloading raw datasets...")
    destinations = download_base_datasets(force=args.force_download)
    print("Raw dataset step completed.")
    for path in destinations:
        print(f"- {path}")


if __name__ == "__main__":
    main()
