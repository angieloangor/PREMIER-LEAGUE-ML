from __future__ import annotations

import argparse

from src.dataops import build_data_artifacts


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description="Build processed data artifacts and DataOps documentation.")


def main() -> None:
    build_parser().parse_args()
    results = build_data_artifacts()
    print("Processed data artifacts generated.")
    print(f"- matches_prepared rows: {results['matches'].shape[0]}")
    print(f"- shots_enriched rows: {results['shots'].shape[0]}")
    print(f"- match_features rows: {results['match_features'].shape[0]}")
    print(f"- manifest: {results['docs']['manifest_json']}")


if __name__ == "__main__":
    main()
