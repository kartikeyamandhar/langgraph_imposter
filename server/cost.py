"""Token-cost computation for telemetry. Prices are per-million-token USD,
keyed by model id, overridable via env (PRICE_<suffix>) without code change.
Defaults track a cheap fast model class; calibrate against the bill."""

import os

# (input_per_mtok, output_per_mtok) in USD. Representative defaults.
PRICING: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-8": (15.00, 75.00),
}
DEFAULT_PRICING = (1.00, 5.00)


def price_for(model: str) -> tuple[float, float]:
    env_in = os.environ.get("PRICE_IN_PER_MTOK")
    env_out = os.environ.get("PRICE_OUT_PER_MTOK")
    if env_in and env_out:
        return float(env_in), float(env_out)
    return PRICING.get(model, DEFAULT_PRICING)


def compute_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    p_in, p_out = price_for(model)
    return round((tokens_in * p_in + tokens_out * p_out) / 1_000_000, 6)
