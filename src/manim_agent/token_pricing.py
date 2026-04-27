"""Local token pricing helpers.

Prices are maintained in ``model_pricing.json`` as CNY per million tokens.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

PRICING_PATH = Path(__file__).with_name("model_pricing.json")


@lru_cache(maxsize=1)
def load_model_pricing() -> dict[str, Any]:
    return json.loads(PRICING_PATH.read_text(encoding="utf-8"))


def resolve_pricing_model(model_name: str | None) -> str | None:
    if not model_name:
        return None

    pricing = load_model_pricing()
    models = pricing.get("models", {})
    if model_name in models:
        return model_name

    normalized = model_name.strip().lower()
    aliases = pricing.get("aliases", {})
    if normalized in aliases:
        return aliases[normalized]

    compact = normalized.replace("_", "-")
    return aliases.get(compact)


def infer_pricing_model_name(
    model_name: str | None,
    model_usage: dict[str, Any] | None = None,
) -> str | None:
    """Choose the best model name for local pricing lookup."""
    if resolve_pricing_model(model_name):
        return model_name

    if isinstance(model_usage, dict) and len(model_usage) == 1:
        candidate = next(iter(model_usage.keys()))
        if resolve_pricing_model(candidate):
            return candidate

    return model_name


def _pick_price_entry(model_name: str, context_tokens: int | None) -> dict[str, Any] | None:
    pricing = load_model_pricing()
    model_key = resolve_pricing_model(model_name)
    if not model_key:
        return None
    entry = pricing.get("models", {}).get(model_key)
    if not isinstance(entry, dict):
        return None

    tiers = entry.get("tiers")
    if not isinstance(tiers, list):
        return entry

    context = context_tokens or 0
    for tier in tiers:
        if not isinstance(tier, dict):
            continue
        minimum = tier.get("context_tokens_min") or 0
        maximum = tier.get("context_tokens_max")
        if context >= minimum and (maximum is None or context < maximum):
            return tier
    return tiers[-1] if tiers and isinstance(tiers[-1], dict) else None


def _first_int(usage: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = usage.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
    return None


def normalize_token_usage(usage: dict[str, Any] | None) -> dict[str, int | None]:
    usage = usage or {}
    input_tokens = _first_int(
        usage,
        (
            "input_tokens",
            "input_token_count",
            "prompt_tokens",
            "prompt_token_count",
        ),
    )
    output_tokens = _first_int(
        usage,
        ("output_tokens", "output_token_count", "completion_tokens", "completion_token_count"),
    )
    cache_read_tokens = _first_int(
        usage,
        (
            "cache_read_tokens",
            "cache_read_input_tokens",
            "cached_tokens",
            "cache_hit_tokens",
        ),
    )
    cache_write_tokens = _first_int(
        usage,
        ("cache_write_tokens", "cache_creation_tokens", "cache_creation_input_tokens"),
    )
    total_tokens = _first_int(usage, ("total_tokens", "total_token_count"))

    if total_tokens is None:
        total_tokens = sum(
            value or 0
            for value in (input_tokens, output_tokens, cache_read_tokens, cache_write_tokens)
        ) or None

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_write_tokens": cache_write_tokens,
        "total_tokens": total_tokens,
    }


def estimate_token_cost_cny(
    model_name: str | None,
    usage: dict[str, Any] | None,
) -> dict[str, Any]:
    normalized = normalize_token_usage(usage)
    resolved_model = resolve_pricing_model(model_name)
    price = _pick_price_entry(resolved_model or "", normalized["total_tokens"])
    if not resolved_model or not price:
        return {
            **normalized,
            "model_name": model_name,
            "pricing_model": None,
            "estimated_cost_cny": None,
            "cost_estimate_note": "pricing_not_found",
        }

    input_tokens = normalized["input_tokens"]
    output_tokens = normalized["output_tokens"]
    cache_read_tokens = normalized["cache_read_tokens"]
    cache_write_tokens = normalized["cache_write_tokens"]
    total_tokens = normalized["total_tokens"]

    has_breakdown = any(
        value is not None
        for value in (input_tokens, output_tokens, cache_read_tokens, cache_write_tokens)
    )
    if not has_breakdown and total_tokens is not None:
        input_tokens = total_tokens

    def part(tokens: int | None, key: str) -> float:
        rate = price.get(key)
        if tokens is None or not isinstance(rate, (int, float)):
            return 0.0
        return tokens * float(rate) / 1_000_000

    estimated = (
        part(input_tokens, "input")
        + part(output_tokens, "output")
        + part(cache_read_tokens, "cache_read")
        + part(cache_write_tokens, "cache_write")
    )

    return {
        **normalized,
        "input_tokens": input_tokens,
        "model_name": model_name,
        "pricing_model": resolved_model,
        "estimated_cost_cny": estimated,
        "cost_estimate_note": "usage_breakdown" if has_breakdown else "total_tokens_as_input",
    }


def estimate_result_cost_cny(
    model_name: str | None,
    usage: dict[str, Any] | None,
    model_usage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Estimate CNY cost for a Claude Agent SDK result message."""
    inferred_model = infer_pricing_model_name(model_name, model_usage)
    return estimate_token_cost_cny(inferred_model, usage)
