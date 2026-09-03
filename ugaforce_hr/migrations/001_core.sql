-- ============================================================
-- UGAFORCE-HR — Core Database Schema (PostgreSQL)
-- Phase 1: Core Employee Service + RBAC
-- ============================================================

CREATE TABLE ugaforce_hr_departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    parent_dept_id UUID REFERENCES ugaforce_hr_departments(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ugaforce_hr_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE ugaforce_hr_role_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id UUID NOT NULL REFERENCES ugaforce_hr_roles(id) ON DELETE CASCADE,
    resource TEXT NOT NULL,
    can_view BOOLEAN NOT NULL DEFAULT false,
    can_edit BOOLEAN NOT NULL DEFAULT false,
    scope TEXT NOT NULL DEFAULT 'self',
    UNIQUE (role_id, resource)
);

CREATE TABLE ugaforce_hr_employees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_number TEXT UNIQUE NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    personal_email TEXT,
    work_email TEXT UNIQUE,
    phone TEXT,
    date_of_birth DATE,
    hire_date DATE NOT NULL,
    termination_date DATE,
    employment_status TEXT NOT NULL DEFAULT 'active',
    job_title TEXT,
    department_id UUID REFERENCES ugaforce_hr_departments(id),
    manager_id UUID REFERENCES ugaforce_hr_employees(id),
    role_id UUID NOT NULL REFERENCES ugaforce_hr_roles(id),
    employment_type TEXT NOT NULL DEFAULT 'full_time',
    pay_currency TEXT NOT NULL DEFAULT 'USD',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ugaforce_hr_employee_sensitive_data (
    employee_id UUID PRIMARY KEY REFERENCES ugaforce_hr_employees(id) ON DELETE CASCADE,
    national_id_enc BYTEA,
    bank_account_enc BYTEA,
    tax_id_enc BYTEA,
    base_salary NUMERIC(14,2),
    salary_effective_at DATE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ugaforce_hr_employee_addresses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES ugaforce_hr_employees(id) ON DELETE CASCADE,
    address_type TEXT NOT NULL DEFAULT 'home',
    line1 TEXT,
    line2 TEXT,
    city TEXT,
    region TEXT,
    postal_code TEXT,
    country TEXT,
    is_current BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE ugaforce_hr_emergency_contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES ugaforce_hr_employees(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    relationship TEXT,
    phone TEXT,
    email TEXT
);

CREATE TABLE ugaforce_hr_profile_change_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES ugaforce_hr_employees(id),
    field_name TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_by UUID REFERENCES ugaforce_hr_employees(id),
    reviewed_at TIMESTAMPTZ
);

CREATE TABLE ugaforce_hr_employment_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES ugaforce_hr_employees(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    effective_date DATE NOT NULL,
    old_value_json JSONB,
    new_value_json JSONB,
    created_by UUID REFERENCES ugaforce_hr_employees(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ugaforce_hr_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id UUID REFERENCES ugaforce_hr_employees(id),
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id UUID NOT NULL,
    before_json JSONB,
    after_json JSONB,
    ip_address INET,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_log_entity ON ugaforce_hr_audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_log_actor ON ugaforce_hr_audit_log(actor_id);

CREATE TABLE ugaforce_hr_event_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    published BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ
);
CREATE INDEX idx_event_outbox_unpublished ON ugaforce_hr_event_outbox(published) WHERE published = false;
CREATE INDEX idx_employees_department ON ugaforce_hr_employees(department_id);
CREATE INDEX idx_employees_manager ON ugaforce_hr_employees(manager_id);
CREATE INDEX idx_employees_status ON ugaforce_hr_employees(employment_status);
