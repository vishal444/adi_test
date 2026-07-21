from __future__ import annotations

import argparse
import json
from pathlib import Path

from .knowledge_graph import (
    NetworkXSemanticGraph,
    initialize_knowledge_graph_from_env,
    make_knowledge_graph_from_env,
)
from .llm_control import LLMError, make_llm
from .ministries.health.synthetic import seed_synthetic_business_data
from .ministries.registry import MINISTRIES, active_graph_definitions
from .orchestration import GovernedQueryPipeline
from .storage import Database


DEFAULT_DB = Path("var/kerala_demo.db")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Governed semantic-graph-to-SQL pilot")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite database path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Create and seed the demo database")
    init.add_argument("--reset", action="store_true", help="Replace an existing demo database")

    seed = subparsers.add_parser("seed", help="Load deterministic bulk synthetic business data")
    seed.add_argument("--rows-per-table", type=int, default=2_000)
    seed.add_argument("--random-seed", type=int, default=20_260_721)
    seed.add_argument("--reset", action="store_true", help="Recreate the database first")

    query = subparsers.add_parser("query", help="Run a natural-language query")
    query.add_argument("question")
    query.add_argument("--provider", choices=("local", "openai"), default="local")
    query.add_argument("--json", action="store_true", help="Print the complete outcome as JSON")
    query.add_argument("--row-limit", type=int, default=100)

    subparsers.add_parser("ministries", help="List active and planned ministry modules")
    graph_init = subparsers.add_parser(
        "graph-init", help="Build the persisted NetworkX semantic K-Graph"
    )
    graph_init.add_argument("--reset", action="store_true", help="Rebuild the graph file")
    subparsers.add_parser("graph-status", help="Verify and summarize the NetworkX graph file")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "ministries":
        for ministry in MINISTRIES:
            print(f"{ministry.code:16} {ministry.status:12} {ministry.display_name}")
        return 0

    if args.command in {"graph-init", "graph-status"}:
        graph = None
        try:
            if args.command == "graph-init":
                graph = initialize_knowledge_graph_from_env(
                    active_graph_definitions(), reset=args.reset
                )
            else:
                graph = make_knowledge_graph_from_env()
            graph.verify_connectivity()
            if not isinstance(graph, NetworkXSemanticGraph):
                raise RuntimeError("Unexpected semantic graph adapter.")
            stats = graph.stats()
            if args.command == "graph-init":
                print(f"NetworkX semantic K-Graph initialized: {stats['path']}")
            else:
                print(f"NetworkX K-Graph: OK ({stats['path']})")
            print(f"Nodes: {stats['nodes']}")
            print(f"Edges: {stats['edges']}")
            return 0
        except Exception as exc:
            print(f"K-Graph error: {exc}")
            return 2
        finally:
            if graph is not None:
                graph.close()

    database = Database(args.db)
    if args.command == "init":
        database.initialize(reset=args.reset)
        print(f"Initialized demo database: {database.path}")
        return 0

    if args.command == "seed":
        if args.reset or not database.exists():
            database.initialize(reset=args.reset)
        counts = seed_synthetic_business_data(
            database,
            rows_per_table=args.rows_per_table,
            random_seed=args.random_seed,
        )
        print(f"Seeded synthetic database: {database.path}")
        print(f"district: {counts.district}")
        print(f"hospital: {counts.hospital}")
        print(f"hospital_funding: {counts.hospital_funding}")
        print(f"hospital_output: {counts.hospital_output}")
        return 0

    if not database.exists():
        database.initialize()
    graph = None
    try:
        graph = make_knowledge_graph_from_env()
        graph.verify_connectivity()
        llm = make_llm(args.provider)
        outcome = GovernedQueryPipeline(
            database, llm, graph, row_limit=args.row_limit
        ).run(args.question)
    except (LLMError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}")
        return 2
    except Exception as exc:
        print(f"K-Graph query error: {exc}")
        return 2
    finally:
        if graph is not None:
            graph.close()

    if args.json:
        print(json.dumps(outcome.to_dict(), indent=2, default=str))
    else:
        print(f"Status: {outcome.status}")
        print(f"Assurance: {outcome.assurance}")
        if outcome.stop_reason:
            print(f"Stop reason: {outcome.stop_reason}")
        if outcome.question_spec.defaulted_fields:
            print("Defaults: " + "; ".join(outcome.question_spec.defaulted_fields))
        if outcome.sql:
            print("\nValidated SQL:\n" + outcome.sql.strip())
            print(f"\nRows: {len(outcome.rows)}")
        print("\nFindings:\n" + outcome.findings)
    return 0 if outcome.status != "STOP" else 1


if __name__ == "__main__":
    raise SystemExit(main())
