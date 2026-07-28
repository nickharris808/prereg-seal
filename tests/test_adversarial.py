"""Adversarial regression suite for prereg-seal.

Oracle: a seal must match exactly when the criteria are the same, and must never
match when they differ — and "the same" must mean what a human means by it.
"""
from __future__ import annotations

import json
import unicodedata

import pytest

import prereg_seal as P

SPEC = {"criterion": "worst-corner EPE", "threshold_nm": 3.0, "corners": ["nominal"]}


# ---------------------------------------------------------------- Unicode

@pytest.mark.parametrize("text", ["café", "naïve", "Ångström", "ﬁle", "한국어"])
def test_visually_identical_strings_hash_identically(text):
    """The trap this exists to prevent: an editor silently changing normalisation."""
    nfc = {"k": unicodedata.normalize("NFC", text)}
    nfd = {"k": unicodedata.normalize("NFD", text)}
    assert P.digest(nfc) == P.digest(nfd)
    assert P.matches(nfd, P.seal(nfc))


def test_genuinely_different_text_still_differs():
    assert P.digest({"k": "café"}) != P.digest({"k": "cafe"})


def test_normalisation_applies_to_keys_and_nested_values():
    a = {unicodedata.normalize("NFC", "clé"): {"x": [unicodedata.normalize("NFC", "é")]}}
    b = {unicodedata.normalize("NFD", "clé"): {"x": [unicodedata.normalize("NFD", "é")]}}
    assert P.digest(a) == P.digest(b)


# ---------------------------------------------------------------- type discrimination

def test_int_float_bool_are_distinguished():
    ds = {P.digest({"x": v}) for v in (1, 1.0, True)}
    assert len(ds) == 3, "1, 1.0 and True must not collide"


def test_list_and_tuple_collide_by_design():
    """JSON has no tuple; they serialise identically, so they hash identically."""
    assert P.digest({"x": [1, 2]}) == P.digest({"x": (1, 2)})


def test_key_order_is_irrelevant():
    assert P.digest({"a": 1, "b": 2}) == P.digest({"b": 2, "a": 1})


# ---------------------------------------------------------------- refuse the ambiguous

@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_numbers_are_refused(bad):
    """NaN/Infinity are not valid JSON; hashing them would not be portable."""
    with pytest.raises(ValueError):
        P.digest({"x": bad})


def test_unserialisable_object_raises():
    with pytest.raises(TypeError):
        P.digest({"x": object()})


# ---------------------------------------------------------------- tamper

@pytest.mark.parametrize("mutate", [
    lambda s: dict(s, threshold_nm=5.0),
    lambda s: dict(s, corners=[]),
    lambda s: {k: v for k, v in s.items() if k != "criterion"},
    lambda s: dict(s, extra="added later"),
])
def test_any_change_breaks_the_seal(mutate):
    sealed = P.seal(SPEC)
    assert not P.matches(mutate(SPEC), sealed)


def test_reverting_restores_the_match():
    sealed = P.seal(SPEC)
    doctored = dict(SPEC, threshold_nm=9.9)
    assert not P.matches(doctored, sealed)
    assert P.matches(dict(doctored, threshold_nm=3.0), sealed)


def test_binding_detects_a_swapped_seal():
    bound = P.bind({"measured": 2.4}, P.seal(SPEC))
    doctored = dict(SPEC, threshold_nm=9.9)
    forged = dict(bound, seal=P.seal(doctored))
    with pytest.raises(P.SealMismatch):
        P.verify_bound(forged, doctored)


def test_legacy_format_gets_a_migration_message_not_a_bare_mismatch():
    s = P.seal(SPEC)
    s["format"] = "prereg-seal/1"
    with pytest.raises(P.SealMismatch, match="Unicode normalisation"):
        P.verify(SPEC, s)


def test_unknown_format_is_refused():
    s = P.seal(SPEC)
    s["format"] = "something/9"
    with pytest.raises(P.SealMismatch):
        P.verify(SPEC, s)


def test_seal_without_a_digest_is_refused():
    with pytest.raises(P.SealMismatch):
        P.verify(SPEC, {"format": P.FORMAT})


# ---------------------------------------------------------------- empty / enormous

def test_empty_spec_is_sealable_but_distinct():
    assert P.digest({}) != P.digest({"a": 1})
    assert P.matches({}, P.seal({}))


def test_large_spec():
    big = {f"k{i}": {"nested": list(range(20))} for i in range(2000)}
    assert P.matches(big, P.seal(big))


def test_deeply_nested_spec():
    d = cur = {}
    for i in range(80):
        cur["n"] = {}
        cur = cur["n"]
    assert P.matches(d, P.seal(d))


def test_seal_never_leaks_the_specification():
    s = P.seal({"threshold_nm": 3.0, "secret_corner": "xyzzy"})
    assert "xyzzy" not in json.dumps(s) and "3.0" not in json.dumps(s)
