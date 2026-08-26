"""Command-line entry: uv run insitu [--vault PATH]."""

from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="insitu",
        description="Insitu MCP server: situated identity for agents.",
    )
    parser.add_argument(
        "--vault",
        default=None,
        help="Vault root. Used when INSITU_HOME is unset. Default: ~/.insitu.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    from insitu.server import run

    vault: Path | None = Path(args.vault) if args.vault else None
    run(cli_vault=vault)


if __name__ == "__main__":
    main()
