INSERT OR IGNORE INTO healthcare_facility_level VALUES
(1, 'SUBCENTRE_JAK', 'Sub Centre / Janakeeya Arogya Kendram (Health & Wellness Centre)', 1, 'Vaccinations, antenatal care, basic health services, and health education.', 'direct', 0),
(2, 'PHC_FHC', 'Primary Health Centre / Family Health Centre', 2, 'First doctor contact, common illnesses, chronic disease management, and minor procedures; FHCs provide longer hours and expanded services.', 'direct', 0),
(3, 'CHC_BLOCK_FHC', 'Community Health Centre / Block FHC', 3, 'Basic specialist medicine, surgery, obstetrics and pediatrics, inpatient beds, and emergency stabilization.', 'referral_or_emergency', 0),
(4, 'TALUK_THQH', 'Taluk Hospital / Taluk Headquarters Hospital', 4, 'Broader specialist services, surgeries, labor rooms, blood storage, X-ray, and ICU services where available.', 'referral_or_emergency', 0),
(5, 'DH_GH', 'District Hospital / General Hospital', 5, 'Full secondary care with multiple specialties, major surgery, ICU, dialysis, and trauma services.', 'referral_or_emergency', 0),
(6, 'MCH', 'Medical College Hospital', 6, 'Tertiary care, super-specialists, advanced surgery, teaching, research, and referral cases across districts.', 'referral_or_emergency', 0),
(7, 'SUPER_SPECIALTY', 'Super-specialty Institute', 7, 'Disease-specific advanced care such as oncology, cardiac, neurological, and other institute-specific services.', 'specialty_referral_only', 1);

INSERT OR IGNORE INTO healthcare_referral_route VALUES
(1, 2, 'severity_escalation', 'Escalate when basic services are insufficient or doctor assessment is required.'),
(2, 3, 'severity_escalation', 'Escalate when specialist assessment, inpatient care, or emergency stabilization is required.'),
(3, 4, 'severity_escalation', 'Escalate when broader specialist, surgical, diagnostic, or critical-care capability is required.'),
(4, 5, 'severity_escalation', 'Escalate when full secondary multi-specialty, major surgery, dialysis, or trauma capability is required.'),
(5, 6, 'severity_escalation', 'Escalate complex tertiary, advanced surgical, teaching-hospital, or cross-district referral cases.'),
(6, 7, 'disease_specific_referral', 'Refer only when the illness matches the institute specialty; this is not a general public escalation destination.');

INSERT OR IGNORE INTO district VALUES
(1, 'Thiruvananthapuram'),
(2, 'Kollam'),
(3, 'Pathanamthitta'),
(4, 'Alappuzha'),
(5, 'Kottayam'),
(6, 'Idukki'),
(7, 'Ernakulam'),
(8, 'Thrissur'),
(9, 'Palakkad'),
(10, 'Malappuram'),
(11, 'Kozhikode'),
(12, 'Wayanad'),
(13, 'Kannur'),
(14, 'Kasaragod');

INSERT OR IGNORE INTO syndrome_category VALUES
('ACUTE_RESPIRATORY', 'Acute respiratory syndrome', 'Acute respiratory symptoms grouped for early-warning surveillance.', 1),
('ACUTE_DIARRHOEAL', 'Acute diarrhoeal syndrome', 'Acute diarrhoea grouped for early-warning surveillance.', 1),
('ACUTE_FEVER', 'Acute fever syndrome', 'Undifferentiated acute fever grouped for early-warning surveillance.', 1),
('FEVER_RASH', 'Fever with rash syndrome', 'Fever accompanied by rash grouped for early-warning surveillance.', 1),
('ENCEPHALITIS', 'Acute encephalitis syndrome', 'Acute encephalitis symptoms grouped for early-warning surveillance.', 1);

INSERT OR IGNORE INTO district_facility_distribution_profile
    (district_id, level_id, profile_type, typical_min_count, typical_max_count,
     typical_count_label, example_min_count, example_max_count, population_served,
     is_approximate, source_version)
SELECT d.district_id,
       profile.level_id,
       'typical_medium_district',
       profile.typical_min_count,
       profile.typical_max_count,
       profile.typical_count_label,
       profile.example_min_count,
       profile.example_max_count,
       profile.population_served,
       1,
       'kerala-typical-district-profile-v1'
FROM district AS d
CROSS JOIN (
    SELECT 5 AS level_id, 1 AS typical_min_count, 1 AS typical_max_count,
           NULL AS typical_count_label, 1 AS example_min_count, 1 AS example_max_count,
           'Entire district' AS population_served
    UNION ALL
    SELECT 4, 3, 8, NULL, 4, 7, 'One per taluk'
    UNION ALL
    SELECT 3, 5, 15, NULL, 6, 12, 'One per block or service cluster'
    UNION ALL
    SELECT 2, 30, 60, NULL, 30, 50, 'One per panchayat or approximately 30,000 people'
    UNION ALL
    SELECT 1, NULL, NULL, 'Hundreds', 150, 300, 'Villages and wards'
) AS profile;

INSERT OR IGNORE INTO hospital
    (hospital_id, hospital_name, district_id, master_facility_id)
VALUES
(1, 'Alappuzha General Hospital', 4, NULL),
(2, 'Kozhikode District Hospital', 11, NULL),
(3, 'Thrissur General Hospital', 8, NULL);

INSERT OR IGNORE INTO hospital_facility_classification VALUES
(1, 5, '2020-04-01', NULL, 'demo-health-v2'),
(2, 5, '2020-04-01', NULL, 'demo-health-v2'),
(3, 5, '2020-04-01', NULL, 'demo-health-v2');

INSERT OR IGNORE INTO hospital_funding VALUES
(1, 2022, 'operating', 100.0, 'demo-health-v1'),
(1, 2023, 'operating', 120.0, 'demo-health-v1'),
(1, 2024, 'operating', 142.0, 'demo-health-v1'),
(1, 2025, 'operating', 160.0, 'demo-health-v1'),
(2, 2022, 'operating', 120.0, 'demo-health-v1'),
(2, 2023, 'operating', 130.0, 'demo-health-v1'),
(2, 2024, 'operating', 141.0, 'demo-health-v1'),
(2, 2025, 'operating', 150.0, 'demo-health-v1'),
(3, 2022, 'operating', 90.0, 'demo-health-v1'),
(3, 2023, 'operating', 95.0, 'demo-health-v1'),
(3, 2024, 'operating', 100.0, 'demo-health-v1'),
(3, 2025, 'operating', 105.0, 'demo-health-v1');

INSERT OR IGNORE INTO hospital_output VALUES
(1, 2022, 4000, 10500, 1000, 'demo-health-v1'),
(1, 2023, 4050, 10600, 1010, 'demo-health-v1'),
(1, 2024, 4100, 10650, 1020, 'demo-health-v1'),
(1, 2025, 4100, 10670, 1030, 'demo-health-v1'),
(2, 2022, 5000, 13500, 1500, 'demo-health-v1'),
(2, 2023, 5200, 14300, 1600, 'demo-health-v1'),
(2, 2024, 5500, 15000, 1700, 'demo-health-v1'),
(2, 2025, 5800, 15900, 1800, 'demo-health-v1'),
(3, 2022, 3500, 9500, 1000, 'demo-health-v1'),
(3, 2023, 3650, 9900, 1050, 'demo-health-v1'),
(3, 2024, 3800, 10300, 1100, 'demo-health-v1'),
(3, 2025, 4000, 10800, 1200, 'demo-health-v1');

INSERT OR IGNORE INTO hospital_equipment VALUES
(1, 1, 'MRI Scanner', 'ALP-MRI-001', 'operational', '2021-06-15', '2026-04-10', 18.5, 'demo-health-v1'),
(2, 2, 'CT Scanner', 'KOZ-CT-001', 'maintenance', '2020-09-01', '2026-06-28', 96.0, 'demo-health-v1'),
(3, 3, 'Ventilator', 'TSR-VEN-001', 'out_of_service', '2019-03-20', '2025-12-12', 240.0, 'demo-health-v1');

-- The daily surveillance fixture follows the runtime date so a fresh demo can
-- run the default "previous Kerala reporting day" check immediately.
WITH RECURSIVE baseline_week(week_number) AS (
    SELECT 1
    UNION ALL
    SELECT week_number + 1 FROM baseline_week WHERE week_number < 8
)
INSERT OR IGNORE INTO hospital_admission_daily
    (hospital_id, patient_district_id, reporting_date, syndrome_code,
     age_band, admissions, source_version)
SELECT h.hospital_id,
       h.district_id,
       date('now', '-1 day', printf('-%d days', 7 * baseline_week.week_number)),
       'ACUTE_RESPIRATORY',
       'ALL',
       CASE h.hospital_id WHEN 1 THEN 4 WHEN 2 THEN 5 ELSE 4 END,
       'demo-daily-health-v1'
FROM hospital AS h
CROSS JOIN baseline_week;

INSERT OR IGNORE INTO hospital_admission_daily
    (hospital_id, patient_district_id, reporting_date, syndrome_code,
     age_band, admissions, source_version)
SELECT h.hospital_id,
       h.district_id,
       date('now', '-1 day'),
       'ACUTE_RESPIRATORY',
       'ALL',
       CASE h.hospital_id WHEN 1 THEN 5 WHEN 2 THEN 20 ELSE 6 END,
       'demo-daily-health-v1'
FROM hospital AS h;

INSERT OR IGNORE INTO hospital_daily_submission
    (hospital_id, reporting_date, submitted_at, submission_status, source_version)
SELECT hospital_id,
       reporting_date,
       datetime('now'),
       'complete',
       'demo-daily-health-v1'
FROM (
    SELECT DISTINCT hospital_id, reporting_date
    FROM hospital_admission_daily
    WHERE source_version = 'demo-daily-health-v1'
);
