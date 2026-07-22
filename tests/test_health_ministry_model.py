from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from kgraph_llm.knowledge_graph import NetworkXSemanticGraph
from kgraph_llm.ministries.health.comprehensive_synthetic import (
    HIGH_CARDINALITY_TABLES,
    seed_comprehensive_health_data,
)
from kgraph_llm.ministries.health.synthetic import seed_synthetic_business_data
from kgraph_llm.ministries.registry import active_graph_definitions
from kgraph_llm.storage import Database


class HealthMinistryModelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp_dir.name) / "health-ministry.db")
        self.database.initialize()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_report_layers_and_core_tables_are_bootstrapped(self) -> None:
        expected = {
            "master_organisation",
            "master_facility",
            "master_geographic_area",
            "master_source_system",
            "analytics_facility_monthly_summary",
            "analytics_medicine_monthly",
            "analytics_equipment_monthly",
            "analytics_staffing_monthly",
            "analytics_service_monthly",
            "analytics_referral_flow_monthly",
            "analytics_procurement_monthly",
            "analytics_supplier_performance_monthly",
            "analytics_infrastructure_monthly",
            "analytics_vehicle_monthly",
            "analytics_programme_monthly",
            "analytics_scheme_monthly",
            "analytics_medical_college_annual",
            "analytics_quality_monthly",
            "analytics_project_monthly",
            "analytics_data_quality_monthly",
            "analytics_audit_issue",
            "finance_budget_monthly",
            "finance_expenditure_monthly",
            "finance_liability_monthly",
            "restricted_beneficiary",
            "restricted_household",
            "restricted_scheme_enrollment",
            "restricted_claim_identity_link",
            "restricted_fraud_signal",
            "restricted_investigation",
            "semantic_metric_definition",
            "semantic_dimension_definition",
            "semantic_capability",
            "semantic_capability_input",
            "semantic_allowed_join",
            "semantic_quality_rule",
            "semantic_access_policy",
        }
        with sqlite3.connect(self.database.path) as connection:
            actual = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        self.assertTrue(expected.issubset(actual))
        self.assertEqual(foreign_key_errors, [])

    def test_rates_are_derived_in_governed_views(self) -> None:
        with sqlite3.connect(self.database.path) as connection:
            connection.row_factory = sqlite3.Row
            facility = connection.execute(
                """
                SELECT bed_occupancy_percentage,
                       staff_sufficiency_percentage,
                       budget_utilisation_percentage
                FROM analytics_health_facility_monthly
                WHERE facility_id = 1 AND month_id = '2026-06-01'
                """
            ).fetchone()
            medicine = connection.execute(
                """
                SELECT medicine_sufficiency_percentage, expiry_loss_percentage
                FROM analytics_health_medicine_monthly
                WHERE facility_id = 1 AND month_id = '2026-06-01'
                """
            ).fetchone()
            equipment = connection.execute(
                """
                SELECT equipment_functionality_percentage,
                       maintenance_cost_ratio_percentage
                FROM analytics_health_equipment_monthly
                WHERE facility_id = 1 AND month_id = '2026-06-01'
                """
            ).fetchone()

        self.assertAlmostEqual(facility["bed_occupancy_percentage"], 74.4681, places=4)
        self.assertAlmostEqual(facility["staff_sufficiency_percentage"], 87.9032, places=4)
        self.assertEqual(facility["budget_utilisation_percentage"], 80.0)
        self.assertEqual(medicine["medicine_sufficiency_percentage"], 86.0)
        self.assertAlmostEqual(medicine["expiry_loss_percentage"], 1.4516, places=4)
        self.assertEqual(equipment["equipment_functionality_percentage"], 87.5)
        self.assertAlmostEqual(
            equipment["maintenance_cost_ratio_percentage"], 1.8333, places=4
        )

    def test_semantic_registry_records_quality_privacy_and_join_rules(self) -> None:
        with sqlite3.connect(self.database.path) as connection:
            metric = connection.execute(
                """
                SELECT privacy_classification, minimum_data_quality_score
                FROM semantic_metric_definition
                WHERE metric_code = 'MEDICINE_SUFFICIENCY'
                """
            ).fetchone()
            capability = connection.execute(
                """
                SELECT minimum_data_quality_score, known_limitations
                FROM semantic_capability
                WHERE capability_code = 'health.detect_medicine_shortages'
                """
            ).fetchone()
            join = connection.execute(
                """
                SELECT cardinality, approval_status
                FROM semantic_allowed_join
                WHERE left_dataset = 'analytics_health_facility_monthly'
                  AND right_dataset = 'analytics_health_equipment_monthly'
                """
            ).fetchone()

        self.assertEqual(metric, ("INTERNAL", 85.0))
        self.assertEqual(capability[0], 90.0)
        self.assertIn("drill-down", capability[1])
        self.assertEqual(join, ("ONE_TO_MANY_BY_CATEGORY", "APPROVED"))

    def test_peripheral_graph_contains_structure_not_restricted_people(self) -> None:
        graph = NetworkXSemanticGraph.from_definitions(active_graph_definitions())
        entity_names = {
            attributes["name"]
            for _, attributes in graph.graph.nodes(data=True)
            if attributes.get("kind") == "SemanticEntity"
        }
        relationships = {
            (
                attributes.get("from_entity"),
                attributes.get("predicate"),
                attributes.get("to_entity"),
            )
            for _, _, attributes in graph.graph.edges(data=True)
            if attributes.get("relation") == "SEMANTIC_RELATION"
        }

        self.assertTrue(
            {
                "Department",
                "Directorate",
                "Organisation",
                "Facility",
                "Programme",
                "Scheme",
                "Supplier",
                "AnalyticalMetric",
                "AnalyticalCapability",
            }.issubset(entity_names)
        )
        self.assertNotIn("Person", entity_names)
        self.assertNotIn("Beneficiary", entity_names)
        self.assertIn(("Organisation", "operates", "Facility"), relationships)
        self.assertIn(("Facility", "requires", "StaffCategory"), relationships)
        self.assertIn(
            ("AnalyticalCapability", "uses_metric", "AnalyticalMetric"),
            relationships,
        )
        self.assertFalse(
            any(name.startswith("restricted_") for name in graph.allowed_datasets())
        )

    def test_graph_registers_grains_and_category_safe_joins(self) -> None:
        graph = NetworkXSemanticGraph.from_definitions(active_graph_definitions())
        dataset_nodes = {
            attributes["name"]: attributes
            for _, attributes in graph.graph.nodes(data=True)
            if attributes.get("kind") == "SemanticDataset"
        }
        joins = [
            attributes
            for _, _, attributes in graph.graph.edges(data=True)
            if attributes.get("relation") == "DATASET_JOIN"
        ]

        self.assertEqual(
            dataset_nodes["analytics_health_service_monthly"]["grain"],
            "Facility x ServiceCategory x DemographicGroup x Month",
        )
        equipment_join = next(
            row
            for row in joins
            if row.get("right_dataset") == "analytics_health_equipment_monthly"
        )
        self.assertEqual(
            equipment_join["cardinality"], "one_to_many_by_equipment_category"
        )

    def test_comprehensive_synthetic_seed_populates_every_table_and_column(self) -> None:
        seed_synthetic_business_data(self.database, rows_per_table=50)
        result = seed_comprehensive_health_data(self.database, rows_per_table=50)

        self.assertEqual(result.empty_tables, ())
        self.assertEqual(result.all_null_columns, ())
        self.assertTrue(
            all(result.table_counts[table] == 50 for table in HIGH_CARDINALITY_TABLES)
        )


if __name__ == "__main__":
    unittest.main()
