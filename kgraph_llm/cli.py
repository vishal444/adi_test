from __future__ import annotations

import argparse
import json
import sqlite3
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .knowledge_graph import (
    NetworkXSemanticGraph,
    initialize_knowledge_graph_from_env,
    make_knowledge_graph_from_env,
)
from .llm_control import LLMError, make_llm
from .ministries.health.comprehensive_synthetic import (
    HIGH_CARDINALITY_TABLES,
    seed_comprehensive_health_data,
)
from .ministries.health.synthetic import seed_synthetic_business_data
from .ministries.health.surveillance import DailyAdmissionSurveillance
from .ministries.registry import MINISTRIES, active_graph_definitions
from .orchestration import GovernedQueryPipeline
from .semantic_query import OPERATORS, OPERATOR_REGISTRY_VERSION
from .storage import Database


DEFAULT_DB = Path("var/kerala_demo.db")


def format_result_table(rows: Sequence[Mapping[str, Any]]) -> str:
    """Render governed result rows as a terminal- and Markdown-friendly table."""
    if not rows:
        return "| Result |\n| --- |\n| No rows returned |"

    columns = tuple(
        dict.fromkeys(
            key
            for row in rows
            for key in row
            if not key.startswith("_")
        )
    )
    if not columns:
        return "| Result |\n| --- |\n| No displayable columns returned |"

    def display(value: Any) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "true" if value else "false"
        return (
            str(value)
            .replace("\r\n", "\n")
            .replace("\r", "\n")
            .replace("\n", "<br>")
            .replace("|", r"\|")
        )

    values = tuple(
        tuple(display(row.get(column)) for column in columns)
        for row in rows
    )
    numeric = tuple(
        any(row.get(column) is not None for row in rows)
        and all(
            row.get(column) is None
            or (
                isinstance(row.get(column), (int, float))
                and not isinstance(row.get(column), bool)
            )
            for row in rows
        )
        for column in columns
    )
    widths = tuple(
        max(len(column), *(len(row[index]) for row in values))
        for index, column in enumerate(columns)
    )

    def render_row(cells: Sequence[str], *, align_numbers: bool = False) -> str:
        rendered = []
        for index, cell in enumerate(cells):
            if align_numbers and numeric[index]:
                rendered.append(cell.rjust(widths[index]))
            else:
                rendered.append(cell.ljust(widths[index]))
        return "| " + " | ".join(rendered) + " |"

    separator = "| " + " | ".join(
        ("-" * max(3, width - 1) + ":") if numeric[index] else "-" * max(3, width)
        for index, width in enumerate(widths)
    ) + " |"
    return "\n".join(
        (
            render_row(columns),
            separator,
            *(render_row(row, align_numbers=True) for row in values),
        )
    )


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
    query.add_argument(
        "--provider", choices=("local", "openai", "google", "gemini"), default="local"
    )
    query.add_argument("--json", action="store_true", help="Print the complete outcome as JSON")
    query.add_argument("--row-limit", type=int, default=100)

    subparsers.add_parser("ministries", help="List active and planned ministry modules")
    subparsers.add_parser("operators", help="List implemented and planned query operators")
    graph_init = subparsers.add_parser(
        "graph-init", help="Build the persisted NetworkX semantic K-Graph"
    )
    graph_init.add_argument("--reset", action="store_true", help="Rebuild the graph file")
    subparsers.add_parser("graph-status", help="Verify and summarize the NetworkX graph file")
    surveillance = subparsers.add_parser(
        "daily-surveillance",
        help="Run the deterministic admission-spike check for one closed reporting day",
    )
    surveillance.add_argument(
        "--reporting-date",
        help="Closed reporting date in YYYY-MM-DD; defaults to yesterday in Kerala",
    )
    surveillance.add_argument(
        "--json", action="store_true", help="Print the complete outcome as JSON"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "ministries":
        for ministry in MINISTRIES:
            print(f"{ministry.code:16} {ministry.status:12} {ministry.display_name}")
        return 0

    if args.command == "operators":
        print(f"Operator registry: {OPERATOR_REGISTRY_VERSION}")
        for operator in OPERATORS:
            print(
                f"{operator.name:24} {operator.category:12} "
                f"{operator.status:11} {operator.description}"
            )
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
        # initialize(reset=False) is also the schema-upgrade path for an older
        # local demo database; CREATE IF NOT EXISTS preserves existing data.
        database.initialize(reset=args.reset)
        counts = seed_synthetic_business_data(
            database,
            rows_per_table=args.rows_per_table,
            random_seed=args.random_seed,
        )
        comprehensive = seed_comprehensive_health_data(
            database,
            rows_per_table=args.rows_per_table,
            random_seed=args.random_seed + 1,
        )
        print(f"Seeded synthetic database: {database.path}")
        print(f"district: {counts.district}")
        print(
            "district_facility_distribution_profile: "
            f"{counts.district_facility_distribution_profile}"
        )
        print(f"healthcare_facility_level: {counts.healthcare_facility_level}")
        print(f"healthcare_referral_route: {counts.healthcare_referral_route}")
        print(f"hospital: {counts.hospital}")
        print(
            "hospital_facility_classification: "
            f"{counts.hospital_facility_classification}"
        )
        print(f"hospital_funding: {counts.hospital_funding}")
        print(f"hospital_output: {counts.hospital_output}")
        print(f"hospital_equipment: {counts.hospital_equipment}")
        print(
            "designated_high_cardinality_tables: "
            f"{len(HIGH_CARDINALITY_TABLES)}"
        )
        print(f"empty_tables: {len(comprehensive.empty_tables)}")
        print(f"all_null_columns: {len(comprehensive.all_null_columns)}")
        return 0

    if args.command == "daily-surveillance":
        if not database.exists():
            database.initialize()
        try:
            outcome = DailyAdmissionSurveillance(database).run(args.reporting_date)
        except (sqlite3.Error, ValueError) as exc:
            print(f"Daily surveillance error: {exc}")
            return 2
        if args.json:
            print(json.dumps(outcome.to_dict(), indent=2, default=str))
        else:
            print(f"Run: {outcome.run_id}")
            print(f"Reporting date: {outcome.reporting_date}")
            print(f"Status: {outcome.status}")
            print(
                "Submission coverage: "
                f"{outcome.complete_hospitals}/{outcome.expected_hospitals} "
                f"({outcome.reporting_completeness:.1%})"
            )
            print(outcome.message)
            for signal in outcome.signals:
                print(
                    f"{signal.signal_level:5} {signal.geography_type:8} "
                    f"{signal.geography_name}: {signal.syndrome_code} "
                    f"observed={signal.observed_count} "
                    f"expected={signal.expected_count:.2f} "
                    f"score={signal.anomaly_score:.2f} "
                    f"hospitals={signal.contributing_hospitals}"
                )
        return 0 if outcome.status == "COMPLETED" else 1

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
            print("\nResult data:\n" + format_result_table(outcome.rows))
        if outcome.provenance.get("execution_mode") == "SEMANTIC_PLAN_COMPILED":
            plan = outcome.provenance["semantic_plan"]
            print(
                "Semantic plan: "
                f"{plan['operation']} / {plan['transform']} "
                f"({outcome.provenance['compiler_version']})"
            )
            print(f"Verification: {outcome.provenance['verification_status']}")
            print(
                "Result coverage: "
                f"{outcome.provenance['returned_rows']}/"
                f"{outcome.provenance['total_result_rows']}"
                + (" (truncated)" if outcome.provenance["result_truncated"] else "")
            )
        print("\nFindings:\n" + outcome.findings)
    return 0 if outcome.status != "STOP" else 1


if __name__ == "__main__":
    raise SystemExit(main())
