from __future__ import annotations

import hashlib
import json
import random
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Iterable

from ...storage.database import Database


HIGH_CARDINALITY_TABLES = (
    "master_facility",
    "master_supplier",
    "master_project",
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
    "analytics_audit_issue",
    "analytics_project_monthly",
    "analytics_data_quality_monthly",
    "finance_budget_monthly",
    "finance_expenditure_monthly",
    "finance_liability_monthly",
    "restricted_household",
    "restricted_beneficiary",
    "restricted_scheme_enrollment",
    "restricted_claim_identity_link",
    "restricted_fraud_signal",
    "restricted_investigation",
    "hospital_daily_submission",
    "hospital_admission_daily",
    "daily_surveillance_run",
    "health_surveillance_signal",
)


@dataclass(frozen=True)
class ComprehensiveSyntheticResult:
    rows_per_table: int
    table_counts: dict[str, int]
    empty_tables: tuple[str, ...]
    all_null_columns: tuple[str, ...]


def _month_ids(start_year: int = 2022, years: int = 5) -> tuple[str, ...]:
    return tuple(
        f"{year:04d}-{month:02d}-01"
        for year in range(start_year, start_year + years)
        for month in range(1, 13)
    )


def _batch(
    connection: sqlite3.Connection,
    sql: str,
    rows: Iterable[tuple[Any, ...]],
) -> None:
    connection.executemany(sql, rows)


def _coverage(connection: sqlite3.Connection) -> tuple[dict[str, int], tuple[str, ...], tuple[str, ...]]:
    tables = tuple(
        row[0]
        for row in connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        )
    )
    counts: dict[str, int] = {}
    empty: list[str] = []
    all_null: list[str] = []
    for table in tables:
        quoted_table = '"' + table.replace('"', '""') + '"'
        count = int(connection.execute(f"SELECT COUNT(*) FROM {quoted_table}").fetchone()[0])
        counts[table] = count
        if count == 0:
            empty.append(table)
            continue
        for column_row in connection.execute(f"PRAGMA table_info({quoted_table})"):
            column = str(column_row[1])
            quoted_column = '"' + column.replace('"', '""') + '"'
            populated = connection.execute(
                f"SELECT 1 FROM {quoted_table} WHERE {quoted_column} IS NOT NULL LIMIT 1"
            ).fetchone()
            if populated is None:
                all_null.append(f"{table}.{column}")
    return counts, tuple(empty), tuple(all_null)


def seed_comprehensive_health_data(
    database: Database,
    *,
    rows_per_table: int = 2_000,
    random_seed: int = 20_260_722,
) -> ComprehensiveSyntheticResult:
    """Populate the complete health test model with deterministic synthetic data.

    High-cardinality master, analytical, finance, restricted-token, and daily
    surveillance tables receive exactly ``rows_per_table`` rows. Natural
    reference catalogs retain realistic cardinality. No names, identifiers, or
    tokens in this function represent real people or Kerala Government records.
    """

    if rows_per_table < 2:
        raise ValueError("rows_per_table must be at least 2")

    generator = random.Random(random_seed)
    months = _month_ids()
    districts = tuple(range(101, 115))
    organisation_ids = (11, 12, 13, 14, 15, 16, 17, 21, 22, 23, 24, 25, 26, 27)
    today = date(2026, 7, 22)

    with sqlite3.connect(database.path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")

        # Delete generated facts from leaves to roots. Natural reference
        # catalogs and the semantic policy catalog are retained.
        for table in (
            "restricted_investigation",
            "restricted_fraud_signal",
            "restricted_claim_identity_link",
            "restricted_scheme_enrollment",
            "restricted_beneficiary",
            "restricted_household",
            "analytics_audit_issue",
            "analytics_project_monthly",
            "analytics_medical_college_annual",
            "analytics_quality_monthly",
            "analytics_scheme_monthly",
            "analytics_programme_monthly",
            "analytics_vehicle_monthly",
            "analytics_infrastructure_monthly",
            "analytics_supplier_performance_monthly",
            "analytics_procurement_monthly",
            "analytics_referral_flow_monthly",
            "analytics_service_monthly",
            "analytics_staffing_monthly",
            "analytics_equipment_monthly",
            "analytics_medicine_monthly",
            "analytics_facility_monthly_summary",
            "analytics_data_quality_monthly",
            "finance_liability_monthly",
            "finance_expenditure_monthly",
            "finance_budget_monthly",
            "master_project",
            "master_supplier",
            "master_facility",
            "health_surveillance_signal",
            "daily_surveillance_run",
            "hospital_admission_daily",
            "hospital_daily_submission",
        ):
            connection.execute(f'DELETE FROM "{table}"')

        # Expand the reporting calendar and add governed local-body and district
        # organisation fixtures needed by the generated facility records.
        calendar_rows = []
        for month_id in months:
            year = int(month_id[:4])
            month = int(month_id[5:7])
            fiscal_year = year if month >= 4 else year - 1
            fiscal_month = ((month - 4) % 12) + 1
            quarter = ((fiscal_month - 1) // 3) + 1
            calendar_rows.append(
                (month_id, year, month, fiscal_year, quarter, datetime.strptime(month_id, "%Y-%m-%d").strftime("%B %Y"))
            )
        _batch(
            connection,
            """
            INSERT OR REPLACE INTO master_calendar
                (month_id, calendar_year, calendar_month, fiscal_year_start,
                 fiscal_quarter, month_name)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            calendar_rows,
        )

        _batch(
            connection,
            """
            INSERT OR IGNORE INTO master_geographic_area
                (geographic_area_id, area_code, area_name, area_level,
                 parent_geographic_area_id, effective_from, effective_to, active)
            VALUES (?, ?, ?, 'LOCAL_BODY', ?, '2020-04-01', NULL, 1)
            """,
            (
                (2_001 + offset, f"SYN-LSG-{offset + 1:02d}", f"Synthetic Local Body {offset + 1:02d}", district_id)
                for offset, district_id in enumerate(districts)
            ),
        )
        connection.execute(
            """
            UPDATE master_geographic_area
            SET effective_to = '2025-03-31', active = 0
            WHERE geographic_area_id = 2001
            """
        )
        _batch(
            connection,
            """
            INSERT OR IGNORE INTO master_organisation
                (organisation_id, organisation_code, organisation_name,
                 organisation_type, parent_organisation_id,
                 administrative_level, system_of_medicine_id, district_id,
                 effective_from, effective_to, active)
            VALUES (?, ?, ?, 'DISTRICT_OFFICE', 11, 'DISTRICT', 1, ?,
                    '2020-04-01', NULL, 1)
            """,
            (
                (101 + offset, f"DHS-DIST-{offset + 1:02d}", f"Synthetic District Health Office {offset + 1:02d}", district_id)
                for offset, district_id in enumerate(districts)
            ),
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO master_organisation
                (organisation_id, organisation_code, organisation_name,
                 organisation_type, parent_organisation_id,
                 administrative_level, system_of_medicine_id, district_id,
                 effective_from, effective_to, active)
            VALUES (999, 'SYN-RETIRED-ORG', 'Synthetic Retired Health Office',
                    'DISTRICT_OFFICE', 11, 'DISTRICT', 1, 101,
                    '2020-04-01', '2025-03-31', 0)
            """
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO master_programme
                (programme_id, programme_code, programme_name,
                 programme_category, administering_organisation_id,
                 effective_from, effective_to, active)
            VALUES (99, 'SYN-CLOSED-PROGRAMME', 'Synthetic Closed Programme',
                    'TEST', 13, '2020-04-01', '2025-03-31', 0)
            """
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO master_scheme
                (scheme_id, scheme_code, scheme_name, scheme_category,
                 administering_organisation_id, effective_from,
                 effective_to, active)
            VALUES (99, 'SYN-CLOSED-SCHEME', 'Synthetic Closed Scheme', 'TEST',
                    15, '2020-04-01', '2025-03-31', 0)
            """
        )

        facility_rows = []
        ownerships = (
            "STATE_GOVERNMENT",
            "LOCAL_GOVERNMENT",
            "AUTONOMOUS",
            "PRIVATE",
            "COOPERATIVE",
        )
        urban_rural = ("URBAN", "RURAL", "TRIBAL", "MIXED")
        for i in range(1, rows_per_table + 1):
            district_offset = (i - 1) % len(districts)
            facility_type_id = ((i - 1) % 9) + 1
            closed = i % 50 == 0
            facility_rows.append(
                (
                    i,
                    f"SYN-FAC-{i:06d}",
                    f"Synthetic Health Facility {i:06d}",
                    facility_type_id,
                    organisation_ids[(i - 1) % len(organisation_ids)],
                    districts[district_offset],
                    2_001 + district_offset,
                    ((i - 1) % 8) + 1,
                    ownerships[(i - 1) % len(ownerships)],
                    urban_rural[(i - 1) % len(urban_rural)],
                    "TEACHING" if facility_type_id in (6, 7) else "NON_TEACHING",
                    generator.randint(0, 1_200),
                    "CLOSED" if closed else "OPERATIONAL",
                    round(8.2 + generator.random() * 4.2, 6),
                    round(74.8 + generator.random() * 2.0, 6),
                    "2020-04-01",
                    "2025-03-31" if closed else None,
                    ((i - 1) % 9) + 1,
                    "synthetic-ministry-v2",
                )
            )
        _batch(
            connection,
            """
            INSERT INTO master_facility
                (facility_id, facility_code, facility_name, facility_type_id,
                 parent_organisation_id, district_id, local_body_id,
                 system_of_medicine_id, ownership_type, urban_rural_category,
                 teaching_status, sanctioned_bed_capacity, operational_status,
                 latitude, longitude, effective_from, effective_to,
                 source_system_id, source_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            facility_rows,
        )

        _batch(
            connection,
            """
            INSERT INTO master_supplier
                (supplier_id, supplier_code, supplier_name, supplier_type,
                 district_id, active)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    i,
                    f"SYN-SUP-{i:06d}",
                    f"Synthetic Health Supplier {i:06d}",
                    ("MEDICINE_SUPPLIER", "EQUIPMENT_SUPPLIER", "CONTRACTOR", "SERVICE_PROVIDER")[(i - 1) % 4],
                    districts[(i - 1) % len(districts)],
                    0 if i % 80 == 0 else 1,
                )
                for i in range(1, rows_per_table + 1)
            ),
        )
        _batch(
            connection,
            """
            INSERT INTO master_project
                (project_id, project_code, project_name, project_category,
                 facility_id, responsible_organisation_id, budget_head_id,
                 approved_on, planned_completion_date, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    i,
                    f"SYN-PROJ-{i:06d}",
                    f"Synthetic Health Project {i:06d}",
                    ("BUILDING_EXPANSION", "EQUIPMENT_INSTALLATION", "DIGITAL_HEALTH", "OXYGEN_INFRASTRUCTURE")[(i - 1) % 4],
                    i,
                    organisation_ids[(i - 1) % len(organisation_ids)],
                    ((i - 1) % 3) + 1,
                    "2026-04-01",
                    "2028-03-31",
                    1,
                )
                for i in range(1, rows_per_table + 1)
            ),
        )

        # Facility summary and resource facts. Each row uses a distinct facility
        # key, which guarantees the requested row count without violating grain.
        _batch(
            connection,
            """
            INSERT INTO analytics_facility_monthly_summary
                (facility_id, month_id, outpatient_visits, inpatient_admissions,
                 emergency_visits, surgeries_completed, deliveries_completed,
                 diagnostic_tests_completed, patients_referred_out,
                 patients_referred_in, sanctioned_beds, operational_beds,
                 occupied_bed_days, available_bed_days, total_staff_required,
                 total_staff_sanctioned, total_staff_available,
                 total_budget_available, total_expenditure,
                 average_waiting_minutes, service_cancellation_count,
                 patient_grievance_count, reported_deaths, source_system_id,
                 source_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    i, months[(i - 1) % len(months)], generator.randint(500, 40_000),
                    generator.randint(50, 8_000), generator.randint(20, 4_000),
                    generator.randint(0, 2_000), generator.randint(0, 500),
                    generator.randint(100, 30_000), generator.randint(0, 400),
                    generator.randint(0, 300), 100 + (i % 900), 80 + (i % 700),
                    1_500 + (i % 15_000), 2_400 + (i % 20_000),
                    60 + (i % 700), 55 + (i % 650), 45 + (i % 600),
                    float(5_000_000 + i * 10_000), float(3_500_000 + i * 8_000),
                    round(10 + generator.random() * 110, 2), i % 40, i % 30,
                    i % 80, 1, "synthetic-ministry-v2",
                )
                for i in range(1, rows_per_table + 1)
            ),
        )
        _batch(
            connection,
            """
            INSERT INTO analytics_medicine_monthly
                (facility_id, month_id, opening_stock_value,
                 medicine_received_value, medicine_consumed_value,
                 closing_stock_value, estimated_required_stock_value,
                 available_stock_value, medicine_procurement_cost,
                 medicine_distribution_cost, expired_medicine_value,
                 damaged_medicine_value, emergency_local_purchase_cost,
                 stockout_days, critical_stockout_incidents,
                 average_supply_delay_days, source_system_id, source_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    i, months[(i - 1) % len(months)], 1_000_000 + i * 1_000,
                    700_000 + i * 700, 650_000 + i * 650, 1_050_000 + i * 1_050,
                    1_200_000 + i * 1_200, 1_000_000 + i * 950,
                    720_000 + i * 710, 20_000 + i * 10, 2_000 + i * 3,
                    500 + i, 5_000 + i * 5, i % 31, i % 7,
                    round(1 + generator.random() * 40, 2), 2, "synthetic-ministry-v2",
                )
                for i in range(1, rows_per_table + 1)
            ),
        )
        _batch(
            connection,
            """
            INSERT INTO analytics_equipment_monthly
                (facility_id, equipment_category_id, month_id,
                 equipment_required_count, equipment_available_count,
                 equipment_functional_count, equipment_nonfunctional_count,
                 equipment_under_maintenance_count,
                 new_equipment_procured_count, equipment_procurement_value,
                 equipment_maintenance_cost, spare_parts_cost,
                 total_downtime_hours, average_repair_time_days,
                 utilisation_rate, maintenance_compliance_rate,
                 source_system_id, source_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    i, ((i - 1) % 4) + 1, months[(i - 1) % len(months)],
                    10 + (i % 90), 8 + (i % 80), 6 + (i % 70), 1 + (i % 5),
                    1 + (i % 4), i % 6, float(1_000_000 + i * 2_000),
                    float(20_000 + i * 30), float(5_000 + i * 10),
                    round(generator.random() * 300, 2), round(1 + generator.random() * 20, 2),
                    round(20 + generator.random() * 80, 2), round(40 + generator.random() * 60, 2),
                    3, "synthetic-ministry-v2",
                )
                for i in range(1, rows_per_table + 1)
            ),
        )
        _batch(
            connection,
            """
            INSERT INTO analytics_staffing_monthly
                (facility_id, staff_category_id, month_id, sanctioned_posts,
                 required_posts, filled_posts, staff_actually_available,
                 permanent_staff_count, contract_staff_count,
                 temporary_staff_count, staff_on_leave, staff_on_deputation,
                 overtime_hours, training_hours, salary_cost,
                 contract_staff_cost, overtime_cost, source_system_id,
                 source_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    i, ((i - 1) % 4) + 1, months[(i - 1) % len(months)],
                    30 + (i % 300), 35 + (i % 320), 25 + (i % 260),
                    20 + (i % 240), 18 + (i % 210), 2 + (i % 40), i % 15,
                    i % 20, i % 6, round(generator.random() * 1_000, 2),
                    round(generator.random() * 300, 2), float(1_000_000 + i * 2_500),
                    float(100_000 + i * 300), float(10_000 + i * 20),
                    4, "synthetic-ministry-v2",
                )
                for i in range(1, rows_per_table + 1)
            ),
        )
        _batch(
            connection,
            """
            INSERT INTO analytics_service_monthly
                (facility_id, service_category_id, demographic_group_id,
                 month_id, service_capacity, service_demand,
                 services_delivered, services_cancelled, patients_waiting,
                 average_waiting_days, required_staff_count,
                 available_staff_count, required_equipment_count,
                 functional_equipment_count, referrals_out, referrals_in,
                 estimated_unmet_demand, service_availability_status,
                 source_system_id, source_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    i, ((i - 1) % 5) + 1, ((i - 1) % 4) + 1,
                    months[(i - 1) % len(months)], 500 + (i % 5_000),
                    550 + (i % 5_500), 400 + (i % 4_800), i % 80, i % 300,
                    round(generator.random() * 30, 2), 10 + (i % 150),
                    8 + (i % 130), 4 + (i % 50), 3 + (i % 45), i % 100,
                    i % 90, i % 400,
                    ("AVAILABLE", "CONSTRAINED", "UNAVAILABLE")[(i - 1) % 3],
                    1, "synthetic-ministry-v2",
                )
                for i in range(1, rows_per_table + 1)
            ),
        )
        _batch(
            connection,
            """
            INSERT INTO analytics_referral_flow_monthly
                (source_facility_id, destination_facility_id,
                 service_category_id, month_id, referral_count,
                 emergency_referral_count, accepted_referral_count,
                 rejected_referral_count, completed_referral_count,
                 average_transfer_minutes, average_distance_km,
                 ambulance_used_count, main_resource_gap_category,
                 source_system_id, source_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    i, (i % rows_per_table) + 1, ((i - 1) % 5) + 1,
                    months[(i - 1) % len(months)], 20 + (i % 300),
                    i % 100, 15 + (i % 250), i % 20, 12 + (i % 220),
                    round(10 + generator.random() * 180, 2),
                    round(1 + generator.random() * 200, 2), i % 80,
                    ("Specialist unavailable", "No operational bed", "Equipment unavailable", "Medicine unavailable")[(i - 1) % 4],
                    1, "synthetic-ministry-v2",
                )
                for i in range(1, rows_per_table + 1)
            ),
        )
        _batch(
            connection,
            """
            INSERT INTO analytics_procurement_monthly
                (procuring_organisation_id, facility_id, supplier_id,
                 procurement_category_id, month_id, requested_value,
                 approved_value, ordered_value, received_value, paid_value,
                 purchase_order_count, completed_order_count,
                 delayed_order_count, cancelled_order_count,
                 average_procurement_days, average_delivery_delay_days,
                 quality_rejection_value, penalty_amount,
                 emergency_purchase_value, source_system_id, source_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    organisation_ids[(i - 1) % len(organisation_ids)], i, i,
                    ((i - 1) % 4) + 1, months[(i - 1) % len(months)],
                    float(500_000 + i * 1_000), float(480_000 + i * 950),
                    float(450_000 + i * 900), float(420_000 + i * 850),
                    float(390_000 + i * 800), 5 + (i % 80), 3 + (i % 70),
                    i % 15, i % 5, round(5 + generator.random() * 90, 2),
                    round(generator.random() * 45, 2), float(i * 30),
                    float(i * 10), float(i * 100), 2, "synthetic-ministry-v2",
                )
                for i in range(1, rows_per_table + 1)
            ),
        )
        _batch(
            connection,
            """
            INSERT INTO analytics_supplier_performance_monthly
                (supplier_id, procurement_category_id, month_id,
                 contract_value, ordered_value, delivered_value, paid_value,
                 orders_received, orders_completed, orders_delayed,
                 orders_rejected, average_delivery_delay_days,
                 quality_rejection_rate, contract_compliance_rate,
                 payment_pending_value, supplier_risk_score,
                 source_system_id, source_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    i, ((i - 1) % 4) + 1, months[(i - 1) % len(months)],
                    float(1_000_000 + i * 2_000), float(900_000 + i * 1_800),
                    float(820_000 + i * 1_600), float(780_000 + i * 1_500),
                    10 + (i % 100), 8 + (i % 90), i % 20, i % 8,
                    round(generator.random() * 45, 2), round(generator.random() * 10, 2),
                    round(50 + generator.random() * 50, 2), float(20_000 + i * 100),
                    round(generator.random() * 100, 2), 2, "synthetic-ministry-v2",
                )
                for i in range(1, rows_per_table + 1)
            ),
        )
        _batch(
            connection,
            """
            INSERT INTO analytics_infrastructure_monthly
                (facility_id, infrastructure_category_id, month_id,
                 required_capacity, available_capacity, functional_capacity,
                 maintenance_cost, repair_cost, capital_expenditure,
                 downtime_hours, inspection_issues, critical_issues,
                 issues_resolved, source_system_id, source_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    i, ((i - 1) % 4) + 1, months[(i - 1) % len(months)],
                    float(100 + i % 500), float(90 + i % 450), float(80 + i % 400),
                    float(20_000 + i * 20), float(10_000 + i * 10),
                    float(50_000 + i * 100), round(generator.random() * 200, 2),
                    i % 30, i % 8, i % 25, 8, "synthetic-ministry-v2",
                )
                for i in range(1, rows_per_table + 1)
            ),
        )
        _batch(
            connection,
            """
            INSERT INTO analytics_vehicle_monthly
                (facility_id, station_code, vehicle_category_id, month_id,
                 required_vehicle_count, available_vehicle_count,
                 functional_vehicle_count, trip_count, emergency_trip_count,
                 distance_travelled_km, patients_transported, fuel_cost,
                 maintenance_cost, staff_cost, downtime_hours,
                 average_response_minutes, average_trip_minutes,
                 source_system_id, source_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    i, f"STATION-{((i - 1) % 100) + 1:03d}", ((i - 1) % 3) + 1,
                    months[(i - 1) % len(months)], 2 + (i % 12), 1 + (i % 10),
                    1 + (i % 9), 20 + (i % 500), 5 + (i % 200),
                    float(500 + i * 3), 10 + (i % 300), float(20_000 + i * 20),
                    float(10_000 + i * 15), float(30_000 + i * 25),
                    round(generator.random() * 120, 2), round(5 + generator.random() * 60, 2),
                    round(10 + generator.random() * 180, 2), 1, "synthetic-ministry-v2",
                )
                for i in range(1, rows_per_table + 1)
            ),
        )

        programme_rows = []
        scheme_rows = []
        data_quality_rows = []
        for i in range(rows_per_table):
            programme_index = i
            programme_id = (programme_index % 2) + 1
            programme_index //= 2
            district_id = districts[programme_index % len(districts)]
            programme_index //= len(districts)
            demographic_id = (programme_index % 4) + 1
            programme_index //= 4
            month_id = months[programme_index % len(months)]
            programme_rows.append(
                (
                    programme_id, district_id, demographic_id, month_id,
                    10_000 + i * 10, 9_000 + i * 9, 7_000 + i * 7,
                    8_000 + i * 8, float(1_000_000 + i * 1_000),
                    float(900_000 + i * 900), float(800_000 + i * 800),
                    20 + (i % 100), 15 + (i % 90), round(generator.random() * 100, 2),
                    6, "synthetic-ministry-v2",
                )
            )

            scheme_index = i
            scheme_id = 1
            district_id = districts[scheme_index % len(districts)]
            scheme_index //= len(districts)
            demographic_id = (scheme_index % 4) + 1
            scheme_index //= 4
            month_id = months[scheme_index % len(months)]
            eligible = 20_000 + i * 5
            enrolled = int(eligible * 0.8)
            submitted = 500 + (i % 2_000)
            approved = int(submitted * 0.85)
            scheme_rows.append(
                (
                    scheme_id, district_id, demographic_id, month_id,
                    5_000 + i, 4_000 + i, eligible, enrolled, 300 + (i % 5_000),
                    submitted, approved, submitted - approved,
                    float(submitted * 20_000), float(approved * 19_000),
                    float(approved * 18_500), 18_500.0,
                    round(2 + generator.random() * 30, 2), i % 50, i % 20,
                    7, "synthetic-ministry-v2",
                )
            )

            dq_index = i
            source_id = (dq_index % 9) + 1
            dq_index //= 9
            organisation_id = organisation_ids[dq_index % len(organisation_ids)]
            dq_index //= len(organisation_ids)
            month_id = months[dq_index % len(months)]
            expected = 1_000 + (i % 10_000)
            received = expected - (i % 30)
            valid = received - (i % 10)
            data_quality_rows.append(
                (
                    source_id, organisation_id, month_id, expected, received,
                    valid, received - valid, round(generator.random() * 4, 2),
                    round(generator.random() * 2, 2), round(generator.random() * 8, 2),
                    round(generator.random() * 5, 2), round(generator.random() * 5, 2),
                    round(85 + generator.random() * 15, 2), "synthetic-ministry-v2",
                )
            )

        _batch(
            connection,
            """
            INSERT INTO analytics_programme_monthly
                (programme_id, district_id, demographic_group_id, month_id,
                 target_population, eligible_population, population_reached,
                 services_delivered, programme_budget, funds_released,
                 programme_expenditure, planned_activities,
                 completed_activities, outcome_indicator_value,
                 source_system_id, source_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            programme_rows,
        )
        _batch(
            connection,
            """
            INSERT INTO analytics_scheme_monthly
                (scheme_id, district_id, demographic_group_id, month_id,
                 eligible_households, enrolled_households,
                 eligible_individuals, enrolled_individuals,
                 beneficiaries_served, claims_submitted, claims_approved,
                 claims_rejected, claim_amount_requested,
                 claim_amount_approved, claim_amount_paid,
                 average_claim_value, average_claim_processing_days,
                 suspected_duplicate_count, fraud_signal_count,
                 source_system_id, source_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            scheme_rows,
        )
        _batch(
            connection,
            """
            INSERT INTO analytics_data_quality_monthly
                (source_system_id, organisation_id, month_id,
                 records_expected, records_received, records_valid,
                 records_rejected, missing_field_percentage,
                 duplicate_percentage, late_submission_percentage,
                 validation_failure_percentage, data_freshness_days,
                 overall_data_quality_score, source_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            data_quality_rows,
        )

        _batch(
            connection,
            """
            INSERT INTO analytics_medical_college_annual
                (institution_id, academic_year, undergraduate_seats,
                 postgraduate_seats, super_specialty_seats,
                 students_enrolled, students_graduated,
                 sanctioned_faculty_posts, filled_faculty_posts,
                 teaching_beds, clinical_departments, patient_volume,
                 surgeries_completed, research_projects, research_grants,
                 publications, clinical_trials, education_budget,
                 hospital_budget, research_expenditure,
                 infrastructure_expenditure, accreditation_status,
                 inspection_deficiency_count, source_system_id, source_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    i, f"{2020 + (i % 6)}-{str(2021 + (i % 6))[-2:]}",
                    50 + (i % 250), 20 + (i % 150), i % 40,
                    500 + (i % 2_000), 100 + (i % 500), 80 + (i % 400),
                    70 + (i % 350), 200 + (i % 1_500), 10 + (i % 50),
                    10_000 + i * 10, 500 + (i % 4_000), 5 + (i % 100),
                    float(100_000 + i * 1_000), 2 + (i % 100), i % 20,
                    float(5_000_000 + i * 2_000), float(20_000_000 + i * 5_000),
                    float(500_000 + i * 1_000), float(1_000_000 + i * 1_500),
                    ("ACCREDITED", "PROVISIONAL", "REVIEW_DUE")[(i - 1) % 3],
                    i % 15, 1, "synthetic-ministry-v2",
                )
                for i in range(1, rows_per_table + 1)
            ),
        )
        _batch(
            connection,
            """
            INSERT INTO analytics_quality_monthly
                (facility_id, quality_category_id, month_id,
                 inspections_completed, issues_identified, critical_issues,
                 issues_resolved, adverse_incident_count, complaint_count,
                 complaints_resolved, average_resolution_days,
                 compliance_percentage, quality_score, accreditation_status,
                 source_system_id, source_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    i, ((i - 1) % 4) + 1, months[(i - 1) % len(months)],
                    1 + (i % 10), i % 30, i % 5, i % 25, i % 8, i % 40,
                    i % 35, round(generator.random() * 30, 2),
                    round(60 + generator.random() * 40, 2),
                    round(60 + generator.random() * 40, 2),
                    ("ACCREDITED", "PROVISIONAL", "NOT_ACCREDITED")[(i - 1) % 3],
                    9, "synthetic-ministry-v2",
                )
                for i in range(1, rows_per_table + 1)
            ),
        )
        _batch(
            connection,
            """
            INSERT INTO analytics_audit_issue
                (audit_issue_id, organisation_id, facility_id, audit_type,
                 issue_category, issue_date, financial_value, severity,
                 responsible_organisation_id, resolution_due_date,
                 resolution_status, resolved_date, source_system_id,
                 source_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    i, organisation_ids[(i - 1) % len(organisation_ids)], i,
                    ("FINANCIAL", "PROCUREMENT", "QUALITY", "DATA")[(i - 1) % 4],
                    ("Excess expenditure", "Unused asset", "Data-quality failure", "Regulatory non-compliance")[(i - 1) % 4],
                    (today - timedelta(days=i % 1_000)).isoformat(), float(i * 500),
                    ("LOW", "MEDIUM", "HIGH", "CRITICAL")[(i - 1) % 4],
                    organisation_ids[i % len(organisation_ids)],
                    (today + timedelta(days=90 + i % 200)).isoformat(),
                    ("OPEN", "IN_PROGRESS", "RESOLVED", "ACCEPTED_RISK")[(i - 1) % 4],
                    (today + timedelta(days=i % 60)).isoformat(), 9, "synthetic-ministry-v2",
                )
                for i in range(1, rows_per_table + 1)
            ),
        )
        _batch(
            connection,
            """
            INSERT INTO analytics_project_monthly
                (project_id, month_id, approved_cost, revised_cost,
                 amount_released, amount_spent, outstanding_liability,
                 planned_progress_percentage, actual_progress_percentage,
                 expected_completion_date, delay_days, contractor_id,
                 project_status, risk_level, source_system_id, source_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    i, months[(i - 1) % len(months)], float(1_000_000 + i * 3_000),
                    float(1_100_000 + i * 3_200), float(600_000 + i * 1_500),
                    float(500_000 + i * 1_200), float(50_000 + i * 100),
                    round(generator.random() * 100, 2), round(generator.random() * 100, 2),
                    "2028-03-31", i % 365, i,
                    ("PLANNED", "IN_PROGRESS", "ON_HOLD", "COMPLETED")[(i - 1) % 4],
                    ("LOW", "MEDIUM", "HIGH", "CRITICAL")[(i - 1) % 4],
                    8, "synthetic-ministry-v2",
                )
                for i in range(1, rows_per_table + 1)
            ),
        )

        _batch(
            connection,
            """
            INSERT INTO finance_budget_monthly
                (organisation_id, facility_id, budget_head_id, month_id,
                 original_budget, revised_budget, funds_released,
                 funds_available, committed_expenditure, actual_expenditure,
                 unpaid_liabilities, funds_surrendered, release_delay_days,
                 payment_delay_days, source_system_id, source_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    organisation_ids[(i - 1) % len(organisation_ids)], i,
                    ((i - 1) % 3) + 1, months[(i - 1) % len(months)],
                    float(2_000_000 + i * 4_000), float(2_100_000 + i * 4_100),
                    float(1_800_000 + i * 3_500), float(1_700_000 + i * 3_300),
                    float(1_500_000 + i * 3_000), float(1_300_000 + i * 2_700),
                    float(100_000 + i * 100), float(i * 20),
                    round(generator.random() * 30, 2), round(generator.random() * 60, 2),
                    5, "synthetic-ministry-v2",
                )
                for i in range(1, rows_per_table + 1)
            ),
        )
        _batch(
            connection,
            """
            INSERT INTO finance_expenditure_monthly
                (facility_id, cost_category_id, month_id, budget_amount,
                 committed_amount, expenditure_amount, outstanding_amount,
                 previous_year_expenditure, source_system_id, source_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    i, ((i - 1) % 4) + 1, months[(i - 1) % len(months)],
                    float(1_000_000 + i * 2_000), float(900_000 + i * 1_800),
                    float(800_000 + i * 1_600), float(100_000 + i * 200),
                    float(750_000 + i * 1_500), 5, "synthetic-ministry-v2",
                )
                for i in range(1, rows_per_table + 1)
            ),
        )
        _batch(
            connection,
            """
            INSERT INTO finance_liability_monthly
                (organisation_id, facility_id, cost_category_id, month_id,
                 opening_liability, liability_incurred, liability_paid,
                 closing_liability, overdue_liability, source_system_id,
                 source_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    organisation_ids[(i - 1) % len(organisation_ids)], i,
                    ((i - 1) % 4) + 1, months[(i - 1) % len(months)],
                    float(100_000 + i * 100), float(80_000 + i * 80),
                    float(60_000 + i * 60), float(120_000 + i * 120),
                    float(20_000 + i * 20), 5, "synthetic-ministry-v2",
                )
                for i in range(1, rows_per_table + 1)
            ),
        )

        # Restricted rows use opaque synthetic tokens only. They are not added
        # to the general K-Graph or governed view catalog.
        _batch(
            connection,
            """
            INSERT INTO restricted_household
                (household_token, district_id, created_at, retention_until,
                 tokenization_version)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                (
                    f"hh_test_{i:08d}", districts[(i - 1) % len(districts)],
                    "2026-07-22T00:00:00+00:00", "2031-07-22", "synthetic-token-v1",
                )
                for i in range(1, rows_per_table + 1)
            ),
        )
        _batch(
            connection,
            """
            INSERT INTO restricted_beneficiary
                (beneficiary_token, household_token, district_id,
                 demographic_group_id, created_at, retention_until,
                 tokenization_version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    f"beneficiary_test_{i:08d}", f"hh_test_{i:08d}",
                    districts[(i - 1) % len(districts)], ((i - 1) % 4) + 1,
                    "2026-07-22T00:00:00+00:00", "2031-07-22", "synthetic-token-v1",
                )
                for i in range(1, rows_per_table + 1)
            ),
        )
        _batch(
            connection,
            """
            INSERT INTO restricted_scheme_enrollment
                (beneficiary_token, scheme_id, enrolled_from, enrolled_to,
                 eligibility_status, source_system_id)
            VALUES (?, 1, ?, ?, ?, 7)
            """,
            (
                (
                    f"beneficiary_test_{i:08d}", "2026-04-01", "2027-03-31",
                    ("ELIGIBLE", "ENROLLED", "SUSPENDED")[(i - 1) % 3],
                )
                for i in range(1, rows_per_table + 1)
            ),
        )
        _batch(
            connection,
            """
            INSERT INTO restricted_claim_identity_link
                (claim_token, beneficiary_token, scheme_id, facility_id,
                 service_month, source_system_id)
            VALUES (?, ?, 1, ?, ?, 7)
            """,
            (
                (
                    f"claim_test_{i:08d}", f"beneficiary_test_{i:08d}", i,
                    months[(i - 1) % len(months)],
                )
                for i in range(1, rows_per_table + 1)
            ),
        )
        _batch(
            connection,
            """
            INSERT INTO restricted_fraud_signal
                (fraud_signal_id, beneficiary_token, household_token,
                 claim_token, signal_type, risk_score, review_status,
                 created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    i, f"beneficiary_test_{i:08d}", f"hh_test_{i:08d}",
                    f"claim_test_{i:08d}",
                    ("DUPLICATE_CLAIM", "IDENTITY_MISMATCH", "UNUSUAL_FREQUENCY")[(i - 1) % 3],
                    round(generator.random() * 100, 2),
                    ("NEEDS_REVIEW", "VERIFIED", "DISMISSED")[(i - 1) % 3],
                    "2026-07-22T00:00:00+00:00",
                )
                for i in range(1, rows_per_table + 1)
            ),
        )
        _batch(
            connection,
            """
            INSERT INTO restricted_investigation
                (investigation_id, fraud_signal_id, opened_at, closed_at,
                 investigation_status, assigned_role, outcome_code)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    i, i, "2026-07-22T00:00:00+00:00",
                    "2026-07-23T00:00:00+00:00",
                    ("SUBSTANTIATED", "UNSUBSTANTIATED", "REFERRED")[(i - 1) % 3],
                    "authorised_scheme_investigator",
                    ("RECOVER", "CLOSE", "REFER")[(i - 1) % 3],
                )
                for i in range(1, rows_per_table + 1)
            ),
        )

        # Daily surveillance fixtures use legacy hospital IDs seeded by the
        # existing bulk seeder. One row per hospital gives exactly N rows.
        _batch(
            connection,
            """
            INSERT INTO hospital_daily_submission
                (hospital_id, reporting_date, submitted_at,
                 submission_status, source_version)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                (
                    i, (today - timedelta(days=(i - 1) % 60)).isoformat(),
                    f"{(today - timedelta(days=(i - 1) % 60)).isoformat()}T23:00:00+05:30",
                    ("complete", "partial", "missing")[(i - 1) % 3],
                    "synthetic-daily-v2",
                )
                for i in range(1, rows_per_table + 1)
            ),
        )
        syndromes = ("ACUTE_RESPIRATORY", "ACUTE_DIARRHOEAL", "ACUTE_FEVER", "FEVER_RASH", "ENCEPHALITIS")
        _batch(
            connection,
            """
            INSERT INTO hospital_admission_daily
                (hospital_id, patient_district_id, reporting_date,
                 syndrome_code, age_band, admissions, source_version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    i, ((i - 1) % 14) + 1,
                    (today - timedelta(days=(i - 1) % 60)).isoformat(),
                    syndromes[(i - 1) % len(syndromes)],
                    ("0-4", "5-17", "18-44", "45-64", "65+")[(i - 1) % 5],
                    1 + (i % 100), "synthetic-daily-v2",
                )
                for i in range(1, rows_per_table + 1)
            ),
        )
        _batch(
            connection,
            """
            INSERT INTO daily_surveillance_run
                (run_id, reporting_date, started_at, completed_at,
                 method_version, expected_hospitals, complete_hospitals,
                 reporting_completeness, run_status, signal_count, config_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    i, (today - timedelta(days=(i - 1) % 365)).isoformat(),
                    "2026-07-22T00:00:00+00:00", "2026-07-22T00:05:00+00:00",
                    "synthetic-detector-v1", rows_per_table, rows_per_table,
                    1.0, "COMPLETED", 1,
                    json.dumps({"synthetic": True, "run": i}, sort_keys=True),
                )
                for i in range(1, rows_per_table + 1)
            ),
        )
        _batch(
            connection,
            """
            INSERT INTO health_surveillance_signal
                (signal_id, run_id, reporting_date, geography_type,
                 geography_id, geography_name, syndrome_code, observed_count,
                 expected_count, baseline_stddev, anomaly_score,
                 observed_expected_ratio, contributing_hospitals,
                 reporting_completeness, corroborated, signal_level,
                 review_status, method_version, evidence_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    i, i, (today - timedelta(days=(i - 1) % 365)).isoformat(),
                    "HOSPITAL", i, f"Synthetic Hospital {i:06d}",
                    syndromes[(i - 1) % len(syndromes)], 10 + (i % 100),
                    5.0 + (i % 20), 1.0 + (i % 5), 2.0 + (i % 10),
                    round((10 + (i % 100)) / (5.0 + (i % 20)), 4),
                    1 + (i % 20), 1.0, 1,
                    "HIGH" if i % 4 == 0 else "WATCH",
                    ("NEEDS_REVIEW", "VERIFIED", "DISMISSED")[(i - 1) % 3],
                    "synthetic-detector-v1",
                    json.dumps({"synthetic": True, "signal": i}, sort_keys=True),
                    "2026-07-22T00:05:00+00:00",
                )
                for i in range(1, rows_per_table + 1)
            ),
        )

        # Populate optional compatibility and policy columns at least once.
        connection.execute(
            "UPDATE hospital SET effective_to = '2025-03-31' WHERE hospital_id = 50"
        )
        connection.execute(
            """
            UPDATE hospital_facility_classification
            SET effective_to = '2025-03-31'
            WHERE hospital_id = 50
            """
        )
        connection.execute(
            """
            UPDATE semantic_access_policy
            SET row_filter_expression = 'privacy_classification <> RESTRICTED'
            WHERE access_policy_id = 1
            """
        )

        # Audit rows are synthetic execution logs. Preserve any real local test
        # executions and top up only to the requested row count.
        audit_count = int(connection.execute("SELECT COUNT(*) FROM audit_execution").fetchone()[0])
        if audit_count < rows_per_table:
            _batch(
                connection,
                """
                INSERT INTO audit_execution
                    (created_at, question_sha256, question_spec_json,
                     generated_sql, status, row_count, llm_provider,
                     provenance_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (
                        "2026-07-22T00:00:00+00:00",
                        hashlib.sha256(f"synthetic question {i}".encode()).hexdigest(),
                        json.dumps({"synthetic": True, "question": i}, sort_keys=True),
                        "SELECT 1 AS synthetic_result",
                        "PASS_WITH_LIMITATIONS", 1, "synthetic",
                        json.dumps({"synthetic": True, "execution": i}, sort_keys=True),
                    )
                    for i in range(1, rows_per_table - audit_count + 1)
                ),
            )

        counts, empty_tables, all_null_columns = _coverage(connection)
        for table in HIGH_CARDINALITY_TABLES:
            actual = counts.get(table)
            if actual != rows_per_table:
                raise RuntimeError(
                    f"Synthetic row-count verification failed for {table}: "
                    f"expected {rows_per_table}, found {actual}"
                )
        if empty_tables:
            raise RuntimeError(
                "Synthetic coverage left empty tables: " + ", ".join(empty_tables)
            )
        if all_null_columns:
            raise RuntimeError(
                "Synthetic coverage left all-null columns: "
                + ", ".join(all_null_columns)
            )

    return ComprehensiveSyntheticResult(
        rows_per_table=rows_per_table,
        table_counts=counts,
        empty_tables=empty_tables,
        all_null_columns=all_null_columns,
    )
