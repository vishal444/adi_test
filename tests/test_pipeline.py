from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from kgraph_llm.core import SemanticQueryPlan
from kgraph_llm.governance import SQLGuard, UnsafeSQL
from kgraph_llm.knowledge_graph import NetworkXSemanticGraph
from kgraph_llm.ministries.health.local_llm import LocalHealthDemoLLM
from kgraph_llm.ministries.health.synthetic import seed_synthetic_business_data
from kgraph_llm.ministries.registry import (
    MINISTRIES,
    active_graph_definitions,
    active_ministries,
)
from kgraph_llm.orchestration import GovernedQueryPipeline
from kgraph_llm.semantic_query import (
    OPERATORS,
    SemanticQueryCompiler,
    SemanticResultVerifier,
    operator_capabilities,
)
from kgraph_llm.storage import Database


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
        self.assertIn("descriptive result", outcome.findings)
        self.assertEqual(outcome.provenance["execution_mode"], "SEMANTIC_PLAN_COMPILED")
        self.assertEqual(outcome.provenance["compiler_version"], "semantic-sql-1.2.0")
        self.assertEqual(
            outcome.provenance["operator_registry_version"],
            "semantic-operators-1.2.0",
        )
        self.assertEqual(outcome.provenance["verification_status"], "EXECUTION_VERIFIED")
        self.assertEqual(outcome.provenance["total_result_rows"], 3)
        self.assertFalse(outcome.provenance["result_truncated"])
        self.assertEqual(
            outcome.provenance["semantic_plan"]["transform"],
            "endpoint_growth_pct",
        )
        self.assertTrue(outcome.question_spec.defaulted_fields)

    def test_semantic_plan_bypasses_llm_sql_and_analysis(self) -> None:
        adapter = LocalHealthDemoLLM()
        self.assertFalse(hasattr(adapter, "generate_sql"))
        self.assertFalse(hasattr(adapter, "analyze"))
        outcome = GovernedQueryPipeline(self.db, adapter, self.graph).run(
            "Which hospitals received more operating funding without comparable output growth?"
        )
        self.assertEqual(outcome.status, "PASS_WITH_LIMITATIONS")
        self.assertEqual(outcome.provenance["verification_status"], "EXECUTION_VERIFIED")

    def test_generic_verifier_rejects_tampered_calculation(self) -> None:
        outcome = GovernedQueryPipeline(self.db, LocalHealthDemoLLM(), self.graph).run(
            "Which hospitals received more operating funding without comparable output growth?"
        )
        tampered = [dict(row) for row in outcome.rows]
        tampered[0]["total_output_growth_pct"] = -999.0
        plan = SemanticQueryPlan.from_dict(outcome.provenance["semantic_plan"])
        compiled = SemanticQueryCompiler().compile(plan, outcome.graph_context)
        with self.assertRaisesRegex(ValueError, "QUERY_RESULT_INVALID"):
            SemanticResultVerifier().verify(
                compiled, tuple(tampered), row_limit=100
            )

    def test_generic_operator_supports_the_opposite_comparison(self) -> None:
        outcome = GovernedQueryPipeline(self.db, LocalHealthDemoLLM(), self.graph).run(
            "Which hospitals had lower operating funding growth than output growth from 2022 to 2025?"
        )
        self.assertEqual(outcome.status, "PASS_WITH_LIMITATIONS")
        self.assertEqual(
            outcome.provenance["semantic_plan"]["comparison"]["operator"], "<"
        )
        self.assertEqual(outcome.provenance["verification_status"], "EXECUTION_VERIFIED")

    def test_semantic_plan_provenance_is_audited(self) -> None:
        GovernedQueryPipeline(self.db, LocalHealthDemoLLM(), self.graph).run(
            "Which hospitals received more operating funding without comparable output growth?"
        )
        with sqlite3.connect(self.db.path) as connection:
            raw = connection.execute(
                "SELECT provenance_json FROM audit_execution ORDER BY execution_id DESC LIMIT 1"
            ).fetchone()[0]
        provenance = json.loads(raw)
        self.assertEqual(provenance["verification_status"], "EXECUTION_VERIFIED")
        self.assertEqual(provenance["execution_mode"], "SEMANTIC_PLAN_COMPILED")
        self.assertEqual(provenance["semantic_plan"]["operation"], "aggregate")

    def test_semantic_graph_returns_relations_and_frames(self) -> None:
        spec = LocalHealthDemoLLM().interpret("Compare hospital funding and output")
        context = self.graph.retrieve(spec)
        names = {dataset.name for dataset in context.datasets}
        self.assertIn("analytics_health_hospital_funding_year", names)
        self.assertIn("analytics_health_hospital_output_year", names)
        self.assertTrue(any(row["predicate"] == "located_in" for row in context.relationships))
        self.assertEqual(len(context.dataset_joins), 1)
        self.assertEqual(
            context.dataset_joins[0]["keys"],
            [["hospital_id", "hospital_id"], ["fiscal_year", "fiscal_year"]],
        )

    def test_generic_records_operator_applies_graph_validated_filter(self) -> None:
        class FilterPlanLLM(LocalHealthDemoLLM):
            def plan_query(self, spec, context):
                return SemanticQueryPlan(
                    operation="records",
                    datasets=("analytics_health_hospital_equipment",),
                    fields=(
                        "hospital_name",
                        "equipment_type",
                        "operational_status",
                    ),
                    filters=(
                        {
                            "field": "operational_status",
                            "operator": "=",
                            "value": "maintenance",
                        },
                    ),
                    order_by=({"field": "hospital_name", "direction": "ASC"},),
                )

        outcome = GovernedQueryPipeline(self.db, FilterPlanLLM(), self.graph).run(
            "Show hospital equipment under maintenance"
        )
        self.assertEqual(outcome.status, "PASS_WITH_LIMITATIONS")
        self.assertEqual(len(outcome.rows), 1)
        self.assertEqual(outcome.rows[0]["operational_status"], "maintenance")
        self.assertNotIn("maintenance", outcome.sql or "")

    def test_hallucinated_plan_schema_stops_before_execution(self) -> None:
        class InvalidPlanLLM(LocalHealthDemoLLM):
            def plan_query(self, spec, context):
                return SemanticQueryPlan(
                    operation="records",
                    datasets=("hospital",),
                    fields=("secret_column",),
                )

        outcome = GovernedQueryPipeline(self.db, InvalidPlanLLM(), self.graph).run(
            "Show hospital equipment"
        )
        self.assertEqual(outcome.status, "STOP")
        self.assertIn("PLAN_INVALID", outcome.stop_reason or "")
        self.assertIsNone(outcome.sql)

    def test_semantic_plan_cannot_change_interpreted_years(self) -> None:
        class WrongYearsLLM(LocalHealthDemoLLM):
            def plan_query(self, spec, context):
                plan = super().plan_query(spec, context)
                return SemanticQueryPlan(
                    **{
                        **plan.to_dict(),
                        "start_year": 2021,
                    }
                )

        outcome = GovernedQueryPipeline(self.db, WrongYearsLLM(), self.graph).run(
            "Compare hospital funding growth and output growth from 2022 to 2025"
        )
        self.assertEqual(outcome.status, "STOP")
        self.assertIn("planned endpoint years differ", outcome.stop_reason or "")

    def test_generic_aggregate_operator_uses_kgraph_metric_formula(self) -> None:
        outcome = GovernedQueryPipeline(self.db, LocalHealthDemoLLM(), self.graph).run(
            "Show equipment downtime by hospital"
        )
        self.assertEqual(outcome.status, "PASS_WITH_LIMITATIONS")
        self.assertEqual(outcome.rows[0]["equipment_downtime"], 240.0)
        self.assertEqual(
            outcome.provenance["semantic_plan"]["operation"], "aggregate"
        )
        self.assertEqual(outcome.provenance["verification_status"], "EXECUTION_VERIFIED")

    def test_arithmetic_dag_reconstructs_composite_output(self) -> None:
        class ArithmeticPlanLLM(LocalHealthDemoLLM):
            def plan_query(self, spec, context):
                return SemanticQueryPlan(
                    operation="aggregate",
                    datasets=("analytics_health_hospital_output_year",),
                    dimensions=("hospital_id", "hospital_name"),
                    metrics=(
                        "admissions",
                        "outpatient_visits",
                        "surgeries",
                        "total_output",
                    ),
                    calculations=(
                        {
                            "name": "admissions_plus_outpatient",
                            "operator": "add",
                            "left": "admissions",
                            "right": "outpatient_visits",
                        },
                        {
                            "name": "reconstructed_output",
                            "operator": "add",
                            "left": "admissions_plus_outpatient",
                            "right": "surgeries",
                        },
                    ),
                    order_by=(
                        {"field": "reconstructed_output", "direction": "DESC"},
                    ),
                )

        outcome = GovernedQueryPipeline(self.db, ArithmeticPlanLLM(), self.graph).run(
            "Reconstruct hospital output from admissions, outpatient visits, and surgeries"
        )
        self.assertEqual(outcome.status, "PASS_WITH_LIMITATIONS")
        self.assertTrue(
            all(
                row["reconstructed_output"] == row["total_output"]
                for row in outcome.rows
            )
        )
        self.assertIn(
            "arithmetic_calculations",
            outcome.provenance["verification_diagnostics"]["checked_invariants"],
        )

    def test_divide_threshold_and_top_k_are_composable(self) -> None:
        class RatioPlanLLM(LocalHealthDemoLLM):
            def plan_query(self, spec, context):
                return SemanticQueryPlan(
                    operation="aggregate",
                    datasets=("analytics_health_hospital_output_year",),
                    dimensions=("hospital_id", "hospital_name"),
                    metrics=("surgeries", "admissions"),
                    calculations=(
                        {
                            "name": "surgeries_per_100_admissions",
                            "operator": "divide",
                            "left": "surgeries",
                            "right": "admissions",
                            "scale": 100,
                        },
                    ),
                    comparison={
                        "left": "surgeries_per_100_admissions",
                        "operator": ">",
                        "right_value": 0,
                    },
                    order_by=(
                        {
                            "field": "surgeries_per_100_admissions",
                            "direction": "DESC",
                        },
                    ),
                    result_limit=2,
                )

        outcome = GovernedQueryPipeline(self.db, RatioPlanLLM(), self.graph).run(
            "Show the top two hospitals by surgeries per 100 admissions"
        )
        self.assertEqual(outcome.status, "PASS_WITH_LIMITATIONS")
        self.assertEqual(len(outcome.rows), 2)
        self.assertEqual(outcome.provenance["total_result_rows"], 3)
        self.assertTrue(outcome.provenance["result_truncated"])
        self.assertTrue(
            all(row["surgeries_per_100_admissions"] > 0 for row in outcome.rows)
        )

    def test_endpoint_change_and_ratio_are_generic_transforms(self) -> None:
        class EndpointPlanLLM(LocalHealthDemoLLM):
            transform = "endpoint_change"

            def plan_query(self, spec, context):
                return SemanticQueryPlan(
                    operation="aggregate",
                    datasets=("analytics_health_hospital_funding_year",),
                    dimensions=("hospital_id", "hospital_name"),
                    metrics=("operating_funding",),
                    transform=self.transform,
                    order_by=(
                        {
                            "field": f"operating_funding_{self.transform.removeprefix('endpoint_')}",
                            "direction": "DESC",
                        },
                    ),
                    start_year=2022,
                    end_year=2025,
                    result_limit=1,
                )

        for transform, output_field in (
            ("endpoint_change", "operating_funding_change"),
            ("endpoint_ratio", "operating_funding_ratio"),
        ):
            with self.subTest(transform=transform):
                adapter = EndpointPlanLLM()
                adapter.transform = transform
                outcome = GovernedQueryPipeline(self.db, adapter, self.graph).run(
                    "Show the largest hospital funding change from 2022 to 2025"
                )
                self.assertEqual(outcome.status, "PASS_WITH_LIMITATIONS")
                self.assertIn(output_field, outcome.rows[0])
                self.assertEqual(
                    outcome.provenance["verification_status"], "EXECUTION_VERIFIED"
                )

    def test_capability_catalog_remains_internal(self) -> None:
        runtime = operator_capabilities()["operators"]
        self.assertTrue(runtime)
        self.assertTrue(all(row["status"] == "implemented" for row in runtime))
        self.assertIn("rolling_average", {operator.name for operator in OPERATORS})
        self.assertIn("rolling_average", {row["name"] for row in runtime})

    def test_semantic_plan_parser_accepts_nullable_optional_arrays(self) -> None:
        plan = SemanticQueryPlan.from_dict(
            {
                "operation": "records",
                "datasets": ["approved_view"],
                "dimensions": None,
                "metrics": None,
                "fields": ["entity_id"],
                "filters": None,
                "calculations": None,
                "comparison": None,
                "order_by": None,
            }
        )
        self.assertEqual(plan.dimensions, ())
        self.assertEqual(plan.calculations, ())

    def test_equipment_is_linked_to_hospitals_in_database_and_graph(self) -> None:
        outcome = GovernedQueryPipeline(self.db, LocalHealthDemoLLM(), self.graph).run(
            "Show the equipment belonging to each hospital"
        )
        self.assertEqual(outcome.status, "PASS_WITH_LIMITATIONS")
        self.assertEqual(len(outcome.rows), 3)
        self.assertEqual(
            {row["equipment_type"] for row in outcome.rows},
            {"MRI Scanner", "CT Scanner", "Ventilator"},
        )
        self.assertTrue(all(row["hospital_id"] for row in outcome.rows))
        self.assertIsNotNone(outcome.graph_context)
        self.assertTrue(
            any(
                row["predicate"] == "has_equipment"
                for row in outcome.graph_context.relationships
            )
        )
        self.assertIn(
            "analytics_health_hospital_equipment",
            {dataset.name for dataset in outcome.graph_context.datasets},
        )

    def test_healthcare_referral_hierarchy_and_specialty_boundary(self) -> None:
        outcome = GovernedQueryPipeline(self.db, LocalHealthDemoLLM(), self.graph).run(
            "Show the Kerala hospital referral hierarchy by severity"
        )
        self.assertEqual(outcome.status, "PASS_WITH_LIMITATIONS")
        self.assertEqual(len(outcome.rows), 6)
        self.assertEqual(outcome.rows[0]["from_level_code"], "SUBCENTRE_JAK")
        self.assertEqual(outcome.rows[-1]["to_level_code"], "SUPER_SPECIALTY")
        self.assertEqual(outcome.rows[-1]["route_type"], "disease_specific_referral")
        self.assertEqual(outcome.rows[-1]["to_public_access_mode"], "specialty_referral_only")
        self.assertEqual(outcome.rows[-1]["to_disease_specific"], 1)
        self.assertEqual(outcome.provenance["verification_status"], "EXECUTION_VERIFIED")
        self.assertIsNotNone(outcome.graph_context)
        predicates = {row["predicate"] for row in outcome.graph_context.relationships}
        self.assertIn("refers_to", predicates)
        self.assertIn("disease_specific_referral_to", predicates)

    def test_all_districts_have_approximate_referral_pyramid_profiles(self) -> None:
        outcome = GovernedQueryPipeline(
            self.db, LocalHealthDemoLLM(), self.graph, row_limit=100
        ).run("Show the typical referral pyramid distribution for each Kerala district")
        self.assertEqual(outcome.status, "PASS_WITH_LIMITATIONS")
        self.assertEqual(len(outcome.rows), 70)
        self.assertEqual({row["district_id"] for row in outcome.rows}, set(range(1, 15)))
        self.assertEqual(len({row["level_code"] for row in outcome.rows}), 5)
        self.assertTrue(all(row["is_approximate"] == 1 for row in outcome.rows))
        subcentre = next(
            row for row in outcome.rows if row["level_code"] == "SUBCENTRE_JAK"
        )
        self.assertEqual(subcentre["typical_count_label"], "Hundreds")
        self.assertEqual(subcentre["example_min_count"], 150)
        self.assertEqual(subcentre["example_max_count"], 300)
        district_hospital = next(
            row for row in outcome.rows if row["level_code"] == "DH_GH"
        )
        self.assertEqual(district_hospital["typical_min_count"], 1)
        self.assertEqual(district_hospital["typical_max_count"], 1)
        self.assertEqual(outcome.provenance["verification_status"], "EXECUTION_VERIFIED")
        self.assertIsNotNone(outcome.graph_context)
        self.assertIn(
            "typically_contains",
            {row["predicate"] for row in outcome.graph_context.relationships},
        )

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
        self.assertEqual(counts.district_facility_distribution_profile, 70)
        self.assertEqual(counts.healthcare_facility_level, 7)
        self.assertEqual(counts.healthcare_referral_route, 6)
        self.assertEqual(counts.hospital_facility_classification, 2_000)
        self.assertEqual(counts.hospital_funding, 2_000)
        self.assertEqual(counts.hospital_output, 2_000)
        self.assertEqual(counts.hospital_equipment, 2_000)
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
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM hospital_equipment").fetchone()[0],
                2_000,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM hospital_facility_classification"
                ).fetchone()[0],
                2_000,
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM healthcare_facility_level").fetchone()[0],
                7,
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM healthcare_referral_route").fetchone()[0],
                6,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM district_facility_distribution_profile"
                ).fetchone()[0],
                70,
            )
        outcome = GovernedQueryPipeline(self.db, LocalHealthDemoLLM(), self.graph).run(
            "Which hospitals received more operating funding without comparable output growth?"
        )
        self.assertEqual(outcome.status, "PASS_WITH_LIMITATIONS")
        self.assertEqual(len(outcome.rows), 100)
        self.assertGreater(outcome.provenance["total_result_rows"], len(outcome.rows))
        self.assertTrue(outcome.provenance["result_truncated"])
        self.assertIn("Showing the first 100 of", outcome.findings)

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

    def test_time_bucket_lag_lead_and_rolling_windows_are_verified(self) -> None:
        class WindowPlanLLM(LocalHealthDemoLLM):
            def plan_query(self, spec, context):
                return SemanticQueryPlan(
                    operation="aggregate",
                    datasets=("analytics_health_hospital_output_year",),
                    dimensions=("hospital_id", "hospital_name"),
                    metrics=("admissions",),
                    time_bucket={"name": "period", "field": "fiscal_year", "grain": "year"},
                    window_calculations=(
                        {"name": "previous_admissions", "operator": "lag", "input": "admissions", "partition_by": ["hospital_id"], "order_field": "period", "direction": "ASC", "offset": 1},
                        {"name": "next_admissions", "operator": "lead", "input": "admissions", "partition_by": ["hospital_id"], "order_field": "period", "direction": "ASC", "offset": 1},
                        {"name": "rolling_admissions", "operator": "rolling_sum", "input": "admissions", "partition_by": ["hospital_id"], "order_field": "period", "direction": "ASC", "window": 2},
                        {"name": "rolling_average_admissions", "operator": "rolling_average", "input": "admissions", "partition_by": ["hospital_id"], "order_field": "period", "direction": "ASC", "window": 2},
                        {"name": "rolling_stddev_admissions", "operator": "rolling_stddev", "input": "admissions", "partition_by": ["hospital_id"], "order_field": "period", "direction": "ASC", "window": 2},
                    ),
                    order_by=(
                        {"field": "hospital_id", "direction": "ASC"},
                        {"field": "period", "direction": "ASC"},
                    ),
                )

        outcome = GovernedQueryPipeline(self.db, WindowPlanLLM(), self.graph).run(
            "Show hospital admissions over time"
        )
        self.assertEqual(outcome.status, "PASS_WITH_LIMITATIONS", outcome.stop_reason)
        self.assertEqual(len(outcome.rows), 12)
        self.assertIsNone(outcome.rows[0]["previous_admissions"])
        self.assertEqual(outcome.rows[0]["next_admissions"], outcome.rows[1]["admissions"])
        self.assertIn(
            "window_formulas",
            outcome.provenance["verification_diagnostics"]["checked_invariants"],
        )

    def test_generic_statistical_operators_are_recomputed(self) -> None:
        class StatisticsPlanLLM(LocalHealthDemoLLM):
            def plan_query(self, spec, context):
                return SemanticQueryPlan(
                    operation="aggregate",
                    datasets=("analytics_health_hospital_output_year",),
                    dimensions=("hospital_id", "hospital_name", "fiscal_year"),
                    metrics=("admissions", "surgeries"),
                    statistics=(
                        {"name": "admissions_z", "operator": "z_score", "input": "admissions", "partition_by": []},
                        {"name": "admissions_percentile", "operator": "percentile", "input": "admissions", "partition_by": []},
                        {"name": "admissions_outlier", "operator": "iqr_outlier", "input": "admissions", "partition_by": []},
                        {"name": "admissions_trend", "operator": "trend_slope", "input": "admissions", "time": "fiscal_year", "partition_by": ["hospital_id"]},
                        {"name": "activity_correlation", "operator": "correlation", "left": "admissions", "right": "surgeries", "partition_by": ["hospital_id"]},
                    ),
                    order_by=(
                        {"field": "hospital_id", "direction": "ASC"},
                        {"field": "fiscal_year", "direction": "ASC"},
                    ),
                )

        outcome = GovernedQueryPipeline(self.db, StatisticsPlanLLM(), self.graph).run(
            "Analyze hospital admissions and surgeries"
        )
        self.assertEqual(outcome.status, "PASS_WITH_LIMITATIONS", outcome.stop_reason)
        self.assertEqual(len(outcome.rows), 12)
        self.assertTrue(all(0 <= row["admissions_percentile"] <= 1 for row in outcome.rows))
        self.assertIn(
            "statistical_formulas",
            outcome.provenance["verification_diagnostics"]["checked_invariants"],
        )

    def test_data_quality_operators_return_one_verified_summary(self) -> None:
        class QualityPlanLLM(LocalHealthDemoLLM):
            def plan_query(self, spec, context):
                return SemanticQueryPlan(
                    operation="data_quality",
                    datasets=("analytics_health_hospital_equipment",),
                    data_quality_checks=(
                        {"name": "maintenance_missing", "operator": "missing_count", "field": "last_maintenance_on"},
                        {"name": "maintenance_missing_pct", "operator": "missing_pct", "field": "last_maintenance_on"},
                        {"name": "equipment_types", "operator": "distinct_count", "field": "equipment_type"},
                        {"name": "repeated_equipment_types", "operator": "duplicate_count", "field": "equipment_type"},
                        {"name": "minimum_downtime", "operator": "minimum", "field": "downtime_hours_last_12m"},
                        {"name": "maximum_downtime", "operator": "maximum", "field": "downtime_hours_last_12m"},
                        {"name": "latest_maintenance", "operator": "freshness_max", "field": "last_maintenance_on"},
                    ),
                )

        outcome = GovernedQueryPipeline(self.db, QualityPlanLLM(), self.graph).run(
            "Check hospital equipment data quality"
        )
        self.assertEqual(outcome.status, "PASS_WITH_LIMITATIONS", outcome.stop_reason)
        self.assertEqual(len(outcome.rows), 1)
        self.assertEqual(outcome.rows[0]["row_count"], 3)
        self.assertIn(
            "data_quality_invariants",
            outcome.provenance["verification_diagnostics"]["checked_invariants"],
        )

    def test_graph_path_and_neighborhood_execute_without_sql(self) -> None:
        class GraphPlanLLM(LocalHealthDemoLLM):
            operator = "graph_path"

            def plan_query(self, spec, context):
                graph_query = (
                    {
                        "operator": "graph_path",
                        "start": "Hospital",
                        "end": "Equipment",
                        "start_kind": "entity",
                        "end_kind": "entity",
                        "direction": "outgoing",
                        "max_depth": 3,
                        "edge_types": ["SEMANTIC_RELATION"],
                    }
                    if self.operator == "graph_path"
                    else {
                        "operator": "graph_neighborhood",
                        "start": "Hospital",
                        "direction": "outgoing",
                        "max_depth": 1,
                        "edge_types": ["SEMANTIC_RELATION"],
                        "node_kinds": ["SemanticEntity"],
                    }
                )
                return SemanticQueryPlan(operation="graph", datasets=(), graph_query=graph_query)

        adapter = GraphPlanLLM()
        path = GovernedQueryPipeline(self.db, adapter, self.graph).run(
            "How is a hospital related to equipment?"
        )
        self.assertEqual(path.status, "PASS_WITH_LIMITATIONS", path.stop_reason)
        self.assertIsNone(path.sql)
        self.assertEqual(path.rows[0]["relation"], "has_equipment")
        self.assertEqual(path.provenance["execution_mode"], "KGRAPH_PLAN_EXECUTED")

        adapter.operator = "graph_neighborhood"
        neighborhood = GovernedQueryPipeline(self.db, adapter, self.graph).run(
            "What is connected to a hospital and its equipment?"
        )
        self.assertEqual(neighborhood.status, "PASS_WITH_LIMITATIONS", neighborhood.stop_reason)
        self.assertTrue(any(row["node_name"] == "Equipment" for row in neighborhood.rows))


if __name__ == "__main__":
    unittest.main()
