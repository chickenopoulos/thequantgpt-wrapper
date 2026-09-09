"""Seed formula packs for language-steered alpha mining."""

from __future__ import annotations

from typing import Any

SEED_PACKS: dict[str, list[dict[str, Any]]] = {
    "leftover": [
        {
            "id": "A_LO1",
            "expr": "cs_zscore(intra)",
            "description": "Intraday leftover: names that closed weak vs the open, cross-sectionally.",
            "tags": ["leftover", "mean_reversion"],
        },
        {
            "id": "A_LO2",
            "expr": "-cs_rank(ts_delta(close, 1))",
            "description": "One-bar reversal of close.",
            "tags": ["leftover", "mean_reversion"],
        },
        {
            "id": "A_LO3",
            "expr": "-cs_zscore(ts_mean(ret, 5))",
            "description": "Five-day return reversal.",
            "tags": ["leftover", "mean_reversion"],
        },
    ],
    "volume": [
        {
            "id": "A_VP1",
            "expr": "-cs_zscore(ts_corr(close, volume, 20))",
            "description": "Price-volume divergence: trend without volume confirmation.",
            "tags": ["volume", "confirmation"],
        },
        {
            "id": "A_VP2",
            "expr": "cs_zscore(sign(ts_delta(close, 1)) * ts_zscore(volume, 20))",
            "description": "Volume surprise in the direction of the last close change.",
            "tags": ["volume", "confirmation"],
        },
        {
            "id": "A_VP3",
            "expr": "-cs_rank(ts_corr(ret, volume, 10))",
            "description": "Short-horizon return-volume correlation, inverted.",
            "tags": ["volume"],
        },
    ],
    "wick": [
        {
            "id": "A_WK1",
            "expr": "cs_zscore(div(upper_wick, rng))",
            "description": "Upper wick as a fraction of the bar range (selling pressure).",
            "tags": ["wick"],
        },
        {
            "id": "A_WK2",
            "expr": "-cs_zscore(div(lower_wick, rng))",
            "description": "Lower wick as a fraction of the bar range (buying pressure), inverted.",
            "tags": ["wick"],
        },
    ],
    "momentum": [
        {
            "id": "A_MO1",
            "expr": "cs_rank(ts_sum(ret, 20))",
            "description": "Twenty-day residual momentum. Drop this if the user said not momentum.",
            "tags": ["momentum"],
        },
        {
            "id": "A_MO2",
            "expr": "cs_zscore(ts_delta(close, 5))",
            "description": "Five-day price change. Usually momentum in disguise.",
            "tags": ["momentum"],
        },
    ],
}

DEFAULT_PACKS = ("leftover", "volume", "wick", "momentum")


def seeds_for_packs(packs: list[str] | None = None) -> list[dict[str, Any]]:
    chosen = list(packs) if packs else list(DEFAULT_PACKS)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pack in chosen:
        key = str(pack).strip().lower()
        if key not in SEED_PACKS:
            raise ValueError(f"Unknown seed pack {pack!r}. Known: {sorted(SEED_PACKS)}")
        for item in SEED_PACKS[key]:
            if item["id"] in seen:
                continue
            seen.add(item["id"])
            out.append(dict(item))
    return out
