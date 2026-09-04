-- Require existing accounts with no recorded permanent password to replace their initial credential.
UPDATE ugaforce_hr_users
SET must_change_password = true,
    updated_at = now()
WHERE password_changed_at IS NULL;
