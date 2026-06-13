"""CLI: run the content factory and persist a versioned (unshipped) pack.

    python -m factory.run --category Food Animals --difficulty easy medium

Without a database it prints the accepted candidates instead of persisting,
so the pipeline is inspectable offline.
"""

import argparse
import asyncio

from factory.graph import build_factory_graph
from factory.packs import Candidate


async def produce(categories: list[str], difficulties: list[str], n: int) -> list[Candidate]:
    graph = build_factory_graph()
    requests = [(c, d, n) for c in categories for d in difficulties]
    result = await graph.ainvoke({"requests": requests})
    return result["accepted"]


async def _main(args: argparse.Namespace) -> None:
    accepted = await produce(args.category, args.difficulty, args.n)
    if not args.persist:
        for c in accepted:
            print(f"{c.difficulty:6} {c.category:10} {c.secret_word}  d={c.category_distance:.2f}")
        print(f"\n{len(accepted)} candidates accepted (not persisted; pass --persist).")
        return

    from factory.store import write_pack
    from server.db import make_engine, make_sessionmaker

    engine = make_engine()
    sessions = make_sessionmaker(engine)
    async with sessions() as session:
        version = await write_pack(session, accepted)
    await engine.dispose()
    print(f"Wrote pack version {version} with {len(accepted)} entries (unshipped).")


def main() -> None:
    p = argparse.ArgumentParser(description="Run the Blindspot content factory.")
    p.add_argument("--category", nargs="+", default=["Food", "Animals", "Places"])
    p.add_argument("--difficulty", nargs="+", default=["easy", "medium", "hard"])
    p.add_argument("--n", type=int, default=5)
    p.add_argument("--persist", action="store_true", help="write a pack to the database")
    asyncio.run(_main(p.parse_args()))


if __name__ == "__main__":
    main()
