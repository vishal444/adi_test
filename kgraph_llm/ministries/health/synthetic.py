from __future__ import annotations

import random
import sqlite3
from dataclasses import dataclass

from ...storage.database import Database


KERALA_DISTRICTS = (
    "Thiruvananthapuram",
    "Kollam",
    "Pathanamthitta",
    "Alappuzha",
    "Kottayam",
    "Idukki",
    "Ernakulam",
    "Thrissur",
    "Palakkad",
    "Malappuram",
    "Kozhikode",
    "Wayanad",
    "Kannur",
    "Kasaragod",
)


@dataclass(frozen=True)
class SyntheticCounts:
    district: int
    hospital: int
    hospital_funding: int
    hospital_output: int


def seed_synthetic_business_data(
    database: Database,
    *,
    rows_per_table: int = 2_000,
    random_seed: int = 20_260_721,
) -> SyntheticCounts:
    """Replace business fixtures with deterministic, referentially valid test data.

    Hospital, funding, and output receive exactly ``rows_per_table`` rows. Funding
    and output use two endpoint years for half of the hospitals so growth queries
    remain meaningful. District and semantic tables retain their natural cardinality.
    """
    if rows_per_table < 2:
        raise ValueError("rows_per_table must be at least 2")

    generator = random.Random(random_seed)
    compared_hospitals = rows_per_table // 2
    if compared_hospitals == 0:
        raise ValueError("At least two fact rows are required for comparison data.")

    districts = tuple(
        (index, name) for index, name in enumerate(KERALA_DISTRICTS, start=1)
    )
    hospitals = []
    for hospital_id in range(1, rows_per_table + 1):
        district_id = ((hospital_id - 1) % len(districts)) + 1
        district_name = districts[district_id - 1][1]
        hospitals.append(
            (
                hospital_id,
                f"{district_name} Synthetic Hospital {hospital_id:04d}",
                district_id,
                "2020-04-01",
                None,
            )
        )

    funding_rows = []
    output_rows = []
    for hospital_id in range(1, compared_hospitals + 1):
        base_funding = round(generator.uniform(70.0, 260.0), 2)
        funding_growth = generator.uniform(-0.05, 0.75)
        base_admissions = generator.randint(1_500, 8_000)
        base_outpatients = generator.randint(6_000, 30_000)
        base_surgeries = generator.randint(250, 2_500)
        output_growth = generator.uniform(-0.08, 0.55)

        funding_rows.extend(
            (
                (hospital_id, 2022, "operating", base_funding, "synthetic-health-v1"),
                (
                    hospital_id,
                    2025,
                    "operating",
                    round(base_funding * (1.0 + funding_growth), 2),
                    "synthetic-health-v1",
                ),
            )
        )
        output_rows.extend(
            (
                (
                    hospital_id,
                    2022,
                    base_admissions,
                    base_outpatients,
                    base_surgeries,
                    "synthetic-health-v1",
                ),
                (
                    hospital_id,
                    2025,
                    max(0, round(base_admissions * (1.0 + output_growth))),
                    max(0, round(base_outpatients * (1.0 + output_growth))),
                    max(0, round(base_surgeries * (1.0 + output_growth))),
                    "synthetic-health-v1",
                ),
            )
        )

    # For odd row counts, add one start-year observation for the next hospital.
    if len(funding_rows) < rows_per_table:
        hospital_id = compared_hospitals + 1
        funding_rows.append(
            (hospital_id, 2022, "operating", 100.0, "synthetic-health-v1")
        )
        output_rows.append(
            (hospital_id, 2022, 2_000, 8_000, 500, "synthetic-health-v1")
        )

    with sqlite3.connect(database.path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("DELETE FROM hospital_output")
        connection.execute("DELETE FROM hospital_funding")
        connection.execute("DELETE FROM hospital")
        connection.execute("DELETE FROM district")
        connection.execute("DELETE FROM audit_execution")
        connection.executemany(
            "INSERT INTO district(district_id, district_name) VALUES (?, ?)", districts
        )
        connection.executemany(
            """
            INSERT INTO hospital
                (hospital_id, hospital_name, district_id, effective_from, effective_to)
            VALUES (?, ?, ?, ?, ?)
            """,
            hospitals,
        )
        connection.executemany(
            """
            INSERT INTO hospital_funding
                (hospital_id, fiscal_year, funding_category, amount_lakh, source_version)
            VALUES (?, ?, ?, ?, ?)
            """,
            funding_rows,
        )
        connection.executemany(
            """
            INSERT INTO hospital_output
                (hospital_id, fiscal_year, admissions, outpatient_visits, surgeries, source_version)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            output_rows,
        )

    return SyntheticCounts(
        district=len(districts),
        hospital=len(hospitals),
        hospital_funding=len(funding_rows),
        hospital_output=len(output_rows),
    )
