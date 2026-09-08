USE [SUP]
GO

-- ============================================================================
-- Non-destructive deployment script for the max_pc_reservations column.
-- Safe to run against the live table -- ADDs a nullable column only, no
-- existing rows are touched (they'll read as NULL until the backfill script
-- runs, see SQL/oead_student_features_BACKFILL_max_pc_reservations.sql).
--
-- Idempotent: safe to re-run, no-ops if the column already exists.
-- ============================================================================

IF NOT EXISTS (
    SELECT 1
    FROM sys.columns
    WHERE object_id = OBJECT_ID(N'[ml].[oead_student_features]')
      AND name = 'max_pc_reservations'
)
BEGIN
    ALTER TABLE [ml].[oead_student_features]
        ADD [max_pc_reservations] [tinyint] NULL;
END
GO
