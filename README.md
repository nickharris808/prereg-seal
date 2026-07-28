# prereg-seal

[![ci](https://github.com/nickharris808/prereg-seal/actions/workflows/ci.yml/badge.svg)](https://github.com/nickharris808/prereg-seal/actions/workflows/ci.yml)
![license](https://img.shields.io/badge/license-Apache--2.0-blue)
![python](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)
![dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)
![tests](https://img.shields.io/badge/tests-17%20passing-brightgreen)

**Seal your acceptance criteria before you measure, so nobody — including you — can move the
goalposts afterward.**

This is not a fraud-detection tool. The failure it prevents is ordinary and mostly honest: a
threshold gets adjusted once a result is in, and six months later everyone sincerely remembers it
the other way round. A seal makes the ordering a checkable fact instead of a memory.

Dependency-free. One file. Under 200 lines.

## Install

> **Not yet on PyPI.** Install from the repository — it works exactly the same:
>
> ```
> pip install git+https://github.com/nickharris808/prereg-seal.git
> ```

```
pip install prereg-seal
```

## 30-second quickstart

```python
import prereg_seal as P

spec = {
    "criterion": "worst-corner edge placement within budget",
    "threshold_nm": 3.0,
    "corners": ["nominal", "defocus+", "defocus-", "dose+", "dose-"],
    "protocol": "held-out clips, no reuse",
}

sealed = P.seal(spec)          # do this BEFORE you run anything
print(sealed["digest"])        # publish this; it does not reveal the spec

# ... run the experiment ...

P.verify(spec, sealed)         # raises SealMismatch if the criteria moved
```

Loosen the threshold after the fact and it is caught:

```python
import prereg_seal as P

spec = {"criterion": "worst-corner edge placement within budget", "threshold_nm": 3.0}
sealed = P.seal(spec)

doctored = dict(spec, threshold_nm=5.0)          # loosened after the fact
try:
    P.verify(doctored, sealed)                   # this RAISES — it does not return a flag
except P.SealMismatch as e:
    print(e)
```

```
specification does not match its seal (sealed 817659d0d172891d…, recomputed ba3bbfc3422636dd…) — the criteria changed after sealing, or the seal is not the one for these criteria
```

Use `P.matches(spec, sealed)` if you want a boolean instead of an exception.

## The second failure direction

Catching a doctored spec is the easy half. The harder case is someone doctoring the spec *and*
minting a fresh seal to match. `bind()` covers the result and the seal **together**, so the swap
stops recomputing:

```python
import prereg_seal as P

spec = {"criterion": "worst-corner edge placement within budget", "threshold_nm": 3.0}
result = {"measured_nm": 2.4, "verdict": "PASS"}

bound = P.bind(result, P.seal(spec))
P.verify_bound(bound, spec)                        # honest case: returns quietly

doctored = dict(spec, threshold_nm=5.0)
forged = dict(bound, seal=P.seal(doctored))        # a seal that genuinely matches the doctored spec
try:
    P.verify_bound(forged, doctored)
except P.SealMismatch as e:
    print(e)
```

```
seal binding does not recompute — the result or the seal was altered after binding
```

## In CI

```yaml
- uses: nickharris808/prereg-seal/action@v1
  with:
    spec: bench/acceptance.json
```

Or directly:

```
prereg-seal seal bench/acceptance.json     # once, before the first run
prereg-seal check bench/acceptance.json    # in CI, forever after
```

`check` exits non-zero on mismatch, and exits non-zero when the seal is **missing** — an unsealed
evaluation is the condition this tool exists to prevent, so it is a failure, not a skip.

## Use it against yourself

The most valuable application is the one nobody enjoys: seal your own benchmark criteria, publish
the digest with the preprint, and let reviewers check it. The second most valuable is sealing
criteria you send to *someone else* — `P.seal(spec)` reveals nothing about the spec, so you can
publish a seal before a blind evaluation and disclose the criteria after.

## What it cannot do

It proves a specification is the one that was sealed. It **cannot prove when** the seal was made —
a digest carries no time. For that you need an external anchor: a commit in a public repository, a
timestamping service, a preprint. Anchor deliberately; the seal is the easy half.

It also cannot tell you whether your criteria were any *good*. Sealing a bad threshold just means
you are honestly stuck with a bad threshold.

## Related

`prereg-seal` was factored out of a certificate-verification toolchain, where a seal binds the
acceptance criteria into the certificate chain itself. If you need that — machine-checkable
certificates whose verdicts a third party can re-derive — see `lcert-verify`. This package is
useful entirely on its own and has no dependency on it.

What this tool cannot do is tell you whether the criteria were *met*. Sealing a threshold fixes it
in time; establishing that a physical artifact satisfies it needs sound enclosures over physical
models, which is a separate closed product and not in these packages.

## License

Apache-2.0.

---

## The rest of the toolkit

One idea, six pieces: **a recorded verdict is a claim to be checked, never an input to be trusted.**

| | |
|---|---|
| [**lcert-verify**](https://github.com/nickharris808/lcert-verify) | Re-derive a manufacturing certificate's verdict. Stdlib only. |
| [**equiv-receipt**](https://github.com/nickharris808/equiv-receipt) | Prove two circuits equivalent, with a receipt anyone can re-check. |
| [**prereg-seal**](https://github.com/nickharris808/prereg-seal) | Seal acceptance criteria before you measure. |
| [**cert-atlas**](https://github.com/nickharris808/cert-atlas) | 21 labelled forgeries and a metric no degenerate verifier can win. |
| [**certified-mcp**](https://github.com/nickharris808/certified-mcp) | The above, as tools your AI agent can call. |
| [**lcert-verify-web**](https://github.com/nickharris808/lcert-verify-web) | The verifier in a browser. Nothing uploaded. |

**Try it now, no install:** [🔏 the verifier Space](https://huggingface.co/spaces/nickh007/cert-verifier) ·
**Browse the forgeries:** [📊 the atlas dataset](https://huggingface.co/datasets/nickh007/cert-atlas)

### Where the free edition stops

Everything here **checks**. None of it **produces** a certificate that is physically meaningful —
that needs sound enclosures over real process models, which is a separate commercial product. If
you need certificates rather than a way to check them, that is the conversation to have.
