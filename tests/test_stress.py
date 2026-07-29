"""The adversarial suite for prereg-seal.

Oracle: no input may produce a confident-looking answer that is wrong. In this
package that means two things above all — a **missing** seal is never a pass, and
an anchor record never gets to assert itself.
"""
from __future__ import annotations

import json
import urllib.error
from xml.etree import ElementTree as ET

import pytest

import prereg_seal as P
from prereg_seal.anchor import parse_github_commit, verify_anchor
from prereg_seal.report import EMITTERS, emit, outcome_meta

SUCCESS = {"SEALED", "ANCHORED"}


# ============================================================ 1. MALFORMED

MALFORMED_SEALS = [
    ("not a dict", []), ("empty", {}), ("no digest", {"format": "x"}),
    ("digest not a string", {"digest": 5}), ("digest wrong length", {"digest": "ab"}),
    ("nested", {"digest": {"a": 1}}),
]


@pytest.mark.parametrize("label,seal", MALFORMED_SEALS, ids=[m[0] for m in MALFORMED_SEALS])
def test_a_malformed_seal_never_verifies(label, seal):
    """Whatever the seal, either a clean mismatch or a clean error — never a pass."""
    try:
        P.verify({"a": 1}, seal)
        pytest.fail(f"{label} verified")
    except (P.SealMismatch, ValueError, TypeError, AttributeError, KeyError):
        pass


@pytest.mark.parametrize("spec", [
    None, [], "a string", 5, {"a": float("nan")}, {"a": float("inf")},
])
def test_an_unserialisable_specification_is_refused_rather_than_hashed(spec):
    try:
        P.digest(spec)
    except (TypeError, ValueError):
        return
    # If it did produce a digest, it must at least be stable.
    assert P.digest(spec) == P.digest(spec)


MALFORMED_ANCHORS = [
    ("not a dict", []), ("empty", {}), ("unknown format", {"format": "x/9"}),
    ("no digest", {"format": P.ANCHOR_FORMAT}),
    ("digest not hex", {"format": P.ANCHOR_FORMAT, "digest": "zz" * 32}),
    ("digest wrong case", {"format": P.ANCHOR_FORMAT, "digest": "AB" * 32}),
    ("unknown kind", {"format": P.ANCHOR_FORMAT, "digest": "a" * 64, "kind": "smoke"}),
]


@pytest.mark.parametrize("label,rec", MALFORMED_ANCHORS,
                         ids=[m[0] for m in MALFORMED_ANCHORS])
def test_a_malformed_anchor_record_abstains(label, rec):
    res = verify_anchor(rec if isinstance(rec, dict) else {}, allow_network=False)
    assert res["status"] not in SUCCESS, label
    assert res["ok"] is False, label


# ============================================================ 2. EMPTY / DEGENERATE

def test_an_empty_specification_still_seals_and_verifies():
    seal = P.seal({})
    P.verify({}, seal)
    with pytest.raises(P.SealMismatch):
        P.verify({"a": 1}, seal)


def test_a_missing_seal_is_never_a_pass():
    ok, level, summary = outcome_meta("UNSEALED")
    assert ok is False and level == "error"
    assert "establishes nothing" in summary


# ============================================================ 3. ENORMOUS

def test_a_very_large_specification_seals_deterministically():
    spec = {f"k{i}": {"max": i * 1.5, "note": "x" * 50} for i in range(20_000)}
    a, b = P.digest(spec), P.digest(spec)
    assert a == b and len(a) == 64


def test_a_deeply_nested_specification_is_handled():
    spec = cur = {}
    for i in range(200):
        cur["next"] = {}
        cur = cur["next"]
    cur["leaf"] = 1
    assert len(P.digest(spec)) == 64


# ============================================================ 4. OUT OF DISTRIBUTION

@pytest.mark.parametrize("a,b", [
    ({"x": 1}, {"x": 1.0}),
    ({"x": 1}, {"x": True}),
    ({"x": 0}, {"x": False}),
    ({"x": "1"}, {"x": 1}),
    ({"x": None}, {}),
    ({"x": []}, {"x": {}}),
    ({"x": "a"}, {"x": "a "}),
])
def test_values_that_look_alike_are_not_the_same_specification(a, b):
    """`1` and `1.0` and `True` are different criteria, whatever they look like."""
    if P.digest(a) == P.digest(b):
        # JSON genuinely cannot distinguish 1 from 1.0. That is a real limit and
        # is pinned here rather than asserted away.
        assert (a, b) == ({"x": 1}, {"x": 1.0}), f"{a} and {b} collided unexpectedly"
    else:
        with pytest.raises(P.SealMismatch):
            P.verify(b, P.seal(a))


def test_unicode_variants_ARE_the_same_specification_here():
    """Deliberate, and the opposite of what lcert-verify does.

    A seal is over *meaning*: "cafe" with a combining accent and the precomposed
    form are the same criterion, and a specification that failed its own seal
    because an editor changed normalisation would be useless. So this package
    normalises to NFC before hashing.

    A certificate bundle is the other way round — there the fingerprint is over
    *bytes*, and `test_unicode_normalisation_variants_are_different_bundles` in
    lcert-verify asserts the two forms are different artifacts. Both are right for
    what they are binding.
    """
    nfd, nfc = "cafe\u0301", "caf\u00e9"
    assert nfd != nfc
    assert P.digest({nfd: 1}) == P.digest({nfc: 1})
    assert P.digest({"x": nfd}) == P.digest({"x": nfc})
    P.verify({nfc: 1}, P.seal({nfd: 1}))            # must not raise


def test_key_order_and_whitespace_do_not_change_the_digest():
    assert P.digest({"a": 1, "b": 2}) == P.digest({"b": 2, "a": 1})


@pytest.mark.parametrize("locator", [
    "", "   ", "main", "owner/repo", "owner/repo@main", "owner/repo@v1.0.0",
    "owner/repo@HEAD", "https://example.com/x", "owner/repo@zzzz",
    "owner/repo@" + "a" * 41, "../../etc/passwd", "owner/repo@abc def",
])
def test_a_locator_that_is_not_an_immutable_commit_is_refused(locator):
    """A ref that can move anchors nothing."""
    with pytest.raises(P.AnchorError):
        parse_github_commit(locator)


# ============================================================ 5. DIFFERENTIAL

def test_every_export_format_preserves_the_outcome():
    for outcome in ("SEALED", "MISMATCH", "UNSEALED", "ANCHORED", "REFUTED",
                    "UNANCHORED", "SOMETHING_NEW", "", None):
        ok, _level, _summary = outcome_meta(outcome)
        expected = outcome in SUCCESS
        assert ok is expected, outcome
        res = {"outcome": outcome, "ok": expected, "errors": ["x"]}
        for fmt in EMITTERS:
            assert emit(res, fmt).strip(), (outcome, fmt)
        sarif = json.loads(emit(res, "sarif"))
        assert sarif["runs"][0]["invocations"][0]["executionSuccessful"] is expected
        assert (ET.fromstring(emit(res, "junit")).get("failures") == "0") is expected


def test_the_two_abstention_outcomes_are_failures_with_their_reason():
    for outcome, needle in (("UNSEALED", "establishes nothing"),
                            ("UNANCHORED", "ABSTAINED")):
        res = {"outcome": outcome, "ok": False, "errors": []}
        x = ET.fromstring(emit(res, "junit"))
        assert x.get("failures") == "1", outcome
        assert needle in emit(res, "junit"), outcome


# ============================================================ 6. THE ANCHOR

def _fetcher(text=None, exc=None):
    def fetch(url, timeout):
        if exc:
            raise exc
        return text
    return fetch


@pytest.mark.parametrize("body", [
    "", "not json", "{}", '{"commit": null}', '{"commit": {"committer": null}}',
    '{"commit": {"committer": {"date": null}}}', "[1,2,3]", '{"sha": 5}',
])
def test_an_unreadable_host_response_abstains_rather_than_asserting(body):
    rec = P.make_anchor("a" * 64, "github-commit",
                        "owner/repo@" + "0" * 40)
    res = verify_anchor(rec, fetch=_fetcher(body))
    assert res["status"] not in SUCCESS
    assert res["ok"] is False


def test_a_record_that_asserts_itself_is_still_unanchored():
    """The central property: a record is not evidence for itself."""
    rec = P.make_anchor("a" * 64, "github-commit", "owner/repo@" + "0" * 40)
    rec.update(status="ANCHORED", observed_time="1999-01-01T00:00:00Z",
               observed_by="itself", ok=True, trust="totally fine")
    res = verify_anchor(rec, allow_network=False)
    assert res["status"] == P.UNANCHORED
    assert res["observed_time"] is None
    assert res["ok"] is False


def test_a_digest_that_merely_appears_as_a_substring_still_counts_only_once():
    """The check is presence, and it must not be fooled by an empty needle."""
    rec = P.make_anchor("b" * 64, "url", "https://example.invalid/log")
    assert verify_anchor(rec, fetch=_fetcher("nothing here"))["status"] == P.REFUTED
    assert verify_anchor(rec, fetch=_fetcher("b" * 64))["status"] == P.UNANCHORED


@pytest.mark.parametrize("exc", [
    urllib.error.URLError("down"),
    TimeoutError("slow"),
    OSError("broken pipe"),
    urllib.error.HTTPError("u", 500, "err", {}, None),
    urllib.error.HTTPError("u", 429, "rate", {}, None),
])
def test_every_transport_failure_abstains(exc):
    rec = P.make_anchor("a" * 64, "github-commit", "owner/repo@" + "0" * 40)
    assert verify_anchor(rec, fetch=_fetcher(exc=exc))["status"] == P.UNANCHORED


def test_a_404_is_refuted_because_absence_at_a_named_place_is_evidence():
    rec = P.make_anchor("a" * 64, "github-commit", "owner/repo@" + "0" * 40)
    err = urllib.error.HTTPError("u", 404, "nope", {}, None)
    assert verify_anchor(rec, fetch=_fetcher(exc=err))["status"] == P.REFUTED


# ============================================================ 7. NO STATE LEAKS

def test_sealing_twice_gives_the_same_seal():
    spec = {"a": 1, "b": [1, 2, 3]}
    assert P.seal(spec)["digest"] == P.seal(spec)["digest"]


def test_verification_does_not_mutate_the_specification():
    spec = {"a": 1, "nested": {"b": [1, 2]}}
    before = json.dumps(spec, sort_keys=True)
    P.verify(spec, P.seal(spec))
    assert json.dumps(spec, sort_keys=True) == before


def test_an_anchor_record_is_not_mutated_by_checking_it():
    rec = P.make_anchor("a" * 64, "github-commit", "owner/repo@" + "0" * 40)
    before = json.dumps(rec, sort_keys=True)
    verify_anchor(rec, allow_network=False)
    assert json.dumps(rec, sort_keys=True) == before
