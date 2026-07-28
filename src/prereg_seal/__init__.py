"""prereg-seal — seal an acceptance specification before you measure."""
from .anchor import (  # noqa: F401
    ANCHORED, ANCHOR_FORMAT, REFUTED, UNANCHORED, AnchorError, describe,
    make_anchor, verify_anchor,
)
from .core import (  # noqa: F401
    DOMAIN, FORMAT, SealMismatch, bind, canonicalize, digest, guard, matches,
    read_seal, seal, verify, verify_bound, write_seal,
)

__version__ = "1.0.0"
__all__ = ["FORMAT", "DOMAIN", "SealMismatch", "canonicalize", "digest", "seal",
           "verify", "matches", "bind", "verify_bound", "write_seal", "read_seal",
           "guard", "make_anchor", "verify_anchor", "describe", "AnchorError",
           "ANCHOR_FORMAT", "ANCHORED", "REFUTED", "UNANCHORED", "__version__"]
