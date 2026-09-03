-- UGAFORCE-HR Phase 2: production indexes for People operations.
CREATE INDEX IF NOT EXISTS idx_ugaforce_hr_employees_name
    ON ugaforce_hr_employees (last_name, first_name);
CREATE INDEX IF NOT EXISTS idx_ugaforce_hr_employees_work_email
    ON ugaforce_hr_employees (work_email);
CREATE INDEX IF NOT EXISTS idx_ugaforce_hr_employees_role
    ON ugaforce_hr_employees (role_id);
CREATE INDEX IF NOT EXISTS idx_ugaforce_hr_profile_changes_status
    ON ugaforce_hr_profile_change_requests (status, requested_at);
CREATE INDEX IF NOT EXISTS idx_ugaforce_hr_audit_created
    ON ugaforce_hr_audit_log (created_at DESC);
