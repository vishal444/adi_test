-- Small, referentially complete demonstration of the ministry analytics model.

INSERT OR IGNORE INTO master_source_system VALUES
(1, 'EHEALTH', 'eHealth Kerala', 'State Digital Health Mission', 'Health analytics steward', 'DAILY', 1),
(2, 'KMSCL_DDMS', 'KMSCL Drug Distribution Management System', 'KMSCL', 'Supply-chain data steward', 'DAILY', 1),
(3, 'KMSCL_EMS', 'KMSCL Equipment Management System', 'KMSCL', 'Biomedical equipment steward', 'DAILY', 1),
(4, 'SPARK', 'Service and Payroll Administrative Repository for Kerala', 'Government of Kerala', 'HR data steward', 'MONTHLY', 1),
(5, 'FINANCE', 'Treasury and departmental finance systems', 'Government of Kerala', 'Finance data steward', 'MONTHLY', 1),
(6, 'NHM_MIS', 'National Health Mission MIS', 'NHM Kerala', 'Programme data steward', 'MONTHLY', 1),
(7, 'SHA_CLAIMS', 'State Health Agency claims platform', 'State Health Agency Kerala', 'Claims data steward', 'DAILY', 1),
(8, 'PROJECT_MIS', 'Capital project monitoring system', 'Health and Family Welfare Department', 'Project data steward', 'MONTHLY', 1),
(9, 'AUDIT_MIS', 'Departmental audit and compliance register', 'Health and Family Welfare Department', 'Audit data steward', 'MONTHLY', 1);

INSERT OR IGNORE INTO master_calendar VALUES
('2026-04-01', 2026, 4, 2026, 1, 'April 2026'),
('2026-05-01', 2026, 5, 2026, 1, 'May 2026'),
('2026-06-01', 2026, 6, 2026, 1, 'June 2026'),
('2026-07-01', 2026, 7, 2026, 2, 'July 2026');

INSERT OR IGNORE INTO master_geographic_area
    (geographic_area_id, area_code, area_name, area_level,
     parent_geographic_area_id, effective_from, effective_to, active)
VALUES
(1, 'KL', 'Kerala', 'STATE', NULL, '1956-11-01', NULL, 1),
(101, 'KL-TVM', 'Thiruvananthapuram', 'DISTRICT', 1, '1956-11-01', NULL, 1),
(102, 'KL-KLM', 'Kollam', 'DISTRICT', 1, '1956-11-01', NULL, 1),
(103, 'KL-PTA', 'Pathanamthitta', 'DISTRICT', 1, '1982-11-01', NULL, 1),
(104, 'KL-ALP', 'Alappuzha', 'DISTRICT', 1, '1957-08-17', NULL, 1),
(105, 'KL-KTM', 'Kottayam', 'DISTRICT', 1, '1956-11-01', NULL, 1),
(106, 'KL-IDK', 'Idukki', 'DISTRICT', 1, '1972-01-26', NULL, 1),
(107, 'KL-EKM', 'Ernakulam', 'DISTRICT', 1, '1958-04-01', NULL, 1),
(108, 'KL-TSR', 'Thrissur', 'DISTRICT', 1, '1956-11-01', NULL, 1),
(109, 'KL-PKD', 'Palakkad', 'DISTRICT', 1, '1957-01-01', NULL, 1),
(110, 'KL-MLP', 'Malappuram', 'DISTRICT', 1, '1969-06-16', NULL, 1),
(111, 'KL-KKD', 'Kozhikode', 'DISTRICT', 1, '1957-01-01', NULL, 1),
(112, 'KL-WYD', 'Wayanad', 'DISTRICT', 1, '1980-11-01', NULL, 1),
(113, 'KL-KNR', 'Kannur', 'DISTRICT', 1, '1957-01-01', NULL, 1),
(114, 'KL-KSD', 'Kasaragod', 'DISTRICT', 1, '1984-05-24', NULL, 1),
(1001, 'KL-ALP-LSG-DEMO', 'Alappuzha local body demo', 'LOCAL_BODY', 104, '2020-04-01', NULL, 1),
(1002, 'KL-KKD-LSG-DEMO', 'Kozhikode local body demo', 'LOCAL_BODY', 111, '2020-04-01', NULL, 1),
(1003, 'KL-TSR-LSG-DEMO', 'Thrissur local body demo', 'LOCAL_BODY', 108, '2020-04-01', NULL, 1);

-- Systems of medicine are seeded before organisations because organisations
-- carry an optional governed system classification.
INSERT OR IGNORE INTO master_system_of_medicine VALUES
(1, 'MODERN', 'Modern Medicine', 1),
(2, 'AYURVEDA', 'Ayurveda', 1),
(3, 'HOMOEOPATHY', 'Homoeopathy', 1),
(4, 'SIDDHA', 'Siddha', 1),
(5, 'UNANI', 'Unani', 1),
(6, 'YOGA', 'Yoga', 1),
(7, 'NATUROPATHY', 'Naturopathy', 1),
(8, 'MIXED', 'Mixed', 1);

INSERT OR IGNORE INTO master_organisation
    (organisation_id, organisation_code, organisation_name, organisation_type,
     parent_organisation_id, administrative_level, system_of_medicine_id,
     district_id, effective_from, effective_to, active)
VALUES
(1, 'GOK', 'Government of Kerala', 'GOVERNMENT', NULL, 'STATE', NULL, NULL, '1956-11-01', NULL, 1),
(10, 'HFW', 'Health and Family Welfare Department', 'DEPARTMENT', 1, 'STATE', 1, NULL, '1956-11-01', NULL, 1),
(11, 'DHS', 'Directorate of Health Services', 'DIRECTORATE', 10, 'STATE', 1, NULL, '1956-11-01', NULL, 1),
(12, 'DME', 'Directorate of Medical Education', 'DIRECTORATE', 10, 'STATE', 1, NULL, '1983-01-01', NULL, 1),
(13, 'NHM', 'National Health Mission Kerala', 'MISSION', 10, 'STATE', 1, NULL, '2005-01-01', NULL, 1),
(14, 'KMSCL', 'Kerala Medical Services Corporation Limited', 'CORPORATION', 10, 'STATE', 1, NULL, '2007-12-28', NULL, 1),
(15, 'SHA', 'State Health Agency Kerala', 'AGENCY', 10, 'STATE', 1, NULL, '2020-01-01', NULL, 1),
(16, 'DCD', 'Drugs Control Department', 'REGULATOR', 10, 'STATE', 1, NULL, '1961-01-01', NULL, 1),
(17, 'CFS', 'Commissionerate of Food Safety', 'REGULATOR', 10, 'STATE', 1, NULL, '2006-01-01', NULL, 1),
(20, 'AYUSH', 'AYUSH Department', 'DEPARTMENT', 1, 'STATE', 2, NULL, '2015-01-01', NULL, 1),
(21, 'ISM', 'Indian Systems of Medicine', 'DIRECTORATE', 20, 'STATE', 2, NULL, '1956-11-01', NULL, 1),
(22, 'HOMEO', 'Directorate of Homoeopathy', 'DIRECTORATE', 20, 'STATE', 3, NULL, '1956-11-01', NULL, 1),
(23, 'DAME', 'Directorate of Ayurveda Medical Education', 'DIRECTORATE', 20, 'STATE', 2, NULL, '1956-11-01', NULL, 1),
(24, 'HME', 'Homoeopathic Medical Education', 'DIRECTORATE', 20, 'STATE', 3, NULL, '1956-11-01', NULL, 1),
(25, 'NAM', 'National AYUSH Mission Kerala', 'MISSION', 20, 'STATE', 8, NULL, '2014-01-01', NULL, 1),
(26, 'OUSHADHI', 'Oushadhi', 'CORPORATION', 20, 'STATE', 2, NULL, '1975-01-01', NULL, 1),
(27, 'HOMCO', 'HOMCO', 'CORPORATION', 20, 'STATE', 3, NULL, '1974-01-01', NULL, 1);

INSERT OR IGNORE INTO master_facility_type VALUES
(1, 'SUBCENTRE_JAK', 'Sub Centre / Janakeeya Arogya Kendram', 1, 0, 0, 1),
(2, 'PHC_FHC', 'Primary Health Centre / Family Health Centre', 2, 0, 0, 1),
(3, 'CHC_BLOCK_FHC', 'Community Health Centre / Block Family Health Centre', 3, 0, 0, 1),
(4, 'TALUK_THQH', 'Taluk Hospital / Taluk Headquarters Hospital', 4, 0, 0, 1),
(5, 'DISTRICT_GENERAL', 'District Hospital / General Hospital', 5, 0, 0, 1),
(6, 'MEDICAL_COLLEGE', 'Medical College Hospital', 6, 1, 0, 1),
(7, 'SPECIALTY_INSTITUTE', 'Specialised or super-specialty institution', 7, 1, 1, 1),
(8, 'AYURVEDA_HOSPITAL', 'Ayurveda Hospital', 3, 0, 0, 1),
(9, 'HOMEO_HOSPITAL', 'Homoeopathy Hospital', 3, 0, 0, 1);

INSERT OR IGNORE INTO master_facility
    (facility_id, facility_code, facility_name, facility_type_id,
     parent_organisation_id, district_id, local_body_id,
     system_of_medicine_id, ownership_type, urban_rural_category,
     teaching_status, sanctioned_bed_capacity, operational_status,
     latitude, longitude, effective_from, effective_to, source_system_id,
     source_version)
VALUES
(1, 'ALP-GH-001', 'Alappuzha General Hospital', 5, 11, 104, 1001, 1, 'STATE_GOVERNMENT', 'URBAN', 'NON_TEACHING', 500, 'OPERATIONAL', 9.4981, 76.3388, '2020-04-01', NULL, 1, 'demo-ministry-v1'),
(2, 'KKD-DH-001', 'Kozhikode District Hospital', 5, 11, 111, 1002, 1, 'STATE_GOVERNMENT', 'URBAN', 'NON_TEACHING', 450, 'OPERATIONAL', 11.2588, 75.7804, '2020-04-01', NULL, 1, 'demo-ministry-v1'),
(3, 'TSR-GH-001', 'Thrissur General Hospital', 5, 11, 108, 1003, 1, 'STATE_GOVERNMENT', 'URBAN', 'NON_TEACHING', 400, 'OPERATIONAL', 10.5276, 76.2144, '2020-04-01', NULL, 1, 'demo-ministry-v1');

-- Reconcile the compatibility hospital identities after the canonical
-- facilities exist. Unmapped compatibility rows retain NULL during migration.
UPDATE hospital
SET master_facility_id = (
    SELECT facility.facility_id
    FROM master_facility AS facility
    WHERE facility.facility_name = hospital.hospital_name
)
WHERE master_facility_id IS NULL
  AND EXISTS (
      SELECT 1
      FROM master_facility AS facility
      WHERE facility.facility_name = hospital.hospital_name
  );

INSERT OR IGNORE INTO master_cost_category VALUES
(1, 'SALARY', 'Salary', 1), (2, 'MEDICINE', 'Medicine', 1),
(3, 'EQUIPMENT_MAINT', 'Equipment maintenance', 1), (4, 'CAPITAL', 'Capital works', 1);

INSERT OR IGNORE INTO master_staff_category VALUES
(1, 'DOCTOR', 'Doctors', 1, 1), (2, 'NURSE', 'Nurses', 1, 1),
(3, 'PHARMACIST', 'Pharmacists', 1, 1), (4, 'SUPPORT', 'Support staff', 0, 1);

INSERT OR IGNORE INTO master_equipment_category VALUES
(1, 'DIAGNOSTIC', 'Diagnostic equipment', 'IMPORTANT', 1),
(2, 'ICU', 'ICU equipment', 'CRITICAL', 1),
(3, 'IMAGING', 'Imaging equipment', 'CRITICAL', 1),
(4, 'IT', 'IT equipment', 'ROUTINE', 1);

INSERT OR IGNORE INTO master_service_category VALUES
(1, 'PRIMARY_CARE', 'Primary care', 1), (2, 'EMERGENCY', 'Emergency care', 1),
(3, 'SURGERY', 'Surgery', 1), (4, 'MATERNAL', 'Maternal care', 1),
(5, 'DIAGNOSTIC', 'Diagnostic services', 1);

INSERT OR IGNORE INTO master_infrastructure_category VALUES
(1, 'ELECTRICITY', 'Electricity', 1, 1), (2, 'OXYGEN', 'Medical oxygen', 1, 1),
(3, 'WATER', 'Water supply', 1, 1), (4, 'INTERNET', 'Internet connectivity', 0, 1);

INSERT OR IGNORE INTO master_procurement_category VALUES
(1, 'MEDICINES', 'Medicines', 1), (2, 'EQUIPMENT', 'Equipment', 1),
(3, 'MAINTENANCE', 'Equipment maintenance', 1), (4, 'IT', 'IT systems', 1);

INSERT OR IGNORE INTO master_vehicle_category VALUES
(1, 'EMERGENCY_AMBULANCE', 'Emergency ambulance', 1, 1),
(2, 'PATIENT_TRANSPORT', 'Patient transport ambulance', 0, 1),
(3, 'MOBILE_MEDICAL', 'Mobile medical unit', 0, 1);

INSERT OR IGNORE INTO master_quality_category VALUES
(1, 'PATIENT_SAFETY', 'Patient safety', 1),
(2, 'INFECTION_CONTROL', 'Infection control', 1),
(3, 'EMERGENCY_READINESS', 'Emergency readiness', 1),
(4, 'CITIZEN_SATISFACTION', 'Citizen satisfaction', 1);

INSERT OR IGNORE INTO master_demographic_group VALUES
(1, 'ALL', 'All population', 'ALL', 'AGGREGATE', 1),
(2, 'TRIBAL', 'Scheduled Tribe population', 'TRIBAL', 'AGGREGATE', 1),
(3, 'DISABILITY', 'Persons with disabilities', 'DISABILITY', 'AGGREGATE', 1),
(4, 'WOMEN', 'Women', 'SEX', 'AGGREGATE', 1);

INSERT OR IGNORE INTO master_programme VALUES
(1, 'MATERNAL_HEALTH', 'Maternal Health Programme', 'MATERNAL_HEALTH', 13, '2005-01-01', NULL, 1),
(2, 'NCD_SCREENING', 'Non-communicable Disease Screening', 'NCD', 13, '2010-01-01', NULL, 1);

INSERT OR IGNORE INTO master_scheme VALUES
(1, 'KASP', 'Karunya Arogya Suraksha Padhathi', 'HEALTH_INSURANCE', 15, '2020-01-01', NULL, 1);

INSERT OR IGNORE INTO master_supplier VALUES
(1, 'DEMO-PHARMA', 'Demonstration Pharmaceutical Supplier', 'MEDICINE_SUPPLIER', 107, 1),
(2, 'DEMO-EQUIP', 'Demonstration Biomedical Supplier', 'EQUIPMENT_SUPPLIER', 101, 1);

INSERT OR IGNORE INTO master_budget_head VALUES
(1, 'HFW-OPERATING', 'Health facility operating budget', NULL, 'STATE_PLAN', 1),
(2, 'HFW-MEDICINE', 'Essential medicines', 1, 'STATE_PLAN', 1),
(3, 'HFW-CAPITAL', 'Health capital projects', NULL, 'STATE_PLAN', 1);

INSERT OR IGNORE INTO master_project VALUES
(1, 'ALP-OXYGEN-001', 'Alappuzha oxygen infrastructure upgrade', 'OXYGEN_INFRASTRUCTURE', 1, 10, 3, '2026-04-01', '2027-03-31', 1);

INSERT OR IGNORE INTO analytics_facility_monthly_summary
    (facility_id, month_id, outpatient_visits, inpatient_admissions,
     emergency_visits, surgeries_completed, deliveries_completed,
     diagnostic_tests_completed, patients_referred_out, patients_referred_in,
     sanctioned_beds, operational_beds, occupied_bed_days, available_bed_days,
     total_staff_required, total_staff_sanctioned, total_staff_available,
     total_budget_available, total_expenditure, average_waiting_minutes,
     service_cancellation_count, patient_grievance_count, reported_deaths,
     source_system_id, source_version)
VALUES
(1, '2026-06-01', 10670, 4100, 1800, 1030, 190, 8400, 130, 92, 500, 470, 10500, 14100, 620, 590, 545, 16000000, 12800000, 42, 18, 12, 44, 1, 'demo-ministry-v1'),
(2, '2026-06-01', 15900, 5800, 2200, 1800, 240, 11200, 175, 118, 450, 430, 10800, 12900, 700, 660, 610, 15000000, 13350000, 55, 25, 20, 61, 1, 'demo-ministry-v1'),
(3, '2026-06-01', 10800, 4000, 1700, 1200, 210, 9000, 145, 105, 400, 380, 8900, 11400, 580, 550, 500, 10500000, 9135000, 38, 14, 8, 39, 1, 'demo-ministry-v1');

INSERT OR IGNORE INTO analytics_medicine_monthly
    (facility_id, month_id, opening_stock_value, medicine_received_value,
     medicine_consumed_value, closing_stock_value,
     estimated_required_stock_value, available_stock_value,
     medicine_procurement_cost, medicine_distribution_cost,
     expired_medicine_value, damaged_medicine_value,
     emergency_local_purchase_cost, stockout_days,
     critical_stockout_incidents, average_supply_delay_days,
     source_system_id, source_version)
VALUES
(1, '2026-06-01', 4200000, 3100000, 3000000, 4300000, 5000000, 4300000, 3100000, 90000, 45000, 8000, 160000, 2, 1, 7, 2, 'demo-ministry-v1'),
(2, '2026-06-01', 3900000, 2200000, 3300000, 2800000, 4700000, 2800000, 2200000, 85000, 70000, 12000, 510000, 9, 4, 28, 2, 'demo-ministry-v1'),
(3, '2026-06-01', 3600000, 2900000, 2800000, 3700000, 4200000, 3700000, 2900000, 82000, 35000, 6000, 90000, 1, 0, 5, 2, 'demo-ministry-v1');

INSERT OR IGNORE INTO analytics_equipment_monthly
    (facility_id, equipment_category_id, month_id,
     equipment_required_count, equipment_available_count,
     equipment_functional_count, equipment_nonfunctional_count,
     equipment_under_maintenance_count, new_equipment_procured_count,
     equipment_procurement_value, equipment_maintenance_cost,
     spare_parts_cost, total_downtime_hours, average_repair_time_days,
     utilisation_rate, maintenance_compliance_rate,
     source_system_id, source_version)
VALUES
(1, 3, '2026-06-01', 8, 8, 7, 1, 1, 0, 12000000, 220000, 50000, 18.5, 3, 78, 92, 3, 'demo-ministry-v1'),
(2, 3, '2026-06-01', 8, 7, 5, 2, 2, 0, 11000000, 510000, 180000, 96, 12, 64, 71, 3, 'demo-ministry-v1'),
(3, 2, '2026-06-01', 24, 22, 20, 2, 1, 1, 9500000, 390000, 120000, 48, 6, 72, 85, 3, 'demo-ministry-v1');

INSERT OR IGNORE INTO analytics_staffing_monthly
    (facility_id, staff_category_id, month_id, sanctioned_posts,
     required_posts, filled_posts, staff_actually_available,
     permanent_staff_count, contract_staff_count, temporary_staff_count,
     staff_on_leave, staff_on_deputation, overtime_hours, training_hours,
     salary_cost, contract_staff_cost, overtime_cost,
     source_system_id, source_version)
VALUES
(1, 1, '2026-06-01', 120, 130, 108, 101, 98, 10, 0, 6, 1, 420, 80, 9200000, 700000, 180000, 4, 'demo-ministry-v1'),
(2, 1, '2026-06-01', 140, 155, 119, 110, 105, 14, 0, 8, 1, 610, 70, 10100000, 980000, 260000, 4, 'demo-ministry-v1'),
(3, 2, '2026-06-01', 240, 255, 224, 210, 202, 22, 0, 12, 2, 530, 110, 11800000, 1050000, 230000, 4, 'demo-ministry-v1');

INSERT OR IGNORE INTO analytics_service_monthly
    (facility_id, service_category_id, demographic_group_id, month_id,
     service_capacity, service_demand, services_delivered,
     services_cancelled, patients_waiting, average_waiting_days,
     required_staff_count, available_staff_count,
     required_equipment_count, functional_equipment_count,
     referrals_out, referrals_in, estimated_unmet_demand,
     service_availability_status, source_system_id, source_version)
VALUES
(1, 3, 1, '2026-06-01', 1200, 1280, 1030, 18, 75, 6, 42, 38, 16, 15, 41, 22, 250, 'CONSTRAINED', 1, 'demo-ministry-v1'),
(2, 3, 1, '2026-06-01', 1850, 2010, 1800, 25, 110, 9, 55, 47, 20, 17, 65, 38, 210, 'CONSTRAINED', 1, 'demo-ministry-v1'),
(3, 4, 4, '2026-06-01', 260, 245, 210, 4, 18, 2, 34, 31, 12, 11, 11, 8, 35, 'AVAILABLE', 1, 'demo-ministry-v1');

INSERT OR IGNORE INTO finance_budget_monthly
    (organisation_id, facility_id, budget_head_id, month_id,
     original_budget, revised_budget, funds_released, funds_available,
     committed_expenditure, actual_expenditure, unpaid_liabilities,
     funds_surrendered, release_delay_days, payment_delay_days,
     source_system_id, source_version)
VALUES
(11, 1, 1, '2026-06-01', 18000000, 18000000, 16000000, 16000000, 14000000, 12800000, 900000, 0, 4, 12, 5, 'demo-ministry-v1'),
(11, 2, 1, '2026-06-01', 17000000, 17000000, 15000000, 15000000, 14500000, 13350000, 1250000, 0, 6, 18, 5, 'demo-ministry-v1'),
(11, 3, 1, '2026-06-01', 12000000, 12000000, 10500000, 10500000, 9800000, 9135000, 420000, 0, 2, 8, 5, 'demo-ministry-v1');

INSERT OR IGNORE INTO analytics_programme_monthly
    (programme_id, district_id, demographic_group_id, month_id,
     target_population, eligible_population, population_reached,
     services_delivered, programme_budget, funds_released,
     programme_expenditure, planned_activities, completed_activities,
     outcome_indicator_value, source_system_id, source_version)
VALUES
(1, 104, 4, '2026-06-01', 25000, 23500, 21800, 26400, 8000000, 7600000, 7100000, 120, 112, 94.2, 6, 'demo-ministry-v1'),
(2, 111, 1, '2026-06-01', 180000, 165000, 124000, 132000, 12500000, 11000000, 9800000, 250, 219, 75.2, 6, 'demo-ministry-v1');

INSERT OR IGNORE INTO analytics_scheme_monthly
    (scheme_id, district_id, demographic_group_id, month_id,
     eligible_households, enrolled_households, eligible_individuals,
     enrolled_individuals, beneficiaries_served, claims_submitted,
     claims_approved, claims_rejected, claim_amount_requested,
     claim_amount_approved, claim_amount_paid, average_claim_value,
     average_claim_processing_days, suspected_duplicate_count,
     fraud_signal_count, source_system_id, source_version)
VALUES
(1, 104, 1, '2026-06-01', 220000, 205000, 520000, 485000, 12800, 14100, 13250, 850, 225000000, 207000000, 198000000, 14943.4, 12, 43, 18, 7, 'demo-ministry-v1');

INSERT OR IGNORE INTO analytics_project_monthly
    (project_id, month_id, approved_cost, revised_cost, amount_released,
     amount_spent, outstanding_liability, planned_progress_percentage,
     actual_progress_percentage, expected_completion_date, delay_days,
     contractor_id, project_status, risk_level, source_system_id,
     source_version)
VALUES
(1, '2026-06-01', 45000000, 47000000, 18000000, 14500000, 2500000, 25, 21, '2027-05-31', 61, 2, 'IN_PROGRESS', 'HIGH', 8, 'demo-ministry-v1');

INSERT OR IGNORE INTO analytics_data_quality_monthly
    (source_system_id, organisation_id, month_id, records_expected,
     records_received, records_valid, records_rejected,
     missing_field_percentage, duplicate_percentage,
     late_submission_percentage, validation_failure_percentage,
     data_freshness_days, overall_data_quality_score, source_version)
VALUES
(1, 11, '2026-06-01', 1000, 982, 965, 17, 1.2, 0.3, 2.1, 1.7, 1, 95.4, 'demo-ministry-v1'),
(2, 14, '2026-06-01', 600, 600, 594, 6, 0.4, 0.1, 0.8, 1.0, 1, 98.2, 'demo-ministry-v1');

INSERT OR IGNORE INTO semantic_metric_definition VALUES
(1, 'MEDICINE_SUFFICIENCY', 'Medicine sufficiency percentage', 'analytics_health_medicine_monthly', '100 * available_stock_value / estimated_required_stock_value', 'ratio', 'percent', 14, 'INTERNAL', 85, '1.0.0', 1),
(2, 'EQUIPMENT_FUNCTIONALITY', 'Equipment functionality percentage', 'analytics_health_equipment_monthly', '100 * equipment_functional_count / equipment_available_count', 'ratio', 'percent', 14, 'INTERNAL', 85, '1.0.0', 1),
(3, 'STAFF_SUFFICIENCY', 'Staff sufficiency percentage', 'analytics_health_staffing_monthly', '100 * staff_actually_available / required_posts', 'ratio', 'percent', 11, 'INTERNAL', 85, '1.0.0', 1),
(4, 'BUDGET_UTILISATION', 'Budget utilisation percentage', 'analytics_health_budget_monthly', '100 * actual_expenditure / funds_available', 'ratio', 'percent', 10, 'INTERNAL', 90, '1.0.0', 1),
(5, 'PROGRAMME_COVERAGE', 'Programme coverage percentage', 'analytics_health_programme_monthly', '100 * population_reached / eligible_population', 'ratio', 'percent', 13, 'INTERNAL', 85, '1.0.0', 1);

INSERT OR IGNORE INTO semantic_dimension_definition VALUES
(1, 'FACILITY', 'Facility', 'master_facility', 'facility_id', 'facility_name', 'INTERNAL', 1),
(2, 'DISTRICT', 'District', 'master_geographic_area', 'geographic_area_id', 'area_name', 'PUBLIC', 1),
(3, 'MONTH', 'Month', 'master_calendar', 'month_id', 'month_name', 'PUBLIC', 1),
(4, 'DEMOGRAPHIC_GROUP', 'Demographic group', 'master_demographic_group', 'demographic_group_id', 'group_name', 'INTERNAL', 1),
(5, 'DEPARTMENT', 'Department', 'master_organisation', 'organisation_id', 'organisation_name', 'INTERNAL', 1);

INSERT OR IGNORE INTO semantic_capability VALUES
(1, 'health.compare_facility_performance', 'Compare facility performance', 'Compare governed resource, service, and finance measures across facilities.', 'facility x month', 'INTERNAL', 85, 'Comparisons require compatible facility types and visible data-quality scores.', 1),
(2, 'health.detect_medicine_shortages', 'Detect medicine shortages', 'Identify facilities with low aggregate medicine sufficiency or recurring stockouts.', 'facility x month', 'INTERNAL', 90, 'Aggregate values require source-system drill-down to identify a specific medicine.', 1),
(3, 'health.identify_staffing_gaps', 'Identify staffing gaps', 'Compare required, sanctioned, filled, and actually available staff.', 'facility x staff category x month', 'INTERNAL', 85, 'Required-post norms must be versioned outside the fact table.', 1),
(4, 'health.analyse_budget_utilisation', 'Analyse budget utilisation', 'Compare available funds, commitments, expenditure, and liabilities.', 'organisation or facility x budget head x month', 'INTERNAL', 90, 'Monthly values do not replace treasury reconciliation.', 1),
(5, 'health.evaluate_programme_performance', 'Evaluate programme performance', 'Compare population coverage, cost, activities, and outcomes.', 'programme x district x demographic group x month', 'INTERNAL', 85, 'Outcome indicators may not be comparable across programme definitions.', 1),
(6, 'health.department_cross_domain_overview', 'Department cross-domain overview', 'Compare pre-aggregated Health activity, resources, logistics, finance, programme, governance, quality, project, and surveillance measures.', 'department x month', 'INTERNAL', 90, 'Ratios are recomputed before domains are combined; UNASSIGNED must be reviewed through semantic_health_department_attribution_issue before certified use, and drill-down requires the source governed mart.', 1);

INSERT OR IGNORE INTO semantic_capability_input VALUES
(1, 'DATASET', 'analytics_health_facility_monthly', 1),
(1, 'DIMENSION', 'facility', 1),
(2, 'DATASET', 'analytics_health_medicine_monthly', 1),
(2, 'METRIC', 'medicine_sufficiency_percentage', 1),
(3, 'DATASET', 'analytics_health_staffing_monthly', 1),
(3, 'METRIC', 'staff_sufficiency_percentage', 1),
(4, 'DATASET', 'analytics_health_budget_monthly', 1),
(4, 'METRIC', 'budget_utilisation_percentage', 1),
(5, 'DATASET', 'analytics_health_programme_monthly', 1),
(5, 'DIMENSION', 'demographic_group', 0),
(6, 'DATASET', 'analytics_health_department_monthly', 1),
(6, 'DIMENSION', 'department', 1),
(6, 'DIMENSION', 'month', 1);

INSERT OR IGNORE INTO semantic_allowed_join VALUES
('analytics_health_facility_monthly', 'analytics_health_medicine_monthly', 'facility_id,month_id', 'facility_id,month_id', 'ONE_TO_ONE', 'APPROVED'),
('analytics_health_facility_monthly', 'analytics_health_equipment_monthly', 'facility_id,month_id', 'facility_id,month_id', 'ONE_TO_MANY_BY_CATEGORY', 'APPROVED'),
('analytics_health_facility_monthly', 'analytics_health_staffing_monthly', 'facility_id,month_id', 'facility_id,month_id', 'ONE_TO_MANY_BY_CATEGORY', 'APPROVED'),
('analytics_health_facility_monthly', 'analytics_health_budget_monthly', 'facility_id,month_id', 'facility_id,month_id', 'ONE_TO_MANY_BY_BUDGET_HEAD', 'APPROVED');

INSERT OR IGNORE INTO semantic_quality_rule VALUES
(1, 'DQ_FACILITY_MONTH_REQUIRED', 'analytics_health_facility_monthly', 'facility_id IS NOT NULL AND month_id IS NOT NULL', 'BLOCKING', 'STOP_ANALYSIS', 1),
(2, 'DQ_MEDICINE_REQUIRED_POSITIVE', 'analytics_health_medicine_monthly', 'estimated_required_stock_value >= 0', 'ERROR', 'QUARANTINE', 1),
(3, 'DQ_SCORE_THRESHOLD', 'analytics_health_data_quality_monthly', 'overall_data_quality_score >= 85', 'BLOCKING', 'STOP_ANALYSIS', 1);

INSERT OR IGNORE INTO semantic_access_policy VALUES
(1, 'POLICY_AGGREGATE_ANALYTICS', 'DATASET', 'analytics_health_%', 'health_analyst', NULL, 'Ministry planning and performance analysis only.', 1),
(2, 'POLICY_RESTRICTED_IDENTITIES', 'DATASET', 'restricted_%', 'authorised_investigator', NULL, 'Eligibility, claims, fraud investigation, or legally authorised audit only.', 1);
