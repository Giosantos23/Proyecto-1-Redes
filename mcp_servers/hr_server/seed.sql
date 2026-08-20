INSERT OR IGNORE INTO employees (employee_id, full_name, department, job_title, email, phone, manager_id, employment_status) VALUES
('EMP-001', 'Ana López', 'Finance', 'Financial Analyst', 'ana.lopez@example.test', '+502 5550-1001', 'EMP-003', 'active'),
('EMP-002', 'Carlos Méndez', 'Human Resources', 'HR Specialist', 'carlos.mendez@example.test', '+502 5550-1002', 'EMP-003', 'active'),
('EMP-003', 'Sofía Ramírez', 'Operations', 'Operations Manager', 'sofia.ramirez@example.test', '+502 5550-1003', NULL, 'active'),
('EMP-004', 'Luis García', 'Information Technology', 'Systems Engineer', 'luis.garcia@example.test', '+502 5550-1004', 'EMP-003', 'active');

INSERT OR IGNORE INTO vacation_balances (employee_id, year, entitled_days, used_days) VALUES
('EMP-001', 2026, 15, 4),
('EMP-002', 2026, 15, 7),
('EMP-003', 2026, 20, 5),
('EMP-004', 2026, 15, 2);
