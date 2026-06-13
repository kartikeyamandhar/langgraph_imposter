"""The fail-closed audit is the safety boundary. These tests pin every reject
path and prove the band is enforced — never widened to pass."""

from server.audit import DIFFICULTY_BANDS, audit_clue
from server.embeddings import stub_embed
from server.rhyme import rhymes, rime
from server.tests.helpers import band_embed

EASY_LOW, EASY_HIGH = DIFFICULTY_BANDS["easy"]
HARD_LOW, HARD_HIGH = DIFFICULTY_BANDS["hard"]


class TestRhyme:
    def test_basic_rhymes(self):
        assert rhymes("cat", "hat")
        assert rhymes("nation", "station")
        assert rhymes("pancake", "lake")

    def test_non_rhymes(self):
        assert not rhymes("cat", "dog")
        assert not rhymes("pancake", "syrup")

    def test_identical_is_not_a_rhyme(self):
        assert not rhymes("cat", "cat")

    def test_rime_extraction(self):
        assert rime("pancake") == "ak"
        assert rime("cat") == "at"
        assert rime("fog") == "og"


def banded_embed(target_word: str, sim: float):
    """Place the literal clue 'clue' at cosine `sim` to the secret word."""
    return band_embed(target_word, "clue", sim)


class TestAudit:
    def test_contains_secret_fails(self):
        r = audit_clue("pancake mix", "pancake", "easy", stub_embed)
        assert not r.passed
        assert any("contains" in v for v in r.violations)

    def test_stem_match_fails(self):
        r = audit_clue("camp", "camping", "easy", stub_embed)
        assert not r.passed
        assert any("form of" in v for v in r.violations)

    def test_rhyme_fails(self):
        r = audit_clue("lake", "pancake", "easy", stub_embed)
        assert not r.passed
        assert any("rhymes" in v for v in r.violations)

    def test_too_many_words_fails(self):
        r = audit_clue("one two three four", "pancake", "easy", stub_embed)
        assert not r.passed
        assert any("max 3" in v for v in r.violations)

    def test_empty_secret_does_not_match_as_containment(self):
        # Regression: an empty secret must not register as "contains the word"
        # (an empty string is a substring of everything).
        r = audit_clue("anything here", "", "easy", stub_embed)
        assert not any("contains" in v for v in r.violations)

    # Sims are derived from the live band constants so recalibrating the bands
    # never silently breaks these tests — they assert band *logic*, not numbers.
    def test_too_similar_is_a_leak(self):
        embed = banded_embed("pancake", sim=min(1.0, EASY_HIGH + 0.1))
        r = audit_clue("clue", "pancake", "easy", embed)
        assert not r.passed
        assert any("too close" in v for v in r.violations)

    def test_too_distant_is_off_topic(self):
        embed = banded_embed("pancake", sim=max(0.0, EASY_LOW - 0.1))
        r = audit_clue("clue", "pancake", "easy", embed)
        assert not r.passed
        assert any("too far" in v for v in r.violations)

    def test_inside_band_passes(self):
        embed = banded_embed("pancake", sim=(EASY_LOW + EASY_HIGH) / 2)
        r = audit_clue("clue", "pancake", "easy", embed)
        assert r.passed, r.violations

    def test_band_tightens_with_difficulty(self):
        # A sim between hard's and easy's upper bound: fine on easy, a leak on hard.
        sim = (HARD_HIGH + EASY_HIGH) / 2
        assert audit_clue("clue", "pancake", "easy", banded_embed("pancake", sim)).passed
        assert not audit_clue("clue", "pancake", "hard", banded_embed("pancake", sim)).passed
