from __future__ import annotations

import argparse

import uvicorn

from api.config import get_settings


def build_parser() -> argparse.ArgumentParser:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Run the FastAPI serving layer.")
    parser.add_argument("--host", default=settings.default_host, help="Bind host for the API server.")
    parser.add_argument("--port", type=int, default=settings.default_port, help="Bind port for the API server.")
    parser.add_argument("--reload", action="store_true", help="Enable autoreload for local development.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    uvicorn.run("api.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
