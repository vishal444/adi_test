CREATE TABLE IF NOT EXISTS district (
    district_id INTEGER PRIMARY KEY,
    district_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS hospital (
    hospital_id INTEGER PRIMARY KEY,
    hospital_name TEXT NOT NULL UNIQUE,
    district_id INTEGER NOT NULL REFERENCES district(district_id),
    effective_from TEXT NOT NULL,
    effective_to TEXT
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

CREATE VIEW IF NOT EXISTS analytics_health_hospital_funding_year AS
SELECT h.hospital_id,
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

CREATE VIEW IF NOT EXISTS analytics_health_hospital_output_year AS
SELECT h.hospital_id,
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

