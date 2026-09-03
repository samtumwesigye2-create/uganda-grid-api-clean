-- UGAFORCE-HR Phase 3: Recruiting / ATS
-- Source-aligned with the updated UGAFORCE-HR package.

CREATE TABLE IF NOT EXISTS ugaforce_hr_job_requisitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    department_id UUID REFERENCES ugaforce_hr_departments(id),
    hiring_manager_id UUID NOT NULL REFERENCES ugaforce_hr_employees(id),
    headcount INTEGER NOT NULL DEFAULT 1 CHECK (headcount > 0),
    employment_type TEXT NOT NULL DEFAULT 'full_time',
    status TEXT NOT NULL DEFAULT 'draft',
    target_pay_min NUMERIC(12,2),
    target_pay_max NUMERIC(12,2),
    justification TEXT,
    requested_by UUID REFERENCES ugaforce_hr_employees(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    approved_at TIMESTAMPTZ,
    CHECK (target_pay_min IS NULL OR target_pay_max IS NULL OR target_pay_min <= target_pay_max)
);

CREATE TABLE IF NOT EXISTS ugaforce_hr_job_postings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requisition_id UUID NOT NULL REFERENCES ugaforce_hr_job_requisitions(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description_md TEXT NOT NULL,
    location TEXT,
    remote_policy TEXT NOT NULL DEFAULT 'onsite',
    status TEXT NOT NULL DEFAULT 'draft',
    published_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    public_slug TEXT UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ugaforce_hr_job_posting_channels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_posting_id UUID NOT NULL REFERENCES ugaforce_hr_job_postings(id) ON DELETE CASCADE,
    channel TEXT NOT NULL,
    external_ref TEXT,
    posted_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS ugaforce_hr_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT,
    resume_storage_key TEXT,
    linkedin_url TEXT,
    source TEXT,
    referred_by_employee_id UUID REFERENCES ugaforce_hr_employees(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ugaforce_hr_pipeline_stages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_posting_id UUID NOT NULL REFERENCES ugaforce_hr_job_postings(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    stage_order INTEGER NOT NULL,
    stage_type TEXT NOT NULL DEFAULT 'interview',
    UNIQUE (job_posting_id, stage_order)
);

CREATE TABLE IF NOT EXISTS ugaforce_hr_applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id UUID NOT NULL REFERENCES ugaforce_hr_candidates(id) ON DELETE CASCADE,
    job_posting_id UUID NOT NULL REFERENCES ugaforce_hr_job_postings(id),
    status TEXT NOT NULL DEFAULT 'applied',
    current_stage_id UUID REFERENCES ugaforce_hr_pipeline_stages(id),
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    rejected_reason TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (candidate_id, job_posting_id)
);

CREATE TABLE IF NOT EXISTS ugaforce_hr_application_stage_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES ugaforce_hr_applications(id) ON DELETE CASCADE,
    stage_id UUID NOT NULL REFERENCES ugaforce_hr_pipeline_stages(id),
    entered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    exited_at TIMESTAMPTZ,
    outcome TEXT
);

CREATE TABLE IF NOT EXISTS ugaforce_hr_interviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES ugaforce_hr_applications(id) ON DELETE CASCADE,
    stage_id UUID NOT NULL REFERENCES ugaforce_hr_pipeline_stages(id),
    scheduled_at TIMESTAMPTZ,
    duration_minutes INTEGER NOT NULL DEFAULT 30 CHECK (duration_minutes > 0),
    format TEXT NOT NULL DEFAULT 'video',
    status TEXT NOT NULL DEFAULT 'scheduled',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ugaforce_hr_interview_panelists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id UUID NOT NULL REFERENCES ugaforce_hr_interviews(id) ON DELETE CASCADE,
    employee_id UUID NOT NULL REFERENCES ugaforce_hr_employees(id),
    role TEXT NOT NULL DEFAULT 'interviewer',
    UNIQUE (interview_id, employee_id)
);

CREATE TABLE IF NOT EXISTS ugaforce_hr_interview_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id UUID NOT NULL REFERENCES ugaforce_hr_interviews(id) ON DELETE CASCADE,
    panelist_id UUID NOT NULL REFERENCES ugaforce_hr_employees(id),
    recommendation TEXT NOT NULL,
    notes TEXT,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (interview_id, panelist_id)
);

CREATE TABLE IF NOT EXISTS ugaforce_hr_offers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES ugaforce_hr_applications(id),
    job_title TEXT NOT NULL,
    department_id UUID REFERENCES ugaforce_hr_departments(id),
    base_salary NUMERIC(12,2) NOT NULL CHECK (base_salary >= 0),
    bonus_target NUMERIC(12,2),
    equity_units NUMERIC(14,2),
    start_date DATE,
    status TEXT NOT NULL DEFAULT 'draft',
    expires_at TIMESTAMPTZ,
    created_by UUID REFERENCES ugaforce_hr_employees(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at TIMESTAMPTZ,
    responded_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_hr_requisitions_status ON ugaforce_hr_job_requisitions(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_hr_postings_status ON ugaforce_hr_job_postings(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_hr_candidates_name ON ugaforce_hr_candidates(last_name, first_name);
CREATE INDEX IF NOT EXISTS idx_hr_candidates_email ON ugaforce_hr_candidates(lower(email));
CREATE INDEX IF NOT EXISTS idx_hr_applications_posting ON ugaforce_hr_applications(job_posting_id, status);
CREATE INDEX IF NOT EXISTS idx_hr_applications_candidate ON ugaforce_hr_applications(candidate_id);
CREATE INDEX IF NOT EXISTS idx_hr_stage_history_app ON ugaforce_hr_application_stage_history(application_id, entered_at DESC);
CREATE INDEX IF NOT EXISTS idx_hr_interviews_application ON ugaforce_hr_interviews(application_id, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_hr_offers_application ON ugaforce_hr_offers(application_id);
CREATE INDEX IF NOT EXISTS idx_hr_offers_status ON ugaforce_hr_offers(status);

INSERT INTO ugaforce_hr_role_permissions(role_id, resource, can_view, can_edit, scope)
SELECT r.id, x.resource, x.can_view, x.can_edit, x.scope
FROM ugaforce_hr_roles r
JOIN (VALUES
 ('MANAGER','recruiting',true,false,'team'),
 ('HR_SPECIALIST','recruiting',true,true,'organization'),
 ('HR_MANAGER','recruiting',true,true,'organization'),
 ('HR_ADMIN','recruiting',true,true,'organization')
) AS x(role_name,resource,can_view,can_edit,scope) ON x.role_name=r.name
ON CONFLICT (role_id, resource) DO UPDATE SET can_view=EXCLUDED.can_view, can_edit=EXCLUDED.can_edit, scope=EXCLUDED.scope;
