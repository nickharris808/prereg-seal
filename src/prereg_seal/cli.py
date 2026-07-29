"""``prereg-seal seal|check|show|anchor|verify-anchor``."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import SealMismatch, digest, read_seal, verify, write_seal


def _load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="prereg-seal",
                                 description="Seal acceptance criteria before measuring.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("seal", help="seal a specification file")
    s.add_argument("spec", help="JSON file holding the acceptance specification")
    s.add_argument("-o", "--out", default=None, help="seal path (default: <spec>.seal.json)")
    s.add_argument("--note", default="", help="free-text note recorded in the seal")

    c = sub.add_parser("check", help="check a specification against its seal")
    c.add_argument("spec")
    c.add_argument("seal", nargs="?", default=None)
    c.add_argument("--format", choices=("text", "json", "jsonl", "sarif", "junit"),
                   default="text")
    c.add_argument("-o", "--output", default="")

    d = sub.add_parser("show", help="print the digest of a specification")
    d.add_argument("spec")

    an = sub.add_parser("anchor",
                        help="record where a seal digest was published, so 'sealed' "
                             "can become 'sealed before'")
    an.add_argument("seal", help="the seal file, or a bare 64-hex digest")
    an.add_argument("locator", help="owner/repo@sha, a commit URL, or any URL")
    an.add_argument("--kind", choices=("github-commit", "url"), default="github-commit")
    an.add_argument("--note", default="")
    an.add_argument("-o", "--out", default="", help="write the record here")

    va = sub.add_parser("verify-anchor",
                        help="go and check the digest really is where the record says")
    va.add_argument("record")
    va.add_argument("--offline", action="store_true",
                    help="do not touch the network; the result is then UNANCHORED")
    va.add_argument("--format", choices=("text", "json", "jsonl", "sarif", "junit"),
                    default="text")
    va.add_argument("-o", "--output", default="")

    a = ap.parse_args(argv if argv is not None else sys.argv[1:])

    if a.cmd == "seal":
        out = a.out or (str(a.spec) + ".seal.json")
        sealed = write_seal(out, _load(a.spec), note=a.note)
        print(f"sealed {a.spec}\n  digest {sealed['digest']}\n  wrote  {out}")
        return 0

    if a.cmd == "check":
        from .report import emit
        seal_path = a.seal or (str(a.spec) + ".seal.json")
        res = {"outcome": "SEALED", "ok": True, "errors": []}
        try:
            verify(_load(a.spec), read_seal(seal_path))
            res["digest"] = digest(_load(a.spec))
        except SealMismatch as e:
            res = {"outcome": "MISMATCH", "ok": False, "errors": [str(e)]}
        except FileNotFoundError:
            res = {"outcome": "UNSEALED", "ok": False, "errors": [
                f"no seal at {seal_path} — refusing to pass an unsealed check"]}
        if a.format != "text":
            out = emit(res, a.format, source=str(a.spec))
            if a.output:
                Path(a.output).write_text(out + "\n", encoding="utf-8")
            else:
                print(out)
        elif res["ok"]:
            print(f"OK  {a.spec} matches {seal_path}")
        else:
            print(("SEAL MISMATCH" if res["outcome"] == "MISMATCH" else "UNSEALED"),
                  file=sys.stderr)
            for e in res["errors"]:
                print(f"  {e}", file=sys.stderr)
        return 0 if res["ok"] else 1

    if a.cmd == "anchor":
        from .anchor import make_anchor
        raw = str(a.seal)
        dg = raw if len(raw) == 64 and all(c in "0123456789abcdef" for c in raw.lower()) \
            else read_seal(raw)["digest"]
        rec = make_anchor(dg, a.kind, a.locator, note=a.note)
        out = a.out or "anchor.json"
        Path(out).write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
        print(f"wrote {out}")
        print("This record asserts nothing yet. Run `prereg-seal verify-anchor` — "
              "the claim is only worth what the check says.")
        return 0

    if a.cmd == "verify-anchor":
        from .anchor import describe, verify_anchor
        res = verify_anchor(_load(a.record), allow_network=not a.offline)
        if a.format != "text":
            from .report import emit
            out = emit(res, a.format, source=str(a.record))
            if a.output:
                Path(a.output).write_text(out + "\n", encoding="utf-8")
            else:
                print(out)
        else:
            print(describe(res))
        return {"ANCHORED": 0, "REFUTED": 1}.get(res["status"], 4)

    print(digest(_load(a.spec)))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
