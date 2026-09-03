-- UGAFORCE-HR Phase 6: Payroll & Benefits
-- Source-aligned with the updated payroll schema and adapted to Phase 5 timesheets.

INSERT INTO ugaforce_hr_roles(name, description) VALUES
 ('PAYROLL_ADMIN','Payroll operations administrator')
ON CONFLICT (name) DO NOTHING;

CREATE TABLE IF NOT EXISTS ugaforce_hr_pay_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    pay_frequency TEXT NOT NULL DEFAULT 'biweekly',
    currency TEXT NOT NULL DEFAULT 'USD',
    country_code TEXT NOT NULL DEFAULT 'UG',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ugaforce_hr_employee_pay_groups (
    employee_id UUID PRIMARY KEY REFERENCES ugaforce_hr_employees(id) ON DELETE CASCADE,
    pay_group_id UUID NOT NULL REFERENCES ugaforce_hr_pay_groups(id),
    effective_date DATE NOT NULL DEFAULT CURRENT_DATE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ugaforce_hr_benefit_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    provider TEXT,
    employee_cost NUMERIC(10,2) NOT NULL DEFAULT 0,
    employer_cost NUMERIC(10,2) NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ugaforce_hr_benefit_enrollments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES ugaforce_hr_employees(id) ON DELETE CASCADE,
    plan_id UUID NOT NULL REFERENCES ugaforce_hr_benefit_plans(id),
    tier TEXT NOT NULL DEFAULT 'employee_only',
    effective_date DATE NOT NULL,
    end_date DATE,
    status TEXT NOT NULL DEFAULT 'active',
    enrolled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(employee_id, plan_id, effective_date)
);
CREATE INDEX IF NOT EXISTS idx_hr_benefit_enrollments_employee ON ugaforce_hr_benefit_enrollments(employee_id, status);

CREATE TABLE IF NOT EXISTS ugaforce_hr_enrollment_windows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    window_type TEXT NOT NULL,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    applies_to_employee_id UUID REFERENCES ugaforce_hr_employees(id) ON DELETE CASCADE,
    CHECK (ends_at > starts_at)
);

CREATE TABLE IF NOT EXISTS ugaforce_hr_payroll_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pay_group_id UUID REFERENCES ugaforce_hr_pay_groups(id),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    pay_date DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    total_gross NUMERIC(14,2) NOT NULL DEFAULT 0,
    total_net NUMERIC(14,2) NOT NULL DEFAULT 0,
    created_by UUID REFERENCES ugaforce_hr_employees(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    locked_at TIMESTAMPTZ,
    approved_by UUID REFERENCES ugaforce_hr_employees(id),
    approved_at TIMESTAMPTZ,
    disbursed_at TIMESTAMPTZ,
    CHECK(period_end >= period_start)
);
CREATE INDEX IF NOT EXISTS idx_hr_payroll_runs_status ON ugaforce_hr_payroll_runs(status, pay_date DESC);

CREATE TABLE IF NOT EXISTS ugaforce_hr_payroll_line_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payroll_run_id UUID NOT NULL REFERENCES ugaforce_hr_payroll_runs(id) ON DELETE CASCADE,
    employee_id UUID NOT NULL REFERENCES ugaforce_hr_employees(id),
    timesheet_id UUID REFERENCES ugaforce_hr_timesheets(id),
    base_pay NUMERIC(12,2) NOT NULL DEFAULT 0,
    overtime_pay NUMERIC(12,2) NOT NULL DEFAULT 0,
    bonus NUMERIC(12,2) NOT NULL DEFAULT 0,
    gross_pay NUMERIC(12,2) NOT NULL DEFAULT 0,
    tax_withholding NUMERIC(12,2) NOT NULL DEFAULT 0,
    benefit_deductions NUMERIC(12,2) NOT NULL DEFAULT 0,
    other_deductions NUMERIC(12,2) NOT NULL DEFAULT 0,
    net_pay NUMERIC(12,2) NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    payment_reference TEXT,
    UNIQUE(payroll_run_id, employee_id)
);
CREATE INDEX IF NOT EXISTS idx_hr_payroll_line_items_run ON ugaforce_hr_payroll_line_items(payroll_run_id);
CREATE INDEX IF NOT EXISTS idx_hr_payroll_line_items_employee ON ugaforce_hr_payroll_line_items(employee_id);

CREATE TABLE IF NOT EXISTS ugaforce_hr_payroll_line_item_details (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    line_item_id UUID NOT NULL REFERENCES ugaforce_hr_payroll_line_items(id) ON DELETE CASCADE,
    detail_type TEXT NOT NULL,
    label TEXT NOT NULL,
    amount NUMERIC(12,2) NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ugaforce_hr_payroll_adjustments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payroll_run_id UUID NOT NULL REFERENCES ugaforce_hr_payroll_runs(id) ON DELETE CASCADE,
    employee_id UUID NOT NULL REFERENCES ugaforce_hr_employees(id),
    adjustment_type TEXT NOT NULL,
    label TEXT NOT NULL,
    amount NUMERIC(12,2) NOT NULL,
    created_by UUID REFERENCES ugaforce_hr_employees(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_hr_payroll_adjustments_run ON ugaforce_hr_payroll_adjustments(payroll_run_id, employee_id);

CREATE TABLE IF NOT EXISTS ugaforce_hr_pay_slips (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payroll_line_item_id UUID NOT NULL UNIQUE REFERENCES ugaforce_hr_payroll_line_items(id) ON DELETE CASCADE,
    employee_id UUID NOT NULL REFERENCES ugaforce_hr_employees(id),
    storage_key TEXT,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    viewed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_hr_pay_slips_employee ON ugaforce_hr_pay_slips(employee_id, generated_at DESC);

CREATE TABLE IF NOT EXISTS ugaforce_hr_tax_jurisdictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    country TEXT NOT NULL,
    region TEXT,
    tax_year INTEGER NOT NULL,
    rules_json JSONB NOT NULL,
    effective_date DATE NOT NULL,
    UNIQUE(country, region, tax_year)
);

CREATE TABLE IF NOT EXISTS ugaforce_hr_employee_tax_profiles (
    employee_id UUID PRIMARY KEY REFERENCES ugaforce_hr_employees(id) ON DELETE CASCADE,
    jurisdiction_id UUID NOT NULL REFERENCES ugaforce_hr_tax_jurisdictions(id),
    filing_status TEXT,
    withholding_allowances INTEGER NOT NULL DEFAULT 0,
    additional_withholding NUMERIC(10,2) NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ugaforce_hr_accounting_journal_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payroll_run_id UUID NOT NULL REFERENCES ugaforce_hr_payroll_runs(id) ON DELETE CASCADE,
    gl_account TEXT NOT NULL,
    debit NUMERIC(14,2) NOT NULL DEFAULT 0,
    credit NUMERIC(14,2) NOT NULL DEFAULT 0,
    exported_to TEXT,
    exported_at TIMESTAMPTZ,
    external_ref TEXT
);
CREATE INDEX IF NOT EXISTS idx_hr_journal_entries_run ON ugaforce_hr_accounting_journal_entries(payroll_run_id);

INSERT INTO ugaforce_hr_pay_groups(name,pay_frequency,currency,country_code) VALUES
 ('Standard Payroll','biweekly','USD','UG')
ON CONFLICT (name) DO NOTHING;

INSERT INTO ugaforce_hr_role_permissions(role_id, resource, can_view, can_edit, scope)
SELECT r.id, x.resource, x.can_view, x.can_edit, x.scope
FROM ugaforce_hr_roles r
JOIN (VALUES
 ('EMPLOYEE','payroll',true,false,'self'),
 ('EMPLOYEE','benefits',true,true,'self'),
 ('MANAGER','benefits',true,false,'team'),
 ('HR_SPECIALIST','benefits',true,true,'organization'),
 ('HR_MANAGER','benefits',true,true,'organization'),
 ('HR_ADMIN','benefits',true,true,'organization'),
 ('HR_MANAGER','payroll',true,false,'organization'),
 ('HR_ADMIN','payroll',true,true,'organization'),
 ('PAYROLL_ADMIN','payroll',true,true,'organization'),
 ('PAYROLL_ADMIN','benefits',true,false,'organization')
) AS x(role_name,resource,can_view,can_edit,scope) ON x.role_name=r.name
ON CONFLICT (role_id,resource) DO UPDATE SET can_view=excluded.can_view,can_edit=excluded.can_edit,scope=excluded.scope;
