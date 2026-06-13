"""The fail-closed audit is the safety boundary. These tests pin every reject
path and prove the band is enforced — never widened to pass."""

from server.audit import audit_clue
from server.embeddings import stub_embed
from server.rhyme import rhymes, rime
from server.tests.helpers import band_embed


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

    def test_too_similar_is_a_leak(self):
        embed = banded_embed("pancake", sim=0.95)
        r = audit_clue("clue", "pancake", "easy", embed)
        assert not r.passed
        assert any("too close" in v for v in r.violations)

    def test_too_distant_is_off_topic(self):
        embed = banded_embed("pancake", sim=0.0)
        r = audit_clue("clue", "pancake", "easy", embed)
        assert not r.passed
        assert any("too far" in v for v in r.violations)

    def test_inside_band_passes(self):
        embed = banded_embed("pancake", sim=0.4)
        r = audit_clue("clue", "pancake", "easy", embed)
        assert r.passed, r.violations

    def test_band_tightens_with_difficulty(self):
        # 0.58 passes easy (high 0.60) but leaks on hard (high 0.50).
        embed = banded_embed("pancake", sim=0.58)
        assert audit_clue("clue", "pancake", "easy", embed).passed
        assert not audit_clue("clue", "pancake", "hard", embed).passed
