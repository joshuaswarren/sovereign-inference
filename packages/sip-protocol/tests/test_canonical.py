# SPDX-License-Identifier: Apache-2.0
import pytest

from sip_protocol import canonical_json


def test_keys_are_sorted_and_compact() -> None:
    assert canonical_json({"b": 1, "a": 2}) == b'{"a":2,"b":1}'


def test_nested_objects_are_recursively_sorted() -> None:
    out = canonical_json({"z": {"y": 1, "x": 2}, "a": [3, 2, 1]})
    assert out == b'{"a":[3,2,1],"z":{"x":2,"y":1}}'


def test_unicode_is_preserved_not_escaped() -> None:
    assert canonical_json({"name": "Wārren"}) == '{"name":"Wārren"}'.encode()


def test_non_finite_floats_are_rejected() -> None:
    with pytest.raises(ValueError):
        canonical_json({"x": float("nan")})


def test_is_deterministic_regardless_of_insertion_order() -> None:
    a = canonical_json({"one": 1, "two": 2, "three": 3})
    b = canonical_json({"three": 3, "two": 2, "one": 1})
    assert a == b
