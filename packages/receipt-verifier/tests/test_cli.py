# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path

import pytest

from sip_receipts.cli import main


def test_keygen_emits_keypair(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["keygen"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["public_key"].startswith("ed25519:")
    assert payload["private_key"].startswith("ed25519:")


def test_demo_then_verify_roundtrip(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["demo"]) == 0
    receipt_text = capsys.readouterr().out
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(receipt_text, "utf-8")

    assert main(["verify", str(receipt_path)]) == 0
    assert "OK" in capsys.readouterr().out


def test_sign_then_verify(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # keygen -> file
    key_path = tmp_path / "key.json"
    assert main(["keygen", "-o", str(key_path)]) == 0
    capsys.readouterr()
    public_key = json.loads(key_path.read_text())["public_key"]

    # an unsigned receipt referencing that provider key
    unsigned = {
        "receipt_version": "sip-ai.receipt.v1",
        "request_id": "req-xyz",
        "provider_pubkey": public_key,
        "model_manifest_hash": "sha256:" + "0" * 64,
        "model_alias": "test-model",
        "runtime": "llama.cpp",
        "input_tokens": 10,
        "output_tokens": 20,
        "price_units": "test",
        "price_amount": "0",
        "privacy_mode": "direct",
        "started_at": "2026-06-29T18:15:02Z",
        "completed_at": "2026-06-29T18:15:09Z",
        "response_hash": "sha256:" + "1" * 64,
    }
    receipt_path = tmp_path / "unsigned.json"
    receipt_path.write_text(json.dumps(unsigned), "utf-8")

    signed_path = tmp_path / "signed.json"
    assert main(["sign", str(receipt_path), "--key", str(key_path), "-o", str(signed_path)]) == 0
    capsys.readouterr()

    assert main(["verify", str(signed_path)]) == 0


def test_verify_fails_on_tampered_receipt(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["demo"]) == 0
    receipt = json.loads(capsys.readouterr().out)
    receipt["output_tokens"] = 1
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(json.dumps(receipt), "utf-8")

    assert main(["verify", str(bad_path)]) == 1
    assert "FAIL" in capsys.readouterr().err
