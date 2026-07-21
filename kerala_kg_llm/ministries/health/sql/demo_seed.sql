INSERT OR IGNORE INTO district VALUES
(1, 'Alappuzha'),
(2, 'Kozhikode'),
(3, 'Thrissur');

INSERT OR IGNORE INTO hospital VALUES
(1, 'Alappuzha General Hospital', 1, '2020-04-01', NULL),
(2, 'Kozhikode District Hospital', 2, '2020-04-01', NULL),
(3, 'Thrissur General Hospital', 3, '2020-04-01', NULL);

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

