"""The content-factory batch graph: propose -> verify -> calibrate -> collect.

A straight offline pipeline (no interrupts, no checkpointer), built as a
LangGraph so it shares the project's mental model. Run on demand or nightly;
the survivors are persisted as a versioned pack via factory.store.
"""

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from factory.calibrate import calibrate
from factory.packs import Candidate
from factory.propose import ProposeFn, default_propose, seed_embed
from factory.verifiers import verify
from server.embeddings import EmbedFn


class FactoryState(TypedDict, total=False):
    requests: list[tuple[str, str, int]]  # (category, difficulty, n)
    proposed: list[Candidate]
    accepted: list[Candidate]
    rejected: list[tuple[Candidate, list[str]]]


def build_factory_graph(
    propose: ProposeFn | None = None, embed: EmbedFn | None = None
):
    proposer = propose or default_propose()
    embed = embed or seed_embed()

    async def propose_node(state: FactoryState) -> dict[str, Any]:
        proposed: list[Candidate] = []
        for category, difficulty, n in state["requests"]:
            proposed.extend(await proposer(category, difficulty, n))
        return {"proposed": proposed}

    def verify_node(state: FactoryState) -> dict[str, Any]:
        accepted: list[Candidate] = []
        rejected: list[tuple[Candidate, list[str]]] = []
        for cand in state["proposed"]:
            violations = verify(cand, embed)
            if violations:
                rejected.append((cand, violations))
            else:
                accepted.append(cand)
        return {"accepted": accepted, "rejected": rejected}

    def calibrate_node(state: FactoryState) -> dict[str, Any]:
        return {"accepted": [calibrate(c) for c in state["accepted"]]}

    g: StateGraph = StateGraph(FactoryState)
    g.add_node("propose", propose_node)
    g.add_node("verify", verify_node)
    g.add_node("calibrate", calibrate_node)
    g.add_edge(START, "propose")
    g.add_edge("propose", "verify")
    g.add_edge("verify", "calibrate")
    g.add_edge("calibrate", END)
    return g.compile()
