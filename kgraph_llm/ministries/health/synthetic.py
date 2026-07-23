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

HEALTHCARE_FACILITY_LEVELS = (
    (1, "SUBCENTRE_JAK", "Sub Centre / Janakeeya Arogya Kendram (Health & Wellness Centre)", 1, "Vaccinations, antenatal care, basic health services, and health education.", "direct", 0),
    (2, "PHC_FHC", "Primary Health Centre / Family Health Centre", 2, "First doctor contact, common illnesses, chronic disease management, and minor procedures; FHCs provide longer hours and expanded services.", "direct", 0),
    (3, "CHC_BLOCK_FHC", "Community Health Centre / Block FHC", 3, "Basic specialist medicine, surgery, obstetrics and pediatrics, inpatient beds, and emergency stabilization.", "referral_or_emergency", 0),
    (4, "TALUK_THQH", "Taluk Hospital / Taluk Headquarters Hospital", 4, "Broader specialist services, surgeries, labor rooms, blood storage, X-ray, and ICU services where available.", "referral_or_emergency", 0),
    (5, "DH_GH", "District Hospital / General Hospital", 5, "Full secondary care with multiple specialties, major surgery, ICU, dialysis, and trauma services.", "referral_or_emergency", 0),
    (6, "MCH", "Medical College Hospital", 6, "Tertiary care, super-specialists, advanced surgery, teaching, research, and referral cases across districts.", "referral_or_emergency", 0),
    (7, "SUPER_SPECIALTY", "Super-specialty Institute", 7, "Disease-specific advanced care such as oncology, cardiac, neurological, and other institute-specific services.", "specialty_referral_only", 1),
)

HEALTHCARE_REFERRAL_ROUTES = (
    (1, 2, "severity_escalation", "Escalate when basic services are insufficient or doctor assessment is required."),
    (2, 3, "severity_escalation", "Escalate when specialist assessment, inpatient care, or emergency stabilization is required."),
    (3, 4, "severity_escalation", "Escalate when broader specialist, surgical, diagnostic, or critical-care capability is required."),
    (4, 5, "severity_escalation", "Escalate when full secondary multi-specialty, major surgery, dialysis, or trauma capability is required."),
    (5, 6, "severity_escalation", "Escalate complex tertiary, advanced surgical, teaching-hospital, or cross-district referral cases."),
    (6, 7, "disease_specific_referral", "Refer only when the illness matches the institute specialty; this is not a general public escalation destination."),
)

DISTRICT_FACILITY_PROFILE = (
    (5, 1, 1, None, 1, 1, "Entire district"),
    (4, 3, 8, None, 4, 7, "One per taluk"),
    (3, 5, 15, None, 6, 12, "One per block or service cluster"),
    (2, 30, 60, None, 30, 50, "One per panchayat or approximately 30,000 people"),
    (1, None, None, "Hundreds", 150, 300, "Villages and wards"),
)


@dataclass(frozen=True)
class SyntheticCounts:
    district: int
    district_facility_distribution_profile: int
    healthcare_facility_level: int
    healthcare_referral_route: int
    hospital: int
    hospital_facility_classification: int
    hospital_funding: int
    hospital_output: int
    hospital_equipment: int


def seed_synthetic_business_data(
    database: Database,
    *,
    rows_per_table: int = 2_000,
    random_seed: int = 20_260_721,
) -> SyntheticCounts:
    """Replace business fixtures with deterministic, referentially valid test data.

    Hospital, funding, output, and equipment receive exactly ``rows_per_table``
    rows. Funding and output use two endpoint years for half of the hospitals so
    growth queries remain meaningful. District retains its natural cardinality.
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

    equipment_types = (
        "CT Scanner",
        "MRI Scanner",
        "Ultrasound Machine",
        "Ventilator",
        "Dialysis Machine",
        "X-Ray Machine",
        "Patient Monitor",
    )
    equipment_rows = []
    for equipment_id in range(1, rows_per_table + 1):
        hospital_id = equipment_id
        equipment_type = equipment_types[(equipment_id - 1) % len(equipment_types)]
        status = generator.choices(
            ("operational", "maintenance", "out_of_service"),
            weights=(82, 13, 5),
            k=1,
        )[0]
        downtime = {
            "operational": generator.uniform(0, 36),
            "maintenance": generator.uniform(36, 180),
            "out_of_service": generator.uniform(180, 720),
        }[status]
        commissioned_year = generator.randint(2015, 2024)
        maintenance_month = generator.randint(1, 12)
        maintenance_day = generator.randint(1, 28)
        equipment_rows.append(
            (
                equipment_id,
                hospital_id,
                equipment_type,
                f"KHL-{hospital_id:04d}-{equipment_id:06d}",
                status,
                f"{commissioned_year}-04-01",
                f"2025-{maintenance_month:02d}-{maintenance_day:02d}",
                round(downtime, 1),
                "synthetic-health-v1",
            )
        )

    level_ids = tuple(row[0] for row in HEALTHCARE_FACILITY_LEVELS)
    level_weights = (35, 28, 15, 10, 6, 4, 2)
    hospital_classifications = []
    for hospital_id in range(1, rows_per_table + 1):
        level_id = (
            hospital_id
            if hospital_id <= len(level_ids)
            else generator.choices(level_ids, weights=level_weights, k=1)[0]
        )
        hospital_classifications.append(
            (hospital_id, level_id, "2020-04-01", None, "synthetic-health-v2")
        )

    district_profiles = tuple(
        (
            district_id,
            level_id,
            "typical_medium_district",
            typical_min,
            typical_max,
            typical_label,
            example_min,
            example_max,
            population_served,
            1,
            "kerala-typical-district-profile-v1",
        )
        for district_id, _ in districts
        for (
            level_id,
            typical_min,
            typical_max,
            typical_label,
            example_min,
            example_max,
            population_served,
        ) in DISTRICT_FACILITY_PROFILE
    )

    with sqlite3.connect(database.path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("DELETE FROM health_surveillance_signal")
        connection.execute("DELETE FROM daily_surveillance_run")
        connection.execute("DELETE FROM hospital_admission_daily")
        connection.execute("DELETE FROM hospital_daily_submission")
        connection.execute("DELETE FROM hospital_equipment")
        connection.execute("DELETE FROM hospital_output")
        connection.execute("DELETE FROM hospital_funding")
        connection.execute("DELETE FROM hospital_facility_classification")
        connection.execute("DELETE FROM hospital")
        connection.execute("DELETE FROM district_facility_distribution_profile")
        connection.execute("DELETE FROM healthcare_referral_route")
        connection.execute("DELETE FROM healthcare_facility_level")
        connection.execute("DELETE FROM district")
        connection.execute("DELETE FROM syndrome_category")
        connection.execute("DELETE FROM audit_execution")
        connection.executemany(
            "INSERT INTO district(district_id, district_name) VALUES (?, ?)", districts
        )
        connection.executemany(
            """
            INSERT INTO syndrome_category
                (syndrome_code, display_name, description, active)
            VALUES (?, ?, ?, 1)
            """,
            (
                ("ACUTE_RESPIRATORY", "Acute respiratory syndrome", "Synthetic surveillance category."),
                ("ACUTE_DIARRHOEAL", "Acute diarrhoeal syndrome", "Synthetic surveillance category."),
                ("ACUTE_FEVER", "Acute fever syndrome", "Synthetic surveillance category."),
                ("FEVER_RASH", "Fever with rash syndrome", "Synthetic surveillance category."),
                ("ENCEPHALITIS", "Acute encephalitis syndrome", "Synthetic surveillance category."),
            ),
        )
        connection.executemany(
            """
            INSERT INTO healthcare_facility_level
                (level_id, level_code, display_name, hierarchy_order, main_role,
                 public_access_mode, disease_specific)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            HEALTHCARE_FACILITY_LEVELS,
        )
        connection.executemany(
            """
            INSERT INTO healthcare_referral_route
                (from_level_id, to_level_id, route_type, referral_rule)
            VALUES (?, ?, ?, ?)
            """,
            HEALTHCARE_REFERRAL_ROUTES,
        )
        connection.executemany(
            """
            INSERT INTO district_facility_distribution_profile
                (district_id, level_id, profile_type, typical_min_count,
                 typical_max_count, typical_count_label, example_min_count,
                 example_max_count, population_served, is_approximate,
                 source_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            district_profiles,
        )
        connection.executemany(
            """
            INSERT INTO hospital
                (hospital_id, hospital_name, district_id, master_facility_id)
            VALUES (?, ?, ?, ?)
            """,
            hospitals,
        )
        connection.executemany(
            """
            INSERT INTO hospital_facility_classification
                (hospital_id, level_id, effective_from, effective_to, source_version)
            VALUES (?, ?, ?, ?, ?)
            """,
            hospital_classifications,
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
        connection.executemany(
            """
            INSERT INTO hospital_equipment
                (equipment_id, hospital_id, equipment_type, asset_code,
                 operational_status, commissioned_on, last_maintenance_on,
                 downtime_hours_last_12m, source_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            equipment_rows,
        )

    return SyntheticCounts(
        district=len(districts),
        district_facility_distribution_profile=len(district_profiles),
        healthcare_facility_level=len(HEALTHCARE_FACILITY_LEVELS),
        healthcare_referral_route=len(HEALTHCARE_REFERRAL_ROUTES),
        hospital=len(hospitals),
        hospital_facility_classification=len(hospital_classifications),
        hospital_funding=len(funding_rows),
        hospital_output=len(output_rows),
        hospital_equipment=len(equipment_rows),
    )
