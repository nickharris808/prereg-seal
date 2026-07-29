"""Structured output: JSON, JSON Lines, SARIF 2.1.0, JUnit XML.

One place decides how an outcome renders, so the formats cannot drift apart.

Two things this package has to say that a boolean cannot. A **missing** seal is
not a pass — an unsealed check establishes nothing, and reporting it green is
worse than reporting nothing. And an **abstained anchor** (`UNANCHORED`) is not a
failure of the seal; it means the publication could not be checked. Neither
SARIF nor JUnit has a state for either, so both are rendered as failures with
the reason attached.
"""
from __future__ import annotations

import json
from typing import Dict, Tuple
from xml.etree import ElementTree as ET

#: outcome -> (counts as success, SARIF level, one-line summary)
_META: Dict[str, Tuple[bool, str, str]] = {
    "SEALED": (True, "note",
               "the specification matches the seal it was fixed under"),
    "MISMATCH": (False, "error",
                 "the specification has changed since it was sealed"),
    "UNSEALED": (False, "error",
                 "no seal was found — an unsealed check establishes nothing, so "
                 "this is a failure rather than a pass"),
    "ANCHORED": (True, "note",
                 "the seal digest is published where the record says, and the "
                 "host reports a time"),
    "REFUTED": (False, "error",
                "the digest is not published where the record claims"),
    "UNANCHORED": (False, "warning",
                   "ABSTAINED: the publication could not be checked, so no "
                   "'sealed before' bound follows. Not a failure of the seal."),
}


def outcome_meta(outcome: str) -> Tuple[bool, str, str]:
    """Metadata for an outcome. An unrecognised one is a failure, never a pass."""
    return _META.get(
        outcome, (False, "error",
                  f"unrecognised outcome {outcome!r} — treated as a failure, "
                  f"because an outcome this tool does not understand cannot be "
                  f"reported as success"))


def _fields(res: Dict, source: str) -> Dict:
    outcome = res.get("outcome") or res.get("status")
    ok, level, summary = outcome_meta(outcome)
    return {"outcome": outcome, "ok": bool(res.get("ok", ok)) and ok, "level": level,
            "summary": summary, "source": source,
            "digest": res.get("digest"), "errors": list(res.get("errors") or []),
            "observed_time": res.get("observed_time"),
            "observed_by": res.get("observed_by"), "trust": res.get("trust", "")}


def to_json(res: Dict, source: str = "spec") -> str:
    return json.dumps(_fields(res, source), indent=2, sort_keys=True)


def to_jsonl(res: Dict, source: str = "spec") -> str:
    return json.dumps(_fields(res, source), sort_keys=True)


def to_sarif(res: Dict, source: str = "spec") -> str:
    f = _fields(res, source)
    msg = f["summary"]
    if f["errors"]:
        msg += "\n" + "\n".join(f"- {e}" for e in f["errors"])
    if f["trust"]:
        msg += f"\n({f['trust']})"
    return json.dumps({
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {
                "name": "prereg-seal",
                "informationUri": "https://github.com/nickharris808/prereg-seal",
                "rules": [{"id": "prereg-seal/outcome",
                           "shortDescription": {"text": "Preregistration seal check"},
                           "fullDescription": {"text": (
                               "A missing seal is reported as a failure, not a pass. "
                               "An anchor that could not be checked is reported as "
                               "an abstention, also not a pass.")}}]}},
            "invocations": [{"executionSuccessful": f["ok"]}],
            "results": ([] if f["ok"] else [{
                "ruleId": "prereg-seal/outcome",
                "level": f["level"],
                # The outcome name goes in the message and in properties: a
                # reader in a code-scanning UI needs to know WHICH failure this
                # is, and "level" alone does not say.
                "message": {"text": f"{f['outcome']}: {msg}"},
                "properties": {"outcome": f["outcome"]},
                "locations": [{"physicalLocation": {
                    "artifactLocation": {"uri": source}}}]}]),
        }],
    }, indent=2)


def to_junit(res: Dict, source: str = "spec") -> str:
    f = _fields(res, source)
    suite = ET.Element("testsuite", name="prereg-seal", tests="1",
                       failures="0" if f["ok"] else "1", errors="0", skipped="0")
    case = ET.SubElement(suite, "testcase", classname="prereg-seal",
                         name=f"seal {source}")
    if not f["ok"]:
        fail = ET.SubElement(case, "failure", type=str(f["outcome"]),
                             message=f["summary"])
        fail.text = "\n".join(f["errors"]) or f["summary"]
    out = ET.SubElement(suite, "system-out")
    out.text = (f"outcome={f['outcome']} digest={f['digest']} "
                f"observed_time={f['observed_time']} observed_by={f['observed_by']}")
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            + ET.tostring(suite, encoding="unicode"))


EMITTERS = {"json": to_json, "jsonl": to_jsonl, "sarif": to_sarif, "junit": to_junit}


def emit(res: Dict, fmt: str, **kw) -> str:
    if fmt not in EMITTERS:
        raise ValueError(f"unknown format {fmt!r}; known: {sorted(EMITTERS)}")
    return EMITTERS[fmt](res, **kw)
