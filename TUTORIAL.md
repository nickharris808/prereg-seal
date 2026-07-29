# Tutorial — prereg-seal

Fix your acceptance criteria before you measure, so nobody — including you — can move them
afterwards.

## Install

```bash
pip install "prereg-seal @ git+https://github.com/nickharris808/prereg-seal.git@main"
```

## 1. Seal, once, before the first run

```bash
prereg-seal seal bench/acceptance.json
# sealed bench/acceptance.json
#   digest 4f2a…
#   wrote  bench/acceptance.json.seal.json
```

Commit both. The seal is a digest over the **canonical** form of your specification, so key order
and whitespace do not matter and a value change does.

## 2. Check it on every run

```bash
prereg-seal check bench/acceptance.json
# OK  bench/acceptance.json matches bench/acceptance.json.seal.json
```

Non-zero if the specification moved — **and non-zero if the seal is missing.** An unsealed check
establishes nothing, and passing it would be worse than saying nothing at all.

## 3. In code

```python
import prereg_seal as P

seal = P.seal({"epe_nm": {"max": 2.0}})
P.verify(spec, seal)                 # raises SealMismatch if it moved
P.guard(spec, seal)                  # same, as a context manager around your run
```

`bind` and `verify_bound` cover the case where a *result* must be tied to the specification it was
judged against, so a doctored specification plus a matching seal is still caught.

## 4. Turning "sealed" into "sealed *before*"

A digest carries no time. Nothing about a hash says when it was computed, and the failure
preregistration prevents is writing the criteria **after** seeing the result.

There is no offline trick for this: establishing that something existed before a moment needs a
witness you do not control. So this does not invent a bound — it records where the digest was
published and goes and looks.

```bash
# publish the digest somewhere public — a commit message, a log, a preprint — then:
prereg-seal anchor bench/acceptance.json.seal.json nickharris808/myrepo@0123abc -o anchor.json
prereg-seal verify-anchor anchor.json
```

| | Meaning | Exit |
|---|---|---|
| `ANCHORED` | the digest really is at the locator, and the host reports a time | 0 |
| `REFUTED` | the locator exists and the digest is **not** there | 1 |
| `UNANCHORED` | unreachable, or no time reported — **an abstention** | 4 |

Two refusals worth knowing:

- **It never accepts the record's own claim.** Run `--offline` against a record that says
  `"status": "ANCHORED"` and the answer is still `UNANCHORED`. A record that asserted itself would
  establish exactly nothing.
- **A mutable ref is not an anchor.** `owner/repo@main` is rejected, because `main` moves. Only a
  full commit sha.

And one thing it is blunt about: the time is the **host's word**, and the output says so. A
commit's committer date is set by whoever made the commit, so it is GitHub's record of a claim,
not an independent attestation.

## 5. In CI

```bash
prereg-seal check spec.json --format sarif -o seal.sarif
prereg-seal verify-anchor anchor.json --format junit -o results.xml
```

A **missing** seal and an **`UNANCHORED`** result both render as failures with the reason
attached, because neither SARIF nor JUnit has a state for "nothing was established".

---

*See [CLI.md](CLI.md), [TROUBLESHOOTING.md](TROUBLESHOOTING.md), and
[certified-oss](https://github.com/nickharris808/certified-oss).*
