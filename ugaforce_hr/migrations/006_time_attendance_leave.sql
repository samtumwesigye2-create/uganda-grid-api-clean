-- UGAFORCE-HR Phase 5: Time, Attendance and Leave

CREATE TABLE IF NOT EXISTS ugaforce_hr_work_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    timezone TEXT NOT NULL DEFAULT 'UTC',
    weekly_hours NUMERIC(6,2) NOT NULL DEFAULT 40,
    work_days SMALLINT[] NOT NULL DEFAULT ARRAY[1,2,3,4,5],
    start_time TIME,
    end_time TIME,
    grace_minutes INTEGER NOT NULL DEFAULT 5,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ugaforce_hr_employee_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES ugaforce_hr_employees(id) ON DELETE CASCADE,
    schedule_id UUID NOT NULL REFERENCES ugaforce_hr_work_schedules(id),
    effective_from DATE NOT NULL,
    effective_to DATE,
    UNIQUE(employee_id, effective_from)
);
CREATE INDEX IF NOT EXISTS idx_hr_employee_schedules_current ON ugaforce_hr_employee_schedules(employee_id, effective_from DESC);

CREATE TABLE IF NOT EXISTS ugaforce_hr_time_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES ugaforce_hr_employees(id) ON DELETE CASCADE,
    clock_in TIMESTAMPTZ NOT NULL,
    clock_out TIMESTAMPTZ,
    source TEXT NOT NULL DEFAULT 'web',
    location_text TEXT,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    approved_by UUID REFERENCES ugaforce_hr_employees(id),
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (clock_out IS NULL OR clock_out >= clock_in)
);
CREATE INDEX IF NOT EXISTS idx_hr_time_entries_employee_clockin ON ugaforce_hr_time_entries(employee_id, clock_in DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_hr_time_entries_one_open ON ugaforce_hr_time_entries(employee_id) WHERE clock_out IS NULL;

CREATE TABLE IF NOT EXISTS ugaforce_hr_timesheets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES ugaforce_hr_employees(id) ON DELETE CASCADE,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    regular_hours NUMERIC(8,2) NOT NULL DEFAULT 0,
    overtime_hours NUMERIC(8,2) NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'draft',
    submitted_at TIMESTAMPTZ,
    approved_by UUID REFERENCES ugaforce_hr_employees(id),
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(employee_id, period_start, period_end),
    CHECK(period_end >= period_start)
);
CREATE INDEX IF NOT EXISTS idx_hr_timesheets_status ON ugaforce_hr_timesheets(status, period_start DESC);

CREATE TABLE IF NOT EXISTS ugaforce_hr_leave_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    paid BOOLEAN NOT NULL DEFAULT true,
    annual_entitlement_days NUMERIC(6,2) NOT NULL DEFAULT 0,
    requires_approval BOOLEAN NOT NULL DEFAULT true,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ugaforce_hr_leave_balances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES ugaforce_hr_employees(id) ON DELETE CASCADE,
    leave_type_id UUID NOT NULL REFERENCES ugaforce_hr_leave_types(id),
    year INTEGER NOT NULL,
    opening_days NUMERIC(7,2) NOT NULL DEFAULT 0,
    accrued_days NUMERIC(7,2) NOT NULL DEFAULT 0,
    used_days NUMERIC(7,2) NOT NULL DEFAULT 0,
    adjustment_days NUMERIC(7,2) NOT NULL DEFAULT 0,
    UNIQUE(employee_id, leave_type_id, year)
);

CREATE TABLE IF NOT EXISTS ugaforce_hr_leave_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES ugaforce_hr_employees(id) ON DELETE CASCADE,
    leave_type_id UUID NOT NULL REFERENCES ugaforce_hr_leave_types(id),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    requested_days NUMERIC(7,2) NOT NULL,
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_by UUID REFERENCES ugaforce_hr_employees(id),
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,
    CHECK(end_date >= start_date),
    CHECK(requested_days > 0)
);
CREATE INDEX IF NOT EXISTS idx_hr_leave_requests_status ON ugaforce_hr_leave_requests(status, requested_at DESC);
CREATE INDEX IF NOT EXISTS idx_hr_leave_requests_employee ON ugaforce_hr_leave_requests(employee_id, start_date DESC);

CREATE TABLE IF NOT EXISTS ugaforce_hr_holidays (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    holiday_date DATE NOT NULL,
    name TEXT NOT NULL,
    country_code TEXT NOT NULL DEFAULT 'UG',
    region TEXT,
    paid BOOLEAN NOT NULL DEFAULT true,
    UNIQUE(holiday_date, country_code, region)
);

INSERT INTO ugaforce_hr_leave_types(code,name,paid,annual_entitlement_days) VALUES
 ('ANNUAL','Annual Leave',true,20),
 ('SICK','Sick Leave',true,10),
 ('UNPAID','Unpaid Leave',false,0),
 ('BEREAVEMENT','Bereavement Leave',true,3)
ON CONFLICT (code) DO NOTHING;

INSERT INTO ugaforce_hr_work_schedules(name,timezone,weekly_hours,start_time,end_time) VALUES
 ('Standard 40 Hour Week','Africa/Kampala',40,'08:00','17:00')
ON CONFLICT (name) DO NOTHING;

INSERT INTO ugaforce_hr_role_permissions(role_id, resource, can_view, can_edit, scope)
SELECT r.id, x.resource, x.can_view, x.can_edit, x.scope
FROM ugaforce_hr_roles r
JOIN (VALUES
 ('EMPLOYEE','attendance',true,true,'self'),
 ('EMPLOYEE','leave',true,true,'self'),
 ('MANAGER','attendance',true,false,'team'),
 ('MANAGER','leave',true,true,'team'),
 ('HR_SPECIALIST','attendance',true,true,'organization'),
 ('HR_SPECIALIST','leave',true,true,'organization'),
 ('HR_MANAGER','attendance',true,true,'organization'),
 ('HR_MANAGER','leave',true,true,'organization'),
 ('HR_ADMIN','attendance',true,true,'organization'),
 ('HR_ADMIN','leave',true,true,'organization')
) AS x(role_name,resource,can_view,can_edit,scope) ON x.role_name=r.name
ON CONFLICT (role_id,resource) DO UPDATE SET can_view=excluded.can_view,can_edit=excluded.can_edit,scope=excluded.scope;
