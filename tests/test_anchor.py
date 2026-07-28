"""Time anchors: the record never gets to assert itself.

Every check here runs with an injected fetcher, so the suite is offline and
deterministic. One test does hit the network and skips when it cannot.
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.error

import pytest

import prereg_seal as P
from prereg_seal.anchor import parse_github_commit, verify_anchor

DIGEST = "b" * 64
LOCATOR = "nickharris808/prereg-seal@0123456789abcdef0123456789abcdef01234567"


def _commit_json(digest, when="2026-07-28T12:00:00Z"):
    return json.dumps({"sha": "0123456789abcdef0123456789abcdef01234567",
                       "commit": {"message": f"anchor {digest}",
                                  "committer": {"date": when}}})


def _fetcher(text=None, exc=None):
    def fetch(url, timeout):
        if exc:
            raise exc
        return text
    return fetch


# ---------------------------------------------------------------- the three verdicts

def test_a_published_digest_with_a_time_is_anchored():
    rec = P.make_anchor(DIGEST, "github-commit", LOCATOR)
    res = verify_anchor(rec, fetch=_fetcher(_commit_json(DIGEST)))
    assert res["status"] == P.ANCHORED and res["ok"]
    assert res["observed_time"] == "2026-07-28T12:00:00Z"
    assert res["observed_by"] == "github.com"


def test_a_digest_that_is_not_there_is_refuted():
    rec = P.make_anchor(DIGEST, "github-commit", LOCATOR)
    res = verify_anchor(rec, fetch=_fetcher(_commit_json("c" * 64)))
    assert res["status"] == P.REFUTED and not res["ok"]
    assert any("not published where this record claims" in e for e in res["errors"])


def test_an_unreachable_host_abstains_rather_than_accepting():
    rec = P.make_anchor(DIGEST, "github-commit", LOCATOR)
    res = verify_anchor(rec, fetch=_fetcher(exc=urllib.error.URLError("down")))
    assert res["status"] == P.UNANCHORED and not res["ok"]


def test_a_missing_locator_is_refuted_not_abstained():
    """404 means the story does not hold up; that is evidence, not absence of it."""
    rec = P.make_anchor(DIGEST, "github-commit", LOCATOR)
    err = urllib.error.HTTPError(LOCATOR, 404, "Not Found", {}, None)
    assert verify_anchor(rec, fetch=_fetcher(exc=err))["status"] == P.REFUTED


def test_a_server_error_abstains():
    rec = P.make_anchor(DIGEST, "github-commit", LOCATOR)
    err = urllib.error.HTTPError(LOCATOR, 503, "Unavailable", {}, None)
    assert verify_anchor(rec, fetch=_fetcher(exc=err))["status"] == P.UNANCHORED


def test_offline_never_accepts_the_records_own_claim():
    """The whole point: a record that asserted itself would establish nothing."""
    rec = P.make_anchor(DIGEST, "github-commit", LOCATOR)
    rec["status"] = "ANCHORED"                      # a producer lying outright
    rec["observed_time"] = "1999-01-01T00:00:00Z"
    res = verify_anchor(rec, allow_network=False)
    assert res["status"] == P.UNANCHORED
    assert res["observed_time"] is None


def test_publication_without_a_time_does_not_give_a_bound():
    """A URL fetch proves the digest is there *now*, which is not a 'before'."""
    rec = P.make_anchor(DIGEST, "url", "https://example.invalid/log.txt")
    res = verify_anchor(rec, fetch=_fetcher(f"...{DIGEST}..."))
    assert res["status"] == P.UNANCHORED
    assert any("no time" in e for e in res["errors"])


def test_a_url_anchor_still_refutes_a_digest_that_is_absent():
    rec = P.make_anchor(DIGEST, "url", "https://example.invalid/log.txt")
    assert verify_anchor(rec, fetch=_fetcher("nothing here"))["status"] == P.REFUTED


# ---------------------------------------------------------------- honesty of the claim

def test_the_result_names_who_is_being_trusted():
    rec = P.make_anchor(DIGEST, "github-commit", LOCATOR)
    res = verify_anchor(rec, fetch=_fetcher(_commit_json(DIGEST)))
    assert "github.com" in res["trust"]
    assert "not an independent attestation" in res["trust"]
    assert "forgeable" in res["note"] or "controls this field" in res["note"]


def test_describe_does_not_overstate_an_abstention():
    rec = P.make_anchor(DIGEST, "github-commit", LOCATOR)
    text = P.describe(verify_anchor(rec, allow_network=False))
    assert "nothing was established either way" in text
    assert "ANCHORED" not in text.replace("UNANCHORED", "")


# ---------------------------------------------------------------- records

def test_a_record_is_born_unverified():
    assert P.make_anchor(DIGEST, "url", "https://x.invalid")["status"] == \
        "UNVERIFIED-UNTIL-CHECKED"


@pytest.mark.parametrize("bad,msg", [
    (("short", "url", "https://x.invalid"), "64 lowercase hex"),
    ((DIGEST, "smoke-signal", "x"), "unknown anchor kind"),
    ((DIGEST, "url", "   "), "needs a locator"),
])
def test_malformed_records_are_refused(bad, msg):
    with pytest.raises(P.AnchorError, match=msg):
        P.make_anchor(*bad)


def test_an_unknown_record_format_abstains():
    assert verify_anchor({"format": "other/9"})["status"] == P.UNANCHORED


@pytest.mark.parametrize("locator", [
    "owner/repo@abc1234",
    "https://github.com/owner/repo/commit/0123456789abcdef0123456789abcdef01234567",
    "https://github.com/owner/repo.git@abc1234",
])
def test_commit_locators_are_parsed(locator):
    p = parse_github_commit(locator)
    assert p["owner"] == "owner" and p["repo"] == "repo" and p["sha"].startswith("abc") \
        or p["sha"].startswith("0123")


def test_an_unreadable_locator_says_what_it_wanted():
    with pytest.raises(P.AnchorError, match="owner/repo@sha"):
        parse_github_commit("just some text")


# ---------------------------------------------------------------- CLI

def _cli(args):
    return subprocess.run([sys.executable, "-m", "prereg_seal.cli", *args],
                          capture_output=True, text=True)


def test_cli_anchor_then_verify_offline(tmp_path):
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"epe_nm": {"max": 2.0}}))
    assert _cli(["seal", str(spec)]).returncode == 0
    rec = tmp_path / "anchor.json"
    r = _cli(["anchor", str(spec) + ".seal.json", LOCATOR, "-o", str(rec)])
    assert r.returncode == 0 and "asserts nothing yet" in r.stdout
    v = _cli(["verify-anchor", str(rec), "--offline"])
    assert v.returncode == 4, "an abstention needs its own exit code"
    assert "UNANCHORED" in v.stdout


def test_cli_anchor_accepts_a_bare_digest(tmp_path):
    rec = tmp_path / "a.json"
    r = _cli(["anchor", DIGEST, LOCATOR, "-o", str(rec)])
    assert r.returncode == 0
    assert json.loads(rec.read_text())["digest"] == DIGEST


# ---------------------------------------------------------------- live

def test_a_mutable_ref_is_not_an_anchor():
    """`@main` moves. An anchor that can be rewritten anchors nothing."""
    with pytest.raises(P.AnchorError, match="owner/repo@sha"):
        parse_github_commit("nickharris808/prereg-seal@main")
    with pytest.raises(P.AnchorError):
        parse_github_commit("nickharris808/prereg-seal@v1.0.0")


@pytest.mark.network
def test_a_real_public_commit_can_be_checked():
    """Hits github.com. Skipped when the network is unavailable."""
    rec = P.make_anchor("d" * 64, "github-commit",
                        "nickharris808/prereg-seal@c96629b7acdf225ab75e532b2851f449fc2848b1")
    try:
        res = verify_anchor(rec, timeout=10)
    except Exception:                       # pragma: no cover - network shape varies
        pytest.skip("network unavailable")
    if res["status"] == P.UNANCHORED and any("reach" in e for e in res["errors"]):
        pytest.skip("network unavailable")
    # A digest of all 'd's is not in that commit, so the honest answer is REFUTED —
    # the live path reaches GitHub, reads a real commit, and says no.
    assert res["status"] == P.REFUTED
