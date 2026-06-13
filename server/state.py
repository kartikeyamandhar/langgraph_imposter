"""Game state. The LangGraph instance for a room is the single writer to this."""

from typing import Any, Literal, TypedDict

Phase = Literal[
    "lobby",
    "assigning",  # transient: lobby approved start, roles being dealt
    "clue",
    "discussion",
    "vote",
    "scoring",  # transient: vote resolved, scores being applied
    "imposter_guess",
    "reveal",
    "match_end",
]

WinMode = Literal["points", "rounds"]  # first to 7 points, or 5 rounds — host picks in lobby

POINTS_TO_WIN = 7
MAX_ROUNDS = 5
DEFAULT_DISCUSSION_SECONDS = 90
MIN_DISCUSSION_SECONDS = 30
MAX_DISCUSSION_SECONDS = 180
MIN_PLAYERS = 4
MAX_PLAYERS = 10
SECOND_IMPOSTER_MIN_PLAYERS = 8
IMPOSTER_GUESS_SECONDS = 30
MAX_CLUE_WORDS = 3


class PlayerInfo(TypedDict):
    id: str
    name: str
    seat: int
    is_ai: bool


class Settings(TypedDict):
    discussion_seconds: int
    win_mode: WinMode
    second_imposter: bool


class RoundResult(TypedDict):
    round_no: int
    imposter_ids: list[str]
    secret_word: str
    category: str
    eliminated: str | None
    imposter_caught: bool
    guess: str | None
    guess_correct: bool | None
    winner: Literal["imposter", "civilians"]


class GameState(TypedDict, total=False):
    room: str
    host_id: str
    phase: Phase
    players: list[PlayerInfo]
    settings: Settings

    # Per round
    round_no: int
    imposter_ids: list[str]
    category: str
    secret_word: str
    difficulty: str
    used_words: list[str]
    speaking_order: list[str]
    clue_index: int
    clues: list[dict[str, str]]  # [{player_id, clue}] in submission order
    action_error: dict[str, str] | None  # {player_id, error}, delivered privately
    discussion_deadline: float | None
    votes: dict[str, str]  # voter_id -> target_id, secret until resolve
    revote: bool
    revote_candidates: list[str]
    eliminated: str | None
    guess_deadline: float | None
    last_result: RoundResult | None

    # Match
    scores: dict[str, int]
    results: list[RoundResult]
    match_winners: list[str]

    # Telemetry hooks (filled by AI seats from M2)
    ai_private: dict[str, Any]
