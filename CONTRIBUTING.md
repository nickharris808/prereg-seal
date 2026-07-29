# Contributing to prereg-seal

This package is part of [certified-oss][p]. **The portfolio-wide guide is
[CONTRIBUTING.md][c] and it is the one to read** — it covers the rules that are not negotiable,
how to install packages that depend on each other, and what kind of contribution is most wanted
(a forgery this project fails to catch).

What is specific to this package:

- **A missing seal is not a pass.** `check` exits non-zero when the seal is absent, and every
  emitter renders that as a failure.
- **An anchor record never asserts itself.** `verify_anchor` with no network returns `UNANCHORED`
  however confidently the record describes itself, and a mutable ref is refused.

## Working on it

```bash
pip install -e ".[test]"
pytest -q
ruff check .
```

## Licence

Apache-2.0. By contributing you agree your contribution is licensed the same way.

[p]: https://github.com/nickharris808/certified-oss
[c]: https://github.com/nickharris808/certified-oss/blob/main/CONTRIBUTING.md
