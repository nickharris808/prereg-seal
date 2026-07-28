# Contributing

`prereg-seal` is intentionally tiny. The whole implementation is one file you can
read in ten minutes, and it should stay that way.

## The rules

1. **No dependencies.** Standard library only. This tool gets installed into
   other people's CI; it must never drag anything in.
2. **The canonical form is frozen.** `canonicalize()` defines what "the same
   specification" means. Changing it invalidates every seal anyone has ever
   written. If it must change, that is a new `FORMAT` string, not an edit.
3. **Fail closed.** A missing seal, an unreadable seal, or an unknown format is
   a failure, never a pass. New code paths must preserve this.
4. **Every check needs a tamper test**, and a matching *revert* test showing the
   check goes green again. A check that can only fail proves nothing.

## Running the tests

```
pip install -e ".[test]"
pytest
```

## Scope

This tool proves a specification is the one that was sealed. It cannot prove
*when* it was sealed — that needs an external anchor (a commit in a public repo,
a timestamping service, a preprint). Issues asking for trusted timestamping are
welcome; issues asking the seal to imply time on its own will be closed.
