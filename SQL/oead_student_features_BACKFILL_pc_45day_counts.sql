USE [SUP]
GO

-- ============================================================================
-- One-time backfill for n_pc_reserved_45 / n_pc_attended_45 (BI-8174) on rows
-- that existed before these columns were added. The incremental proc
-- (usp_UPDATE_oead_student_features) only re-derives rows for students whose
-- DWH.dim_student row has start_time > @lastStartTimeUtc -- it will NOT
-- backfill older rows on its own.
--
-- Run this ONCE, after deploying:
--   1. SQL/oead_student_history_ALTER_ADD_pc_45day_counts.sql
--   2. SQL/oead_student_features_ALTER_ADD_pc_45day_counts.sql
--   3. The updated usp_UPDATE_oead_student_features stored procedure
--
-- Design note: same as the max_pc_reservations backfill, modifiedAt is only
-- bumped for rows whose computed value actually changes, which is what
-- queues a row for the next `python sync.py` run (no watermark reset, no
-- DynamoDB table rebuild needed).
--
-- Sentinel note: unlike max_pc_reservations (where real values start at 1,
-- so 0 was free to use as the "unset" comparison sentinel), 0 IS a
-- legitimate real value here (a student can genuinely have 0 PC
-- reservations/attendance in the last 45 days). So the change-detection
-- comparisons below use -1 as the sentinel instead -- same convention
-- already used in this proc's STEP 3 MERGE for an analogous int column.
-- ============================================================================

-- Step A: backfill oead_student_history (where STEP 4/5 of the proc
-- computes and persists these two counts).
;WITH q AS (

    SELECT
          ra.[studentId]
        , COUNT(1) AS [n_pc_reserved_45]
        , SUM(CASE WHEN ra.[attended] = 1 THEN 1 ELSE 0 END) AS [n_pc_attended_45]

    FROM [LK].[dbo].[oead_reservations_attendance] ra

    WHERE ra.[startTime] >= DATEADD(DAY, -45, SYSUTCDATETIME())

    GROUP BY ra.[studentId]

)

UPDATE tgt
SET
      tgt.[n_pc_reserved_45] = ISNULL(q.[n_pc_reserved_45], 0)
    , tgt.[n_pc_attended_45] = ISNULL(q.[n_pc_attended_45], 0)
    , tgt.[modifiedAt] = SYSUTCDATETIME()
FROM [SUP].[ml].[oead_student_history] tgt
LEFT JOIN q ON q.[studentId] = tgt.[studentId]
WHERE ISNULL(tgt.[n_pc_reserved_45], -1) <> ISNULL(q.[n_pc_reserved_45], 0)
   OR ISNULL(tgt.[n_pc_attended_45], -1) <> ISNULL(q.[n_pc_attended_45], 0);

PRINT 'oead_student_history backfill complete. Rows updated: ' + CAST(@@ROWCOUNT AS varchar(20));

-- Step B: backfill oead_student_features from the now-backfilled
-- oead_student_history, same source STEP 6 of the proc itself reads from.
UPDATE tgt
SET
      tgt.[n_pc_reserved_45] = ISNULL(sh.[n_pc_reserved_45], 0)
    , tgt.[n_pc_attended_45] = ISNULL(sh.[n_pc_attended_45], 0)
    , tgt.[modifiedAt] = SYSUTCDATETIME()
FROM [SUP].[ml].[oead_student_features] tgt
LEFT JOIN [SUP].[ml].[oead_student_history] sh ON sh.[studentId] = tgt.[studentId]
WHERE ISNULL(tgt.[n_pc_reserved_45], -1) <> ISNULL(sh.[n_pc_reserved_45], 0)
   OR ISNULL(tgt.[n_pc_attended_45], -1) <> ISNULL(sh.[n_pc_attended_45], 0);

PRINT 'oead_student_features backfill complete. Rows updated: ' + CAST(@@ROWCOUNT AS varchar(20));
GO
