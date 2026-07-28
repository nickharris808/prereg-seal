"""prereg-seal — seal an acceptance specification before you measure.

The problem this solves is not fraud. It is the ordinary, mostly-honest drift in
which a threshold is chosen after a result is seen, and everyone involved
remembers it the other way round. A seal makes the ordering checkable.

Standard library only.
"""
from __future__ import annotations

import hashlib
import json
import os
import unicodedata
from pathlib import Path
from typing import Any

FORMAT = "prereg-seal/2"
LEGACY_FORMATS = ("prereg-seal/1",)
DOMAIN = b"PREREG-SEAL-v1"


class SealMismatch(Exception):
    """Raised when a specification does not match the seal presented with it."""


def _nfc(obj: Any) -> Any:
    """Recursively NFC-normalise every string.

    Without this, two specifications that are *visually identical* can hash
    differently: "café" composed (U+00E9) and decomposed (U+0065 U+0301) are
    different byte sequences. A seal that fails for an invisible reason is worse
    than no seal, because the user cannot tell a real change from an encoding one.
    """
    if isinstance(obj, str):
        return unicodedata.normalize("NFC", obj)
    if isinstance(obj, dict):
        return {_nfc(k): _nfc(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_nfc(v) for v in obj]
    return obj


def canonicalize(spec: Any) -> bytes:
    """Deterministic bytes for any JSON-serializable specification.

    Sorted keys, no insignificant whitespace, UTF-8, and **NFC-normalised strings**.
    Two specifications that differ only in key order, formatting, or Unicode
    normalisation form produce identical bytes; two that differ in any value do not.

    Note that JSON has no tuple type, so ``[1,2]`` and ``(1,2)`` canonicalise
    identically — by design, since they serialise identically.
    """
    return json.dumps(_nfc(spec), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(spec: Any) -> str:
    """Domain-separated SHA-256 over the canonical form."""
    return hashlib.sha256(DOMAIN + canonicalize(spec)).hexdigest()


def seal(spec: Any, *, note: str = "") -> dict:
    """Produce a seal artifact for ``spec``.

    The seal deliberately does **not** contain the specification. It contains
    the digest. Publishing the seal therefore commits you to the criteria
    without revealing them, which is what makes it usable before a blind
    evaluation.
    """
    return {
        "format": FORMAT,
        "digest": digest(spec),
        "note": str(note),
    }


def verify(spec: Any, sealed: dict) -> None:
    """Raise :class:`SealMismatch` unless ``spec`` matches ``sealed``.

    Both directions fail loudly: altering the specification after sealing
    changes the recomputed digest, and altering the seal to match an altered
    specification is caught by whatever binds the seal (see :func:`bind`).
    """
    if not isinstance(sealed, dict):
        raise SealMismatch("seal artifact is not an object")
    fmt = sealed.get("format")
    if fmt in LEGACY_FORMATS:
        raise SealMismatch(
            f"this seal is {fmt}, which hashed strings without Unicode normalisation. "
            f"Seals written before {FORMAT} cannot be checked against it, because two "
            f"visually identical specifications could hash differently. Re-seal the "
            f"specification with the current version and record the new digest.")
    if fmt != FORMAT:
        raise SealMismatch(f"unknown seal format {fmt!r}")
    got = digest(spec)
    want = sealed.get("digest")
    if not isinstance(want, str) or not want:
        raise SealMismatch("seal carries no digest")
    if got != want:
        raise SealMismatch(
            f"specification does not match its seal (sealed {want[:16]}…, "
            f"recomputed {got[:16]}…) — the criteria changed after sealing, "
            f"or the seal is not the one for these criteria")


def matches(spec: Any, sealed: dict) -> bool:
    """Boolean form of :func:`verify`."""
    try:
        verify(spec, sealed)
        return True
    except SealMismatch:
        return False


def bind(result: dict, sealed: dict) -> dict:
    """Attach a seal to a result record, and cross-bind the pair.

    The cross-binding is what makes the second failure direction detectable:
    swapping in a seal that matches doctored criteria changes ``seal_binding``,
    because the binding covers the result *and* the seal together.
    """
    out = dict(result)
    out["seal"] = dict(sealed)
    payload = canonicalize({"result": result, "seal": sealed})
    out["seal_binding"] = hashlib.sha256(DOMAIN + b"bind" + payload).hexdigest()
    return out


def verify_bound(bound: dict, spec: Any) -> None:
    """Verify a bound result end to end: binding intact **and** spec matches seal."""
    if "seal" not in bound or "seal_binding" not in bound:
        raise SealMismatch("result record carries no bound seal")
    sealed = bound["seal"]
    result = {k: v for k, v in bound.items() if k not in ("seal", "seal_binding")}
    payload = canonicalize({"result": result, "seal": sealed})
    expect = hashlib.sha256(DOMAIN + b"bind" + payload).hexdigest()
    if expect != bound["seal_binding"]:
        raise SealMismatch("seal binding does not recompute — the result or the "
                           "seal was altered after binding")
    verify(spec, sealed)


def write_seal(path, spec: Any, *, note: str = "") -> dict:
    """Seal ``spec`` and write the artifact to ``path``."""
    s = seal(spec, note=note)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(s, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return s


def read_seal(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def guard(spec: Any, seal_path, *, env_var: str = "PREREG_SEAL_ALLOW_UNSEALED") -> dict:
    """Fail-closed guard for use at evaluation time.

    Re-serializes the specification actually in force, recomputes its digest and
    compares it to the seal on disk. Raises unless they match.

    If the seal file is absent this raises too — an *unsealed* evaluation is the
    condition the tool exists to prevent. Set the escape-hatch environment
    variable only for local exploration; it is deliberately verbose to type and
    is reported in the returned record so it cannot pass unnoticed.
    """
    p = Path(seal_path)
    if not p.exists():
        if os.environ.get(env_var) == "1":
            return {"sealed": False, "escape_hatch_used": True, "digest": digest(spec)}
        raise SealMismatch(
            f"no seal at {p} — refusing to evaluate against unsealed criteria")
    sealed = read_seal(p)
    verify(spec, sealed)
    return {"sealed": True, "escape_hatch_used": False, "digest": sealed["digest"]}
