from __future__ import annotations

import json
import math
import sqlite3
import statistics
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from ...storage.database import Database


KERALA_TIMEZONE = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class SurveillanceConfig:
    """Governed pilot thresholds; production values require epidemiological approval."""

    baseline_weeks: int = 8
    minimum_reporting_completeness: float = 0.80
    minimum_case_count: int = 5
    minimum_observed_expected_ratio: float = 1.50
    minimum_anomaly_score: float = 3.0
    corroborating_hospitals: int = 2
    method_version: str = "daily-same-weekday-zscore-v1"

    def validate(self) -> None:
        if not 2 <= self.baseline_weeks <= 52:
            raise ValueError("baseline_weeks must be between 2 and 52.")
        if not 0 < self.minimum_reporting_completeness <= 1:
            raise ValueError("minimum_reporting_completeness must be in (0, 1].")
        if self.minimum_case_count < 1:
            raise ValueError("minimum_case_count must be positive.")
        if self.minimum_observed_expected_ratio <= 1:
            raise ValueError("minimum_observed_expected_ratio must be greater than 1.")
        if self.minimum_anomaly_score <= 0:
            raise ValueError("minimum_anomaly_score must be positive.")
        if self.corroborating_hospitals < 1:
            raise ValueError("corroborating_hospitals must be positive.")


@dataclass(frozen=True)
class SurveillanceSignal:
    signal_id: int
    geography_type: str
    geography_name: str
    syndrome_code: str
    observed_count: int
    expected_count: float
    anomaly_score: float
    contributing_hospitals: int
    signal_level: str


@dataclass(frozen=True)
class DailySurveillanceOutcome:
    run_id: int
    reporting_date: str
    status: str
    expected_hospitals: int
    complete_hospitals: int
    reporting_completeness: float
    signals: tuple[SurveillanceSignal, ...] = ()
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DailyAdmissionSurveillance:
    """Deterministic daily spike detector over governed aggregate admission data."""

    def __init__(
        self,
        database: Database,
        config: SurveillanceConfig | None = None,
    ) -> None:
        self.database = database
        self.config = config or SurveillanceConfig()
        self.config.validate()

    @staticmethod
    def default_reporting_date() -> date:
        return datetime.now(KERALA_TIMEZONE).date() - timedelta(days=1)

    def run(self, reporting_date: date | str | None = None) -> DailySurveillanceOutcome:
        target = self._parse_date(reporting_date or self.default_reporting_date())
        with sqlite3.connect(self.database.path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            expected = self._expected_hospitals(connection, target)
            complete = self._complete_hospitals(connection, target)
            completeness = complete / expected if expected else 0.0
            run_id = self._start_run(
                connection, target, expected, complete, completeness
            )
            connection.commit()

            if expected == 0 or completeness < self.config.minimum_reporting_completeness:
                self._finish_run(connection, run_id, "INCOMPLETE_DATA", 0)
                connection.commit()
                return DailySurveillanceOutcome(
                    run_id=run_id,
                    reporting_date=target.isoformat(),
                    status="INCOMPLETE_DATA",
                    expected_hospitals=expected,
                    complete_hospitals=complete,
                    reporting_completeness=completeness,
                    message=(
                        "No signals were evaluated because the completed hospital "
                        "submission rate was below the governed threshold."
                    ),
                )

            try:
                signals = self._detect(connection, run_id, target, completeness)
                self._finish_run(connection, run_id, "COMPLETED", len(signals))
                connection.commit()
            except Exception:
                connection.rollback()
                self._finish_run(connection, run_id, "FAILED", 0)
                connection.commit()
                raise
            return DailySurveillanceOutcome(
                run_id=run_id,
                reporting_date=target.isoformat(),
                status="COMPLETED",
                expected_hospitals=expected,
                complete_hospitals=complete,
                reporting_completeness=completeness,
                signals=tuple(signals),
                message=(
                    f"Created {len(signals)} signal(s) requiring human review."
                    if signals
                    else "No admission spike crossed the governed pilot thresholds."
                ),
            )

    def _detect(
        self,
        connection: sqlite3.Connection,
        run_id: int,
        target: date,
        completeness: float,
    ) -> list[SurveillanceSignal]:
        baseline_dates = tuple(
            target - timedelta(days=7 * week)
            for week in range(1, self.config.baseline_weeks + 1)
        )
        current = self._current_groups(connection, target)
        names = self._geography_names(connection)
        created: list[SurveillanceSignal] = []
        for geography_type, geography_id, syndrome_code, observed, contributors in current:
            if not self._baseline_is_complete(
                connection, geography_type, geography_id, baseline_dates
            ):
                continue
            baseline = self._baseline_counts(
                connection,
                geography_type,
                geography_id,
                syndrome_code,
                baseline_dates,
            )
            expected = statistics.fmean(baseline)
            stddev = statistics.pstdev(baseline)
            scale = max(stddev, math.sqrt(expected), 1.0)
            score = (observed - expected) / scale
            ratio = observed / expected if expected > 0 else None
            ratio_passes = (
                ratio is None or ratio >= self.config.minimum_observed_expected_ratio
            )
            if not (
                observed >= self.config.minimum_case_count
                and ratio_passes
                and score >= self.config.minimum_anomaly_score
            ):
                continue

            corroborated = contributors >= self.config.corroborating_hospitals
            level = (
                "HIGH"
                if corroborated and geography_type in {"DISTRICT", "STATE"}
                else "WATCH"
            )
            geography_name = names[geography_type][geography_id]
            evidence = {
                "baseline_dates": [value.isoformat() for value in baseline_dates],
                "baseline_counts": baseline,
                "thresholds": asdict(self.config),
                "human_verification_required": True,
                "interpretation": "surveillance signal, not an outbreak declaration",
            }
            cursor = connection.execute(
                """
                INSERT INTO health_surveillance_signal
                    (run_id, reporting_date, geography_type, geography_id,
                     geography_name, syndrome_code, observed_count, expected_count,
                     baseline_stddev, anomaly_score, observed_expected_ratio,
                     contributing_hospitals, reporting_completeness, corroborated,
                     signal_level, method_version, evidence_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    target.isoformat(),
                    geography_type,
                    geography_id,
                    geography_name,
                    syndrome_code,
                    observed,
                    expected,
                    stddev,
                    score,
                    ratio,
                    contributors,
                    completeness,
                    int(corroborated),
                    level,
                    self.config.method_version,
                    json.dumps(evidence, sort_keys=True),
                ),
            )
            created.append(
                SurveillanceSignal(
                    signal_id=int(cursor.lastrowid),
                    geography_type=geography_type,
                    geography_name=geography_name,
                    syndrome_code=syndrome_code,
                    observed_count=observed,
                    expected_count=round(expected, 3),
                    anomaly_score=round(score, 3),
                    contributing_hospitals=contributors,
                    signal_level=level,
                )
            )
        return created

    def _baseline_is_complete(
        self,
        connection: sqlite3.Connection,
        geography_type: str,
        geography_id: int,
        baseline_dates: tuple[date, ...],
    ) -> bool:
        date_strings = tuple(value.isoformat() for value in baseline_dates)
        placeholders = ",".join("?" for _ in date_strings)
        if geography_type == "HOSPITAL":
            completed_dates = int(
                connection.execute(
                    f"""
                    SELECT COUNT(DISTINCT reporting_date)
                    FROM hospital_daily_submission
                    WHERE hospital_id = ?
                      AND submission_status = 'complete'
                      AND reporting_date IN ({placeholders})
                    """,
                    (geography_id, *date_strings),
                ).fetchone()[0]
            )
            return completed_dates == len(baseline_dates)

        for baseline_date in baseline_dates:
            expected = self._expected_hospitals(connection, baseline_date)
            complete = self._complete_hospitals(connection, baseline_date)
            completeness = complete / expected if expected else 0.0
            if completeness < self.config.minimum_reporting_completeness:
                return False
        return True

    @staticmethod
    def _parse_date(value: date | str) -> date:
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("reporting_date must use YYYY-MM-DD format.") from exc

    @staticmethod
    def _expected_hospitals(connection: sqlite3.Connection, target: date) -> int:
        return int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM hospital
                WHERE effective_from <= ?
                  AND (effective_to IS NULL OR effective_to > ?)
                """,
                (target.isoformat(), target.isoformat()),
            ).fetchone()[0]
        )

    @staticmethod
    def _complete_hospitals(connection: sqlite3.Connection, target: date) -> int:
        return int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM hospital_daily_submission AS submission
                JOIN hospital AS h ON h.hospital_id = submission.hospital_id
                WHERE submission.reporting_date = ?
                  AND submission.submission_status = 'complete'
                  AND h.effective_from <= ?
                  AND (h.effective_to IS NULL OR h.effective_to > ?)
                """,
                (target.isoformat(), target.isoformat(), target.isoformat()),
            ).fetchone()[0]
        )

    def _start_run(
        self,
        connection: sqlite3.Connection,
        target: date,
        expected: int,
        complete: int,
        completeness: float,
    ) -> int:
        cursor = connection.execute(
            """
            INSERT INTO daily_surveillance_run
                (reporting_date, method_version, expected_hospitals,
                 complete_hospitals, reporting_completeness, run_status, config_json)
            VALUES (?, ?, ?, ?, ?, 'RUNNING', ?)
            """,
            (
                target.isoformat(),
                self.config.method_version,
                expected,
                complete,
                completeness,
                json.dumps(asdict(self.config), sort_keys=True),
            ),
        )
        return int(cursor.lastrowid)

    @staticmethod
    def _finish_run(
        connection: sqlite3.Connection, run_id: int, status: str, signal_count: int
    ) -> None:
        connection.execute(
            """
            UPDATE daily_surveillance_run
            SET completed_at = CURRENT_TIMESTAMP, run_status = ?, signal_count = ?
            WHERE run_id = ?
            """,
            (status, signal_count, run_id),
        )

    @staticmethod
    def _geography_names(
        connection: sqlite3.Connection,
    ) -> dict[str, dict[int, str]]:
        hospitals = {
            int(row[0]): str(row[1])
            for row in connection.execute("SELECT hospital_id, hospital_name FROM hospital")
        }
        districts = {
            int(row[0]): str(row[1])
            for row in connection.execute("SELECT district_id, district_name FROM district")
        }
        return {"HOSPITAL": hospitals, "DISTRICT": districts, "STATE": {0: "Kerala"}}

    @staticmethod
    def _current_groups(
        connection: sqlite3.Connection, target: date
    ) -> list[tuple[str, int, str, int, int]]:
        target_text = target.isoformat()
        groups: list[tuple[str, int, str, int, int]] = []
        specifications = (
            ("HOSPITAL", "admission.hospital_id"),
            ("DISTRICT", "admission.patient_district_id"),
        )
        for geography_type, field in specifications:
            rows = connection.execute(
                f"""
                SELECT {field}, admission.syndrome_code, SUM(admission.admissions),
                       COUNT(DISTINCT admission.hospital_id)
                FROM hospital_admission_daily AS admission
                JOIN hospital_daily_submission AS submission
                  ON submission.hospital_id = admission.hospital_id
                 AND submission.reporting_date = admission.reporting_date
                 AND submission.submission_status = 'complete'
                WHERE admission.reporting_date = ?
                GROUP BY {field}, admission.syndrome_code
                """,
                (target_text,),
            )
            groups.extend(
                (geography_type, int(row[0]), str(row[1]), int(row[2]), int(row[3]))
                for row in rows
            )
        rows = connection.execute(
            """
            SELECT admission.syndrome_code, SUM(admission.admissions),
                   COUNT(DISTINCT admission.hospital_id)
            FROM hospital_admission_daily AS admission
            JOIN hospital_daily_submission AS submission
              ON submission.hospital_id = admission.hospital_id
             AND submission.reporting_date = admission.reporting_date
             AND submission.submission_status = 'complete'
            WHERE admission.reporting_date = ?
            GROUP BY admission.syndrome_code
            """,
            (target_text,),
        )
        groups.extend(
            ("STATE", 0, str(row[0]), int(row[1]), int(row[2])) for row in rows
        )
        return groups

    @staticmethod
    def _baseline_counts(
        connection: sqlite3.Connection,
        geography_type: str,
        geography_id: int,
        syndrome_code: str,
        baseline_dates: tuple[date, ...],
    ) -> list[int]:
        date_strings = tuple(value.isoformat() for value in baseline_dates)
        placeholders = ",".join("?" for _ in date_strings)
        filters = {
            "HOSPITAL": ("admission.hospital_id = ?", (geography_id,)),
            "DISTRICT": ("admission.patient_district_id = ?", (geography_id,)),
            "STATE": ("1 = 1", ()),
        }
        geography_sql, geography_parameters = filters[geography_type]
        rows = connection.execute(
            f"""
            SELECT admission.reporting_date, SUM(admission.admissions)
            FROM hospital_admission_daily AS admission
            JOIN hospital_daily_submission AS submission
              ON submission.hospital_id = admission.hospital_id
             AND submission.reporting_date = admission.reporting_date
             AND submission.submission_status = 'complete'
            WHERE {geography_sql}
              AND admission.syndrome_code = ?
              AND admission.reporting_date IN ({placeholders})
            GROUP BY admission.reporting_date
            """,
            (*geography_parameters, syndrome_code, *date_strings),
        )
        by_date = {str(row[0]): int(row[1]) for row in rows}
        return [by_date.get(value, 0) for value in date_strings]


def run_daily_admission_surveillance(
    database_path: str | Path,
    reporting_date: date | str | None = None,
    config: SurveillanceConfig | None = None,
) -> DailySurveillanceOutcome:
    return DailyAdmissionSurveillance(Database(database_path), config).run(reporting_date)
