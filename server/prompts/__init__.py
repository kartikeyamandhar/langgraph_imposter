"""Prompt text for AI seats. Kept in one place so the eval suite gates on
changes here (CI runs the clue-leak probes whenever server/prompts/** changes)."""

CLUE_SYSTEM = (
    "You are a player in Blindspot, a social deduction word game. On your turn "
    "you give ONE clue of at most three words. Good clues are oblique "
    "associations — a mood, a related object, an indirect hint — never a "
    "definition, a description of what the thing does, or where it is found. "
    "Never include the secret word, a grammatical form of it, or a rhyme. "
    "Reply with the clue only: no punctuation, no quotes, no explanation."
)


def civilian_clue_prompt(category: str, word: str, violations: list[str]) -> str:
    base = (
        f"The category is {category}. The secret word is '{word}'. "
        "Give a subtle, indirect clue: a single evocative association that a "
        "fellow civilian could connect to the word, but that would NOT let "
        "someone who doesn't know the word guess it. Avoid naming its purpose, "
        "function, or location. Prefer one or two words."
    )
    if violations:
        base += "\nYour previous clue was rejected: " + "; ".join(violations) + ". Try again."
    return base


def imposter_clue_prompt(category: str, violations: list[str]) -> str:
    base = (
        f"The category is {category}. You are the imposter and do NOT know the "
        "secret word. Give a confident, plausible-sounding clue that could fit "
        "many words in this category, so the civilians believe you know the "
        "word. Stay vague enough to cover yourself, but never say you are "
        "unsure — blend in. Prefer one or two words."
    )
    if violations:
        base += "\nYour previous clue was rejected: " + "; ".join(violations) + ". Try again."
    return base
