"""Test helpers for placing a clue at an exact cosine similarity to a secret
word, so audit band edges can be checked precisely."""

from server.embeddings import stub_embed, vector_at


def band_embed(secret: str, clue_word: str, sim: float):
    """Embed where `clue_word` sits at cosine `sim` to `secret`; all other
    strings fall back to the deterministic stub."""
    target = vector_at(stub_embed(secret), sim)

    def embed(text: str):
        return target if text == clue_word else stub_embed(text)

    return embed
