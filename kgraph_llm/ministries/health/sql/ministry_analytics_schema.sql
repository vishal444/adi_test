-- Kerala Health Department ministry analytics model.
--
-- SQLite does not provide PostgreSQL-style schemas, so the report's logical
-- master.*, analytics.*, finance.*, restricted.*, and semantic.* namespaces
-- are represented by explicit table prefixes. Operational source records stay
-- outside this model; facts here are governed aggregates with source lineage.

CREATE TABLE IF NOT EXISTS master_source_system (
    source_system_id INTEGER PRIMARY KEY,
    source_code TEXT NOT NULL UNIQUE,
    source_name TEXT NOT NULL,
    system_owner TEXT NOT NULL,
    data_steward TEXT,
    refresh_frequency TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS master_calendar (
    month_id TEXT PRIMARY KEY,
    calendar_year INTEGER NOT NULL,
    calendar_month INTEGER NOT NULL CHECK (calendar_month BETWEEN 1 AND 12),
    fiscal_year_start INTEGER NOT NULL,
    fiscal_quarter INTEGER NOT NULL CHECK (fiscal_quarter BETWEEN 1 AND 4),
    month_name TEXT NOT NULL,
    CHECK (length(month_id) = 10 AND substr(month_id, 9, 2) = '01')
);

CREATE TABLE IF NOT EXISTS master_geographic_area (
    geographic_area_id INTEGER PRIMARY KEY,
    area_code TEXT NOT NULL UNIQUE,
    area_name TEXT NOT NULL,
    area_level TEXT NOT NULL
        CHECK (area_level IN ('STATE', 'DISTRICT', 'TALUK', 'BLOCK', 'LOCAL_BODY', 'WARD', 'CATCHMENT')),
    parent_geographic_area_id INTEGER REFERENCES master_geographic_area(geographic_area_id),
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    CHECK (effective_to IS NULL OR effective_to > effective_from)
);

CREATE TABLE IF NOT EXISTS master_organisation (
    organisation_id INTEGER PRIMARY KEY,
    organisation_code TEXT NOT NULL UNIQUE,
    organisation_name TEXT NOT NULL,
    organisation_type TEXT NOT NULL
        CHECK (organisation_type IN (
            'GOVERNMENT', 'DEPARTMENT', 'DIRECTORATE', 'MISSION',
            'CORPORATION', 'AGENCY', 'REGULATOR',
            'AUTONOMOUS_INSTITUTION', 'DISTRICT_OFFICE',
            'FACILITY_ADMINISTRATION', 'OTHER'
        )),
    parent_organisation_id INTEGER REFERENCES master_organisation(organisation_id),
    administrative_level TEXT NOT NULL
        CHECK (administrative_level IN (
            'STATE', 'DISTRICT', 'TALUK', 'BLOCK', 'LOCAL_BODY', 'FACILITY'
        )),
    system_of_medicine_id INTEGER REFERENCES master_system_of_medicine(system_of_medicine_id),
    district_id INTEGER REFERENCES master_geographic_area(geographic_area_id),
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    CHECK (effective_to IS NULL OR effective_to > effective_from)
);

-- The triggers also apply the vocabulary when an existing database predates
-- the table-level CHECK constraints.
CREATE TRIGGER IF NOT EXISTS validate_master_organisation_insert
BEFORE INSERT ON master_organisation
WHEN NEW.organisation_type NOT IN (
         'GOVERNMENT', 'DEPARTMENT', 'DIRECTORATE', 'MISSION',
         'CORPORATION', 'AGENCY', 'REGULATOR', 'AUTONOMOUS_INSTITUTION',
         'DISTRICT_OFFICE', 'FACILITY_ADMINISTRATION', 'OTHER'
     )
  OR NEW.administrative_level NOT IN (
         'STATE', 'DISTRICT', 'TALUK', 'BLOCK', 'LOCAL_BODY', 'FACILITY'
     )
BEGIN
    SELECT RAISE(ABORT, 'invalid master_organisation classification');
END;

CREATE TRIGGER IF NOT EXISTS validate_master_organisation_update
BEFORE UPDATE OF organisation_type, administrative_level ON master_organisation
WHEN NEW.organisation_type NOT IN (
         'GOVERNMENT', 'DEPARTMENT', 'DIRECTORATE', 'MISSION',
         'CORPORATION', 'AGENCY', 'REGULATOR', 'AUTONOMOUS_INSTITUTION',
         'DISTRICT_OFFICE', 'FACILITY_ADMINISTRATION', 'OTHER'
     )
  OR NEW.administrative_level NOT IN (
         'STATE', 'DISTRICT', 'TALUK', 'BLOCK', 'LOCAL_BODY', 'FACILITY'
     )
BEGIN
    SELECT RAISE(ABORT, 'invalid master_organisation classification');
END;

CREATE TABLE IF NOT EXISTS master_facility_type (
    facility_type_id INTEGER PRIMARY KEY,
    facility_type_code TEXT NOT NULL UNIQUE,
    facility_type_name TEXT NOT NULL,
    facility_level INTEGER NOT NULL CHECK (facility_level BETWEEN 1 AND 7),
    teaching_capable INTEGER NOT NULL DEFAULT 0 CHECK (teaching_capable IN (0, 1)),
    specialty_only INTEGER NOT NULL DEFAULT 0 CHECK (specialty_only IN (0, 1)),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS master_system_of_medicine (
    system_of_medicine_id INTEGER PRIMARY KEY,
    system_code TEXT NOT NULL UNIQUE,
    system_name TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS master_facility (
    facility_id INTEGER PRIMARY KEY,
    facility_code TEXT NOT NULL UNIQUE,
    facility_name TEXT NOT NULL,
    facility_type_id INTEGER NOT NULL REFERENCES master_facility_type(facility_type_id),
    parent_organisation_id INTEGER NOT NULL REFERENCES master_organisation(organisation_id),
    district_id INTEGER NOT NULL REFERENCES master_geographic_area(geographic_area_id),
    local_body_id INTEGER REFERENCES master_geographic_area(geographic_area_id),
    system_of_medicine_id INTEGER NOT NULL REFERENCES master_system_of_medicine(system_of_medicine_id),
    ownership_type TEXT NOT NULL DEFAULT 'STATE_GOVERNMENT'
        CHECK (ownership_type IN ('STATE_GOVERNMENT', 'LOCAL_GOVERNMENT', 'CENTRAL_GOVERNMENT', 'AUTONOMOUS', 'PRIVATE', 'COOPERATIVE', 'OTHER')),
    urban_rural_category TEXT NOT NULL CHECK (urban_rural_category IN ('URBAN', 'RURAL', 'TRIBAL', 'MIXED')),
    teaching_status TEXT NOT NULL DEFAULT 'NON_TEACHING'
        CHECK (teaching_status IN ('NON_TEACHING', 'TEACHING', 'AFFILIATED')),
    sanctioned_bed_capacity INTEGER NOT NULL DEFAULT 0 CHECK (sanctioned_bed_capacity >= 0),
    operational_status TEXT NOT NULL
        CHECK (operational_status IN ('PLANNED', 'OPERATIONAL', 'PARTIALLY_OPERATIONAL', 'TEMPORARILY_CLOSED', 'CLOSED')),
    latitude REAL CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
    longitude REAL CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    source_system_id INTEGER REFERENCES master_source_system(source_system_id),
    source_version TEXT NOT NULL,
    CHECK (effective_to IS NULL OR effective_to > effective_from)
);

-- SQLite cannot express these cross-table invariants as CHECK constraints.
-- A local body is modelled as a direct child of its administrative district.
CREATE TRIGGER IF NOT EXISTS validate_master_facility_geography_insert
BEFORE INSERT ON master_facility
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1
            FROM master_geographic_area
            WHERE geographic_area_id = NEW.district_id
              AND area_level = 'DISTRICT'
        )
        THEN RAISE(ABORT, 'master_facility.district_id must reference a DISTRICT')
    END;
    SELECT CASE
        WHEN NEW.local_body_id IS NOT NULL
         AND NOT EXISTS (
            SELECT 1
            FROM master_geographic_area
            WHERE geographic_area_id = NEW.local_body_id
              AND area_level = 'LOCAL_BODY'
              AND parent_geographic_area_id = NEW.district_id
        )
        THEN RAISE(ABORT, 'master_facility.local_body_id must reference a LOCAL_BODY in district_id')
    END;
END;

CREATE TRIGGER IF NOT EXISTS validate_master_facility_geography_update
BEFORE UPDATE OF district_id, local_body_id ON master_facility
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1
            FROM master_geographic_area
            WHERE geographic_area_id = NEW.district_id
              AND area_level = 'DISTRICT'
        )
        THEN RAISE(ABORT, 'master_facility.district_id must reference a DISTRICT')
    END;
    SELECT CASE
        WHEN NEW.local_body_id IS NOT NULL
         AND NOT EXISTS (
            SELECT 1
            FROM master_geographic_area
            WHERE geographic_area_id = NEW.local_body_id
              AND area_level = 'LOCAL_BODY'
              AND parent_geographic_area_id = NEW.district_id
        )
        THEN RAISE(ABORT, 'master_facility.local_body_id must reference a LOCAL_BODY in district_id')
    END;
END;

CREATE TRIGGER IF NOT EXISTS protect_master_facility_geography_update
BEFORE UPDATE OF area_level, parent_geographic_area_id ON master_geographic_area
WHEN EXISTS (
    SELECT 1
    FROM master_facility AS facility
    WHERE (facility.district_id = OLD.geographic_area_id
           AND NEW.area_level <> 'DISTRICT')
       OR (facility.local_body_id = OLD.geographic_area_id
           AND (NEW.area_level <> 'LOCAL_BODY'
                OR NEW.parent_geographic_area_id IS NOT facility.district_id))
)
BEGIN
    SELECT RAISE(ABORT, 'geographic area update would invalidate master_facility geography');
END;

CREATE TRIGGER IF NOT EXISTS validate_master_facility_teaching_insert
BEFORE INSERT ON master_facility
WHEN NEW.teaching_status <> 'NON_TEACHING'
 AND NOT EXISTS (
     SELECT 1
     FROM master_facility_type
     WHERE facility_type_id = NEW.facility_type_id
       AND teaching_capable = 1
 )
BEGIN
    SELECT RAISE(ABORT, 'teaching facility requires a teaching-capable facility type');
END;

CREATE TRIGGER IF NOT EXISTS validate_master_facility_teaching_update
BEFORE UPDATE OF facility_type_id, teaching_status ON master_facility
WHEN NEW.teaching_status <> 'NON_TEACHING'
 AND NOT EXISTS (
     SELECT 1
     FROM master_facility_type
     WHERE facility_type_id = NEW.facility_type_id
       AND teaching_capable = 1
 )
BEGIN
    SELECT RAISE(ABORT, 'teaching facility requires a teaching-capable facility type');
END;

CREATE TRIGGER IF NOT EXISTS protect_teaching_capability_update
BEFORE UPDATE OF teaching_capable ON master_facility_type
WHEN NEW.teaching_capable = 0
 AND EXISTS (
     SELECT 1
     FROM master_facility
     WHERE facility_type_id = OLD.facility_type_id
       AND teaching_status <> 'NON_TEACHING'
 )
BEGIN
    SELECT RAISE(ABORT, 'facility type is used by a teaching facility');
END;

CREATE TABLE IF NOT EXISTS master_cost_category (
    cost_category_id INTEGER PRIMARY KEY,
    category_code TEXT NOT NULL UNIQUE,
    category_name TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS master_staff_category (
    staff_category_id INTEGER PRIMARY KEY,
    category_code TEXT NOT NULL UNIQUE,
    category_name TEXT NOT NULL UNIQUE,
    clinical INTEGER NOT NULL DEFAULT 0 CHECK (clinical IN (0, 1)),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS master_equipment_category (
    equipment_category_id INTEGER PRIMARY KEY,
    category_code TEXT NOT NULL UNIQUE,
    category_name TEXT NOT NULL UNIQUE,
    criticality TEXT NOT NULL DEFAULT 'ROUTINE'
        CHECK (criticality IN ('ROUTINE', 'IMPORTANT', 'CRITICAL')),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS master_service_category (
    service_category_id INTEGER PRIMARY KEY,
    category_code TEXT NOT NULL UNIQUE,
    category_name TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS master_infrastructure_category (
    infrastructure_category_id INTEGER PRIMARY KEY,
    category_code TEXT NOT NULL UNIQUE,
    category_name TEXT NOT NULL UNIQUE,
    critical INTEGER NOT NULL DEFAULT 0 CHECK (critical IN (0, 1)),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS master_procurement_category (
    procurement_category_id INTEGER PRIMARY KEY,
    category_code TEXT NOT NULL UNIQUE,
    category_name TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS master_vehicle_category (
    vehicle_category_id INTEGER PRIMARY KEY,
    category_code TEXT NOT NULL UNIQUE,
    category_name TEXT NOT NULL UNIQUE,
    emergency_vehicle INTEGER NOT NULL DEFAULT 0 CHECK (emergency_vehicle IN (0, 1)),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS master_quality_category (
    quality_category_id INTEGER PRIMARY KEY,
    category_code TEXT NOT NULL UNIQUE,
    category_name TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS master_demographic_group (
    demographic_group_id INTEGER PRIMARY KEY,
    group_code TEXT NOT NULL UNIQUE,
    group_name TEXT NOT NULL UNIQUE,
    dimension_type TEXT NOT NULL
        CHECK (dimension_type IN ('ALL', 'AGE', 'SEX', 'DISABILITY', 'SOCIOECONOMIC', 'TRIBAL', 'COASTAL', 'MIGRANT', 'OTHER')),
    privacy_classification TEXT NOT NULL DEFAULT 'AGGREGATE'
        CHECK (privacy_classification IN ('PUBLIC', 'AGGREGATE', 'RESTRICTED')),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS master_programme (
    programme_id INTEGER PRIMARY KEY,
    programme_code TEXT NOT NULL UNIQUE,
    programme_name TEXT NOT NULL,
    programme_category TEXT NOT NULL,
    administering_organisation_id INTEGER NOT NULL REFERENCES master_organisation(organisation_id),
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    CHECK (effective_to IS NULL OR effective_to > effective_from)
);

CREATE TABLE IF NOT EXISTS master_scheme (
    scheme_id INTEGER PRIMARY KEY,
    scheme_code TEXT NOT NULL UNIQUE,
    scheme_name TEXT NOT NULL,
    scheme_category TEXT NOT NULL,
    administering_organisation_id INTEGER NOT NULL REFERENCES master_organisation(organisation_id),
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    CHECK (effective_to IS NULL OR effective_to > effective_from)
);

CREATE TABLE IF NOT EXISTS master_supplier (
    supplier_id INTEGER PRIMARY KEY,
    supplier_code TEXT NOT NULL UNIQUE,
    supplier_name TEXT NOT NULL,
    supplier_type TEXT NOT NULL,
    district_id INTEGER REFERENCES master_geographic_area(geographic_area_id),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS master_budget_head (
    budget_head_id INTEGER PRIMARY KEY,
    budget_head_code TEXT NOT NULL UNIQUE,
    budget_head_name TEXT NOT NULL,
    parent_budget_head_id INTEGER REFERENCES master_budget_head(budget_head_id),
    fund_source TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS master_project (
    project_id INTEGER PRIMARY KEY,
    project_code TEXT NOT NULL UNIQUE,
    project_name TEXT NOT NULL,
    project_category TEXT NOT NULL,
    facility_id INTEGER REFERENCES master_facility(facility_id),
    responsible_organisation_id INTEGER NOT NULL REFERENCES master_organisation(organisation_id),
    budget_head_id INTEGER REFERENCES master_budget_head(budget_head_id),
    approved_on TEXT,
    planned_completion_date TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

-- Aggregate analytical facts -----------------------------------------------

CREATE TABLE IF NOT EXISTS analytics_facility_monthly_summary (
    facility_id INTEGER NOT NULL REFERENCES master_facility(facility_id),
    month_id TEXT NOT NULL REFERENCES master_calendar(month_id),
    outpatient_visits INTEGER NOT NULL DEFAULT 0 CHECK (outpatient_visits >= 0),
    inpatient_admissions INTEGER NOT NULL DEFAULT 0 CHECK (inpatient_admissions >= 0),
    emergency_visits INTEGER NOT NULL DEFAULT 0 CHECK (emergency_visits >= 0),
    surgeries_completed INTEGER NOT NULL DEFAULT 0 CHECK (surgeries_completed >= 0),
    deliveries_completed INTEGER NOT NULL DEFAULT 0 CHECK (deliveries_completed >= 0),
    diagnostic_tests_completed INTEGER NOT NULL DEFAULT 0 CHECK (diagnostic_tests_completed >= 0),
    patients_referred_out INTEGER NOT NULL DEFAULT 0 CHECK (patients_referred_out >= 0),
    patients_referred_in INTEGER NOT NULL DEFAULT 0 CHECK (patients_referred_in >= 0),
    sanctioned_beds INTEGER NOT NULL DEFAULT 0 CHECK (sanctioned_beds >= 0),
    operational_beds INTEGER NOT NULL DEFAULT 0 CHECK (operational_beds >= 0),
    occupied_bed_days INTEGER NOT NULL DEFAULT 0 CHECK (occupied_bed_days >= 0),
    available_bed_days INTEGER NOT NULL DEFAULT 0 CHECK (available_bed_days >= 0),
    total_staff_required INTEGER NOT NULL DEFAULT 0 CHECK (total_staff_required >= 0),
    total_staff_sanctioned INTEGER NOT NULL DEFAULT 0 CHECK (total_staff_sanctioned >= 0),
    total_staff_available INTEGER NOT NULL DEFAULT 0 CHECK (total_staff_available >= 0),
    total_budget_available REAL NOT NULL DEFAULT 0 CHECK (total_budget_available >= 0),
    total_expenditure REAL NOT NULL DEFAULT 0 CHECK (total_expenditure >= 0),
    average_waiting_minutes REAL CHECK (average_waiting_minutes IS NULL OR average_waiting_minutes >= 0),
    service_cancellation_count INTEGER NOT NULL DEFAULT 0 CHECK (service_cancellation_count >= 0),
    patient_grievance_count INTEGER NOT NULL DEFAULT 0 CHECK (patient_grievance_count >= 0),
    reported_deaths INTEGER NOT NULL DEFAULT 0 CHECK (reported_deaths >= 0),
    source_system_id INTEGER NOT NULL REFERENCES master_source_system(source_system_id),
    source_version TEXT NOT NULL,
    loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (facility_id, month_id)
);

CREATE TABLE IF NOT EXISTS analytics_medicine_monthly (
    facility_id INTEGER NOT NULL REFERENCES master_facility(facility_id),
    month_id TEXT NOT NULL REFERENCES master_calendar(month_id),
    opening_stock_value REAL NOT NULL DEFAULT 0 CHECK (opening_stock_value >= 0),
    medicine_received_value REAL NOT NULL DEFAULT 0 CHECK (medicine_received_value >= 0),
    medicine_consumed_value REAL NOT NULL DEFAULT 0 CHECK (medicine_consumed_value >= 0),
    closing_stock_value REAL NOT NULL DEFAULT 0 CHECK (closing_stock_value >= 0),
    estimated_required_stock_value REAL NOT NULL DEFAULT 0 CHECK (estimated_required_stock_value >= 0),
    available_stock_value REAL NOT NULL DEFAULT 0 CHECK (available_stock_value >= 0),
    medicine_procurement_cost REAL NOT NULL DEFAULT 0 CHECK (medicine_procurement_cost >= 0),
    medicine_distribution_cost REAL NOT NULL DEFAULT 0 CHECK (medicine_distribution_cost >= 0),
    expired_medicine_value REAL NOT NULL DEFAULT 0 CHECK (expired_medicine_value >= 0),
    damaged_medicine_value REAL NOT NULL DEFAULT 0 CHECK (damaged_medicine_value >= 0),
    emergency_local_purchase_cost REAL NOT NULL DEFAULT 0 CHECK (emergency_local_purchase_cost >= 0),
    stockout_days INTEGER NOT NULL DEFAULT 0 CHECK (stockout_days BETWEEN 0 AND 31),
    critical_stockout_incidents INTEGER NOT NULL DEFAULT 0 CHECK (critical_stockout_incidents >= 0),
    average_supply_delay_days REAL CHECK (average_supply_delay_days IS NULL OR average_supply_delay_days >= 0),
    source_system_id INTEGER NOT NULL REFERENCES master_source_system(source_system_id),
    source_version TEXT NOT NULL,
    loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (facility_id, month_id)
);

CREATE TABLE IF NOT EXISTS analytics_equipment_monthly (
    facility_id INTEGER NOT NULL REFERENCES master_facility(facility_id),
    equipment_category_id INTEGER NOT NULL REFERENCES master_equipment_category(equipment_category_id),
    month_id TEXT NOT NULL REFERENCES master_calendar(month_id),
    equipment_required_count INTEGER NOT NULL DEFAULT 0 CHECK (equipment_required_count >= 0),
    equipment_available_count INTEGER NOT NULL DEFAULT 0 CHECK (equipment_available_count >= 0),
    equipment_functional_count INTEGER NOT NULL DEFAULT 0 CHECK (equipment_functional_count >= 0),
    equipment_nonfunctional_count INTEGER NOT NULL DEFAULT 0 CHECK (equipment_nonfunctional_count >= 0),
    equipment_under_maintenance_count INTEGER NOT NULL DEFAULT 0 CHECK (equipment_under_maintenance_count >= 0),
    new_equipment_procured_count INTEGER NOT NULL DEFAULT 0 CHECK (new_equipment_procured_count >= 0),
    equipment_procurement_value REAL NOT NULL DEFAULT 0 CHECK (equipment_procurement_value >= 0),
    equipment_maintenance_cost REAL NOT NULL DEFAULT 0 CHECK (equipment_maintenance_cost >= 0),
    spare_parts_cost REAL NOT NULL DEFAULT 0 CHECK (spare_parts_cost >= 0),
    total_downtime_hours REAL NOT NULL DEFAULT 0 CHECK (total_downtime_hours >= 0),
    average_repair_time_days REAL CHECK (average_repair_time_days IS NULL OR average_repair_time_days >= 0),
    utilisation_rate REAL CHECK (utilisation_rate IS NULL OR utilisation_rate BETWEEN 0 AND 100),
    maintenance_compliance_rate REAL CHECK (maintenance_compliance_rate IS NULL OR maintenance_compliance_rate BETWEEN 0 AND 100),
    source_system_id INTEGER NOT NULL REFERENCES master_source_system(source_system_id),
    source_version TEXT NOT NULL,
    loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (facility_id, equipment_category_id, month_id)
);

CREATE TABLE IF NOT EXISTS analytics_staffing_monthly (
    facility_id INTEGER NOT NULL REFERENCES master_facility(facility_id),
    staff_category_id INTEGER NOT NULL REFERENCES master_staff_category(staff_category_id),
    month_id TEXT NOT NULL REFERENCES master_calendar(month_id),
    sanctioned_posts INTEGER NOT NULL DEFAULT 0 CHECK (sanctioned_posts >= 0),
    required_posts INTEGER NOT NULL DEFAULT 0 CHECK (required_posts >= 0),
    filled_posts INTEGER NOT NULL DEFAULT 0 CHECK (filled_posts >= 0),
    staff_actually_available INTEGER NOT NULL DEFAULT 0 CHECK (staff_actually_available >= 0),
    permanent_staff_count INTEGER NOT NULL DEFAULT 0 CHECK (permanent_staff_count >= 0),
    contract_staff_count INTEGER NOT NULL DEFAULT 0 CHECK (contract_staff_count >= 0),
    temporary_staff_count INTEGER NOT NULL DEFAULT 0 CHECK (temporary_staff_count >= 0),
    staff_on_leave INTEGER NOT NULL DEFAULT 0 CHECK (staff_on_leave >= 0),
    staff_on_deputation INTEGER NOT NULL DEFAULT 0 CHECK (staff_on_deputation >= 0),
    overtime_hours REAL NOT NULL DEFAULT 0 CHECK (overtime_hours >= 0),
    training_hours REAL NOT NULL DEFAULT 0 CHECK (training_hours >= 0),
    salary_cost REAL NOT NULL DEFAULT 0 CHECK (salary_cost >= 0),
    contract_staff_cost REAL NOT NULL DEFAULT 0 CHECK (contract_staff_cost >= 0),
    overtime_cost REAL NOT NULL DEFAULT 0 CHECK (overtime_cost >= 0),
    source_system_id INTEGER NOT NULL REFERENCES master_source_system(source_system_id),
    source_version TEXT NOT NULL,
    loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (facility_id, staff_category_id, month_id)
);

CREATE TABLE IF NOT EXISTS analytics_service_monthly (
    facility_id INTEGER NOT NULL REFERENCES master_facility(facility_id),
    service_category_id INTEGER NOT NULL REFERENCES master_service_category(service_category_id),
    demographic_group_id INTEGER NOT NULL REFERENCES master_demographic_group(demographic_group_id),
    month_id TEXT NOT NULL REFERENCES master_calendar(month_id),
    service_capacity INTEGER NOT NULL DEFAULT 0 CHECK (service_capacity >= 0),
    service_demand INTEGER NOT NULL DEFAULT 0 CHECK (service_demand >= 0),
    services_delivered INTEGER NOT NULL DEFAULT 0 CHECK (services_delivered >= 0),
    services_cancelled INTEGER NOT NULL DEFAULT 0 CHECK (services_cancelled >= 0),
    patients_waiting INTEGER NOT NULL DEFAULT 0 CHECK (patients_waiting >= 0),
    average_waiting_days REAL CHECK (average_waiting_days IS NULL OR average_waiting_days >= 0),
    required_staff_count INTEGER NOT NULL DEFAULT 0 CHECK (required_staff_count >= 0),
    available_staff_count INTEGER NOT NULL DEFAULT 0 CHECK (available_staff_count >= 0),
    required_equipment_count INTEGER NOT NULL DEFAULT 0 CHECK (required_equipment_count >= 0),
    functional_equipment_count INTEGER NOT NULL DEFAULT 0 CHECK (functional_equipment_count >= 0),
    referrals_out INTEGER NOT NULL DEFAULT 0 CHECK (referrals_out >= 0),
    referrals_in INTEGER NOT NULL DEFAULT 0 CHECK (referrals_in >= 0),
    estimated_unmet_demand INTEGER NOT NULL DEFAULT 0 CHECK (estimated_unmet_demand >= 0),
    service_availability_status TEXT NOT NULL
        CHECK (service_availability_status IN ('AVAILABLE', 'CONSTRAINED', 'UNAVAILABLE', 'NOT_APPLICABLE')),
    source_system_id INTEGER NOT NULL REFERENCES master_source_system(source_system_id),
    source_version TEXT NOT NULL,
    loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (facility_id, service_category_id, demographic_group_id, month_id)
);

CREATE TABLE IF NOT EXISTS analytics_referral_flow_monthly (
    source_facility_id INTEGER NOT NULL REFERENCES master_facility(facility_id),
    destination_facility_id INTEGER NOT NULL REFERENCES master_facility(facility_id),
    service_category_id INTEGER NOT NULL REFERENCES master_service_category(service_category_id),
    month_id TEXT NOT NULL REFERENCES master_calendar(month_id),
    referral_count INTEGER NOT NULL DEFAULT 0 CHECK (referral_count >= 0),
    emergency_referral_count INTEGER NOT NULL DEFAULT 0 CHECK (emergency_referral_count >= 0),
    accepted_referral_count INTEGER NOT NULL DEFAULT 0 CHECK (accepted_referral_count >= 0),
    rejected_referral_count INTEGER NOT NULL DEFAULT 0 CHECK (rejected_referral_count >= 0),
    completed_referral_count INTEGER NOT NULL DEFAULT 0 CHECK (completed_referral_count >= 0),
    average_transfer_minutes REAL CHECK (average_transfer_minutes IS NULL OR average_transfer_minutes >= 0),
    average_distance_km REAL CHECK (average_distance_km IS NULL OR average_distance_km >= 0),
    ambulance_used_count INTEGER NOT NULL DEFAULT 0 CHECK (ambulance_used_count >= 0),
    main_resource_gap_category TEXT,
    source_system_id INTEGER NOT NULL REFERENCES master_source_system(source_system_id),
    source_version TEXT NOT NULL,
    loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_facility_id, destination_facility_id, service_category_id, month_id),
    CHECK (source_facility_id <> destination_facility_id)
);

CREATE TABLE IF NOT EXISTS analytics_procurement_monthly (
    procuring_organisation_id INTEGER NOT NULL REFERENCES master_organisation(organisation_id),
    facility_id INTEGER REFERENCES master_facility(facility_id),
    supplier_id INTEGER NOT NULL REFERENCES master_supplier(supplier_id),
    procurement_category_id INTEGER NOT NULL REFERENCES master_procurement_category(procurement_category_id),
    month_id TEXT NOT NULL REFERENCES master_calendar(month_id),
    requested_value REAL NOT NULL DEFAULT 0 CHECK (requested_value >= 0),
    approved_value REAL NOT NULL DEFAULT 0 CHECK (approved_value >= 0),
    ordered_value REAL NOT NULL DEFAULT 0 CHECK (ordered_value >= 0),
    received_value REAL NOT NULL DEFAULT 0 CHECK (received_value >= 0),
    paid_value REAL NOT NULL DEFAULT 0 CHECK (paid_value >= 0),
    purchase_order_count INTEGER NOT NULL DEFAULT 0 CHECK (purchase_order_count >= 0),
    completed_order_count INTEGER NOT NULL DEFAULT 0 CHECK (completed_order_count >= 0),
    delayed_order_count INTEGER NOT NULL DEFAULT 0 CHECK (delayed_order_count >= 0),
    cancelled_order_count INTEGER NOT NULL DEFAULT 0 CHECK (cancelled_order_count >= 0),
    average_procurement_days REAL CHECK (average_procurement_days IS NULL OR average_procurement_days >= 0),
    average_delivery_delay_days REAL CHECK (average_delivery_delay_days IS NULL OR average_delivery_delay_days >= 0),
    quality_rejection_value REAL NOT NULL DEFAULT 0 CHECK (quality_rejection_value >= 0),
    penalty_amount REAL NOT NULL DEFAULT 0 CHECK (penalty_amount >= 0),
    emergency_purchase_value REAL NOT NULL DEFAULT 0 CHECK (emergency_purchase_value >= 0),
    source_system_id INTEGER NOT NULL REFERENCES master_source_system(source_system_id),
    source_version TEXT NOT NULL,
    loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (procuring_organisation_id, facility_id, supplier_id, procurement_category_id, month_id)
);

CREATE TABLE IF NOT EXISTS analytics_supplier_performance_monthly (
    supplier_id INTEGER NOT NULL REFERENCES master_supplier(supplier_id),
    procurement_category_id INTEGER NOT NULL REFERENCES master_procurement_category(procurement_category_id),
    month_id TEXT NOT NULL REFERENCES master_calendar(month_id),
    contract_value REAL NOT NULL DEFAULT 0 CHECK (contract_value >= 0),
    ordered_value REAL NOT NULL DEFAULT 0 CHECK (ordered_value >= 0),
    delivered_value REAL NOT NULL DEFAULT 0 CHECK (delivered_value >= 0),
    paid_value REAL NOT NULL DEFAULT 0 CHECK (paid_value >= 0),
    orders_received INTEGER NOT NULL DEFAULT 0 CHECK (orders_received >= 0),
    orders_completed INTEGER NOT NULL DEFAULT 0 CHECK (orders_completed >= 0),
    orders_delayed INTEGER NOT NULL DEFAULT 0 CHECK (orders_delayed >= 0),
    orders_rejected INTEGER NOT NULL DEFAULT 0 CHECK (orders_rejected >= 0),
    average_delivery_delay_days REAL CHECK (average_delivery_delay_days IS NULL OR average_delivery_delay_days >= 0),
    quality_rejection_rate REAL CHECK (quality_rejection_rate IS NULL OR quality_rejection_rate BETWEEN 0 AND 100),
    contract_compliance_rate REAL CHECK (contract_compliance_rate IS NULL OR contract_compliance_rate BETWEEN 0 AND 100),
    payment_pending_value REAL NOT NULL DEFAULT 0 CHECK (payment_pending_value >= 0),
    supplier_risk_score REAL CHECK (supplier_risk_score IS NULL OR supplier_risk_score BETWEEN 0 AND 100),
    source_system_id INTEGER NOT NULL REFERENCES master_source_system(source_system_id),
    source_version TEXT NOT NULL,
    loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (supplier_id, procurement_category_id, month_id)
);

CREATE TABLE IF NOT EXISTS analytics_infrastructure_monthly (
    facility_id INTEGER NOT NULL REFERENCES master_facility(facility_id),
    infrastructure_category_id INTEGER NOT NULL REFERENCES master_infrastructure_category(infrastructure_category_id),
    month_id TEXT NOT NULL REFERENCES master_calendar(month_id),
    required_capacity REAL NOT NULL DEFAULT 0 CHECK (required_capacity >= 0),
    available_capacity REAL NOT NULL DEFAULT 0 CHECK (available_capacity >= 0),
    functional_capacity REAL NOT NULL DEFAULT 0 CHECK (functional_capacity >= 0),
    maintenance_cost REAL NOT NULL DEFAULT 0 CHECK (maintenance_cost >= 0),
    repair_cost REAL NOT NULL DEFAULT 0 CHECK (repair_cost >= 0),
    capital_expenditure REAL NOT NULL DEFAULT 0 CHECK (capital_expenditure >= 0),
    downtime_hours REAL NOT NULL DEFAULT 0 CHECK (downtime_hours >= 0),
    inspection_issues INTEGER NOT NULL DEFAULT 0 CHECK (inspection_issues >= 0),
    critical_issues INTEGER NOT NULL DEFAULT 0 CHECK (critical_issues >= 0),
    issues_resolved INTEGER NOT NULL DEFAULT 0 CHECK (issues_resolved >= 0),
    source_system_id INTEGER NOT NULL REFERENCES master_source_system(source_system_id),
    source_version TEXT NOT NULL,
    loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (facility_id, infrastructure_category_id, month_id)
);

CREATE TABLE IF NOT EXISTS analytics_vehicle_monthly (
    facility_id INTEGER NOT NULL REFERENCES master_facility(facility_id),
    station_code TEXT NOT NULL DEFAULT 'FACILITY',
    vehicle_category_id INTEGER NOT NULL REFERENCES master_vehicle_category(vehicle_category_id),
    month_id TEXT NOT NULL REFERENCES master_calendar(month_id),
    required_vehicle_count INTEGER NOT NULL DEFAULT 0 CHECK (required_vehicle_count >= 0),
    available_vehicle_count INTEGER NOT NULL DEFAULT 0 CHECK (available_vehicle_count >= 0),
    functional_vehicle_count INTEGER NOT NULL DEFAULT 0 CHECK (functional_vehicle_count >= 0),
    trip_count INTEGER NOT NULL DEFAULT 0 CHECK (trip_count >= 0),
    emergency_trip_count INTEGER NOT NULL DEFAULT 0 CHECK (emergency_trip_count >= 0),
    distance_travelled_km REAL NOT NULL DEFAULT 0 CHECK (distance_travelled_km >= 0),
    patients_transported INTEGER NOT NULL DEFAULT 0 CHECK (patients_transported >= 0),
    fuel_cost REAL NOT NULL DEFAULT 0 CHECK (fuel_cost >= 0),
    maintenance_cost REAL NOT NULL DEFAULT 0 CHECK (maintenance_cost >= 0),
    staff_cost REAL NOT NULL DEFAULT 0 CHECK (staff_cost >= 0),
    downtime_hours REAL NOT NULL DEFAULT 0 CHECK (downtime_hours >= 0),
    average_response_minutes REAL CHECK (average_response_minutes IS NULL OR average_response_minutes >= 0),
    average_trip_minutes REAL CHECK (average_trip_minutes IS NULL OR average_trip_minutes >= 0),
    source_system_id INTEGER NOT NULL REFERENCES master_source_system(source_system_id),
    source_version TEXT NOT NULL,
    loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (facility_id, station_code, vehicle_category_id, month_id)
);

CREATE TABLE IF NOT EXISTS analytics_programme_monthly (
    programme_id INTEGER NOT NULL REFERENCES master_programme(programme_id),
    district_id INTEGER NOT NULL REFERENCES master_geographic_area(geographic_area_id),
    demographic_group_id INTEGER NOT NULL REFERENCES master_demographic_group(demographic_group_id),
    month_id TEXT NOT NULL REFERENCES master_calendar(month_id),
    target_population INTEGER NOT NULL DEFAULT 0 CHECK (target_population >= 0),
    eligible_population INTEGER NOT NULL DEFAULT 0 CHECK (eligible_population >= 0),
    population_reached INTEGER NOT NULL DEFAULT 0 CHECK (population_reached >= 0),
    services_delivered INTEGER NOT NULL DEFAULT 0 CHECK (services_delivered >= 0),
    programme_budget REAL NOT NULL DEFAULT 0 CHECK (programme_budget >= 0),
    funds_released REAL NOT NULL DEFAULT 0 CHECK (funds_released >= 0),
    programme_expenditure REAL NOT NULL DEFAULT 0 CHECK (programme_expenditure >= 0),
    planned_activities INTEGER NOT NULL DEFAULT 0 CHECK (planned_activities >= 0),
    completed_activities INTEGER NOT NULL DEFAULT 0 CHECK (completed_activities >= 0),
    outcome_indicator_value REAL,
    source_system_id INTEGER NOT NULL REFERENCES master_source_system(source_system_id),
    source_version TEXT NOT NULL,
    loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (programme_id, district_id, demographic_group_id, month_id)
);

CREATE TABLE IF NOT EXISTS analytics_scheme_monthly (
    scheme_id INTEGER NOT NULL REFERENCES master_scheme(scheme_id),
    district_id INTEGER NOT NULL REFERENCES master_geographic_area(geographic_area_id),
    demographic_group_id INTEGER NOT NULL REFERENCES master_demographic_group(demographic_group_id),
    month_id TEXT NOT NULL REFERENCES master_calendar(month_id),
    eligible_households INTEGER NOT NULL DEFAULT 0 CHECK (eligible_households >= 0),
    enrolled_households INTEGER NOT NULL DEFAULT 0 CHECK (enrolled_households >= 0),
    eligible_individuals INTEGER NOT NULL DEFAULT 0 CHECK (eligible_individuals >= 0),
    enrolled_individuals INTEGER NOT NULL DEFAULT 0 CHECK (enrolled_individuals >= 0),
    beneficiaries_served INTEGER NOT NULL DEFAULT 0 CHECK (beneficiaries_served >= 0),
    claims_submitted INTEGER NOT NULL DEFAULT 0 CHECK (claims_submitted >= 0),
    claims_approved INTEGER NOT NULL DEFAULT 0 CHECK (claims_approved >= 0),
    claims_rejected INTEGER NOT NULL DEFAULT 0 CHECK (claims_rejected >= 0),
    claim_amount_requested REAL NOT NULL DEFAULT 0 CHECK (claim_amount_requested >= 0),
    claim_amount_approved REAL NOT NULL DEFAULT 0 CHECK (claim_amount_approved >= 0),
    claim_amount_paid REAL NOT NULL DEFAULT 0 CHECK (claim_amount_paid >= 0),
    average_claim_value REAL CHECK (average_claim_value IS NULL OR average_claim_value >= 0),
    average_claim_processing_days REAL CHECK (average_claim_processing_days IS NULL OR average_claim_processing_days >= 0),
    suspected_duplicate_count INTEGER NOT NULL DEFAULT 0 CHECK (suspected_duplicate_count >= 0),
    fraud_signal_count INTEGER NOT NULL DEFAULT 0 CHECK (fraud_signal_count >= 0),
    source_system_id INTEGER NOT NULL REFERENCES master_source_system(source_system_id),
    source_version TEXT NOT NULL,
    loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (scheme_id, district_id, demographic_group_id, month_id)
);

CREATE TABLE IF NOT EXISTS analytics_medical_college_annual (
    institution_id INTEGER NOT NULL REFERENCES master_facility(facility_id),
    academic_year TEXT NOT NULL,
    undergraduate_seats INTEGER NOT NULL DEFAULT 0 CHECK (undergraduate_seats >= 0),
    postgraduate_seats INTEGER NOT NULL DEFAULT 0 CHECK (postgraduate_seats >= 0),
    super_specialty_seats INTEGER NOT NULL DEFAULT 0 CHECK (super_specialty_seats >= 0),
    students_enrolled INTEGER NOT NULL DEFAULT 0 CHECK (students_enrolled >= 0),
    students_graduated INTEGER NOT NULL DEFAULT 0 CHECK (students_graduated >= 0),
    sanctioned_faculty_posts INTEGER NOT NULL DEFAULT 0 CHECK (sanctioned_faculty_posts >= 0),
    filled_faculty_posts INTEGER NOT NULL DEFAULT 0 CHECK (filled_faculty_posts >= 0),
    teaching_beds INTEGER NOT NULL DEFAULT 0 CHECK (teaching_beds >= 0),
    clinical_departments INTEGER NOT NULL DEFAULT 0 CHECK (clinical_departments >= 0),
    patient_volume INTEGER NOT NULL DEFAULT 0 CHECK (patient_volume >= 0),
    surgeries_completed INTEGER NOT NULL DEFAULT 0 CHECK (surgeries_completed >= 0),
    research_projects INTEGER NOT NULL DEFAULT 0 CHECK (research_projects >= 0),
    research_grants REAL NOT NULL DEFAULT 0 CHECK (research_grants >= 0),
    publications INTEGER NOT NULL DEFAULT 0 CHECK (publications >= 0),
    clinical_trials INTEGER NOT NULL DEFAULT 0 CHECK (clinical_trials >= 0),
    education_budget REAL NOT NULL DEFAULT 0 CHECK (education_budget >= 0),
    hospital_budget REAL NOT NULL DEFAULT 0 CHECK (hospital_budget >= 0),
    research_expenditure REAL NOT NULL DEFAULT 0 CHECK (research_expenditure >= 0),
    infrastructure_expenditure REAL NOT NULL DEFAULT 0 CHECK (infrastructure_expenditure >= 0),
    accreditation_status TEXT,
    inspection_deficiency_count INTEGER NOT NULL DEFAULT 0 CHECK (inspection_deficiency_count >= 0),
    source_system_id INTEGER NOT NULL REFERENCES master_source_system(source_system_id),
    source_version TEXT NOT NULL,
    loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (institution_id, academic_year)
);

CREATE TABLE IF NOT EXISTS analytics_quality_monthly (
    facility_id INTEGER NOT NULL REFERENCES master_facility(facility_id),
    quality_category_id INTEGER NOT NULL REFERENCES master_quality_category(quality_category_id),
    month_id TEXT NOT NULL REFERENCES master_calendar(month_id),
    inspections_completed INTEGER NOT NULL DEFAULT 0 CHECK (inspections_completed >= 0),
    issues_identified INTEGER NOT NULL DEFAULT 0 CHECK (issues_identified >= 0),
    critical_issues INTEGER NOT NULL DEFAULT 0 CHECK (critical_issues >= 0),
    issues_resolved INTEGER NOT NULL DEFAULT 0 CHECK (issues_resolved >= 0),
    adverse_incident_count INTEGER NOT NULL DEFAULT 0 CHECK (adverse_incident_count >= 0),
    complaint_count INTEGER NOT NULL DEFAULT 0 CHECK (complaint_count >= 0),
    complaints_resolved INTEGER NOT NULL DEFAULT 0 CHECK (complaints_resolved >= 0),
    average_resolution_days REAL CHECK (average_resolution_days IS NULL OR average_resolution_days >= 0),
    compliance_percentage REAL CHECK (compliance_percentage IS NULL OR compliance_percentage BETWEEN 0 AND 100),
    quality_score REAL CHECK (quality_score IS NULL OR quality_score BETWEEN 0 AND 100),
    accreditation_status TEXT,
    source_system_id INTEGER NOT NULL REFERENCES master_source_system(source_system_id),
    source_version TEXT NOT NULL,
    loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (facility_id, quality_category_id, month_id)
);

CREATE TABLE IF NOT EXISTS analytics_audit_issue (
    audit_issue_id INTEGER PRIMARY KEY,
    organisation_id INTEGER REFERENCES master_organisation(organisation_id),
    facility_id INTEGER REFERENCES master_facility(facility_id),
    audit_type TEXT NOT NULL,
    issue_category TEXT NOT NULL,
    issue_date TEXT NOT NULL,
    financial_value REAL CHECK (financial_value IS NULL OR financial_value >= 0),
    severity TEXT NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    responsible_organisation_id INTEGER NOT NULL REFERENCES master_organisation(organisation_id),
    resolution_due_date TEXT,
    resolution_status TEXT NOT NULL CHECK (resolution_status IN ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'ACCEPTED_RISK')),
    resolved_date TEXT,
    source_system_id INTEGER NOT NULL REFERENCES master_source_system(source_system_id),
    source_version TEXT NOT NULL,
    loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (organisation_id IS NOT NULL OR facility_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS analytics_project_monthly (
    project_id INTEGER NOT NULL REFERENCES master_project(project_id),
    month_id TEXT NOT NULL REFERENCES master_calendar(month_id),
    approved_cost REAL NOT NULL DEFAULT 0 CHECK (approved_cost >= 0),
    revised_cost REAL NOT NULL DEFAULT 0 CHECK (revised_cost >= 0),
    amount_released REAL NOT NULL DEFAULT 0 CHECK (amount_released >= 0),
    amount_spent REAL NOT NULL DEFAULT 0 CHECK (amount_spent >= 0),
    outstanding_liability REAL NOT NULL DEFAULT 0 CHECK (outstanding_liability >= 0),
    planned_progress_percentage REAL CHECK (planned_progress_percentage IS NULL OR planned_progress_percentage BETWEEN 0 AND 100),
    actual_progress_percentage REAL CHECK (actual_progress_percentage IS NULL OR actual_progress_percentage BETWEEN 0 AND 100),
    expected_completion_date TEXT,
    delay_days INTEGER NOT NULL DEFAULT 0 CHECK (delay_days >= 0),
    contractor_id INTEGER REFERENCES master_supplier(supplier_id),
    project_status TEXT NOT NULL CHECK (project_status IN ('PLANNED', 'IN_PROGRESS', 'ON_HOLD', 'COMPLETED', 'CANCELLED')),
    risk_level TEXT NOT NULL CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    source_system_id INTEGER NOT NULL REFERENCES master_source_system(source_system_id),
    source_version TEXT NOT NULL,
    loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, month_id)
);

CREATE TABLE IF NOT EXISTS analytics_data_quality_monthly (
    source_system_id INTEGER NOT NULL REFERENCES master_source_system(source_system_id),
    organisation_id INTEGER NOT NULL REFERENCES master_organisation(organisation_id),
    month_id TEXT NOT NULL REFERENCES master_calendar(month_id),
    records_expected INTEGER NOT NULL DEFAULT 0 CHECK (records_expected >= 0),
    records_received INTEGER NOT NULL DEFAULT 0 CHECK (records_received >= 0),
    records_valid INTEGER NOT NULL DEFAULT 0 CHECK (records_valid >= 0),
    records_rejected INTEGER NOT NULL DEFAULT 0 CHECK (records_rejected >= 0),
    missing_field_percentage REAL CHECK (missing_field_percentage IS NULL OR missing_field_percentage BETWEEN 0 AND 100),
    duplicate_percentage REAL CHECK (duplicate_percentage IS NULL OR duplicate_percentage BETWEEN 0 AND 100),
    late_submission_percentage REAL CHECK (late_submission_percentage IS NULL OR late_submission_percentage BETWEEN 0 AND 100),
    validation_failure_percentage REAL CHECK (validation_failure_percentage IS NULL OR validation_failure_percentage BETWEEN 0 AND 100),
    data_freshness_days REAL CHECK (data_freshness_days IS NULL OR data_freshness_days >= 0),
    overall_data_quality_score REAL CHECK (overall_data_quality_score IS NULL OR overall_data_quality_score BETWEEN 0 AND 100),
    source_version TEXT NOT NULL,
    loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_system_id, organisation_id, month_id)
);

-- Finance facts -------------------------------------------------------------

CREATE TABLE IF NOT EXISTS finance_budget_monthly (
    organisation_id INTEGER NOT NULL REFERENCES master_organisation(organisation_id),
    facility_id INTEGER REFERENCES master_facility(facility_id),
    budget_head_id INTEGER NOT NULL REFERENCES master_budget_head(budget_head_id),
    month_id TEXT NOT NULL REFERENCES master_calendar(month_id),
    original_budget REAL NOT NULL DEFAULT 0 CHECK (original_budget >= 0),
    revised_budget REAL NOT NULL DEFAULT 0 CHECK (revised_budget >= 0),
    funds_released REAL NOT NULL DEFAULT 0 CHECK (funds_released >= 0),
    funds_available REAL NOT NULL DEFAULT 0 CHECK (funds_available >= 0),
    committed_expenditure REAL NOT NULL DEFAULT 0 CHECK (committed_expenditure >= 0),
    actual_expenditure REAL NOT NULL DEFAULT 0 CHECK (actual_expenditure >= 0),
    unpaid_liabilities REAL NOT NULL DEFAULT 0 CHECK (unpaid_liabilities >= 0),
    funds_surrendered REAL NOT NULL DEFAULT 0 CHECK (funds_surrendered >= 0),
    release_delay_days REAL CHECK (release_delay_days IS NULL OR release_delay_days >= 0),
    payment_delay_days REAL CHECK (payment_delay_days IS NULL OR payment_delay_days >= 0),
    source_system_id INTEGER NOT NULL REFERENCES master_source_system(source_system_id),
    source_version TEXT NOT NULL,
    loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (organisation_id, facility_id, budget_head_id, month_id)
);

CREATE TABLE IF NOT EXISTS finance_expenditure_monthly (
    facility_id INTEGER NOT NULL REFERENCES master_facility(facility_id),
    cost_category_id INTEGER NOT NULL REFERENCES master_cost_category(cost_category_id),
    month_id TEXT NOT NULL REFERENCES master_calendar(month_id),
    budget_amount REAL NOT NULL DEFAULT 0 CHECK (budget_amount >= 0),
    committed_amount REAL NOT NULL DEFAULT 0 CHECK (committed_amount >= 0),
    expenditure_amount REAL NOT NULL DEFAULT 0 CHECK (expenditure_amount >= 0),
    outstanding_amount REAL NOT NULL DEFAULT 0 CHECK (outstanding_amount >= 0),
    previous_year_expenditure REAL NOT NULL DEFAULT 0 CHECK (previous_year_expenditure >= 0),
    source_system_id INTEGER NOT NULL REFERENCES master_source_system(source_system_id),
    source_version TEXT NOT NULL,
    loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (facility_id, cost_category_id, month_id)
);

CREATE TABLE IF NOT EXISTS finance_liability_monthly (
    organisation_id INTEGER NOT NULL REFERENCES master_organisation(organisation_id),
    facility_id INTEGER REFERENCES master_facility(facility_id),
    cost_category_id INTEGER NOT NULL REFERENCES master_cost_category(cost_category_id),
    month_id TEXT NOT NULL REFERENCES master_calendar(month_id),
    opening_liability REAL NOT NULL DEFAULT 0 CHECK (opening_liability >= 0),
    liability_incurred REAL NOT NULL DEFAULT 0 CHECK (liability_incurred >= 0),
    liability_paid REAL NOT NULL DEFAULT 0 CHECK (liability_paid >= 0),
    closing_liability REAL NOT NULL DEFAULT 0 CHECK (closing_liability >= 0),
    overdue_liability REAL NOT NULL DEFAULT 0 CHECK (overdue_liability >= 0),
    source_system_id INTEGER NOT NULL REFERENCES master_source_system(source_system_id),
    source_version TEXT NOT NULL,
    loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (organisation_id, facility_id, cost_category_id, month_id)
);

-- SQLite permits NULL inside a composite rowid-table primary key. These
-- expression indexes make the optional facility scope deterministic by
-- treating a ministry/organisation-wide fact as facility scope -1.
CREATE UNIQUE INDEX IF NOT EXISTS uq_procurement_monthly_grain
ON analytics_procurement_monthly (
    procuring_organisation_id,
    ifnull(facility_id, -1),
    supplier_id,
    procurement_category_id,
    month_id
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_budget_monthly_grain
ON finance_budget_monthly (
    organisation_id,
    ifnull(facility_id, -1),
    budget_head_id,
    month_id
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_liability_monthly_grain
ON finance_liability_monthly (
    organisation_id,
    ifnull(facility_id, -1),
    cost_category_id,
    month_id
);

CREATE INDEX IF NOT EXISTS idx_master_facility_district
ON master_facility (district_id, facility_type_id, operational_status);

CREATE INDEX IF NOT EXISTS idx_facility_summary_month
ON analytics_facility_monthly_summary (month_id, facility_id);

CREATE INDEX IF NOT EXISTS idx_medicine_month
ON analytics_medicine_monthly (month_id, facility_id);

CREATE INDEX IF NOT EXISTS idx_equipment_month
ON analytics_equipment_monthly (month_id, equipment_category_id, facility_id);

CREATE INDEX IF NOT EXISTS idx_staffing_month
ON analytics_staffing_monthly (month_id, staff_category_id, facility_id);

CREATE INDEX IF NOT EXISTS idx_service_month
ON analytics_service_monthly (month_id, service_category_id, demographic_group_id, facility_id);

CREATE INDEX IF NOT EXISTS idx_programme_month
ON analytics_programme_monthly (month_id, programme_id, district_id, demographic_group_id);

CREATE INDEX IF NOT EXISTS idx_scheme_month
ON analytics_scheme_monthly (month_id, scheme_id, district_id, demographic_group_id);

CREATE INDEX IF NOT EXISTS idx_data_quality_month
ON analytics_data_quality_monthly (month_id, overall_data_quality_score);

-- Restricted tokenized identity layer. No direct identifiers are represented
-- in the normal analytical or graph layers.

CREATE TABLE IF NOT EXISTS restricted_household (
    household_token TEXT PRIMARY KEY,
    district_id INTEGER NOT NULL REFERENCES master_geographic_area(geographic_area_id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    retention_until TEXT NOT NULL,
    tokenization_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS restricted_beneficiary (
    beneficiary_token TEXT PRIMARY KEY,
    household_token TEXT REFERENCES restricted_household(household_token),
    district_id INTEGER NOT NULL REFERENCES master_geographic_area(geographic_area_id),
    demographic_group_id INTEGER REFERENCES master_demographic_group(demographic_group_id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    retention_until TEXT NOT NULL,
    tokenization_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS restricted_scheme_enrollment (
    beneficiary_token TEXT NOT NULL REFERENCES restricted_beneficiary(beneficiary_token),
    scheme_id INTEGER NOT NULL REFERENCES master_scheme(scheme_id),
    enrolled_from TEXT NOT NULL,
    enrolled_to TEXT,
    eligibility_status TEXT NOT NULL,
    source_system_id INTEGER NOT NULL REFERENCES master_source_system(source_system_id),
    PRIMARY KEY (beneficiary_token, scheme_id, enrolled_from)
);

CREATE TABLE IF NOT EXISTS restricted_claim_identity_link (
    claim_token TEXT PRIMARY KEY,
    beneficiary_token TEXT NOT NULL REFERENCES restricted_beneficiary(beneficiary_token),
    scheme_id INTEGER NOT NULL REFERENCES master_scheme(scheme_id),
    facility_id INTEGER NOT NULL REFERENCES master_facility(facility_id),
    service_month TEXT NOT NULL,
    source_system_id INTEGER NOT NULL REFERENCES master_source_system(source_system_id)
);

CREATE TABLE IF NOT EXISTS restricted_fraud_signal (
    fraud_signal_id INTEGER PRIMARY KEY,
    beneficiary_token TEXT REFERENCES restricted_beneficiary(beneficiary_token),
    household_token TEXT REFERENCES restricted_household(household_token),
    claim_token TEXT REFERENCES restricted_claim_identity_link(claim_token),
    signal_type TEXT NOT NULL,
    risk_score REAL NOT NULL CHECK (risk_score BETWEEN 0 AND 100),
    review_status TEXT NOT NULL CHECK (review_status IN ('NEEDS_REVIEW', 'VERIFIED', 'DISMISSED')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (beneficiary_token IS NOT NULL OR household_token IS NOT NULL OR claim_token IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS restricted_investigation (
    investigation_id INTEGER PRIMARY KEY,
    fraud_signal_id INTEGER NOT NULL REFERENCES restricted_fraud_signal(fraud_signal_id),
    opened_at TEXT NOT NULL,
    closed_at TEXT,
    investigation_status TEXT NOT NULL CHECK (investigation_status IN ('OPEN', 'IN_PROGRESS', 'SUBSTANTIATED', 'UNSUBSTANTIATED', 'REFERRED')),
    assigned_role TEXT NOT NULL,
    outcome_code TEXT,
    CHECK (closed_at IS NULL OR closed_at >= opened_at)
);

-- Semantic governance registry ---------------------------------------------

CREATE TABLE IF NOT EXISTS semantic_metric_definition (
    metric_id INTEGER PRIMARY KEY,
    metric_code TEXT NOT NULL UNIQUE,
    metric_name TEXT NOT NULL,
    dataset_name TEXT NOT NULL,
    expression TEXT NOT NULL,
    aggregation TEXT NOT NULL,
    unit TEXT NOT NULL,
    owner_organisation_id INTEGER NOT NULL REFERENCES master_organisation(organisation_id),
    privacy_classification TEXT NOT NULL CHECK (privacy_classification IN ('PUBLIC', 'INTERNAL', 'RESTRICTED')),
    minimum_data_quality_score REAL NOT NULL DEFAULT 0 CHECK (minimum_data_quality_score BETWEEN 0 AND 100),
    definition_version TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS semantic_dimension_definition (
    dimension_id INTEGER PRIMARY KEY,
    dimension_code TEXT NOT NULL UNIQUE,
    dimension_name TEXT NOT NULL,
    source_table TEXT NOT NULL,
    key_column TEXT NOT NULL,
    label_column TEXT NOT NULL,
    privacy_classification TEXT NOT NULL CHECK (privacy_classification IN ('PUBLIC', 'INTERNAL', 'RESTRICTED')),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS semantic_capability (
    capability_id INTEGER PRIMARY KEY,
    capability_code TEXT NOT NULL UNIQUE,
    capability_name TEXT NOT NULL,
    purpose TEXT NOT NULL,
    output_grain TEXT NOT NULL,
    privacy_classification TEXT NOT NULL CHECK (privacy_classification IN ('PUBLIC', 'INTERNAL', 'RESTRICTED')),
    minimum_data_quality_score REAL NOT NULL DEFAULT 0 CHECK (minimum_data_quality_score BETWEEN 0 AND 100),
    known_limitations TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS semantic_capability_input (
    capability_id INTEGER NOT NULL REFERENCES semantic_capability(capability_id),
    input_type TEXT NOT NULL CHECK (input_type IN ('DATASET', 'METRIC', 'DIMENSION', 'FILTER')),
    input_name TEXT NOT NULL,
    required INTEGER NOT NULL DEFAULT 1 CHECK (required IN (0, 1)),
    PRIMARY KEY (capability_id, input_type, input_name)
);

-- Detailed joins remain allow-list based. Category-grain datasets are omitted
-- unless the compiler can preserve or pre-aggregate every added dimension;
-- district-grain programme/scheme facts are not facility-grain joins.
-- Department-wide cross-domain work uses the separately governed Department x
-- Month mart, whose source domains are pre-aggregated before combination.
CREATE TABLE IF NOT EXISTS semantic_allowed_join (
    left_dataset TEXT NOT NULL,
    right_dataset TEXT NOT NULL,
    left_key TEXT NOT NULL,
    right_key TEXT NOT NULL,
    cardinality TEXT NOT NULL,
    approval_status TEXT NOT NULL CHECK (approval_status IN ('APPROVED', 'DEPRECATED', 'BLOCKED')),
    PRIMARY KEY (left_dataset, right_dataset, left_key, right_key)
);

CREATE TABLE IF NOT EXISTS semantic_quality_rule (
    quality_rule_id INTEGER PRIMARY KEY,
    rule_code TEXT NOT NULL UNIQUE,
    dataset_name TEXT NOT NULL,
    rule_expression TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('INFO', 'WARNING', 'ERROR', 'BLOCKING')),
    failure_action TEXT NOT NULL CHECK (failure_action IN ('FLAG', 'QUARANTINE', 'REJECT', 'STOP_ANALYSIS')),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS semantic_access_policy (
    access_policy_id INTEGER PRIMARY KEY,
    policy_code TEXT NOT NULL UNIQUE,
    resource_type TEXT NOT NULL CHECK (resource_type IN ('DATASET', 'METRIC', 'CAPABILITY')),
    resource_name TEXT NOT NULL,
    permitted_role TEXT NOT NULL,
    row_filter_expression TEXT,
    purpose_limitation TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

-- permitted_role values are external IAM role identifiers. This analytical
-- database deliberately does not duplicate the authoritative role directory.

-- Governed analytical views expose stored components and calculate rates in a
-- single semantic location, avoiding duplicated percentages in fact tables.

CREATE VIEW IF NOT EXISTS analytics_health_facility_monthly AS
SELECT f.facility_id,
       f.facility_code,
       f.facility_name,
       ft.facility_type_name,
       district.area_name AS district_name,
       s.month_id,
       s.outpatient_visits,
       s.inpatient_admissions,
       s.emergency_visits,
       s.surgeries_completed,
       s.deliveries_completed,
       s.diagnostic_tests_completed,
       s.operational_beds,
       s.occupied_bed_days,
       s.available_bed_days,
       CASE WHEN s.available_bed_days = 0 THEN NULL
            ELSE 100.0 * s.occupied_bed_days / s.available_bed_days END AS bed_occupancy_percentage,
       s.total_staff_required,
       s.total_staff_available,
       CASE WHEN s.total_staff_required = 0 THEN NULL
            ELSE 100.0 * s.total_staff_available / s.total_staff_required END AS staff_sufficiency_percentage,
       s.total_budget_available,
       s.total_expenditure,
       CASE WHEN s.total_budget_available = 0 THEN NULL
            ELSE 100.0 * s.total_expenditure / s.total_budget_available END AS budget_utilisation_percentage,
       s.average_waiting_minutes,
       s.patient_grievance_count,
       s.source_version
FROM analytics_facility_monthly_summary AS s
JOIN master_facility AS f ON f.facility_id = s.facility_id
JOIN master_facility_type AS ft ON ft.facility_type_id = f.facility_type_id
JOIN master_geographic_area AS district ON district.geographic_area_id = f.district_id;

CREATE VIEW IF NOT EXISTS analytics_health_medicine_monthly AS
SELECT f.facility_id,
       f.facility_name,
       district.area_name AS district_name,
       m.month_id,
       m.available_stock_value,
       m.estimated_required_stock_value,
       CASE WHEN m.estimated_required_stock_value = 0 THEN NULL
            ELSE 100.0 * m.available_stock_value / m.estimated_required_stock_value END AS medicine_sufficiency_percentage,
       m.medicine_consumed_value,
       m.expired_medicine_value,
       CASE WHEN m.medicine_received_value = 0 THEN NULL
            ELSE 100.0 * m.expired_medicine_value / m.medicine_received_value END AS expiry_loss_percentage,
       m.stockout_days,
       m.critical_stockout_incidents,
       m.average_supply_delay_days,
       m.emergency_local_purchase_cost,
       m.source_version
FROM analytics_medicine_monthly AS m
JOIN master_facility AS f ON f.facility_id = m.facility_id
JOIN master_geographic_area AS district ON district.geographic_area_id = f.district_id;

CREATE VIEW IF NOT EXISTS analytics_health_equipment_monthly AS
SELECT f.facility_id,
       f.facility_name,
       district.area_name AS district_name,
       category.category_name AS equipment_category,
       category.criticality,
       e.month_id,
       e.equipment_required_count,
       e.equipment_available_count,
       e.equipment_functional_count,
       CASE WHEN e.equipment_required_count = 0 THEN NULL
            ELSE 100.0 * e.equipment_available_count / e.equipment_required_count END AS equipment_sufficiency_percentage,
       CASE WHEN e.equipment_available_count = 0 THEN NULL
            ELSE 100.0 * e.equipment_functional_count / e.equipment_available_count END AS equipment_functionality_percentage,
       e.total_downtime_hours,
       e.equipment_maintenance_cost,
       CASE WHEN e.equipment_procurement_value = 0 THEN NULL
            ELSE 100.0 * e.equipment_maintenance_cost / e.equipment_procurement_value END AS maintenance_cost_ratio_percentage,
       e.source_version
FROM analytics_equipment_monthly AS e
JOIN master_facility AS f ON f.facility_id = e.facility_id
JOIN master_geographic_area AS district ON district.geographic_area_id = f.district_id
JOIN master_equipment_category AS category
  ON category.equipment_category_id = e.equipment_category_id;

CREATE VIEW IF NOT EXISTS analytics_health_staffing_monthly AS
SELECT f.facility_id,
       f.facility_name,
       district.area_name AS district_name,
       category.category_name AS staff_category,
       s.month_id,
       s.required_posts,
       s.sanctioned_posts,
       s.filled_posts,
       s.staff_actually_available,
       CASE WHEN s.required_posts = 0 THEN NULL
            ELSE 100.0 * s.staff_actually_available / s.required_posts END AS staff_sufficiency_percentage,
       CASE WHEN s.sanctioned_posts = 0 THEN NULL
            ELSE 100.0 * (s.sanctioned_posts - s.filled_posts) / s.sanctioned_posts END AS vacancy_percentage,
       s.contract_staff_count,
       s.salary_cost,
       s.contract_staff_cost,
       s.overtime_cost,
       s.source_version
FROM analytics_staffing_monthly AS s
JOIN master_facility AS f ON f.facility_id = s.facility_id
JOIN master_geographic_area AS district ON district.geographic_area_id = f.district_id
JOIN master_staff_category AS category ON category.staff_category_id = s.staff_category_id;

CREATE VIEW IF NOT EXISTS analytics_health_service_monthly AS
SELECT f.facility_id,
       f.facility_name,
       district.area_name AS district_name,
       category.category_name AS service_category,
       demographic.group_name AS demographic_group,
       s.month_id,
       s.service_capacity,
       s.service_demand,
       s.services_delivered,
       CASE WHEN s.service_capacity = 0 THEN NULL
            ELSE 100.0 * s.services_delivered / s.service_capacity END AS service_utilisation_percentage,
       s.estimated_unmet_demand,
       s.referrals_out,
       s.average_waiting_days,
       s.service_availability_status,
       s.source_version
FROM analytics_service_monthly AS s
JOIN master_facility AS f ON f.facility_id = s.facility_id
JOIN master_geographic_area AS district ON district.geographic_area_id = f.district_id
JOIN master_service_category AS category ON category.service_category_id = s.service_category_id
JOIN master_demographic_group AS demographic
  ON demographic.demographic_group_id = s.demographic_group_id;

CREATE VIEW IF NOT EXISTS analytics_health_budget_monthly AS
SELECT b.organisation_id,
       organisation.organisation_name,
       b.facility_id,
       facility.facility_name,
       head.budget_head_name,
       b.month_id,
       b.revised_budget,
       b.funds_released,
       b.funds_available,
       b.committed_expenditure,
       b.actual_expenditure,
       b.unpaid_liabilities,
       CASE WHEN b.funds_available = 0 THEN NULL
            ELSE 100.0 * b.actual_expenditure / b.funds_available END AS budget_utilisation_percentage,
       b.release_delay_days,
       b.payment_delay_days,
       b.source_version
FROM finance_budget_monthly AS b
JOIN master_organisation AS organisation
  ON organisation.organisation_id = b.organisation_id
LEFT JOIN master_facility AS facility ON facility.facility_id = b.facility_id
JOIN master_budget_head AS head ON head.budget_head_id = b.budget_head_id;

CREATE VIEW IF NOT EXISTS analytics_health_programme_monthly AS
SELECT programme.programme_id,
       programme.programme_name,
       district.area_name AS district_name,
       demographic.group_name AS demographic_group,
       p.month_id,
       p.target_population,
       p.eligible_population,
       p.population_reached,
       CASE WHEN p.eligible_population = 0 THEN NULL
            ELSE 100.0 * p.population_reached / p.eligible_population END AS coverage_percentage,
       p.programme_budget,
       p.programme_expenditure,
       CASE WHEN p.population_reached = 0 THEN NULL
            ELSE p.programme_expenditure / p.population_reached END AS cost_per_person_reached,
       p.outcome_indicator_value,
       p.source_version
FROM analytics_programme_monthly AS p
JOIN master_programme AS programme ON programme.programme_id = p.programme_id
JOIN master_geographic_area AS district ON district.geographic_area_id = p.district_id
JOIN master_demographic_group AS demographic
  ON demographic.demographic_group_id = p.demographic_group_id;

CREATE VIEW IF NOT EXISTS analytics_health_scheme_monthly AS
SELECT scheme.scheme_id,
       scheme.scheme_name,
       district.area_name AS district_name,
       demographic.group_name AS demographic_group,
       s.month_id,
       s.eligible_individuals,
       s.enrolled_individuals,
       s.beneficiaries_served,
       CASE WHEN s.eligible_individuals = 0 THEN NULL
            ELSE 100.0 * s.enrolled_individuals / s.eligible_individuals END AS coverage_percentage,
       s.claims_submitted,
       s.claims_approved,
       s.claims_rejected,
       CASE WHEN s.claims_submitted = 0 THEN NULL
            ELSE 100.0 * s.claims_approved / s.claims_submitted END AS claim_approval_percentage,
       s.claim_amount_paid,
       s.average_claim_processing_days,
       s.fraud_signal_count,
       s.source_version
FROM analytics_scheme_monthly AS s
JOIN master_scheme AS scheme ON scheme.scheme_id = s.scheme_id
JOIN master_geographic_area AS district ON district.geographic_area_id = s.district_id
JOIN master_demographic_group AS demographic
  ON demographic.demographic_group_id = s.demographic_group_id;

CREATE VIEW IF NOT EXISTS analytics_health_data_quality_monthly AS
SELECT source.source_code,
       source.source_name,
       organisation.organisation_name,
       q.month_id,
       q.records_expected,
       q.records_received,
       q.records_valid,
       q.records_rejected,
       q.data_freshness_days,
       q.overall_data_quality_score,
       q.source_version
FROM analytics_data_quality_monthly AS q
JOIN master_source_system AS source ON source.source_system_id = q.source_system_id
JOIN master_organisation AS organisation
  ON organisation.organisation_id = q.organisation_id;

-- Department-wide cross-domain mart ----------------------------------------
--
-- Every source is aggregated independently to Department x Month before the
-- final joins. This is the only approved way to combine category-, facility-,
-- organisation-, programme-, scheme-, and daily-surveillance grains without
-- multiplying measures.

DROP VIEW IF EXISTS semantic_health_department_attribution_issue;
CREATE VIEW semantic_health_department_attribution_issue AS
WITH RECURSIVE
organisation_ancestry (
    organisation_id, ancestor_id, parent_organisation_id,
    ancestor_type, depth
) AS (
    SELECT organisation_id,
           organisation_id,
           parent_organisation_id,
           organisation_type,
           0
    FROM master_organisation
    UNION ALL
    SELECT ancestry.organisation_id,
           parent.organisation_id,
           parent.parent_organisation_id,
           parent.organisation_type,
           ancestry.depth + 1
    FROM organisation_ancestry AS ancestry
    JOIN master_organisation AS parent
      ON parent.organisation_id = ancestry.parent_organisation_id
    WHERE ancestry.depth < 20
),
resolved_organisation AS (
    SELECT DISTINCT organisation_id
    FROM organisation_ancestry
    WHERE ancestor_type = 'DEPARTMENT'
)
SELECT 'ORGANISATION' AS entity_type,
       organisation.organisation_id AS entity_id,
       organisation.organisation_name AS entity_name,
       'NO_DEPARTMENT_ANCESTOR' AS issue_code
FROM master_organisation AS organisation
LEFT JOIN resolved_organisation AS resolved
  ON resolved.organisation_id = organisation.organisation_id
WHERE resolved.organisation_id IS NULL
  AND organisation.organisation_type <> 'GOVERNMENT'
UNION ALL
SELECT 'FACILITY',
       facility.facility_id,
       facility.facility_name,
       'PARENT_ORGANISATION_HAS_NO_DEPARTMENT'
FROM master_facility AS facility
LEFT JOIN resolved_organisation AS resolved
  ON resolved.organisation_id = facility.parent_organisation_id
WHERE resolved.organisation_id IS NULL
UNION ALL
SELECT 'HOSPITAL',
       hospital.hospital_id,
       hospital.hospital_name,
       CASE
           WHEN hospital.master_facility_id IS NULL
           THEN 'MASTER_FACILITY_NOT_RECONCILED'
           ELSE 'MASTER_FACILITY_NOT_FOUND'
       END
FROM hospital
LEFT JOIN master_facility AS facility
  ON facility.facility_id = hospital.master_facility_id
WHERE hospital.master_facility_id IS NULL
   OR facility.facility_id IS NULL;

DROP VIEW IF EXISTS analytics_health_department_monthly;
CREATE VIEW analytics_health_department_monthly AS
WITH RECURSIVE
organisation_ancestry (
    organisation_id, ancestor_id, parent_organisation_id,
    ancestor_type, ancestor_name, depth
) AS (
    SELECT organisation_id,
           organisation_id,
           parent_organisation_id,
           organisation_type,
           organisation_name,
           0
    FROM master_organisation
    UNION ALL
    SELECT ancestry.organisation_id,
           parent.organisation_id,
           parent.parent_organisation_id,
           parent.organisation_type,
           parent.organisation_name,
           ancestry.depth + 1
    FROM organisation_ancestry AS ancestry
    JOIN master_organisation AS parent
      ON parent.organisation_id = ancestry.parent_organisation_id
    WHERE ancestry.depth < 20
),
resolved_department_map AS (
    SELECT ancestry.organisation_id,
           ancestry.ancestor_id AS department_id,
           ancestry.ancestor_name AS department_name
    FROM organisation_ancestry AS ancestry
    WHERE ancestry.ancestor_type = 'DEPARTMENT'
      AND ancestry.depth = (
          SELECT MIN(candidate.depth)
          FROM organisation_ancestry AS candidate
          WHERE candidate.organisation_id = ancestry.organisation_id
            AND candidate.ancestor_type = 'DEPARTMENT'
      )
),
department_map AS (
    SELECT organisation.organisation_id,
           COALESCE(resolved.department_id, -1) AS department_id,
           COALESCE(resolved.department_name, 'UNASSIGNED') AS department_name
    FROM master_organisation AS organisation
    LEFT JOIN resolved_department_map AS resolved
      ON resolved.organisation_id = organisation.organisation_id
),
facility_department AS (
    SELECT facility.facility_id,
           department.department_id,
           department.department_name
    FROM master_facility AS facility
    JOIN department_map AS department
      ON department.organisation_id = facility.parent_organisation_id
),
department_month AS (
    SELECT organisation.organisation_id AS department_id,
           organisation.organisation_name AS department_name,
           calendar.month_id
    FROM master_organisation AS organisation
    CROSS JOIN master_calendar AS calendar
    WHERE organisation.organisation_type = 'DEPARTMENT'
      AND organisation.active = 1
    UNION ALL
    SELECT -1,
           'UNASSIGNED',
           calendar.month_id
    FROM master_calendar AS calendar
),
facility_activity AS (
    SELECT department.department_id,
           fact.month_id,
           COUNT(DISTINCT fact.facility_id) AS reporting_facility_count,
           SUM(fact.outpatient_visits) AS outpatient_visits,
           SUM(fact.inpatient_admissions) AS inpatient_admissions,
           SUM(fact.emergency_visits) AS emergency_visits,
           SUM(fact.occupied_bed_days) AS occupied_bed_days,
           SUM(fact.available_bed_days) AS available_bed_days
    FROM analytics_facility_monthly_summary AS fact
    JOIN facility_department AS department
      ON department.facility_id = fact.facility_id
    GROUP BY department.department_id, fact.month_id
),
medicine AS (
    SELECT department.department_id,
           fact.month_id,
           SUM(fact.available_stock_value) AS available_stock_value,
           SUM(fact.estimated_required_stock_value) AS required_stock_value,
           SUM(fact.critical_stockout_incidents) AS critical_stockout_incidents
    FROM analytics_medicine_monthly AS fact
    JOIN facility_department AS department
      ON department.facility_id = fact.facility_id
    GROUP BY department.department_id, fact.month_id
),
equipment AS (
    SELECT department.department_id,
           fact.month_id,
           SUM(fact.equipment_available_count) AS equipment_available_count,
           SUM(fact.equipment_functional_count) AS equipment_functional_count,
           SUM(fact.total_downtime_hours) AS equipment_downtime_hours
    FROM analytics_equipment_monthly AS fact
    JOIN facility_department AS department
      ON department.facility_id = fact.facility_id
    GROUP BY department.department_id, fact.month_id
),
staffing AS (
    SELECT department.department_id,
           fact.month_id,
           SUM(fact.required_posts) AS required_posts,
           SUM(fact.staff_actually_available) AS staff_available,
           SUM(fact.salary_cost + fact.contract_staff_cost + fact.overtime_cost)
               AS workforce_cost
    FROM analytics_staffing_monthly AS fact
    JOIN facility_department AS department
      ON department.facility_id = fact.facility_id
    GROUP BY department.department_id, fact.month_id
),
service AS (
    SELECT department.department_id,
           fact.month_id,
           SUM(fact.service_demand) AS service_demand,
           SUM(fact.services_delivered) AS services_delivered,
           SUM(fact.estimated_unmet_demand) AS unmet_service_demand
    FROM analytics_service_monthly AS fact
    JOIN facility_department AS department
      ON department.facility_id = fact.facility_id
    GROUP BY department.department_id, fact.month_id
),
infrastructure AS (
    SELECT department.department_id,
           fact.month_id,
           SUM(fact.critical_issues) AS infrastructure_critical_issues,
           SUM(fact.downtime_hours) AS infrastructure_downtime_hours,
           SUM(fact.maintenance_cost + fact.repair_cost + fact.capital_expenditure)
               AS infrastructure_cost
    FROM analytics_infrastructure_monthly AS fact
    JOIN facility_department AS department
      ON department.facility_id = fact.facility_id
    GROUP BY department.department_id, fact.month_id
),
vehicle AS (
    SELECT department.department_id,
           fact.month_id,
           SUM(fact.available_vehicle_count) AS available_vehicle_count,
           SUM(fact.functional_vehicle_count) AS functional_vehicle_count,
           SUM(fact.emergency_trip_count) AS emergency_trip_count,
           SUM(fact.patients_transported) AS patients_transported
    FROM analytics_vehicle_monthly AS fact
    JOIN facility_department AS department
      ON department.facility_id = fact.facility_id
    GROUP BY department.department_id, fact.month_id
),
procurement AS (
    SELECT department.department_id,
           fact.month_id,
           SUM(fact.requested_value) AS procurement_requested_value,
           SUM(fact.received_value) AS procurement_received_value,
           SUM(fact.paid_value) AS procurement_paid_value
    FROM analytics_procurement_monthly AS fact
    JOIN department_map AS department
      ON department.organisation_id = fact.procuring_organisation_id
    GROUP BY department.department_id, fact.month_id
),
budget AS (
    SELECT department.department_id,
           fact.month_id,
           SUM(fact.funds_available) AS funds_available,
           SUM(fact.actual_expenditure) AS budget_actual_expenditure
    FROM finance_budget_monthly AS fact
    JOIN department_map AS department
      ON department.organisation_id = fact.organisation_id
    GROUP BY department.department_id, fact.month_id
),
programme AS (
    SELECT department.department_id,
           fact.month_id,
           SUM(fact.eligible_population) AS programme_eligible_population,
           SUM(fact.population_reached) AS programme_population_reached,
           SUM(fact.programme_expenditure) AS programme_expenditure
    FROM analytics_programme_monthly AS fact
    JOIN master_programme AS programme
      ON programme.programme_id = fact.programme_id
    JOIN department_map AS department
      ON department.organisation_id = programme.administering_organisation_id
    GROUP BY department.department_id, fact.month_id
),
scheme AS (
    SELECT department.department_id,
           fact.month_id,
           SUM(fact.eligible_individuals) AS scheme_eligible_individuals,
           SUM(fact.enrolled_individuals) AS scheme_enrolled_individuals,
           SUM(fact.beneficiaries_served) AS scheme_beneficiaries_served,
           SUM(fact.claims_submitted) AS claims_submitted,
           SUM(fact.claims_approved) AS claims_approved,
           SUM(fact.claim_amount_paid) AS claim_amount_paid
    FROM analytics_scheme_monthly AS fact
    JOIN master_scheme AS scheme
      ON scheme.scheme_id = fact.scheme_id
    JOIN department_map AS department
      ON department.organisation_id = scheme.administering_organisation_id
    GROUP BY department.department_id, fact.month_id
),
quality AS (
    SELECT department.department_id,
           fact.month_id,
           AVG(fact.quality_score) AS average_quality_score,
           SUM(fact.critical_issues) AS quality_critical_issues
    FROM analytics_quality_monthly AS fact
    JOIN facility_department AS department
      ON department.facility_id = fact.facility_id
    GROUP BY department.department_id, fact.month_id
),
project AS (
    SELECT department.department_id,
           fact.month_id,
           SUM(fact.amount_spent) AS project_amount_spent,
           SUM(fact.outstanding_liability) AS project_outstanding_liability
    FROM analytics_project_monthly AS fact
    JOIN master_project AS project ON project.project_id = fact.project_id
    JOIN department_map AS department
      ON department.organisation_id = project.responsible_organisation_id
    GROUP BY department.department_id, fact.month_id
),
finance_expenditure AS (
    SELECT department.department_id,
           fact.month_id,
           SUM(fact.expenditure_amount) AS classified_expenditure
    FROM finance_expenditure_monthly AS fact
    JOIN facility_department AS department
      ON department.facility_id = fact.facility_id
    GROUP BY department.department_id, fact.month_id
),
liability AS (
    SELECT department.department_id,
           fact.month_id,
           SUM(fact.closing_liability) AS closing_liability,
           SUM(fact.overdue_liability) AS overdue_liability
    FROM finance_liability_monthly AS fact
    JOIN department_map AS department
      ON department.organisation_id = fact.organisation_id
    GROUP BY department.department_id, fact.month_id
),
data_quality AS (
    SELECT department.department_id,
           fact.month_id,
           AVG(fact.overall_data_quality_score) AS average_data_quality_score
    FROM analytics_data_quality_monthly AS fact
    JOIN department_map AS department
      ON department.organisation_id = fact.organisation_id
    GROUP BY department.department_id, fact.month_id
),
audit AS (
    SELECT department.department_id,
           substr(fact.issue_date, 1, 7) || '-01' AS month_id,
           SUM(CASE WHEN fact.resolution_status IN ('OPEN', 'IN_PROGRESS')
                    THEN 1 ELSE 0 END) AS open_audit_issue_count
    FROM analytics_audit_issue AS fact
    JOIN department_map AS department
      ON department.organisation_id = fact.responsible_organisation_id
    GROUP BY department.department_id, substr(fact.issue_date, 1, 7)
),
surveillance AS (
    SELECT COALESCE(department.department_id, -1) AS department_id,
           substr(signal.reporting_date, 1, 7) || '-01' AS month_id,
           COUNT(*) AS surveillance_signal_count
    FROM health_surveillance_signal AS signal
    LEFT JOIN hospital
      ON signal.geography_type = 'HOSPITAL'
     AND hospital.hospital_id = signal.geography_id
    LEFT JOIN facility_department AS department
      ON department.facility_id = hospital.master_facility_id
    GROUP BY COALESCE(department.department_id, -1),
             substr(signal.reporting_date, 1, 7)
)
SELECT month.department_id,
       month.department_name,
       CASE WHEN month.department_id = -1
            THEN 'UNASSIGNED' ELSE 'ASSIGNED' END AS attribution_status,
       month.month_id,
       COALESCE(activity.reporting_facility_count, 0) AS reporting_facility_count,
       COALESCE(activity.outpatient_visits, 0) AS outpatient_visits,
       COALESCE(activity.inpatient_admissions, 0) AS inpatient_admissions,
       COALESCE(activity.emergency_visits, 0) AS emergency_visits,
       CASE WHEN COALESCE(activity.available_bed_days, 0) = 0 THEN NULL
            ELSE 100.0 * activity.occupied_bed_days / activity.available_bed_days
       END AS bed_occupancy_percentage,
       CASE WHEN COALESCE(medicine.required_stock_value, 0) = 0 THEN NULL
            ELSE 100.0 * medicine.available_stock_value / medicine.required_stock_value
       END AS medicine_sufficiency_percentage,
       COALESCE(medicine.critical_stockout_incidents, 0)
           AS critical_stockout_incidents,
       CASE WHEN COALESCE(equipment.equipment_available_count, 0) = 0 THEN NULL
            ELSE 100.0 * equipment.equipment_functional_count
                 / equipment.equipment_available_count
       END AS equipment_functionality_percentage,
       COALESCE(equipment.equipment_downtime_hours, 0)
           AS equipment_downtime_hours,
       CASE WHEN COALESCE(staffing.required_posts, 0) = 0 THEN NULL
            ELSE 100.0 * staffing.staff_available / staffing.required_posts
       END AS staffing_sufficiency_percentage,
       COALESCE(staffing.workforce_cost, 0) AS workforce_cost,
       COALESCE(service.service_demand, 0) AS service_demand,
       COALESCE(service.services_delivered, 0) AS services_delivered,
       COALESCE(service.unmet_service_demand, 0) AS unmet_service_demand,
       COALESCE(infrastructure.infrastructure_critical_issues, 0)
           AS infrastructure_critical_issues,
       COALESCE(infrastructure.infrastructure_downtime_hours, 0)
           AS infrastructure_downtime_hours,
       COALESCE(infrastructure.infrastructure_cost, 0) AS infrastructure_cost,
       CASE WHEN COALESCE(vehicle.available_vehicle_count, 0) = 0 THEN NULL
            ELSE 100.0 * vehicle.functional_vehicle_count
                 / vehicle.available_vehicle_count
       END AS vehicle_functionality_percentage,
       COALESCE(vehicle.emergency_trip_count, 0) AS emergency_trip_count,
       COALESCE(vehicle.patients_transported, 0) AS patients_transported,
       COALESCE(procurement.procurement_requested_value, 0)
           AS procurement_requested_value,
       COALESCE(procurement.procurement_received_value, 0)
           AS procurement_received_value,
       COALESCE(procurement.procurement_paid_value, 0)
           AS procurement_paid_value,
       COALESCE(budget.funds_available, 0) AS funds_available,
       COALESCE(budget.budget_actual_expenditure, 0) AS budget_actual_expenditure,
       CASE WHEN COALESCE(budget.funds_available, 0) = 0 THEN NULL
            ELSE 100.0 * budget.budget_actual_expenditure / budget.funds_available
       END AS budget_utilisation_percentage,
       COALESCE(programme.programme_population_reached, 0)
           AS programme_population_reached,
       COALESCE(programme.programme_expenditure, 0) AS programme_expenditure,
       CASE WHEN COALESCE(programme.programme_eligible_population, 0) = 0 THEN NULL
            ELSE 100.0 * programme.programme_population_reached
                 / programme.programme_eligible_population
       END AS programme_coverage_percentage,
       COALESCE(scheme.scheme_beneficiaries_served, 0)
           AS scheme_beneficiaries_served,
       COALESCE(scheme.claim_amount_paid, 0) AS claim_amount_paid,
       CASE WHEN COALESCE(scheme.scheme_eligible_individuals, 0) = 0 THEN NULL
            ELSE 100.0 * scheme.scheme_enrolled_individuals
                 / scheme.scheme_eligible_individuals
       END AS scheme_coverage_percentage,
       CASE WHEN COALESCE(scheme.claims_submitted, 0) = 0 THEN NULL
            ELSE 100.0 * scheme.claims_approved / scheme.claims_submitted
       END AS claim_approval_percentage,
       quality.average_quality_score,
       COALESCE(quality.quality_critical_issues, 0) AS quality_critical_issues,
       COALESCE(project.project_amount_spent, 0) AS project_amount_spent,
       COALESCE(project.project_outstanding_liability, 0)
           AS project_outstanding_liability,
       COALESCE(finance_expenditure.classified_expenditure, 0)
           AS classified_expenditure,
       COALESCE(liability.closing_liability, 0) AS closing_liability,
       COALESCE(liability.overdue_liability, 0) AS overdue_liability,
       data_quality.average_data_quality_score,
       COALESCE(audit.open_audit_issue_count, 0) AS open_audit_issue_count,
       COALESCE(surveillance.surveillance_signal_count, 0)
           AS surveillance_signal_count
FROM department_month AS month
LEFT JOIN facility_activity AS activity
  ON activity.department_id = month.department_id
 AND activity.month_id = month.month_id
LEFT JOIN medicine
  ON medicine.department_id = month.department_id
 AND medicine.month_id = month.month_id
LEFT JOIN equipment
  ON equipment.department_id = month.department_id
 AND equipment.month_id = month.month_id
LEFT JOIN staffing
  ON staffing.department_id = month.department_id
 AND staffing.month_id = month.month_id
LEFT JOIN service
  ON service.department_id = month.department_id
 AND service.month_id = month.month_id
LEFT JOIN infrastructure
  ON infrastructure.department_id = month.department_id
 AND infrastructure.month_id = month.month_id
LEFT JOIN vehicle
  ON vehicle.department_id = month.department_id
 AND vehicle.month_id = month.month_id
LEFT JOIN procurement
  ON procurement.department_id = month.department_id
 AND procurement.month_id = month.month_id
LEFT JOIN budget
  ON budget.department_id = month.department_id
 AND budget.month_id = month.month_id
LEFT JOIN programme
  ON programme.department_id = month.department_id
 AND programme.month_id = month.month_id
LEFT JOIN scheme
  ON scheme.department_id = month.department_id
 AND scheme.month_id = month.month_id
LEFT JOIN quality
  ON quality.department_id = month.department_id
 AND quality.month_id = month.month_id
LEFT JOIN project
  ON project.department_id = month.department_id
 AND project.month_id = month.month_id
LEFT JOIN finance_expenditure
  ON finance_expenditure.department_id = month.department_id
 AND finance_expenditure.month_id = month.month_id
LEFT JOIN liability
  ON liability.department_id = month.department_id
 AND liability.month_id = month.month_id
LEFT JOIN data_quality
  ON data_quality.department_id = month.department_id
 AND data_quality.month_id = month.month_id
LEFT JOIN audit
  ON audit.department_id = month.department_id
 AND audit.month_id = month.month_id
LEFT JOIN surveillance
  ON surveillance.department_id = month.department_id
 AND surveillance.month_id = month.month_id;
