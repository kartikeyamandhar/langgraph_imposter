from server.cost import compute_cost


def test_known_model_cost():
    # Haiku-class: $1/Mtok in, $5/Mtok out.
    assert compute_cost("claude-haiku-4-5-20251001", 1_000_000, 0) == 1.0
    assert compute_cost("claude-haiku-4-5-20251001", 0, 1_000_000) == 5.0


def test_unknown_model_uses_default():
    assert compute_cost("mystery", 1_000_000, 0) == 1.0


def test_env_override(monkeypatch):
    monkeypatch.setenv("PRICE_IN_PER_MTOK", "2")
    monkeypatch.setenv("PRICE_OUT_PER_MTOK", "10")
    assert compute_cost("anything", 1_000_000, 1_000_000) == 12.0


def test_zero_tokens():
    assert compute_cost("claude-haiku-4-5-20251001", 0, 0) == 0.0
