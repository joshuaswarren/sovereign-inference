# SPDX-License-Identifier: AGPL-3.0-or-later
"""The ``sin`` command-line interface for the Sovereign Inference Node.

A thin, transparent wrapper over the :mod:`sin_node` library. Each subcommand
maps to one library call and renders the result either as a rich human view or
as machine-readable JSON (``--json``). External work (hardware scan, model pull,
serving, benchmarking) is delegated to the library so the CLI stays testable:
the heavy callables are referenced via module-level names that tests monkeypatch.

Subcommands::

    sin scan       [--json]
    sin recommend  --task TASK [--commercial] [--top N] [--json]
    sin catalog    [--json]
    sin serve      --runtime {ollama,llama.cpp} --model NAME [--port P] [--ctx C]
    sin install    --runtime ollama --model NAME
    sin benchmark  --base-url URL --model NAME [--runtime R] [--publish KEYFILE]
    sin status
    sin version
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

# Importing the runtime adapter packages registers their adapters with
# sin_node.adapter (import side effect) so ``get_adapter`` can build them by name.
import sip_runtime_llamacpp  # noqa: F401
import sip_runtime_ollama  # noqa: F401
from rich.console import Console
from rich.table import Table

from sin_node import catalog, hardware, recommend
from sin_node.adapter import available_adapter_names, get_adapter
from sin_node.benchmark import benchmark_endpoint, to_provider_manifest

from . import __version__

# A non-interactive console: errors go to stderr, normal output to stdout.
_out = Console()
_err = Console(stderr=True)


def _print_json(payload: Any) -> None:
    """Emit ``payload`` as indented JSON on stdout (plain, never styled)."""
    print(json.dumps(payload, indent=2))


def _positive_int(value: str) -> int:
    """argparse type: a positive integer (mirrors the API's ``ge=1`` contract)."""
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError(f"must be a positive integer, got {value}")
    return parsed


# --------------------------------------------------------------------- scan


def cmd_scan(args: argparse.Namespace) -> int:
    profile = hardware.scan()
    if args.json:
        _print_json(profile.model_dump(mode="json"))
    else:
        _out.print(hardware.render(profile))
    return 0


# ----------------------------------------------------------------- recommend


def cmd_recommend(args: argparse.Namespace) -> int:
    profile = hardware.scan()
    recommendations = recommend.recommend(
        profile,
        args.task,
        commercial_required=args.commercial,
        top_k=args.top,
    )
    if args.json:
        _print_json([r.model_dump(mode="json") for r in recommendations])
        return 0
    if not recommendations:
        _out.print(f"No catalog models serve the task {args.task!r}.")
        return 0
    table = Table(title=f"Recommendations for {args.task!r}")
    table.add_column("Model")
    table.add_column("Runtime")
    table.add_column("Quant")
    table.add_column("Ctx", justify="right")
    table.add_column("Fits")
    table.add_column("~tok/s", justify="right")
    table.add_column("Why")
    for rec in recommendations:
        tps = "?" if rec.predicted_tps is None else f"{rec.predicted_tps:.0f}"
        table.add_row(
            rec.display_name,
            rec.runtime,
            rec.quant,
            str(rec.context),
            "yes" if rec.fits else "no",
            tps,
            rec.why,
        )
    _out.print(table)
    return 0


# ------------------------------------------------------------------- catalog


def cmd_catalog(args: argparse.Namespace) -> int:
    models = catalog.load_catalog()
    if args.json:
        _print_json([m.model_dump(mode="json") for m in models])
        return 0
    table = Table(title="Model catalog")
    table.add_column("Model id")
    table.add_column("Name")
    table.add_column("Params (B)", justify="right")
    table.add_column("Tasks")
    table.add_column("License")
    for model in models:
        table.add_row(
            model.model_id,
            model.display_name,
            f"{model.params_b:g}",
            ", ".join(model.tasks),
            model.license,
        )
    _out.print(table)
    return 0


# --------------------------------------------------------------------- serve


def cmd_serve(args: argparse.Namespace) -> int:
    try:
        adapter = get_adapter(args.runtime)
        handle = adapter.serve(args.model, port=args.port, ctx_size=args.ctx)
    except Exception as exc:  # surface any adapter failure as exit 1
        _err.print(f"[red]serve failed:[/red] {exc}")
        return 1
    _out.print(handle.base_url)
    return 0


# --------------------------------------------------------------------- share


def cmd_share(args: argparse.Namespace) -> int:
    from sip_discovery import FileDirectory
    from sip_gateway import serve
    from sip_protocol import KeyPair

    from .share import ShareConfig, announce_to_directory, build_share

    try:
        adapter = get_adapter(args.runtime)
    except Exception as exc:  # surface any adapter resolution failure as exit 1
        _err.print(f"[red]unknown runtime:[/red] {exc}")
        return 1

    if args.key_file:
        try:
            keypair = _load_keypair(args.key_file)
        except (OSError, ValueError) as exc:
            _err.print(f"[red]key load failed:[/red] {exc}")
            return 1
    else:
        keypair = KeyPair.generate()
        _err.print("[yellow]no --key-file: generated an ephemeral identity (it changes on restart).[/yellow]")

    config = ShareConfig(
        model=args.model,
        runtime=args.runtime,
        host=args.host,
        port=args.port,
        advertised_url=args.advertised_url,
        token=args.token,
        max_output_tokens=args.max_output_tokens,
        rate_limit_per_minute=args.rate_limit,
        pricing_unit=args.unit,
        input_per_1m=args.input_per_1m,
        output_per_1m=args.output_per_1m,
        require_payment=args.require_payment,
        pic_issuers=tuple(args.pic_issuer or ()),
    )
    result = build_share(config, keypair=keypair, adapter=adapter)

    if args.manifest_out:
        Path(args.manifest_out).write_text(json.dumps(result.manifest, indent=2), encoding="utf-8")
    if args.directory:
        announce_to_directory(FileDirectory(args.directory), result)

    _out.print(f"provider:   {keypair.public_key_str}")
    _out.print(f"serving:    {args.model} via {args.runtime}")
    _out.print(f"advertised: {result.base_url}")
    if args.directory:
        _out.print(f"announced:  {args.directory}")
    if args.no_serve:
        return 0
    _out.print(f"listening on http://{args.host}:{args.port}  (Ctrl-C to stop)")
    serve(result.app, host=args.host, port=args.port)  # pragma: no cover - blocks on the event loop
    return 0


# ------------------------------------------------------------------- install


def cmd_install(args: argparse.Namespace) -> int:
    try:
        adapter = get_adapter(args.runtime)
        adapter.pull(args.model)
    except Exception as exc:  # surface any adapter failure as exit 1
        _err.print(f"[red]install failed:[/red] {exc}")
        return 1
    _out.print(f"Installed {args.model!r} via {args.runtime}.")
    return 0


# ----------------------------------------------------------------- benchmark


def _load_keypair(key_file: str) -> Any:
    """Load an Ed25519 key pair from a ``sip-receipt keygen`` JSON file."""
    from sip_protocol import KeyPair

    data = json.loads(Path(key_file).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "private_key" not in data:
        raise ValueError(f"no 'private_key' field in key file {key_file!r}")
    return KeyPair.from_private_str(data["private_key"])


def cmd_benchmark(args: argparse.Namespace) -> int:
    try:
        result = benchmark_endpoint(args.base_url, args.model, runtime=args.runtime)
    except Exception as exc:  # surface any benchmark failure as exit 1
        _err.print(f"[red]benchmark failed:[/red] {exc}")
        return 1

    if not args.publish:
        _print_json(result.model_dump(mode="json"))
        return 0

    try:
        keypair = _load_keypair(args.publish)
        profile = hardware.scan()
        manifest = to_provider_manifest(
            profile,
            models=[args.model],
            result=result,
            pricing={"unit": "test"},
            privacy_modes=["direct"],
            keypair=keypair,
            published_at=result.measured_at or _now_iso(),
        )
    except Exception as exc:  # surface any publishing failure as exit 1
        _err.print(f"[red]publish failed:[/red] {exc}")
        return 1
    _print_json(manifest)
    return 0


def _now_iso() -> str:
    """Current UTC time as an ISO-8601 string ending in ``Z``."""
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


# -------------------------------------------------------------------- status


def cmd_status(_: argparse.Namespace) -> int:
    table = Table(title="Sovereign Inference Node")
    table.add_column("Component")
    table.add_column("Value")
    table.add_row("sin-cli version", __version__)
    table.add_row("registered adapters", ", ".join(available_adapter_names()) or "none")
    _out.print(table)
    return 0


# ------------------------------------------------------------------- version


def cmd_version(_: argparse.Namespace) -> int:
    print(f"sin {__version__}")
    return 0


# --------------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sin",
        description="Sovereign Inference Node — scan hardware, recommend, serve, and benchmark local models.",
    )
    parser.add_argument("--version", action="version", version=f"sin {__version__}")
    sub = parser.add_subparsers(dest="command")

    p_scan = sub.add_parser("scan", help="detect this machine's hardware and runtimes")
    p_scan.add_argument("--json", action="store_true", help="emit the hardware profile as JSON")
    p_scan.set_defaults(func=cmd_scan)

    p_rec = sub.add_parser("recommend", help="recommend model/runtime/quant combinations for a task")
    p_rec.add_argument("--task", required=True, help="task to optimize for, e.g. coding, chat, embeddings")
    p_rec.add_argument("--commercial", action="store_true", help="require a commercial-use license")
    p_rec.add_argument("--top", type=_positive_int, default=3, help="maximum number of recommendations (default 3)")
    p_rec.add_argument("--json", action="store_true", help="emit recommendations as JSON")
    p_rec.set_defaults(func=cmd_recommend)

    p_cat = sub.add_parser("catalog", help="list the bundled model catalog")
    p_cat.add_argument("--json", action="store_true", help="emit the catalog as JSON")
    p_cat.set_defaults(func=cmd_catalog)

    p_serve = sub.add_parser("serve", help="start a local OpenAI-compatible server for a model")
    p_serve.add_argument("--runtime", required=True, choices=("ollama", "llama.cpp"), help="runtime adapter to use")
    p_serve.add_argument("--model", required=True, help="model name (ollama) or local GGUF path (llama.cpp)")
    p_serve.add_argument("--port", type=int, default=8080, help="port to bind the server (default 8080)")
    p_serve.add_argument("--ctx", type=int, default=4096, help="context window size (default 4096)")
    p_serve.set_defaults(func=cmd_serve)

    p_share = sub.add_parser("share", help="expose this node's model as a discoverable, signed SIP provider")
    p_share.add_argument("--runtime", default="ollama", choices=("ollama", "llama.cpp"), help="runtime adapter")
    p_share.add_argument("--model", required=True, help="model alias to serve and advertise")
    p_share.add_argument("--host", default="127.0.0.1", help="bind host (default 127.0.0.1)")
    p_share.add_argument("--port", type=int, default=8090, help="bind port (default 8090)")
    p_share.add_argument("--advertised-url", help="public URL to announce (default http://HOST:PORT)")
    p_share.add_argument("--token", help="bearer token required of callers (default: open)")
    p_share.add_argument("--max-output-tokens", type=_positive_int, default=512, help="cap output tokens per request")
    p_share.add_argument("--rate-limit", type=int, default=60, help="max requests/minute (default 60)")
    p_share.add_argument("--unit", default="usdc", help="pricing unit advertised (default usdc)")
    p_share.add_argument("--input-per-1m", type=float, default=0.0, help="price per 1M input tokens")
    p_share.add_argument("--output-per-1m", type=float, default=0.0, help="price per 1M output tokens")
    p_share.add_argument("--require-payment", action="store_true", help="require PIC payment for completions")
    p_share.add_argument("--pic-issuer", action="append", help="accepted PIC issuer pubkey (repeatable)")
    p_share.add_argument("--key-file", help="sip-receipt keygen JSON for a stable provider identity")
    p_share.add_argument("--manifest-out", help="write the signed provider manifest to this path")
    p_share.add_argument("--directory", help="announce the manifest to this directory file")
    p_share.add_argument("--no-serve", action="store_true", help="publish/announce only; do not start the server")
    p_share.set_defaults(func=cmd_share)

    p_install = sub.add_parser("install", help="fetch a model via a runtime's pull command")
    p_install.add_argument("--runtime", required=True, choices=("ollama",), help="runtime to pull with")
    p_install.add_argument("--model", required=True, help="model name to pull")
    p_install.set_defaults(func=cmd_install)

    p_bench = sub.add_parser("benchmark", help="benchmark a served endpoint and optionally publish a manifest")
    p_bench.add_argument("--base-url", required=True, help="base URL of the served endpoint")
    p_bench.add_argument("--model", required=True, help="model alias to benchmark")
    p_bench.add_argument("--runtime", default="unknown", help="runtime label to record (default 'unknown')")
    p_bench.add_argument(
        "--publish",
        metavar="KEYFILE",
        help="sign and print a provider manifest using the key pair in this sip-receipt keygen JSON file",
    )
    p_bench.set_defaults(func=cmd_benchmark)

    p_status = sub.add_parser("status", help="show node version and registered runtime adapters")
    p_status.set_defaults(func=cmd_status)

    p_version = sub.add_parser("version", help="print the sin-cli version")
    p_version.set_defaults(func=cmd_version)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 2
    result: int = func(args)
    return result


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
