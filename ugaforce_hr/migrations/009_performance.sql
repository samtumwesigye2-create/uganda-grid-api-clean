-- UGAFORCE-HR Phase 7: Performance Management
CREATE TABLE IF NOT EXISTS ugaforce_hr_review_cycles (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), name TEXT NOT NULL, cycle_type TEXT NOT NULL DEFAULT 'annual', starts_on DATE NOT NULL, ends_on DATE NOT NULL, status TEXT NOT NULL DEFAULT 'draft', created_at TIMESTAMPTZ NOT NULL DEFAULT now(), CHECK(ends_on>=starts_on)
);
CREATE TABLE IF NOT EXISTS ugaforce_hr_goals (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), employee_id UUID NOT NULL REFERENCES ugaforce_hr_employees(id) ON DELETE CASCADE, cycle_id UUID REFERENCES ugaforce_hr_review_cycles(id) ON DELETE SET NULL, title TEXT NOT NULL, description TEXT, weight NUMERIC(5,2) NOT NULL DEFAULT 0, target_value NUMERIC(14,2), current_value NUMERIC(14,2), unit TEXT, status TEXT NOT NULL DEFAULT 'active', due_date DATE, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_hr_goals_employee ON ugaforce_hr_goals(employee_id,status);
CREATE TABLE IF NOT EXISTS ugaforce_hr_performance_reviews (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), cycle_id UUID NOT NULL REFERENCES ugaforce_hr_review_cycles(id) ON DELETE CASCADE, employee_id UUID NOT NULL REFERENCES ugaforce_hr_employees(id) ON DELETE CASCADE, manager_id UUID REFERENCES ugaforce_hr_employees(id), status TEXT NOT NULL DEFAULT 'self_review', self_rating NUMERIC(3,2), manager_rating NUMERIC(3,2), calibrated_rating NUMERIC(3,2), self_comments TEXT, manager_comments TEXT, submitted_at TIMESTAMPTZ, manager_completed_at TIMESTAMPTZ, calibrated_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(cycle_id,employee_id)
);
CREATE INDEX IF NOT EXISTS idx_hr_reviews_status ON ugaforce_hr_performance_reviews(status,cycle_id);
CREATE TABLE IF NOT EXISTS ugaforce_hr_review_feedback (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), review_id UUID NOT NULL REFERENCES ugaforce_hr_performance_reviews(id) ON DELETE CASCADE, reviewer_id UUID REFERENCES ugaforce_hr_employees(id), relationship TEXT NOT NULL DEFAULT 'peer', rating NUMERIC(3,2), comments TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ugaforce_hr_development_plans (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), employee_id UUID NOT NULL REFERENCES ugaforce_hr_employees(id) ON DELETE CASCADE, review_id UUID REFERENCES ugaforce_hr_performance_reviews(id) ON DELETE SET NULL, title TEXT NOT NULL, action_plan TEXT, target_date DATE, status TEXT NOT NULL DEFAULT 'active', created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ugaforce_hr_talent_recommendations (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), review_id UUID NOT NULL REFERENCES ugaforce_hr_performance_reviews(id) ON DELETE CASCADE, employee_id UUID NOT NULL REFERENCES ugaforce_hr_employees(id) ON DELETE CASCADE, recommendation_type TEXT NOT NULL, proposed_job_title TEXT, proposed_salary NUMERIC(12,2), rationale TEXT, status TEXT NOT NULL DEFAULT 'proposed', created_by UUID REFERENCES ugaforce_hr_employees(id), created_at TIMESTAMPTZ NOT NULL DEFAULT now(), decided_by UUID REFERENCES ugaforce_hr_employees(id), decided_at TIMESTAMPTZ
);
INSERT INTO ugaforce_hr_role_permissions(role_id,resource,can_view,can_edit,scope)
SELECT r.id,x.resource,x.can_view,x.can_edit,x.scope FROM ugaforce_hr_roles r JOIN (VALUES
 ('EMPLOYEE','performance',true,true,'self'),('MANAGER','performance',true,true,'team'),('HR_SPECIALIST','performance',true,true,'all'),('HR_MANAGER','performance',true,true,'all'),('HR_ADMIN','performance',true,true,'all')
) x(role_name,resource,can_view,can_edit,scope) ON x.role_name=r.name
ON CONFLICT(role_id,resource) DO UPDATE SET can_view=excluded.can_view,can_edit=excluded.can_edit,scope=excluded.scope;