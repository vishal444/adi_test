from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from kerala_kg_llm.governance import SQLGuard, UnsafeSQL
from kerala_kg_llm.knowledge_graph import NetworkXSemanticGraph
from kerala_kg_llm.ministries.health.local_llm import LocalHealthDemoLLM
from kerala_kg_llm.ministries.health.synthetic import seed_synthetic_business_data
from kerala_kg_llm.ministries.registry import (
    MINISTRIES,
    active_graph_definitions,
    active_ministries,
)
from kerala_kg_llm.orchestration import GovernedQueryPipeline
from kerala_kg_llm.storage import Database


class PipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp_dir.name) / "demo.db")
        self.db.initialize()
        self.graph = NetworkXSemanticGraph.from_definitions(active_graph_definitions())

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_end_to_end_funding_output_question(self) -> None:
        outcome = GovernedQueryPipeline(self.db, LocalHealthDemoLLM(), self.graph).run(
            "Which hospitals received more operating funding without comparable output growth?"
        )
        self.assertEqual(outcome.status, "PASS_WITH_LIMITATIONS")
        self.assertEqual(outcome.assurance, "EXPLORATORY_NOT_CERTIFIED")
        self.assertEqual(len(outcome.rows), 3)
        self.assertEqual(outcome.rows[0]["hospital_name"], "Alappuzha General Hospital")
        self.assertIn("descriptive signal", outcome.findings)
        self.assertEqual(outcome.provenance["method_binding_status"], "BINDING_DEFAULTED")
        self.assertTrue(outcome.question_spec.defaulted_fields)

    def test_semantic_graph_returns_relations_and_frames(self) -> None:
        spec = LocalHealthDemoLLM().interpret("Compare hospital funding and output")
        context = self.graph.retrieve(spec)
        names = {dataset.name for dataset in context.datasets}
        self.assertIn("analytics_health_hospital_funding_year", names)
        self.assertIn("analytics_health_hospital_output_year", names)
        self.assertTrue(any(row["predicate"] == "located_in" for row in context.relationships))

    def test_unknown_entity_stops_before_sql(self) -> None:
        outcome = GovernedQueryPipeline(self.db, LocalHealthDemoLLM(), self.graph).run(
            "Show procurement contract anomalies"
        )
        self.assertEqual(outcome.status, "STOP")
        self.assertIsNone(outcome.sql)
        self.assertIn("METHOD_BINDING_AMBIGUOUS", outcome.stop_reason or "")

    def test_sql_guard_rejects_mutation_and_unknown_tables(self) -> None:
        guard = SQLGuard(self.graph.allowed_datasets())
        with self.db.read_connection() as connection:
            with self.assertRaises(UnsafeSQL):
                guard.validate("DROP TABLE hospital", (), connection)
            with self.assertRaises(UnsafeSQL):
                guard.validate("SELECT * FROM hospital", (), connection)
            with self.assertRaises(UnsafeSQL):
                guard.validate(
                    """
                    SELECT approved.hospital_id
                    FROM analytics_health_hospital_funding_year AS approved, hospital AS raw
                    """,
                    (),
                    connection,
                )

    def test_read_connection_denies_writes(self) -> None:
        with self.db.read_connection() as connection:
            with self.assertRaises(sqlite3.DatabaseError):
                connection.execute("DELETE FROM hospital")

    def test_execution_authorizer_denies_raw_table_bypass(self) -> None:
        with self.assertRaises(sqlite3.DatabaseError):
            self.db.execute_read(
                """
                SELECT approved.hospital_id
                FROM analytics_health_hospital_funding_year AS approved, hospital AS raw
                """,
                (),
                allowed_read_objects={"analytics_health_hospital_funding_year"},
            )

    def test_bulk_synthetic_seed_has_requested_business_counts(self) -> None:
        counts = seed_synthetic_business_data(self.db, rows_per_table=2_000)
        self.assertEqual(counts.hospital, 2_000)
        self.assertEqual(counts.hospital_funding, 2_000)
        self.assertEqual(counts.hospital_output, 2_000)
        self.assertEqual(counts.district, 14)
        with sqlite3.connect(self.db.path) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM hospital").fetchone()[0], 2_000)
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM hospital_funding").fetchone()[0],
                2_000,
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM hospital_output").fetchone()[0],
                2_000,
            )
        outcome = GovernedQueryPipeline(self.db, LocalHealthDemoLLM(), self.graph).run(
            "Which hospitals received more operating funding without comparable output growth?"
        )
        self.assertEqual(outcome.status, "PASS_WITH_LIMITATIONS")
        self.assertEqual(len(outcome.rows), 100)

    def test_only_health_ministry_is_active(self) -> None:
        self.assertEqual([module.code for module in active_ministries()], ["health"])
        self.assertEqual(
            {module.code for module in MINISTRIES},
            {"health", "education", "finance", "procurement", "law_enforcement", "transport", "welfare"},
        )

    def test_sqlite_no_longer_contains_k_graph_tables(self) -> None:
        with sqlite3.connect(self.db.path) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        self.assertNotIn("semantic_entity", tables)
        self.assertNotIn("semantic_dataset", tables)
        self.assertNotIn("semantic_relationship", tables)
        self.assertNotIn("registry_metadata", tables)

    def test_networkx_graph_persistence_preserves_nodes_and_relations(self) -> None:
        path = Path(self.temp_dir.name) / "knowledge_graph.json"
        self.graph.save(path)
        loaded = NetworkXSemanticGraph.load(path)
        loaded.verify_connectivity()
        self.assertEqual(loaded.graph.number_of_nodes(), self.graph.graph.number_of_nodes())
        self.assertEqual(loaded.graph.number_of_edges(), self.graph.graph.number_of_edges())
        context = loaded.retrieve(
            LocalHealthDemoLLM().interpret("Compare hospital funding and output")
        )
        self.assertTrue(any(row["predicate"] == "located_in" for row in context.relationships))
        self.assertEqual(loaded.allowed_datasets(), self.graph.allowed_datasets())


if __name__ == "__main__":
    unittest.main()
