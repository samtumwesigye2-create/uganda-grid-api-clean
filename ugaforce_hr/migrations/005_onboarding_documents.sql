-- UGAFORCE-HR Phase 4: onboarding, documents, IT provisioning and equipment

CREATE TABLE IF NOT EXISTS ugaforce_hr_onboarding_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    department_id UUID REFERENCES ugaforce_hr_departments(id),
    role_id UUID REFERENCES ugaforce_hr_roles(id),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ugaforce_hr_onboarding_template_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID NOT NULL REFERENCES ugaforce_hr_onboarding_templates(id) ON DELETE CASCADE,
    task_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    assignee_role TEXT NOT NULL DEFAULT 'new_hire',
    due_offset_days INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0,
    config_json JSONB
);

CREATE TABLE IF NOT EXISTS ugaforce_hr_onboarding_cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES ugaforce_hr_employees(id) ON DELETE CASCADE,
    template_id UUID REFERENCES ugaforce_hr_onboarding_templates(id),
    offer_id UUID REFERENCES ugaforce_hr_offers(id),
    status TEXT NOT NULL DEFAULT 'in_progress',
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_onboarding_offer_once ON ugaforce_hr_onboarding_cases(offer_id) WHERE offer_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_onboarding_cases_employee ON ugaforce_hr_onboarding_cases(employee_id);
CREATE INDEX IF NOT EXISTS idx_onboarding_cases_status ON ugaforce_hr_onboarding_cases(status, started_at DESC);

CREATE TABLE IF NOT EXISTS ugaforce_hr_onboarding_case_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES ugaforce_hr_onboarding_cases(id) ON DELETE CASCADE,
    template_task_id UUID REFERENCES ugaforce_hr_onboarding_template_tasks(id),
    task_type TEXT NOT NULL,
    title TEXT NOT NULL,
    assignee_id UUID REFERENCES ugaforce_hr_employees(id),
    status TEXT NOT NULL DEFAULT 'pending',
    due_date DATE,
    completed_at TIMESTAMPTZ,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_onboarding_case_tasks_case ON ugaforce_hr_onboarding_case_tasks(case_id);
CREATE INDEX IF NOT EXISTS idx_onboarding_case_tasks_assignee ON ugaforce_hr_onboarding_case_tasks(assignee_id, status);
CREATE INDEX IF NOT EXISTS idx_onboarding_case_tasks_due ON ugaforce_hr_onboarding_case_tasks(status, due_date);

CREATE TABLE IF NOT EXISTS ugaforce_hr_document_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    storage_key TEXT NOT NULL,
    requires_signature BOOLEAN NOT NULL DEFAULT true,
    is_active BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS ugaforce_hr_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES ugaforce_hr_employees(id) ON DELETE CASCADE,
    template_id UUID REFERENCES ugaforce_hr_document_templates(id),
    title TEXT NOT NULL,
    storage_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    external_provider TEXT,
    external_envelope_id TEXT,
    sent_at TIMESTAMPTZ,
    signed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_documents_employee ON ugaforce_hr_documents(employee_id);
CREATE INDEX IF NOT EXISTS idx_documents_expiring ON ugaforce_hr_documents(expires_at) WHERE expires_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS ugaforce_hr_document_signers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES ugaforce_hr_documents(id) ON DELETE CASCADE,
    signer_id UUID REFERENCES ugaforce_hr_employees(id),
    signer_email TEXT,
    sign_order INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'pending',
    signed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS ugaforce_hr_it_provisioning_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES ugaforce_hr_employees(id) ON DELETE CASCADE,
    system_name TEXT NOT NULL,
    action TEXT NOT NULL DEFAULT 'provision',
    status TEXT NOT NULL DEFAULT 'pending',
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    external_ref TEXT
);
CREATE INDEX IF NOT EXISTS idx_it_provisioning_employee ON ugaforce_hr_it_provisioning_requests(employee_id, status);

CREATE TABLE IF NOT EXISTS ugaforce_hr_equipment_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES ugaforce_hr_employees(id) ON DELETE CASCADE,
    item_sku TEXT NOT NULL,
    item_description TEXT,
    status TEXT NOT NULL DEFAULT 'ordered',
    ordered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    delivered_at TIMESTAMPTZ,
    ship_to_address_id UUID REFERENCES ugaforce_hr_employee_addresses(id)
);
CREATE INDEX IF NOT EXISTS idx_equipment_orders_employee ON ugaforce_hr_equipment_orders(employee_id, status);

INSERT INTO ugaforce_hr_role_permissions(role_id, resource, can_view, can_edit, scope)
SELECT r.id, x.resource, x.can_view, x.can_edit, x.scope
FROM ugaforce_hr_roles r
JOIN (VALUES
 ('EMPLOYEE','onboarding',true,false,'self'),
 ('MANAGER','onboarding',true,true,'team'),
 ('HR_SPECIALIST','onboarding',true,true,'organization'),
 ('HR_MANAGER','onboarding',true,true,'organization'),
 ('HR_ADMIN','onboarding',true,true,'organization'),
 ('HR_SPECIALIST','documents',true,true,'organization'),
 ('HR_MANAGER','documents',true,true,'organization'),
 ('HR_ADMIN','documents',true,true,'organization')
) AS x(role_name,resource,can_view,can_edit,scope) ON x.role_name=r.name
ON CONFLICT (role_id, resource) DO UPDATE SET can_view=EXCLUDED.can_view, can_edit=EXCLUDED.can_edit, scope=EXCLUDED.scope;
