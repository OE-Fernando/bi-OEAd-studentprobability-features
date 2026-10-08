USE [SUP]
GO

-- ============================================================================
-- Non-destructive deployment script for n_pc_reserved_45 / n_pc_attended_45
-- (BI-8174). Safe to run against the live table -- ADDs two nullable columns
-- only, no existing rows are touched (they'll read as NULL until the
-- backfill script runs, see SQL/oead_student_features_BACKFILL_pc_45day_counts.sql).
--
-- Idempotent: safe to re-run, no-ops if the columns already exist.
--
-- NOTE: this repo has no CREATE_TBL.sql snapshot for oead_student_history
-- (unlike oead_student_features) -- its full schema isn't tracked here.
-- Worth generating one (e.g. via SSMS "Script Table as > CREATE To") and
-- adding it to this repo while making this change, so the gap doesn't widen.
-- ============================================================================

IF NOT EXISTS (
    SELECT 1
    FROM sys.columns
    WHERE object_id = OBJECT_ID(N'[ml].[oead_student_history]')
      AND name = 'n_pc_reserved_45'
)
BEGIN
    ALTER TABLE [ml].[oead_student_history]
        ADD [n_pc_reserved_45] [int] NULL;
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.columns
    WHERE object_id = OBJECT_ID(N'[ml].[oead_student_history]')
      AND name = 'n_pc_attended_45'
)
BEGIN
    ALTER TABLE [ml].[oead_student_history]
        ADD [n_pc_attended_45] [int] NULL;
END
GO
