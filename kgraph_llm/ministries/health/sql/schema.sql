CREATE TABLE IF NOT EXISTS district (
    district_id INTEGER PRIMARY KEY,
    district_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS hospital (
    hospital_id INTEGER PRIMARY KEY,
    hospital_name TEXT NOT NULL UNIQUE,
    district_id INTEGER NOT NULL REFERENCES district(district_id),
    master_facility_id INTEGER REFERENCES master_facility(facility_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_hospital_master_facility
ON hospital(master_facility_id)
WHERE master_facility_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS healthcare_facility_level (
    level_id INTEGER PRIMARY KEY,
    level_code TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    hierarchy_order INTEGER NOT NULL UNIQUE CHECK (hierarchy_order BETWEEN 1 AND 7),
    main_role TEXT NOT NULL,
    public_access_mode TEXT NOT NULL
        CHECK (public_access_mode IN ('direct', 'referral_or_emergency', 'specialty_referral_only')),
    disease_specific INTEGER NOT NULL DEFAULT 0 CHECK (disease_specific IN (0, 1))
);

CREATE TABLE IF NOT EXISTS healthcare_referral_route (
    from_level_id INTEGER NOT NULL REFERENCES healthcare_facility_level(level_id),
    to_level_id INTEGER NOT NULL REFERENCES healthcare_facility_level(level_id),
    route_type TEXT NOT NULL
        CHECK (route_type IN ('severity_escalation', 'disease_specific_referral')),
    referral_rule TEXT NOT NULL,
    PRIMARY KEY (from_level_id, to_level_id, route_type),
    CHECK (from_level_id <> to_level_id)
);

CREATE TABLE IF NOT EXISTS hospital_facility_classification (
    hospital_id INTEGER NOT NULL REFERENCES hospital(hospital_id),
    level_id INTEGER NOT NULL REFERENCES healthcare_facility_level(level_id),
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    source_version TEXT NOT NULL,
    PRIMARY KEY (hospital_id, effective_from),
    CHECK (effective_to IS NULL OR effective_to > effective_from)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_hospital_facility_classification_current
ON hospital_facility_classification(hospital_id)
WHERE effective_to IS NULL;

CREATE TABLE IF NOT EXISTS district_facility_distribution_profile (
    district_id INTEGER NOT NULL REFERENCES district(district_id),
    level_id INTEGER NOT NULL REFERENCES healthcare_facility_level(level_id),
    profile_type TEXT NOT NULL DEFAULT 'typical_medium_district',
    typical_min_count INTEGER,
    typical_max_count INTEGER,
    typical_count_label TEXT,
    example_min_count INTEGER NOT NULL CHECK (example_min_count >= 0),
    example_max_count INTEGER NOT NULL CHECK (example_max_count >= example_min_count),
    population_served TEXT NOT NULL,
    is_approximate INTEGER NOT NULL DEFAULT 1 CHECK (is_approximate IN (0, 1)),
    source_version TEXT NOT NULL,
    PRIMARY KEY (district_id, level_id, profile_type),
    CHECK (
        (typical_min_count IS NULL AND typical_max_count IS NULL AND typical_count_label IS NOT NULL)
        OR
        (typical_min_count IS NOT NULL AND typical_max_count >= typical_min_count)
    )
);

CREATE TABLE IF NOT EXISTS hospital_funding (
    hospital_id INTEGER NOT NULL REFERENCES hospital(hospital_id),
    fiscal_year INTEGER NOT NULL,
    funding_category TEXT NOT NULL,
    amount_lakh REAL NOT NULL CHECK (amount_lakh >= 0),
    source_version TEXT NOT NULL,
    PRIMARY KEY (hospital_id, fiscal_year, funding_category)
);

CREATE TABLE IF NOT EXISTS hospital_output (
    hospital_id INTEGER NOT NULL REFERENCES hospital(hospital_id),
    fiscal_year INTEGER NOT NULL,
    admissions INTEGER NOT NULL CHECK (admissions >= 0),
    outpatient_visits INTEGER NOT NULL CHECK (outpatient_visits >= 0),
    surgeries INTEGER NOT NULL CHECK (surgeries >= 0),
    source_version TEXT NOT NULL,
    PRIMARY KEY (hospital_id, fiscal_year)
);

CREATE TABLE IF NOT EXISTS syndrome_category (
    syndrome_code TEXT PRIMARY KEY,
    display_name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS hospital_daily_submission (
    hospital_id INTEGER NOT NULL REFERENCES hospital(hospital_id),
    reporting_date TEXT NOT NULL,
    submitted_at TEXT NOT NULL,
    submission_status TEXT NOT NULL
        CHECK (submission_status IN ('complete', 'partial', 'missing')),
    source_version TEXT NOT NULL,
    PRIMARY KEY (hospital_id, reporting_date)
);

CREATE TABLE IF NOT EXISTS hospital_admission_daily (
    hospital_id INTEGER NOT NULL REFERENCES hospital(hospital_id),
    patient_district_id INTEGER NOT NULL REFERENCES district(district_id),
    reporting_date TEXT NOT NULL,
    syndrome_code TEXT NOT NULL REFERENCES syndrome_category(syndrome_code),
    age_band TEXT NOT NULL,
    admissions INTEGER NOT NULL CHECK (admissions >= 0),
    source_version TEXT NOT NULL,
    PRIMARY KEY (
        hospital_id, patient_district_id, reporting_date, syndrome_code, age_band
    )
);

CREATE TABLE IF NOT EXISTS daily_surveillance_run (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    reporting_date TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    method_version TEXT NOT NULL,
    expected_hospitals INTEGER NOT NULL CHECK (expected_hospitals >= 0),
    complete_hospitals INTEGER NOT NULL CHECK (complete_hospitals >= 0),
    reporting_completeness REAL NOT NULL
        CHECK (reporting_completeness BETWEEN 0 AND 1),
    run_status TEXT NOT NULL
        CHECK (run_status IN ('RUNNING', 'COMPLETED', 'INCOMPLETE_DATA', 'FAILED')),
    signal_count INTEGER NOT NULL DEFAULT 0 CHECK (signal_count >= 0),
    config_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS health_surveillance_signal (
    signal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES daily_surveillance_run(run_id),
    reporting_date TEXT NOT NULL,
    geography_type TEXT NOT NULL
        CHECK (geography_type IN ('HOSPITAL', 'DISTRICT', 'STATE')),
    geography_id INTEGER NOT NULL,
    geography_name TEXT NOT NULL,
    syndrome_code TEXT NOT NULL REFERENCES syndrome_category(syndrome_code),
    observed_count INTEGER NOT NULL CHECK (observed_count >= 0),
    expected_count REAL NOT NULL CHECK (expected_count >= 0),
    baseline_stddev REAL NOT NULL CHECK (baseline_stddev >= 0),
    anomaly_score REAL NOT NULL,
    observed_expected_ratio REAL,
    contributing_hospitals INTEGER NOT NULL CHECK (contributing_hospitals >= 0),
    reporting_completeness REAL NOT NULL
        CHECK (reporting_completeness BETWEEN 0 AND 1),
    corroborated INTEGER NOT NULL CHECK (corroborated IN (0, 1)),
    signal_level TEXT NOT NULL CHECK (signal_level IN ('WATCH', 'HIGH')),
    review_status TEXT NOT NULL DEFAULT 'NEEDS_REVIEW'
        CHECK (review_status IN ('NEEDS_REVIEW', 'VERIFIED', 'DISMISSED')),
    method_version TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_id, geography_type, geography_id, syndrome_code)
);

CREATE TABLE IF NOT EXISTS hospital_equipment (
    equipment_id INTEGER PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES hospital(hospital_id),
    equipment_type TEXT NOT NULL,
    asset_code TEXT NOT NULL UNIQUE,
    operational_status TEXT NOT NULL
        CHECK (operational_status IN ('operational', 'maintenance', 'out_of_service')),
    commissioned_on TEXT NOT NULL,
    last_maintenance_on TEXT,
    downtime_hours_last_12m REAL NOT NULL CHECK (downtime_hours_last_12m >= 0),
    source_version TEXT NOT NULL
);

-- Recreate compatibility views so existing databases receive newly governed
-- bridge fields when Database.initialize() upgrades the source schema.
DROP VIEW IF EXISTS analytics_health_hospital_funding_year;
DROP VIEW IF EXISTS analytics_health_hospital_output_year;
DROP VIEW IF EXISTS analytics_health_admission_daily;
DROP VIEW IF EXISTS analytics_health_surveillance_signal;
DROP VIEW IF EXISTS analytics_health_hospital_equipment;
DROP VIEW IF EXISTS analytics_health_hospital_care_level;
DROP VIEW IF EXISTS analytics_health_facility_referral_route;
DROP VIEW IF EXISTS analytics_health_district_referral_pyramid;

CREATE VIEW analytics_health_hospital_funding_year AS
SELECT h.hospital_id,
       h.master_facility_id,
       h.hospital_name,
       d.district_name,
       f.fiscal_year,
       f.funding_category,
       f.amount_lakh AS operating_funding,
       f.source_version
FROM hospital_funding AS f
JOIN hospital AS h ON h.hospital_id = f.hospital_id
JOIN district AS d ON d.district_id = h.district_id
WHERE f.funding_category = 'operating';

CREATE VIEW analytics_health_hospital_output_year AS
SELECT h.hospital_id,
       h.master_facility_id,
       h.hospital_name,
       d.district_name,
       o.fiscal_year,
       o.admissions,
       o.outpatient_visits,
       o.surgeries,
       o.source_version
FROM hospital_output AS o
JOIN hospital AS h ON h.hospital_id = o.hospital_id
JOIN district AS d ON d.district_id = h.district_id;

CREATE VIEW analytics_health_admission_daily AS
SELECT a.hospital_id,
       h.master_facility_id,
       h.hospital_name,
       h.district_id AS hospital_district_id,
       hospital_district.district_name AS hospital_district_name,
       a.patient_district_id,
       patient_district.district_name AS patient_district_name,
       a.reporting_date,
       a.syndrome_code,
       syndrome.display_name AS syndrome_name,
       a.age_band,
       a.admissions,
       submission.submission_status,
       submission.submitted_at,
       a.source_version
FROM hospital_admission_daily AS a
JOIN hospital AS h ON h.hospital_id = a.hospital_id
JOIN district AS hospital_district ON hospital_district.district_id = h.district_id
JOIN district AS patient_district ON patient_district.district_id = a.patient_district_id
JOIN syndrome_category AS syndrome ON syndrome.syndrome_code = a.syndrome_code
LEFT JOIN hospital_daily_submission AS submission
  ON submission.hospital_id = a.hospital_id
 AND submission.reporting_date = a.reporting_date;

CREATE VIEW analytics_health_surveillance_signal AS
SELECT signal.signal_id,
       signal.reporting_date,
       signal.geography_type,
       signal.geography_id,
       signal.geography_name,
       signal.syndrome_code,
       syndrome.display_name AS syndrome_name,
       signal.observed_count,
       signal.expected_count,
       signal.baseline_stddev,
       signal.anomaly_score,
       signal.observed_expected_ratio,
       signal.contributing_hospitals,
       signal.reporting_completeness,
       signal.corroborated,
       signal.signal_level,
       signal.review_status,
       signal.method_version,
       signal.created_at
FROM health_surveillance_signal AS signal
JOIN syndrome_category AS syndrome
  ON syndrome.syndrome_code = signal.syndrome_code;

CREATE VIEW analytics_health_hospital_equipment AS
SELECT e.equipment_id,
       e.hospital_id,
       h.master_facility_id,
       h.hospital_name,
       d.district_name,
       e.equipment_type,
       e.asset_code,
       e.operational_status,
       e.commissioned_on,
       e.last_maintenance_on,
       e.downtime_hours_last_12m,
       e.source_version
FROM hospital_equipment AS e
JOIN hospital AS h ON h.hospital_id = e.hospital_id
JOIN district AS d ON d.district_id = h.district_id;

CREATE VIEW analytics_health_hospital_care_level AS
SELECT h.hospital_id,
       h.master_facility_id,
       h.hospital_name,
       d.district_name,
       l.level_code,
       l.display_name AS care_level_name,
       l.hierarchy_order,
       l.main_role,
       l.public_access_mode,
       l.disease_specific,
       c.effective_from,
       c.effective_to,
       c.source_version
FROM hospital_facility_classification AS c
JOIN hospital AS h ON h.hospital_id = c.hospital_id
JOIN district AS d ON d.district_id = h.district_id
JOIN healthcare_facility_level AS l ON l.level_id = c.level_id
WHERE c.effective_to IS NULL;

CREATE VIEW analytics_health_facility_referral_route AS
SELECT source.hierarchy_order AS from_hierarchy_order,
       source.level_code AS from_level_code,
       source.display_name AS from_level_name,
       source.main_role AS from_main_role,
       source.public_access_mode AS from_public_access_mode,
       target.hierarchy_order AS to_hierarchy_order,
       target.level_code AS to_level_code,
       target.display_name AS to_level_name,
       target.main_role AS to_main_role,
       target.public_access_mode AS to_public_access_mode,
       target.disease_specific AS to_disease_specific,
       route.route_type,
       route.referral_rule
FROM healthcare_referral_route AS route
JOIN healthcare_facility_level AS source ON source.level_id = route.from_level_id
JOIN healthcare_facility_level AS target ON target.level_id = route.to_level_id;

CREATE VIEW analytics_health_district_referral_pyramid AS
SELECT d.district_id,
       d.district_name,
       l.level_code,
       l.display_name AS care_level_name,
       l.hierarchy_order,
       l.main_role,
       profile.typical_min_count,
       profile.typical_max_count,
       profile.typical_count_label,
       profile.example_min_count,
       profile.example_max_count,
       profile.population_served,
       l.public_access_mode,
       profile.profile_type,
       profile.is_approximate,
       profile.source_version
FROM district_facility_distribution_profile AS profile
JOIN district AS d ON d.district_id = profile.district_id
JOIN healthcare_facility_level AS l ON l.level_id = profile.level_id;
