# SPDX-License-Identifier: Apache-2.0
"""Command-line interface for Sovereign Inference signed receipts.

    sip-receipt keygen                       # generate a provider key pair
    sip-receipt demo                         # emit a fully signed sample receipt
    sip-receipt sign receipt.json --key ...  # sign an unsigned receipt
    sip-receipt verify receipt.json          # verify a signed receipt (exit 0/1)

This is a real, dependency-light verifier — judges and users can confirm any
receipt against its provider public key without trusting our infrastructure.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sip_protocol import (
    KeyPair,
    build_receipt,
    hash_response_body,
    sign_receipt,
    verify_receipt,
)


def _load_json(path: str) -> Any:
    return json.loads(Path(path).read_text("utf-8"))


def _resolve_private_key(key_arg: str) -> KeyPair:
    """Accept either an ``ed25519:`` string or a path to a keygen JSON file."""
    if key_arg.startswith("ed25519:"):
        return KeyPair.from_private_str(key_arg)
    data = _load_json(key_arg)
    if isinstance(data, dict) and "private_key" in data:
        return KeyPair.from_private_str(data["private_key"])
    raise SystemExit(f"could not find a private key in {key_arg!r}")


def cmd_keygen(args: argparse.Namespace) -> int:
    kp = KeyPair.generate()
    payload = {"public_key": kp.public_key_str, "private_key": kp.private_key_str}
    text = json.dumps(payload, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", "utf-8")
        print(f"wrote key pair to {args.output}")
    else:
        print(text)
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    kp = KeyPair.generate()
    now = datetime.now(UTC)
    receipt = build_receipt(
        request_id="demo-request-0001",
        provider_pubkey=kp.public_key_str,
        model_manifest_hash="sha256:" + "0" * 64,
        model_alias="qwen-coder-7b-instruct-gguf-q4_k_m",
        runtime="llama.cpp",
        runtime_version="b3000",
        input_tokens=817,
        output_tokens=242,
        price_units="pic",
        price_amount="0.0042",
        privacy_mode="direct",
        started_at=now,
        completed_at=now,
        response_hash=hash_response_body("Here is a small parser..."),
    )
    signed = sign_receipt(receipt, kp)
    print(json.dumps(signed, indent=2))
    return 0


def cmd_sign(args: argparse.Namespace) -> int:
    receipt = _load_json(args.receipt)
    kp = _resolve_private_key(args.key)
    signed = sign_receipt(receipt, kp)
    text = json.dumps(signed, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", "utf-8")
        print(f"wrote signed receipt to {args.output}")
    else:
        print(text)
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    receipt = _load_json(args.receipt)
    result = verify_receipt(receipt)
    if result.valid:
        print(f"OK   receipt verified — provider {receipt.get('provider_pubkey')}")
        return 0
    print("FAIL receipt did not verify:", file=sys.stderr)
    for err in result.errors:
        print(f"  - {err}", file=sys.stderr)
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sip-receipt",
        description="Generate keys, sign, and verify Sovereign Inference signed receipts.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_keygen = sub.add_parser("keygen", help="generate an Ed25519 provider key pair")
    p_keygen.add_argument("-o", "--output", help="write key pair JSON to this file")
    p_keygen.set_defaults(func=cmd_keygen)

    p_demo = sub.add_parser("demo", help="emit a fully signed sample receipt")
    p_demo.set_defaults(func=cmd_demo)

    p_sign = sub.add_parser("sign", help="sign an unsigned receipt JSON file")
    p_sign.add_argument("receipt", help="path to the unsigned receipt JSON")
    p_sign.add_argument("--key", required=True, help="ed25519: private key, or a keygen JSON file path")
    p_sign.add_argument("-o", "--output", help="write the signed receipt to this file")
    p_sign.set_defaults(func=cmd_sign)

    p_verify = sub.add_parser("verify", help="verify a signed receipt JSON file")
    p_verify.add_argument("receipt", help="path to the signed receipt JSON")
    p_verify.set_defaults(func=cmd_verify)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
