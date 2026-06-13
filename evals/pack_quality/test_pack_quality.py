"""CI gate: pack-quality checks. A pack ships only if these pass.

Runs the factory pipeline on the seed requests and asserts every survivor is
clean (no blocklist, no ambiguity, inside its category band), and that the
verifiers actually reject bad candidates.
"""

import pytest
from factory.graph import build_factory_graph
from factory.packs import Candidate
from factory.propose import seed_embed
from factory.verifiers import verify

from server.embeddings import stub_embed
from server.tests.helpers import band_embed


@pytest.fixture
async def accepted():
    graph = build_factory_graph()
    requests = [
        ("Food", "easy", 5),
        ("Animals", "easy", 5),
        ("Places", "medium", 5),
    ]
    result = await graph.ainvoke({"requests": requests})
    return result["accepted"]


async def test_factory_produces_some_words(accepted):
    assert len(accepted) >= 3


async def test_every_shipped_candidate_is_clean(accepted):
    embed = seed_embed()
    for cand in accepted:
        assert verify(cand, embed) == [], f"{cand.secret_word} should be clean"


async def test_blocklist_rejects():
    cand = Candidate(category="Things", secret_word="blood", difficulty="easy")
    assert any("blocklist" in v for v in verify(cand, stub_embed))


async def test_ambiguous_rejects():
    cand = Candidate(category="Things", secret_word="thing", difficulty="easy")
    assert any("ambiguous" in v for v in verify(cand, stub_embed))


async def test_too_short_rejects():
    cand = Candidate(category="Things", secret_word="ox", difficulty="easy")
    assert any("short" in v for v in verify(cand, stub_embed))


async def test_out_of_category_band_rejects():
    # An "easy" word should be close to its category; place it far and expect
    # a band rejection.
    cand = Candidate(category="Food", secret_word="quark", difficulty="easy")
    embed = band_embed("Food", "quark", sim=0.05)
    violations = verify(cand, embed)
    assert any("category band" in v for v in violations)
