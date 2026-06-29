# SPDX-License-Identifier: Apache-2.0
from sip_protocol import (
    KeyPair,
    model_manifest_hash,
    sign_provider_manifest,
    validate_model_manifest,
    verify_provider_manifest,
)


def _model_manifest() -> dict:
    return {
        "schema": "sip-ai.model_manifest.v1",
        "model_id": "qwen-coder-7b-instruct-gguf-q4_k_m",
        "display_name": "Qwen Coder 7B Instruct GGUF Q4_K_M",
        "source_repo": "huggingface:example/repo",
        "weights_hash": "sha256:" + "cd" * 32,
        "format": "GGUF",
        "quantization": "Q4_K_M",
        "license": "apache-2.0",
        "recommended_runtimes": ["llama.cpp", "ollama"],
        "min_memory_gb": 8,
        "recommended_memory_gb": 16,
        "context_tested": [4096, 8192],
        "tasks": ["coding", "general-chat"],
    }


def _provider_manifest(pubkey: str) -> dict:
    return {
        "schema": "sip-ai.provider_manifest.v1",
        "provider_pubkey": pubkey,
        "node_type": "sovereign-node",
        "models": ["qwen-coder-7b-instruct-gguf-q4_k_m"],
        "runtime_adapters": ["llama.cpp"],
        "pricing": {"unit": "pic", "input_per_1m": 0.20, "output_per_1m": 0.80},
        "max_context": 8192,
        "max_concurrency": 2,
        "logging_policy": "no_prompt_logging",
        "retention_policy": "metrics_only_30d",
        "privacy_modes": ["direct", "relay", "private-payment"],
        "benchmark": {"tokens_per_second": 39.4, "ttft_ms": 520},
        "published_at": "2026-06-29T18:00:00Z",
    }


def test_model_manifest_validates() -> None:
    validate_model_manifest(_model_manifest())  # should not raise


def test_model_manifest_hash_is_stable_and_prefixed() -> None:
    manifest = _model_manifest()
    h1 = model_manifest_hash(manifest)
    h2 = model_manifest_hash(dict(reversed(list(manifest.items()))))
    assert h1 == h2  # order-independent
    assert h1.startswith("sha256:")


def test_provider_manifest_sign_and_verify() -> None:
    kp = KeyPair.generate()
    signed = sign_provider_manifest(_provider_manifest(kp.public_key_str), kp)
    assert verify_provider_manifest(signed) is True


def test_provider_manifest_tamper_detected() -> None:
    kp = KeyPair.generate()
    signed = sign_provider_manifest(_provider_manifest(kp.public_key_str), kp)
    signed["pricing"]["output_per_1m"] = 0.01
    assert verify_provider_manifest(signed) is False
