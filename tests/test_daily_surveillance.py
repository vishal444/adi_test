from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from kgraph_llm.ministries.health import DailyAdmissionSurveillance
from kgraph_llm.storage import Database


class DailyAdmissionSurveillanceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp_dir.name) / "surveillance.db")
        self.database.initialize()
        self.reporting_date = date(2026, 1, 20)
        with sqlite3.connect(self.database.path) as connection:
            connection.execute(
                """
                INSERT INTO hospital
                    (hospital_id, hospital_name, district_id, master_facility_id)
                VALUES (4, 'Kozhikode Community Hospital', 11, NULL)
                """
            )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _insert_complete_submission(
        self, connection: sqlite3.Connection, hospital_id: int, reporting_date: date
    ) -> None:
        connection.execute(
            """
            INSERT INTO hospital_daily_submission
                (hospital_id, reporting_date, submitted_at,
                 submission_status, source_version)
            VALUES (?, ?, ?, 'complete', 'test-daily-v1')
            """,
            (
                hospital_id,
                reporting_date.isoformat(),
                f"{reporting_date.isoformat()}T23:00:00+05:30",
            ),
        )

    def _insert_admissions(
        self,
        connection: sqlite3.Connection,
        hospital_id: int,
        reporting_date: date,
        admissions: int,
    ) -> None:
        connection.execute(
            """
            INSERT INTO hospital_admission_daily
                (hospital_id, patient_district_id, reporting_date, syndrome_code,
                 age_band, admissions, source_version)
            VALUES (?, 11, ?, 'ACUTE_RESPIRATORY', 'ALL', ?, 'test-daily-v1')
            """,
            (hospital_id, reporting_date.isoformat(), admissions),
        )

    def test_detects_corroborated_daily_spike_and_requires_review(self) -> None:
        with sqlite3.connect(self.database.path) as connection:
            for week in range(1, 9):
                baseline_date = self.reporting_date - timedelta(days=7 * week)
                for hospital_id in (1, 2, 3, 4):
                    self._insert_complete_submission(
                        connection, hospital_id, baseline_date
                    )
                self._insert_admissions(connection, 2, baseline_date, 5)
                self._insert_admissions(connection, 4, baseline_date, 4)

            for hospital_id in (1, 2, 3, 4):
                self._insert_complete_submission(
                    connection, hospital_id, self.reporting_date
                )
            self._insert_admissions(connection, 2, self.reporting_date, 15)
            self._insert_admissions(connection, 4, self.reporting_date, 15)

        outcome = DailyAdmissionSurveillance(self.database).run(self.reporting_date)

        self.assertEqual(outcome.status, "COMPLETED")
        self.assertEqual(outcome.reporting_completeness, 1.0)
        self.assertEqual(len(outcome.signals), 4)
        district = next(
            signal
            for signal in outcome.signals
            if signal.geography_type == "DISTRICT"
        )
        self.assertEqual(district.geography_name, "Kozhikode")
        self.assertEqual(district.observed_count, 30)
        self.assertEqual(district.expected_count, 9.0)
        self.assertEqual(district.contributing_hospitals, 2)
        self.assertEqual(district.signal_level, "HIGH")

        with sqlite3.connect(self.database.path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT review_status, corroborated, evidence_json
                FROM health_surveillance_signal
                WHERE run_id = ? AND geography_type = 'DISTRICT'
                """,
                (outcome.run_id,),
            ).fetchone()
            run = connection.execute(
                "SELECT run_status, signal_count FROM daily_surveillance_run WHERE run_id = ?",
                (outcome.run_id,),
            ).fetchone()
        self.assertEqual(row["review_status"], "NEEDS_REVIEW")
        self.assertEqual(row["corroborated"], 1)
        self.assertTrue(json.loads(row["evidence_json"])["human_verification_required"])
        self.assertEqual(tuple(run), ("COMPLETED", 4))

    def test_incomplete_daily_reporting_stops_before_signal_detection(self) -> None:
        with sqlite3.connect(self.database.path) as connection:
            for hospital_id in (1, 2, 3):
                self._insert_complete_submission(
                    connection, hospital_id, self.reporting_date
                )
            self._insert_admissions(connection, 2, self.reporting_date, 100)

        outcome = DailyAdmissionSurveillance(self.database).run(self.reporting_date)

        self.assertEqual(outcome.status, "INCOMPLETE_DATA")
        self.assertEqual(outcome.expected_hospitals, 4)
        self.assertEqual(outcome.complete_hospitals, 3)
        self.assertEqual(outcome.reporting_completeness, 0.75)
        self.assertEqual(outcome.signals, ())
        with sqlite3.connect(self.database.path) as connection:
            signal_count = connection.execute(
                "SELECT COUNT(*) FROM health_surveillance_signal WHERE run_id = ?",
                (outcome.run_id,),
            ).fetchone()[0]
            run_status = connection.execute(
                "SELECT run_status FROM daily_surveillance_run WHERE run_id = ?",
                (outcome.run_id,),
            ).fetchone()[0]
        self.assertEqual(signal_count, 0)
        self.assertEqual(run_status, "INCOMPLETE_DATA")


if __name__ == "__main__":
    unittest.main()
