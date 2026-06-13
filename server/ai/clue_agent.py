"""AI clue production: LLM proposes, the fail-closed audit verifies, retry on
violations, then a safe template fallback. Never force-pass (ADR 001).

The propose step is the only LLM seam and is injectable, so the offline suite
runs without a key. Token counts flow out for cost telemetry.
"""

import asyncio
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from server.audit import AuditReport, audit_clue
from server.embeddings import EmbedFn
from server.prompts import CLUE_SYSTEM, civilian_clue_prompt, imposter_clue_prompt

MAX_RETRIES = 3  # loop-backs after the first attempt before falling back


@dataclass
class ClueRequest:
    role: str  # "imposter" | "civilian"
    category: str
    difficulty: str
    secret_word: str  # the real word — used by the audit only; the imposter's
    # prompt never includes it, so the model still sees only the category.


@dataclass
class ClueProposal:
    text: str
    tokens_in: int = 0
    tokens_out: int = 0


# (system_prompt, user_prompt) -> proposal
ProposeFn = Callable[[str, str], Awaitable[ClueProposal]]


@dataclass
class ClueResult:
    text: str
    attempts: int
    retries: int
    fell_back: bool
    tokens_in: int
    tokens_out: int
    report: AuditReport


def _clean(text: str) -> str:
    # Models like to wrap clues in quotes or trailing punctuation.
    return re.sub(r"[^a-zA-Z' ]", "", text).strip()


def safe_fallback(category: str, secret_word: str, embed: EmbedFn) -> tuple[str, AuditReport]:
    """A leak-safe clue for when the agent can't satisfy the audit. Leak-safety
    is non-negotiable; band relevance is best-effort, so the report may still
    show an out-of-band similarity without being a force-pass."""
    candidates = [
        f"about {category.lower()}".strip(),
        "hard to say",
        "tricky one",
        "no easy hint",
    ]
    for cand in candidates:
        words = cand.split()
        if len(words) > 3:
            continue
        report = audit_clue(cand, secret_word, "easy", embed)
        leak = [
            v
            for v in report.violations
            if "contains" in v or "form of" in v or "rhymes" in v
        ]
        if not leak:
            return cand, report
    return "no comment", audit_clue("no comment", secret_word, "easy", embed)


async def produce_clue(
    req: ClueRequest, propose: ProposeFn, embed: EmbedFn
) -> ClueResult:
    secret = req.secret_word
    tokens_in = tokens_out = 0
    last_report: AuditReport | None = None
    violations: list[str] = []

    for attempt in range(MAX_RETRIES + 1):
        # The imposter's prompt omits the word (they only know the category);
        # the audit below still checks the real word to catch a coincidental leak.
        if req.role == "imposter":
            user = imposter_clue_prompt(req.category, violations)
        else:
            user = civilian_clue_prompt(req.category, secret, violations)

        proposal = await propose(CLUE_SYSTEM, user)
        tokens_in += proposal.tokens_in
        tokens_out += proposal.tokens_out
        text = _clean(proposal.text)

        # Off the event loop: the embedder may do a network call (OpenAI).
        report = await asyncio.to_thread(audit_clue, text, secret, req.difficulty, embed)
        last_report = report
        if report.passed:
            return ClueResult(
                text=text,
                attempts=attempt + 1,
                retries=attempt,
                fell_back=False,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                report=report,
            )
        violations = report.violations

    text, report = await asyncio.to_thread(safe_fallback, req.category, secret, embed)
    return ClueResult(
        text=text,
        attempts=MAX_RETRIES + 1,
        retries=MAX_RETRIES,
        fell_back=True,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        report=last_report or report,
    )
