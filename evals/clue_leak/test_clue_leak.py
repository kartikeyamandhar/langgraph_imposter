"""CI gate: zero clue leaks on the probe set.

Runs whenever prompts, validators, or the audit change. A single leaking clue
that the audit accepts fails the build.
"""

import pytest

from evals.probes import CLEAN_CLUES, DETERMINISTIC_LEAKS, LeakProbe
from server.audit import DIFFICULTY_BANDS, audit_clue
from server.embeddings import stub_embed
from server.tests.helpers import band_embed

_EASY_MID = sum(DIFFICULTY_BANDS["easy"]) / 2


def test_zero_deterministic_leaks():
    leaked = []
    for probe in DETERMINISTIC_LEAKS:
        report = audit_clue(probe.clue, probe.secret, "easy", stub_embed)
        if report.passed:
            leaked.append(probe)
    assert leaked == [], f"audit accepted leaking clues: {[(p.secret, p.clue) for p in leaked]}"


def test_embedding_too_close_is_rejected():
    # A clue with no surface overlap but very high semantic similarity must
    # still be caught by the band guard.
    embed = band_embed("pancake", "flapjack", sim=0.97)
    report = audit_clue("flapjack", "pancake", "easy", embed)
    assert not report.passed
    assert any("too close" in v for v in report.violations)


@pytest.mark.parametrize("probe", CLEAN_CLUES, ids=lambda p: p.clue)
def test_clean_clues_are_not_overblocked(probe: LeakProbe):
    # Place the clue mid-band so only the deterministic checks decide. A clean
    # clue must pass — proves we reject leaks without rejecting good clues.
    embed = band_embed(probe.secret, probe.clue, sim=_EASY_MID)
    report = audit_clue(probe.clue, probe.secret, "easy", embed)
    assert report.passed, report.violations
