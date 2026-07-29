# Troubleshooting — prereg-seal

## `SEAL MISMATCH` after an edit I thought was cosmetic

The digest is over the canonical form: key order and whitespace are normalised, so those are safe.
A **value** change is not, and neither is adding or removing a key.

`1`, `1.0` and `true` are *different* values. If your specification is generated, make sure the
generator is deterministic about numeric types.

**To see what moved:** `prereg-seal show spec.json` prints the current digest; compare against the
one in the seal file.

## `no seal at … — refusing to pass an unsealed check`

Working as intended, and it exits non-zero. A check with no seal establishes nothing, so reporting
it green would be worse than reporting nothing.

**Fix:** run `prereg-seal seal` once and commit the result.

## `verify-anchor` returns `UNANCHORED`, exit 4

An abstention, not a failure. One of:

- **The host was unreachable.** The local claim is never accepted in its place.
- **`--offline` was passed.** Then `UNANCHORED` is the only possible answer.
- **The digest is published, but the host reports no time.** The `url` kind establishes
  publication and not a bound, and says so.

## `cannot read '…' as a GitHub commit`

You passed a branch or tag. `owner/repo@main` is refused because `main` moves — an anchor that can
be rewritten anchors nothing. Use a full commit sha.

## `verify-anchor` returns `REFUTED`

The locator exists and the digest is not in it. Either the wrong commit, or the digest was never
published there. This is evidence, not absence of it, which is why it is `REFUTED` and not
`UNANCHORED`.

## The anchor's timestamp looks wrong

It probably is. A commit's committer date is supplied by whoever made the commit and is trivially
forgeable; the tool reports it as *the host's record of a claim* and says so in its own output.

For a genuinely independent timestamp you want a service that attests to what it saw and when.
This module does not pretend to be one.

## Tests are skipped with "network unavailable"

One test hits github.com and skips when it cannot. Everything else runs offline with an injected
fetcher.

---

*Still stuck? Open an issue with the command and the seal file.*
