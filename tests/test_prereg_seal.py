"""Tests for prereg-seal. The tamper tests are the point."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import prereg_seal as P

SPEC = {
    "criterion": "worst-corner edge placement within budget",
    "threshold_nm": 3.0,
    "corners": ["nominal", "defocus+", "defocus-", "dose+", "dose-"],
    "budget": {"pfail": 0.05},
    "protocol": "held-out clips, no reuse",
}


def test_seal_and_verify_roundtrip():
    s = P.seal(SPEC)
    P.verify(SPEC, s)
    assert P.matches(SPEC, s)


def test_key_order_and_whitespace_do_not_matter():
    reordered = json.loads(json.dumps(SPEC, sort_keys=False))
    reordered = dict(reversed(list(reordered.items())))
    assert P.digest(reordered) == P.digest(SPEC)


def test_moving_the_threshold_is_caught():
    s = P.seal(SPEC)
    doctored = dict(SPEC, threshold_nm=5.0)   # loosened after the fact
    assert not P.matches(doctored, s)
    with pytest.raises(P.SealMismatch):
        P.verify(doctored, s)


def test_dropping_a_corner_is_caught():
    s = P.seal(SPEC)
    doctored = dict(SPEC, corners=["nominal"])
    assert not P.matches(doctored, s)


def test_adding_a_field_is_caught():
    s = P.seal(SPEC)
    assert not P.matches(dict(SPEC, extra="added later"), s)


def test_seal_does_not_leak_the_specification():
    """A seal can be published before a blind evaluation."""
    s = P.seal(SPEC)
    blob = json.dumps(s)
    assert "threshold_nm" not in blob
    assert "3.0" not in blob
    assert set(s) == {"format", "digest", "note"}


def test_binding_detects_a_swapped_seal():
    """Direction two: doctor the spec AND mint a matching seal."""
    result = {"measured_nm": 2.4, "verdict": "PASS"}
    bound = P.bind(result, P.seal(SPEC))
    P.verify_bound(bound, SPEC)                      # honest case verifies

    doctored = dict(SPEC, threshold_nm=5.0)
    forged = dict(bound, seal=P.seal(doctored))      # swap in a seal that matches the doctored spec
    with pytest.raises(P.SealMismatch):
        P.verify_bound(forged, doctored)             # binding no longer recomputes


def test_binding_detects_an_altered_result():
    bound = P.bind({"measured_nm": 4.1, "verdict": "FAIL"}, P.seal(SPEC))
    tampered = dict(bound, measured_nm=2.0, verdict="PASS")
    with pytest.raises(P.SealMismatch):
        P.verify_bound(tampered, SPEC)


def test_revert_restores_both_directions():
    """The check must be reversible, or a red result proves nothing."""
    s = P.seal(SPEC)
    doctored = dict(SPEC, threshold_nm=5.0)
    assert not P.matches(doctored, s)
    reverted = dict(doctored, threshold_nm=3.0)
    assert P.matches(reverted, s)


def test_guard_refuses_when_no_seal_exists(tmp_path):
    with pytest.raises(P.SealMismatch):
        P.guard(SPEC, tmp_path / "absent.seal.json")


def test_guard_passes_on_match(tmp_path):
    p = tmp_path / "s.json"
    P.write_seal(p, SPEC)
    rec = P.guard(SPEC, p)
    assert rec["sealed"] is True and rec["escape_hatch_used"] is False


def test_guard_escape_hatch_is_recorded(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREG_SEAL_ALLOW_UNSEALED", "1")
    rec = P.guard(SPEC, tmp_path / "absent.json")
    assert rec["sealed"] is False and rec["escape_hatch_used"] is True


def test_nan_is_rejected():
    """NaN has no canonical JSON form; silently accepting it would break determinism."""
    with pytest.raises(ValueError):
        P.digest({"threshold": float("nan")})


def test_unknown_format_rejected():
    with pytest.raises(P.SealMismatch):
        P.verify(SPEC, {"format": "something-else/9", "digest": P.digest(SPEC)})


def test_cli_end_to_end(tmp_path):
    spec_p = tmp_path / "spec.json"
    spec_p.write_text(json.dumps(SPEC))
    env = {"PYTHONPATH": str(Path(__file__).parent.parent / "src")}

    r = subprocess.run([sys.executable, "-m", "prereg_seal.cli", "seal", str(spec_p)],
                       capture_output=True, text=True, env={**env, "PATH": ""})
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "spec.json.seal.json").exists()

    r = subprocess.run([sys.executable, "-m", "prereg_seal.cli", "check", str(spec_p)],
                       capture_output=True, text=True, env={**env, "PATH": ""})
    assert r.returncode == 0, r.stderr

    spec_p.write_text(json.dumps(dict(SPEC, threshold_nm=9.9)))
    r = subprocess.run([sys.executable, "-m", "prereg_seal.cli", "check", str(spec_p)],
                       capture_output=True, text=True, env={**env, "PATH": ""})
    assert r.returncode == 1
    assert "MISMATCH" in r.stderr


# ---------- README fidelity ----------
# These exist because the README once printed invented digest values. Output
# shown to a reader is a claim like any other and is tested like one.

def _readme():
    return (Path(__file__).parent.parent / "README.md").read_text()


def test_readme_digest_output_is_real():
    """The digests quoted in the README must be the ones the code produces."""
    spec = {"criterion": "worst-corner edge placement within budget", "threshold_nm": 3.0}
    sealed = P.seal(spec)
    doctored = dict(spec, threshold_nm=5.0)
    try:
        P.verify(doctored, sealed)
        raise AssertionError("expected SealMismatch")
    except P.SealMismatch as e:
        msg = str(e)
    readme = _readme()
    assert msg in readme, (
        "README quotes an error message the code does not produce.\n"
        f"actual: {msg}")


def test_readme_binding_output_is_real():
    spec = {"criterion": "worst-corner edge placement within budget", "threshold_nm": 3.0}
    bound = P.bind({"measured_nm": 2.4, "verdict": "PASS"}, P.seal(spec))
    forged = dict(bound, seal=P.seal(dict(spec, threshold_nm=5.0)))
    try:
        P.verify_bound(forged, dict(spec, threshold_nm=5.0))
        raise AssertionError("expected SealMismatch")
    except P.SealMismatch as e:
        assert str(e) in _readme()
