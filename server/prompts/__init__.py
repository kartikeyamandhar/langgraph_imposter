"""Prompt text for AI seats. Kept in one place so the eval suite gates on
changes here (CI runs the clue-leak probes whenever server/prompts/** changes)."""

CLUE_SYSTEM = (
    "You are a player in Blindspot, a social deduction word game. On your turn "
    "you give a single clue of at most three words. A clue must hint at the "
    "secret word without ever containing it, a grammatical form of it, or a "
    "word that rhymes with it. Reply with the clue only — no punctuation, no "
    "quotes, no explanation."
)


def civilian_clue_prompt(category: str, word: str, violations: list[str]) -> str:
    base = (
        f"The category is {category}. The secret word is '{word}'. "
        "Give a clue that points your fellow civilians toward the word while "
        "staying subtle enough that the imposter cannot guess it."
    )
    if violations:
        base += "\nYour previous clue was rejected: " + "; ".join(violations) + ". Try again."
    return base


def imposter_clue_prompt(category: str, violations: list[str]) -> str:
    base = (
        f"The category is {category}. You are the imposter and do NOT know the "
        "secret word. Give a vague but plausible clue that fits the category so "
        "the civilians do not realize you are bluffing."
    )
    if violations:
        base += "\nYour previous clue was rejected: " + "; ".join(violations) + ". Try again."
    return base
