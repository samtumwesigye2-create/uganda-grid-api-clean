-- UGAFORCE-HR Phase 6 safety controls for payroll calculation and payout recording.

ALTER TABLE ugaforce_hr_payroll_runs
    ADD COLUMN IF NOT EXISTS calculation_warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS disbursement_provider TEXT,
    ADD COLUMN IF NOT EXISTS disbursement_reference TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_hr_payroll_disbursement_reference
    ON ugaforce_hr_payroll_runs(disbursement_reference)
    WHERE disbursement_reference IS NOT NULL;
