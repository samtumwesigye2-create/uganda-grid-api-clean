-- UGAFORCE-HR password lifecycle: first-login password replacement and password-change tracking

ALTER TABLE ugaforce_hr_users
    ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE ugaforce_hr_users
    ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_hr_users_must_change_password
    ON ugaforce_hr_users(must_change_password)
    WHERE must_change_password = true;
