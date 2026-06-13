import pytest

from server.validators import guess_matches, simple_stem, validate_clue


class TestValidateClue:
    def test_accepts_clean_clue(self):
        assert validate_clue("maple syrup", "pancake") is None

    def test_accepts_three_words(self):
        assert validate_clue("flat breakfast food", "pancake") is None

    def test_rejects_four_words(self):
        err = validate_clue("a very flat food", "pancake")
        assert err is not None and "3 or fewer" in err

    def test_rejects_empty(self):
        assert validate_clue("   ", "pancake") is not None

    def test_rejects_containment(self):
        assert validate_clue("pancake mix", "pancake") is not None

    def test_rejects_embedded_word(self):
        assert validate_clue("pancakes", "pancake") is not None

    def test_rejects_case_insensitive(self):
        assert validate_clue("PANCAKE", "pancake") is not None

    def test_rejects_stem_match(self):
        # camping → camp
        assert validate_clue("camp", "camping") is not None
        assert validate_clue("camper", "camping") is not None

    def test_allows_related_but_distinct(self):
        assert validate_clue("tent", "camping") is None


class TestStem:
    @pytest.mark.parametrize(
        ("word", "stem"),
        [("pancakes", "pancake"), ("camping", "camp"), ("voted", "vot"), ("fog", "fog")],
    )
    def test_examples(self, word, stem):
        assert simple_stem(word) == stem


class TestGuess:
    def test_exact(self):
        assert guess_matches("pancake", "pancake")

    def test_case_and_space(self):
        assert guess_matches("  Pancake ", "pancake")

    def test_plural(self):
        assert guess_matches("pancakes", "pancake")

    def test_wrong(self):
        assert not guess_matches("waffle", "pancake")

    def test_multiword_guess_fails(self):
        assert not guess_matches("a pancake", "pancake")
