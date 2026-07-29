"""External time anchors — turning "sealed" into "sealed *before*".

The honest-scope table has always said a digest carries no time, and it is right:
nothing about a hash establishes when it was computed. That matters, because the
failure preregistration exists to prevent is writing the criteria *after* seeing
the result. A seal alone does not stop that. Only an upper bound on when the seal
existed does.

There is no cryptographic trick that produces one offline. Establishing that
something existed before a moment requires a **witness you do not control** — a
public log that recorded it. So this module does not invent a bound; it records
where the digest was published and then goes and checks.

Three verdicts, and the third is the point:

``ANCHORED``
    The digest really is at the locator, and the host reports a time. The bound
    is only as good as that host's word, which is stated in the record rather
    than implied.

``REFUTED``
    The locator exists and the digest is **not** there. Somebody's story does not
    hold up.

``UNANCHORED``
    The locator could not be reached, or no time was reported. **Abstention.**
    The local claim is never accepted on its own — a record that asserted itself
    would be exactly the thing this module exists to replace.

Standard library only, and the network is never touched unless you ask for it.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Callable, Dict, Optional

ANCHOR_FORMAT = "prereg-anchor/1"

ANCHORED = "ANCHORED"
REFUTED = "REFUTED"
UNANCHORED = "UNANCHORED"

#: Locator kinds this module knows how to check.
KINDS = ("github-commit", "url")

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_UA = "prereg-seal-anchor/1 (+https://github.com/nickharris808/prereg-seal)"


class AnchorError(ValueError):
    """A malformed anchor record or locator."""


def make_anchor(digest: str, kind: str, locator: str, *, note: str = "") -> Dict:
    """Build an *unverified* anchor record.

    It is unverified on purpose. Creating the record proves nothing; only
    :func:`verify_anchor` does, and only by going and looking.
    """
    digest = str(digest).strip().lower()
    if not _SHA256.match(digest):
        raise AnchorError(f"digest must be 64 lowercase hex characters, got {digest!r}")
    if kind not in KINDS:
        raise AnchorError(f"unknown anchor kind {kind!r}; known: {', '.join(KINDS)}")
    if not locator.strip():
        raise AnchorError("an anchor needs a locator — where the digest was published")
    return {"format": ANCHOR_FORMAT, "digest": digest, "kind": kind,
            "locator": locator.strip(), "note": note,
            "status": "UNVERIFIED-UNTIL-CHECKED"}


def parse_github_commit(locator: str) -> Dict[str, str]:
    """Split ``owner/repo@sha`` or a github.com commit URL into its parts."""
    m = re.match(r"^(?:https?://github\.com/)?([\w.-]+)/([\w.-]+?)"
                 r"(?:\.git)?(?:/commit/|@)([0-9a-fA-F]{7,40})/?$", locator.strip())
    if not m:
        raise AnchorError(
            f"cannot read {locator!r} as a GitHub commit. Use 'owner/repo@sha' or "
            f"'https://github.com/owner/repo/commit/sha'.")
    return {"owner": m.group(1), "repo": m.group(2), "sha": m.group(3)}


def _http_get(url: str, timeout: float) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA,
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310
        return r.read().decode("utf-8", errors="replace")


def verify_anchor(record: Dict, *, fetch: Optional[Callable[[str, float], str]] = None,
                  timeout: float = 15.0, allow_network: bool = True) -> Dict:
    """Check the digest really is where the record says, and when.

    ``fetch(url, timeout) -> text`` can be supplied to test this without a
    network, or to route through your own client. With ``allow_network=False``
    and no ``fetch``, the result is ``UNANCHORED`` — never an accepted claim.
    """
    errors = []
    if record.get("format") != ANCHOR_FORMAT:
        return _result(UNANCHORED, record, None,
                       [f"unknown anchor format {record.get('format')!r}"])
    digest = str(record.get("digest", "")).lower()
    if not _SHA256.match(digest):
        return _result(UNANCHORED, record, None, ["record has no usable digest"])

    getter = fetch
    if getter is None:
        if not allow_network:
            return _result(UNANCHORED, record, None, [
                "no fetcher supplied and network access was not permitted, so the "
                "anchor could not be checked. The record's own claim is not "
                "evidence for itself."])
        getter = _http_get

    kind, locator = record.get("kind"), record.get("locator", "")
    try:
        if kind == "github-commit":
            p = parse_github_commit(locator)
            url = f"https://api.github.com/repos/{p['owner']}/{p['repo']}/commits/{p['sha']}"
            body = json.loads(getter(url, timeout))
            observed_by = "github.com"
            # The host can return anything. A response that is not an object, or
            # whose fields are not where they should be, means the check could
            # not be made -- an abstention, never an exception.
            if not isinstance(body, dict):
                return _result(UNANCHORED, record, None, [
                    f"the host returned {type(body).__name__}, not an object, so "
                    f"nothing could be checked"], observed_by=observed_by)
            commit = body.get("commit")
            committer = commit.get("committer") if isinstance(commit, dict) else None
            when = committer.get("date") if isinstance(committer, dict) else None
            if not isinstance(when, str):
                when = None
            haystack = json.dumps(body)
            # The committer date is supplied by whoever made the commit and is
            # therefore forgeable. The *push* is what GitHub witnessed, so this is
            # stated as the host's record rather than as a fact.
            note = ("committer date as recorded by GitHub; the commit author "
                    "controls this field, so treat it as GitHub's record of a "
                    "claim, not as an independent timestamp")
        elif kind == "url":
            body = getter(locator, timeout)
            observed_by = locator
            when = None
            haystack = body
            note = ("plain fetch: the digest was found at this URL now. No time is "
                    "established by this kind — use an archive or a log that "
                    "timestamps its entries.")
        else:
            return _result(UNANCHORED, record, None, [f"unknown anchor kind {kind!r}"])
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return _result(REFUTED, record, None,
                           [f"locator not found at the host ({exc.code})"])
        return _result(UNANCHORED, record, None,
                       [f"could not reach the host: HTTP {exc.code}"])
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return _result(UNANCHORED, record, None, [f"could not reach the host: {exc}"])
    except (AnchorError, ValueError) as exc:
        return _result(UNANCHORED, record, None, [str(exc)])

    if digest not in haystack.lower():
        errors.append(f"the digest does not appear at {locator} — the seal was "
                      f"not published where this record claims")
        return _result(REFUTED, record, None, errors, observed_by=observed_by)

    if not when:
        return _result(UNANCHORED, record, None, [
            "the digest is published there, but the host reports no time, so no "
            "'sealed before' bound follows"], observed_by=observed_by)

    return _result(ANCHORED, record, when, [], observed_by=observed_by, note=note)


def _result(status, record, when, errors, observed_by="", note="") -> Dict:
    return {"status": status, "digest": record.get("digest"),
            "kind": record.get("kind"), "locator": record.get("locator"),
            "observed_time": when, "observed_by": observed_by,
            "trust": (f"the time above is {observed_by}'s record, not an "
                      f"independent attestation" if when else ""),
            "note": note, "errors": errors,
            "ok": status == ANCHORED}


def describe(result: Dict) -> str:
    """A human-readable line that does not overstate what was established."""
    if result["status"] == ANCHORED:
        return (f"ANCHORED   digest published at {result['locator']}\n"
                f"           time {result['observed_time']} — {result['trust']}\n"
                f"           {result['note']}")
    if result["status"] == REFUTED:
        return "REFUTED    " + "; ".join(result["errors"])
    return ("UNANCHORED " + "; ".join(result["errors"]) +
            "\n           This is an abstention: nothing was established either way.")
