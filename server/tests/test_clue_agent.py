"""Clue agent: propose → audit → retry → safe fallback, never force-pass."""

from server.ai.clue_agent import (
    MAX_RETRIES,
    ClueProposal,
    ClueRequest,
    produce_clue,
    safe_fallback,
)
from server.audit import audit_clue
from server.embeddings import stub_embed
from server.tests.helpers import band_embed


class scripted_propose:
    """A propose callable returning the given texts in order (repeating the
    last), counting how many times it was invoked."""

    def __init__(self, texts: list[str]):
        self.texts = texts
        self.calls = 0

    async def __call__(self, system: str, user: str) -> ClueProposal:
        i = min(self.calls, len(self.texts) - 1)
        self.calls += 1
        return ClueProposal(text=self.texts[i], tokens_in=10, tokens_out=3)


def passing_embed(secret: str):
    """Embed so that the literal clue 'breakfast' lands inside the easy band."""
    return band_embed(secret, "breakfast", 0.4)


class TestProduceClue:
    async def test_first_proposal_passes(self):
        req = ClueRequest("civilian", "Food", "easy", "pancake")
        propose = scripted_propose(["breakfast"])
        result = await produce_clue(req, propose, passing_embed("pancake"))
        assert result.text == "breakfast"
        assert result.retries == 0
        assert not result.fell_back
        assert result.tokens_in == 10 and result.tokens_out == 3

    async def test_retries_then_passes(self):
        req = ClueRequest("civilian", "Food", "easy", "pancake")
        # First two proposals leak, third is clean and in-band.
        propose = scripted_propose(["pancake", "lake", "breakfast"])
        result = await produce_clue(req, propose, passing_embed("pancake"))
        assert result.text == "breakfast"
        assert result.retries == 2
        assert not result.fell_back
        assert propose.calls == 3

    async def test_falls_back_after_max_retries(self):
        req = ClueRequest("civilian", "Food", "easy", "pancake")
        # Always leaks: should exhaust retries and fall back to a safe clue.
        propose = scripted_propose(["pancake"])
        result = await produce_clue(req, propose, stub_embed)
        assert result.fell_back
        assert result.retries == MAX_RETRIES
        assert propose.calls == MAX_RETRIES + 1
        # The fallback never contains the secret word — fail-closed.
        assert "pancake" not in result.text.lower()

    async def test_fallback_is_leak_safe(self):
        clue, _ = safe_fallback("Food", "pancake", stub_embed)
        report = audit_clue(clue, "pancake", "easy", stub_embed)
        leaks = [v for v in report.violations if "contains" in v or "form of" in v or "rhymes" in v]
        assert leaks == []

    async def test_imposter_never_sees_word(self):
        # The imposter request carries no secret word; produce_clue must cope.
        req = ClueRequest("imposter", "Food", "easy", None)
        propose = scripted_propose(["breakfast"])
        result = await produce_clue(req, propose, passing_embed(""))
        assert result.text  # produced something legal
