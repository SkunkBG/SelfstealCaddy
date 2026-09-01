"""Deterministic pseudo-random source.

Deliberately does NOT use ``random.Random``: CPython's Mersenne Twister
seeding and ``_randbelow`` are stable in practice but are not a documented
compatibility guarantee, and a generated site must be reproducible byte for
byte across Python versions and distributions.  A SHA-256 counter stream is
specified behaviour of hashlib and therefore safe.

``derive()`` is the important part of the API.  Every subsystem draws from its
own named substream, so adding a draw to (say) the favicon generator cannot
shift the brand name or the endpoint list of an existing installation.
"""

from __future__ import annotations

import hashlib
from typing import Iterable, List, Sequence, TypeVar

T = TypeVar("T")

_MASK64 = (1 << 64) - 1


class SeededRandom:
    """A reproducible random source keyed by an arbitrary seed string."""

    __slots__ = ("_seed", "_counter")

    def __init__(self, seed: str) -> None:
        self._seed = seed
        self._counter = 0

    @property
    def seed(self) -> str:
        return self._seed

    def derive(self, label: str) -> "SeededRandom":
        """Return an independent substream bound to ``label``."""
        return SeededRandom(f"{self._seed}\x1f{label}")

    # ---- primitives -----------------------------------------------------

    def _next_u64(self) -> int:
        payload = f"{self._seed}\x1e{self._counter}".encode("utf-8")
        self._counter += 1
        return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") & _MASK64

    def below(self, n: int) -> int:
        """Uniform integer in ``[0, n)``, rejection-sampled to avoid modulo bias."""
        if n <= 0:
            raise ValueError("below() requires n > 0")
        if n == 1:
            return 0
        limit = _MASK64 - (_MASK64 % n)
        while True:
            value = self._next_u64()
            if value < limit:
                return value % n

    def between(self, low: int, high: int) -> int:
        """Uniform integer in the inclusive range ``[low, high]``."""
        if high < low:
            raise ValueError("between() requires high >= low")
        return low + self.below(high - low + 1)

    def chance(self, numerator: int, denominator: int = 100) -> bool:
        return self.below(denominator) < numerator

    def choice(self, seq: Sequence[T]) -> T:
        if not seq:
            raise ValueError("choice() requires a non-empty sequence")
        return seq[self.below(len(seq))]

    def shuffled(self, seq: Iterable[T]) -> List[T]:
        items = list(seq)
        for i in range(len(items) - 1, 0, -1):
            j = self.below(i + 1)
            items[i], items[j] = items[j], items[i]
        return items

    def sample(self, seq: Sequence[T], k: int) -> List[T]:
        """``k`` distinct items, order randomised.  Clamped to ``len(seq)``."""
        return self.shuffled(seq)[: max(0, min(k, len(seq)))]

    def subset(self, seq: Sequence[T], low: int, high: int) -> List[T]:
        return self.sample(seq, self.between(low, high))

    def weighted(self, pairs: Sequence[tuple]) -> T:
        """Pick from ``[(item, weight), ...]`` with integer weights."""
        total = sum(int(w) for _, w in pairs)
        if total <= 0:
            raise ValueError("weighted() requires a positive total weight")
        roll = self.below(total)
        upto = 0
        for item, weight in pairs:
            upto += int(weight)
            if roll < upto:
                return item
        return pairs[-1][0]


def seed_from(*parts: str) -> str:
    """Canonical installation seed.

    Hashing rather than concatenating keeps the seed a fixed length and stops
    a long domain from dominating the substream labels.
    """
    joined = "\x1f".join(p.strip().lower() for p in parts if p)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()
