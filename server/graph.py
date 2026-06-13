"""The live game graph: lobby → assign_roles → clue_round → discussion → vote →
resolve, with conditional edges per the spec (re-vote on tie, imposter guess on
catch, next round, match end).

Every human input arrives through interrupt() as Command(resume=event). Each
input-collecting node handles exactly one interrupt per execution and loops via
conditional edges, so every accepted input commits one checkpoint and triggers
one broadcast. Events are dicts: {"type": ..., "actor": player_id, ...}; the
actor is attached by the server from the authenticated socket, never the client.
"""

import random
import time
from typing import Any, cast

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from server import rules
from server.state import (
    MAX_DISCUSSION_SECONDS,
    MAX_PLAYERS,
    MIN_DISCUSSION_SECONDS,
    MIN_PLAYERS,
    SECOND_IMPOSTER_MIN_PLAYERS,
    GameState,
    RoundResult,
)
from server.validators import guess_matches, validate_clue

Event = dict[str, Any]


def _err(actor: str, message: str) -> dict[str, Any]:
    return {"action_error": {"player_id": actor, "error": message}}


def _is_timer(event: Event, phase: str, deadline: float | None) -> bool:
    return (
        event.get("type") == "timer"
        and event.get("phase") == phase
        and deadline is not None
        and abs(float(event.get("deadline", -1)) - deadline) < 1e-6
    )


# --- nodes -----------------------------------------------------------------


def lobby(state: GameState) -> dict[str, Any]:
    event: Event = interrupt({"awaiting": "lobby"})
    actor = event.get("actor", "")
    etype = event.get("type")
    players = list(state.get("players", []))

    if etype == "join":
        p = event["player"]
        if any(x["id"] == p["id"] for x in players):
            return {}
        if len(players) >= MAX_PLAYERS:
            return _err(actor, "Room is full (10 players). Start the game or open a new room.")
        players.append(p)
        return {"players": players, "action_error": None}

    if actor != state["host_id"]:
        return _err(actor, "Waiting for the host to start the game.")

    if etype == "add_ai":
        if len(players) >= MAX_PLAYERS:
            return _err(actor, "Room is full (10 players).")
        players.append(event["player"])
        return {"players": players, "action_error": None}

    if etype == "remove_ai":
        target = event.get("target")
        players = [p for p in players if not (p["id"] == target and p["is_ai"])]
        return {"players": players, "action_error": None}

    if etype == "settings":
        settings = dict(state["settings"])
        if "discussion_seconds" in event:
            secs = int(event["discussion_seconds"])
            settings["discussion_seconds"] = max(
                MIN_DISCUSSION_SECONDS, min(MAX_DISCUSSION_SECONDS, secs)
            )
        if "win_mode" in event and event["win_mode"] in ("points", "rounds"):
            settings["win_mode"] = event["win_mode"]
        if "second_imposter" in event:
            settings["second_imposter"] = bool(event["second_imposter"])
        return {"settings": settings, "action_error": None}

    if etype == "start":
        if len(players) < MIN_PLAYERS:
            return _err(actor, f"Need {MIN_PLAYERS} players to start. {len(players)} joined.")
        return {"phase": "assigning", "action_error": None}

    return _err(actor, "That action is not available in the lobby.")


def assign_roles(state: GameState) -> dict[str, Any]:
    rng = random.Random()
    players = state["players"]
    used = list(state.get("used_words", []))
    category, word, difficulty = _draw(used, rng)
    used.append(word)

    n_imposters = (
        2
        if state["settings"]["second_imposter"] and len(players) >= SECOND_IMPOSTER_MIN_PLAYERS
        else 1
    )
    imposter_ids = [p["id"] for p in rng.sample(players, n_imposters)]
    order = [p["id"] for p in players]
    rng.shuffle(order)  # speaking order is randomized each round

    return {
        "phase": "clue",
        "round_no": state.get("round_no", 0) + 1,
        "imposter_ids": imposter_ids,
        "category": category,
        "secret_word": word,
        "difficulty": difficulty,
        "used_words": used,
        "speaking_order": order,
        "clue_index": 0,
        "clues": [],
        "votes": {},
        "revote": False,
        "revote_candidates": [],
        "eliminated": None,
        "discussion_deadline": None,
        "guess_deadline": None,
        "action_error": None,
        "last_result": None,
    }


def _draw(used: list[str], rng: random.Random) -> tuple[str, str, str]:
    from server.words import draw_word

    return draw_word(used, rng)


def clue_round(state: GameState) -> dict[str, Any]:
    order = state["speaking_order"]
    idx = state["clue_index"]
    active = order[idx]
    event: Event = interrupt({"awaiting": "clue", "player": active})
    actor = event.get("actor", "")

    if event.get("type") != "clue":
        return _err(actor, "Waiting for a clue.")
    if actor != active:
        return _err(actor, "Not your turn yet. Watch the speaking order.")

    clue = str(event.get("text", "")).strip()
    error = validate_clue(clue, state["secret_word"])
    if error:
        # Inline error and retry, same player. Humans and AI hit the same gate.
        return _err(actor, error)

    clues = [*state["clues"], {"player_id": actor, "clue": clue}]
    return {"clues": clues, "clue_index": idx + 1, "action_error": None}


def begin_discussion(state: GameState) -> dict[str, Any]:
    deadline = time.time() + state["settings"]["discussion_seconds"]
    return {"phase": "discussion", "discussion_deadline": deadline, "action_error": None}


def discussion(state: GameState) -> dict[str, Any]:
    event: Event = interrupt({"awaiting": "discussion_end"})
    actor = event.get("actor", "")
    deadline = state.get("discussion_deadline")

    host_ended = event.get("type") == "end_discussion" and actor == state["host_id"]
    if host_ended or _is_timer(event, "discussion", deadline):
        return {
            "phase": "vote",
            "votes": {},
            "revote": False,
            "revote_candidates": [],
            "discussion_deadline": None,
            "action_error": None,
        }
    return _err(actor, "Discussion is still running. The host or the timer ends it.")


def vote(state: GameState) -> dict[str, Any]:
    event: Event = interrupt({"awaiting": "vote"})
    actor = event.get("actor", "")

    if event.get("type") != "vote":
        return _err(actor, "Waiting for votes.")
    player_ids = {p["id"] for p in state["players"]}
    if actor not in player_ids:
        return _err(actor, "Only seated players vote.")
    votes = dict(state["votes"])
    if actor in votes:
        return _err(actor, "Vote already locked.")
    target = str(event.get("target", ""))
    if target not in player_ids:
        return _err(actor, "Pick a player to vote for.")
    if state["revote"] and target not in state["revote_candidates"]:
        return _err(actor, "Re-vote is restricted to the tied players.")

    votes[actor] = target
    return {"votes": votes, "action_error": None}


def resolve_vote(state: GameState) -> dict[str, Any]:
    leaders, _ = rules.tally_votes(state["votes"])

    if len(leaders) > 1:
        if not state["revote"]:
            # Exactly one re-vote, restricted to the tied players.
            return {
                "revote": True,
                "revote_candidates": leaders,
                "votes": {},
                "action_error": None,
            }
        # Second tie: no elimination — the imposter wins the round.
        return {"eliminated": None, "phase": "scoring", "action_error": None}

    eliminated = leaders[0]
    if eliminated in state["imposter_ids"]:
        from server.state import IMPOSTER_GUESS_SECONDS

        return {
            "eliminated": eliminated,
            "phase": "imposter_guess",
            "guess_deadline": time.time() + IMPOSTER_GUESS_SECONDS,
            "action_error": None,
        }
    return {"eliminated": eliminated, "phase": "scoring", "action_error": None}


def imposter_guess(state: GameState) -> dict[str, Any]:
    event: Event = interrupt({"awaiting": "imposter_guess", "player": state["eliminated"]})
    actor = event.get("actor", "")
    deadline = state.get("guess_deadline")

    if _is_timer(event, "imposter_guess", deadline):
        # Time ran out: counts as a wrong guess, civilians take the round.
        return {
            "phase": "scoring",
            "guess_deadline": None,
            "action_error": None,
            "ai_private": {
                **state.get("ai_private", {}),
                "last_guess": None,
                "last_guess_correct": False,
            },
        }

    if event.get("type") != "guess" or actor != state["eliminated"]:
        return _err(actor, "Waiting for the imposter's guess.")

    text = str(event.get("text", "")).strip()
    correct = guess_matches(text, state["secret_word"])
    return {
        "phase": "scoring",
        "guess_deadline": None,
        "action_error": None,
        "ai_private": {**state.get("ai_private", {}), "last_guess": text,
                       "last_guess_correct": correct},
    }


def score_round(state: GameState) -> dict[str, Any]:
    imposters = state["imposter_ids"]
    eliminated = state.get("eliminated")
    caught = eliminated in imposters if eliminated else False
    guess = state.get("ai_private", {}).get("last_guess")
    guess_correct = state.get("ai_private", {}).get("last_guess_correct", False) if caught else None

    if caught and not guess_correct:
        winner = "civilians"
        delta = rules.civilian_round_scores(state["players"], imposters, state["votes"])
    else:
        # Imposter escaped, a civilian was voted out, nobody was eliminated,
        # or the caught imposter guessed the word.
        winner = "imposter"
        delta = rules.imposter_round_scores(state["players"], imposters)

    scores = dict(state.get("scores", {}))
    for pid, pts in delta.items():
        scores[pid] = scores.get(pid, 0) + pts

    result: RoundResult = {
        "round_no": state["round_no"],
        "imposter_ids": imposters,
        "secret_word": state["secret_word"],
        "category": state["category"],
        "eliminated": eliminated,
        "imposter_caught": caught,
        "guess": guess if caught else None,
        "guess_correct": guess_correct,
        "winner": winner,  # type: ignore[typeddict-item]
    }
    new_state: dict[str, Any] = {
        "phase": "reveal",
        "scores": scores,
        "last_result": result,
        "results": [*state.get("results", []), result],
        "action_error": None,
    }
    merged = cast(GameState, {**state, **new_state})
    winners = rules.match_winners(merged)
    if winners:
        new_state["match_winners"] = winners
    return new_state


def reveal(state: GameState) -> dict[str, Any]:
    event: Event = interrupt({"awaiting": "next_round"})
    actor = event.get("actor", "")
    if event.get("type") != "continue" or actor != state["host_id"]:
        return _err(actor, "Waiting for the host to continue.")
    if state.get("match_winners"):
        return {"phase": "match_end", "action_error": None}
    return {"phase": "assigning", "action_error": None}


# --- routing ----------------------------------------------------------------


def route_lobby(state: GameState) -> str:
    return "assign_roles" if state["phase"] == "assigning" else "lobby"


def route_clue(state: GameState) -> str:
    more = state["clue_index"] < len(state["speaking_order"])
    return "clue_round" if more else "begin_discussion"


def route_discussion(state: GameState) -> str:
    return "vote" if state["phase"] == "vote" else "discussion"


def route_vote(state: GameState) -> str:
    return "resolve_vote" if len(state["votes"]) == len(state["players"]) else "vote"


def route_resolve(state: GameState) -> str:
    if state["phase"] == "imposter_guess":
        return "imposter_guess"
    if state["phase"] == "scoring":
        return "score_round"
    return "vote"  # re-vote


def route_reveal(state: GameState) -> str:
    if state["phase"] == "match_end":
        return END
    if state["phase"] == "assigning":
        return "assign_roles"
    return "reveal"


def build_game_graph(checkpointer: BaseCheckpointSaver):
    g: StateGraph = StateGraph(GameState)
    g.add_node("lobby", lobby)
    g.add_node("assign_roles", assign_roles)
    g.add_node("clue_round", clue_round)
    g.add_node("begin_discussion", begin_discussion)
    g.add_node("discussion", discussion)
    g.add_node("vote", vote)
    g.add_node("resolve_vote", resolve_vote)
    g.add_node("imposter_guess", imposter_guess)
    g.add_node("score_round", score_round)
    g.add_node("reveal", reveal)

    g.add_edge(START, "lobby")
    g.add_conditional_edges("lobby", route_lobby, ["lobby", "assign_roles"])
    g.add_edge("assign_roles", "clue_round")
    g.add_conditional_edges("clue_round", route_clue, ["clue_round", "begin_discussion"])
    g.add_edge("begin_discussion", "discussion")
    g.add_conditional_edges("discussion", route_discussion, ["discussion", "vote"])
    g.add_conditional_edges("vote", route_vote, ["vote", "resolve_vote"])
    g.add_conditional_edges(
        "resolve_vote", route_resolve, ["vote", "imposter_guess", "score_round"]
    )
    g.add_edge("imposter_guess", "score_round")
    g.add_edge("score_round", "reveal")
    g.add_conditional_edges("reveal", route_reveal, ["reveal", "assign_roles", END])

    return g.compile(checkpointer=checkpointer)
