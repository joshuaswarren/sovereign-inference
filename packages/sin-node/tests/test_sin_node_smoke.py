# SPDX-License-Identifier: AGPL-3.0-or-later
import importlib


def test_package_imports() -> None:
    module = importlib.import_module("sin_node")
    assert module.__version__ == "0.1.2"
