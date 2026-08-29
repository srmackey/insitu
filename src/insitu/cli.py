"""Command-line entry.

    insitu [--vault PATH]                  start the MCP server (default)
    insitu serve [--vault PATH]            the same, named
    insitu init --admin KEY [--vault PATH] register the first admin
    insitu operators [--vault PATH]        show the operator config

The bare invocation must keep starting the server: every host MCP config
calls this command with no arguments. The subcommand is therefore
optional, and `serve` is what a missing one means.

`init` is command-line only on purpose. It is not an MCP tool, so an
agent cannot register itself as admin mid-session.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


VAULT_HELP = "Vault root. Used when INSITU_HOME is unset. Default: ~/.insitu."


def _sub_vault_parser() -> argparse.ArgumentParser:
    """`--vault` for subcommands, kept on its own dest.

    A separate dest rather than SUPPRESS on a shared action: the two
    positions then never fight over one namespace slot, whatever a given
    Python version does when it merges the subparser namespace.
    """
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--vault", dest="sub_vault", default=None, help=VAULT_HELP)
    return parent


def build_parser() -> argparse.ArgumentParser:
    sub_vault = _sub_vault_parser()
    parser = argparse.ArgumentParser(
        prog="insitu",
        description="Insitu MCP server: situated identity for agents.",
    )
    parser.add_argument("--vault", dest="vault", default=None, help=VAULT_HELP)
    sub = parser.add_subparsers(dest="command")

    sub.add_parser(
        "serve", help="Start the MCP server (default).", parents=[sub_vault]
    )

    init = sub.add_parser(
        "init",
        help="Register the first admin operator. Refuses if one already exists.",
        parents=[sub_vault],
    )
    init.add_argument(
        "--admin",
        required=True,
        metavar="KEY",
        help="Project key (working folder basename) to register as admin.",
    )

    sub.add_parser(
        "operators",
        help="Show the operator config: classes, admins, default.",
        parents=[sub_vault],
    )

    parser.set_defaults(sub_vault=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    chosen = getattr(args, "sub_vault", None) or args.vault
    cli_vault = Path(chosen) if chosen else None
    command = getattr(args, "command", None) or "serve"

    if command == "serve":
        from insitu.server import run

        run(cli_vault=cli_vault)
        return 0

    from insitu.operators import init_admin, operator_status
    from insitu.vault import resolve_vault_root

    root = resolve_vault_root(cli_vault=cli_vault)
    result = init_admin(root, args.admin) if command == "init" else operator_status(root)

    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
