"""Clue agent: propose → audit → retry → safe fallback, never force-pass."""

from server.ai.clue_agent import (
    MAX_RETRIES,
    ClueProposal,
    ClueRequest,
    produce_clue,
    safe_fallback,
)
from server.audit import DIFFICULTY_BANDS, audit_clue
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
    low, high = DIFFICULTY_BANDS["easy"]
    return band_embed(secret, "breakfast", (low + high) / 2)


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

    async def test_imposter_prompt_omits_word_but_audit_uses_it(self):
        # The imposter's prompt must never contain the word, but the audit
        # still checks the real word. A clean proposal should NOT fall back.
        req = ClueRequest("imposter", "Food", "easy", "pancake")
        seen_prompts: list[str] = []

        async def spy_propose(system: str, user: str):
            seen_prompts.append(user)
            return ClueProposal(text="breakfast", tokens_in=4, tokens_out=2)

        result = await produce_clue(req, spy_propose, passing_embed("pancake"))
        assert not result.fell_back
        assert result.text == "breakfast"
        assert all("pancake" not in p.lower() for p in seen_prompts)

    async def test_imposter_does_not_autofallback(self):
        # Regression: an imposter (no word in prompt) used to fail every audit
        # because the empty secret matched as containment -> always "no comment".
        req = ClueRequest("imposter", "Food", "easy", "pancake")
        result = await produce_clue(req, scripted_propose(["breakfast"]), passing_embed("pancake"))
        assert not result.fell_back
