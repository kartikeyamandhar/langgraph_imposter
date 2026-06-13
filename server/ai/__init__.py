"""AI seats: clue agent, fail-closed audit loop, suspicion voting, latency
hiding. The deterministic parts (suspicion scoring) are LLM-free and tested
offline; the clue agent goes through server/llm.py so tests mock one seam."""
