# SPDX-License-Identifier: Apache-2.0
import importlib


def test_package_imports() -> None:
    module = importlib.import_module("sip_runtime_llamacpp")
    assert module.__version__ == "0.1.2"
