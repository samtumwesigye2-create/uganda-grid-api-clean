-- UGAFORCE-HR Phase 2: identity, sessions, RBAC seeds and people controls

CREATE TABLE IF NOT EXISTS ugaforce_hr_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    employee_id UUID UNIQUE REFERENCES ugaforce_hr_employees(id) ON DELETE SET NULL,
    role_name TEXT NOT NULL DEFAULT 'EMPLOYEE',
    active BOOLEAN NOT NULL DEFAULT true,
    failed_signins INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMPTZ,
    last_signin TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ugaforce_hr_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_hash TEXT NOT NULL UNIQUE,
    user_id UUID NOT NULL REFERENCES ugaforce_hr_users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_hr_sessions_user ON ugaforce_hr_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_hr_sessions_active ON ugaforce_hr_sessions(expires_at) WHERE revoked_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_hr_departments_name ON ugaforce_hr_departments(lower(name));
CREATE INDEX IF NOT EXISTS idx_hr_employees_number ON ugaforce_hr_employees(employee_number);
CREATE INDEX IF NOT EXISTS idx_hr_employees_work_email ON ugaforce_hr_employees(lower(work_email));

INSERT INTO ugaforce_hr_roles(name, description) VALUES
 ('EMPLOYEE','Standard employee self-service profile'),
 ('MANAGER','People manager with team visibility'),
 ('HR_SPECIALIST','Human resources operations specialist'),
 ('HR_MANAGER','Human resources management authority'),
 ('HR_ADMIN','UGAFORCE-HR security and platform administrator')
ON CONFLICT (name) DO NOTHING;

INSERT INTO ugaforce_hr_role_permissions(role_id, resource, can_view, can_edit, scope)
SELECT r.id, x.resource, x.can_view, x.can_edit, x.scope
FROM ugaforce_hr_roles r
JOIN (VALUES
 ('EMPLOYEE','people',true,false,'self'),
 ('MANAGER','people',true,false,'team'),
 ('HR_SPECIALIST','people',true,true,'organization'),
 ('HR_MANAGER','people',true,true,'organization'),
 ('HR_ADMIN','people',true,true,'organization'),
 ('HR_MANAGER','audit',true,false,'organization'),
 ('HR_ADMIN','audit',true,true,'organization'),
 ('HR_ADMIN','security',true,true,'organization')
) AS x(role_name,resource,can_view,can_edit,scope) ON x.role_name=r.name
ON CONFLICT (role_id, resource) DO UPDATE SET can_view=EXCLUDED.can_view, can_edit=EXCLUDED.can_edit, scope=EXCLUDED.scope;
