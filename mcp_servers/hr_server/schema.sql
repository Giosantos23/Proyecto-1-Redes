PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS employees (
    employee_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    department TEXT NOT NULL,
    job_title TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT NOT NULL,
    manager_id TEXT,
    employment_status TEXT NOT NULL DEFAULT 'active',
    FOREIGN KEY (manager_id) REFERENCES employees(employee_id)
);

CREATE TABLE IF NOT EXISTS vacation_balances (
    employee_id TEXT NOT NULL,
    year INTEGER NOT NULL,
    entitled_days INTEGER NOT NULL CHECK (entitled_days >= 0),
    used_days INTEGER NOT NULL CHECK (used_days >= 0),
    PRIMARY KEY (employee_id, year),
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
);

CREATE TABLE IF NOT EXISTS leave_requests (
    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
);

CREATE TABLE IF NOT EXISTS overtime_reports (
    report_id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL,
    work_date TEXT NOT NULL,
    hours REAL NOT NULL CHECK (hours > 0 AND hours <= 24),
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
);
