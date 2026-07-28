"""``prereg-seal seal|check|show`` — a three-verb CLI."""
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

    d = sub.add_parser("show", help="print the digest of a specification")
    d.add_argument("spec")

    a = ap.parse_args(argv if argv is not None else sys.argv[1:])

    if a.cmd == "seal":
        out = a.out or (str(a.spec) + ".seal.json")
        sealed = write_seal(out, _load(a.spec), note=a.note)
        print(f"sealed {a.spec}\n  digest {sealed['digest']}\n  wrote  {out}")
        return 0

    if a.cmd == "check":
        seal_path = a.seal or (str(a.spec) + ".seal.json")
        try:
            verify(_load(a.spec), read_seal(seal_path))
        except SealMismatch as e:
            print(f"SEAL MISMATCH\n  {e}", file=sys.stderr)
            return 1
        except FileNotFoundError:
            print(f"no seal at {seal_path} — refusing to pass an unsealed check",
                  file=sys.stderr)
            return 1
        print(f"OK  {a.spec} matches {seal_path}")
        return 0

    print(digest(_load(a.spec)))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
