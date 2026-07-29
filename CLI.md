# CLI reference — `prereg-seal`

**The command listings below are generated.** Run `python gen_cli_docs.py` after changing any
argument; a test fails if they are stale.

## Top level

```
usage: prereg-seal [-h] {seal,check,show,anchor,verify-anchor} ...

Seal acceptance criteria before measuring.

positional arguments:
  {seal,check,show,anchor,verify-anchor}
    seal                seal a specification file
    check               check a specification against its seal
    show                print the digest of a specification
    anchor              record where a seal digest was published, so 'sealed'
                        can become 'sealed before'
    verify-anchor       go and check the digest really is where the record
                        says

options:
  -h, --help            show this help message and exit
```

## `prereg-seal seal`

```
usage: prereg-seal seal [-h] [-o OUT] [--note NOTE] spec

positional arguments:
  spec               JSON file holding the acceptance specification

options:
  -h, --help         show this help message and exit
  -o OUT, --out OUT  seal path (default: <spec>.seal.json)
  --note NOTE        free-text note recorded in the seal
```

## `prereg-seal check`

```
usage: prereg-seal check [-h] [--format {text,json,jsonl,sarif,junit}]
                         [-o OUTPUT]
                         spec [seal]

positional arguments:
  spec
  seal

options:
  -h, --help            show this help message and exit
  --format {text,json,jsonl,sarif,junit}
  -o OUTPUT, --output OUTPUT
```

## `prereg-seal show`

```
usage: prereg-seal show [-h] spec

positional arguments:
  spec

options:
  -h, --help  show this help message and exit
```

## `prereg-seal anchor`

```
usage: prereg-seal anchor [-h] [--kind {github-commit,url}] [--note NOTE]
                          [-o OUT]
                          seal locator

positional arguments:
  seal                  the seal file, or a bare 64-hex digest
  locator               owner/repo@sha, a commit URL, or any URL

options:
  -h, --help            show this help message and exit
  --kind {github-commit,url}
  --note NOTE
  -o OUT, --out OUT     write the record here
```

## `prereg-seal verify-anchor`

```
usage: prereg-seal verify-anchor [-h] [--offline]
                                 [--format {text,json,jsonl,sarif,junit}]
                                 [-o OUTPUT]
                                 record

positional arguments:
  record

options:
  -h, --help            show this help message and exit
  --offline             do not touch the network; the result is then
                        UNANCHORED
  --format {text,json,jsonl,sarif,junit}
  -o OUTPUT, --output OUTPUT
```

## Exit codes

Every command in this toolkit uses the same taxonomy, so a caller can branch on it:

| Code | Meaning |
|---|---|
| `0` | verified / sealed / equivalent — the check was made and it stood |
| `1` | refuted by re-derivation |
| `2` | refuted on integrity: fingerprint, manifest, root, commitment |
| `3` | vacuous — nothing was certified |
| `4` | **abstained** — the evidence for an assertion is absent |
| `5` | usage error — not a verdict at all |

`4` is the one worth wiring up. It is not a failure of the artifact; it means nothing was
established, and treating it as a pass is the failure this toolkit exists to prevent.

---

*Part of [certified-oss](https://github.com/nickharris808/certified-oss).*
