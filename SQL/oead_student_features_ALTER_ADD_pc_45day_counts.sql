USE [SUP]
GO

-- ============================================================================
-- Non-destructive deployment script for n_pc_reserved_45 / n_pc_attended_45
-- (BI-8174). Safe to run against the live table -- ADDs two nullable columns
-- only, no existing rows are touched (they'll read as NULL until the
-- backfill script runs, see SQL/oead_student_features_BACKFILL_pc_45day_counts.sql).
--
-- Idempotent: safe to re-run, no-ops if the columns already exist.
-- ============================================================================

IF NOT EXISTS (
    SELECT 1
    FROM sys.columns
    WHERE object_id = OBJECT_ID(N'[ml].[oead_student_features]')
      AND name = 'n_pc_reserved_45'
)
BEGIN
    ALTER TABLE [ml].[oead_student_features]
        ADD [n_pc_reserved_45] [int] NULL;
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.columns
    WHERE object_id = OBJECT_ID(N'[ml].[oead_student_features]')
      AND name = 'n_pc_attended_45'
)
BEGIN
    ALTER TABLE [ml].[oead_student_features]
        ADD [n_pc_attended_45] [int] NULL;
END
GO
