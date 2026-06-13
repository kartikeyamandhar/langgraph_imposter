"""AIRuntime: the engine's handle on AI seats.

- clue_for / take_clue: produce an audited clue (with latency-hiding precompute)
- vote_for: deterministic suspicion-score vote
- guess_for: imposter's word guess when caught

Pure compute and LLM calls only; telemetry persistence is the engine's job.
The LLM seam is injectable. Without ANTHROPIC_API_KEY the runtime uses a
deterministic offline propose so the whole app (and the test suite) runs at
zero cost — real clues need a key.
"""

import asyncio
import os
from collections.abc import Awaitable, Callable

from server.ai.clue_agent import ClueProposal, ClueRequest, ClueResult, produce_clue
from server.ai.suspicion import VoteDecision, choose_vote
from server.embeddings import EmbedFn, stub_embed
from server.llm import DEFAULT_MODEL_ID
from server.state import GameState

ProposeFn = Callable[[str, str], Awaitable[ClueProposal]]
ProposeFactory = Callable[[str], ProposeFn]


async def _offline_propose(system: str, user: str) -> ClueProposal:
    # Deterministic, network-free. Leak-safe; the audit/fallback do the rest.
    return ClueProposal(text="no easy hint", tokens_in=0, tokens_out=0)


def _live_propose_factory(model: str) -> ProposeFn:  # pragma: no cover - needs a key
    from server.llm import get_chat_model

    async def propose(system: str, user: str) -> ClueProposal:
        model_obj = get_chat_model()
        resp = await model_obj.ainvoke(
            [("system", system), ("human", user)]
        )
        usage = getattr(resp, "usage_metadata", None) or {}
        return ClueProposal(
            text=str(resp.content),
            tokens_in=int(usage.get("input_tokens", 0)),
            tokens_out=int(usage.get("output_tokens", 0)),
        )

    return propose


def default_propose_factory(model: str) -> ProposeFn:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _live_propose_factory(model)
    return lambda system, user: _offline_propose(system, user)


class AIRuntime:
    def __init__(
        self,
        embed: EmbedFn = stub_embed,
        propose_factory: ProposeFactory = default_propose_factory,
    ) -> None:
        self.embed = embed
        self._propose_factory = propose_factory
        self.model = os.environ.get("MODEL_ID", DEFAULT_MODEL_ID)
        self._precomputed: dict[tuple[str, int], dict[str, asyncio.Task[ClueResult]]] = {}

    def _propose(self) -> ProposeFn:
        return self._propose_factory(self.model)

    def _request(self, state: GameState, player_id: str) -> ClueRequest:
        is_imposter = player_id in state.get("imposter_ids", [])
        return ClueRequest(
            role="imposter" if is_imposter else "civilian",
            category=state["category"],
            difficulty=state.get("difficulty", "easy"),
            secret_word=None if is_imposter else state["secret_word"],
        )

    async def clue_for(self, state: GameState, player_id: str) -> ClueResult:
        return await produce_clue(self._request(state, player_id), self._propose(), self.embed)

    # --- latency hiding -----------------------------------------------------

    def start_precompute(self, room: str, state: GameState) -> None:
        """Fan out AI clue generation at round start so each AI's turn has zero
        perceived latency. Pre-computed clues still go through the audit inside
        produce_clue — precompute is not a bypass."""
        key = (room, state["round_no"])
        if key in self._precomputed:
            return
        tasks: dict[str, asyncio.Task[ClueResult]] = {}
        for p in state["players"]:
            if p["is_ai"]:
                tasks[p["id"]] = asyncio.create_task(self.clue_for(state, p["id"]))
        self._precomputed[key] = tasks

    async def take_clue(self, room: str, state: GameState, player_id: str) -> ClueResult:
        key = (room, state["round_no"])
        task = self._precomputed.get(key, {}).pop(player_id, None)
        if task is not None:
            return await task
        return await self.clue_for(state, player_id)

    def clear_round(self, room: str, round_no: int) -> None:
        for task in self._precomputed.pop((room, round_no), {}).values():
            if not task.done():
                task.cancel()

    def cancel_all(self) -> None:
        for tasks in self._precomputed.values():
            for task in tasks.values():
                if not task.done():
                    task.cancel()
        self._precomputed.clear()

    # --- voting & guessing --------------------------------------------------

    def vote_for(self, state: GameState, voter_id: str) -> VoteDecision:
        clues = {c["player_id"]: c["clue"] for c in state.get("clues", [])}
        if state.get("revote"):
            candidates = list(state["revote_candidates"])
        else:
            candidates = [p["id"] for p in state["players"]]
        return choose_vote(voter_id, clues, candidates, self.embed)

    async def guess_for(self, state: GameState) -> tuple[str, int, int]:
        """Imposter's caught-guess. Best-effort via the LLM from category +
        clues; offline it returns an empty (wrong) guess. Returns
        (word, tokens_in, tokens_out)."""
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return "", 0, 0
        clues = ", ".join(c["clue"] for c in state.get("clues", []))  # pragma: no cover
        user = (  # pragma: no cover
            f"Category: {state['category']}. The clues given were: {clues}. "
            "You are the imposter and were caught. Guess the secret word in one word only."
        )
        proposal = await self._propose()(  # pragma: no cover
            "You are guessing a secret word. Reply with one word only.", user
        )
        words = proposal.text.strip().split()  # pragma: no cover
        return (words[0] if words else ""), proposal.tokens_in, proposal.tokens_out
