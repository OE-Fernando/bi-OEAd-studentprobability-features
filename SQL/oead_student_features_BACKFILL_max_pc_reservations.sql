USE [SUP]
GO

-- ============================================================================
-- One-time backfill for max_pc_reservations on rows that existed before this
-- column was added (the incremental proc, usp_UPDATE_oead_student_features,
-- only re-derives rows for recently-active students -- it will NOT backfill
-- older rows on its own).
--
-- Run this ONCE, after deploying:
--   1. SQL/oead_student_features_ALTER_ADD_max_pc_reservations.sql
--   2. The updated usp_UPDATE_oead_student_features stored procedure
--
-- Design note (matches STEP 6 in the stored proc): modifiedAt is only bumped
-- for rows whose computed value actually changes. This is intentional --
-- sync.py's incremental cursor (sync_state.json) picks up any row whose
-- modifiedAt moves forward, so bumping it here is what queues these rows for
-- the next `python sync.py` run. No watermark reset and no DynamoDB table
-- rebuild needed.
-- ============================================================================

;WITH src AS (

    SELECT
          sf.[PK]
        , ISNULL(dp.[max_pc_reservations], 1) AS [max_pc_reservations]

    FROM [SUP].[ml].[oead_student_features] sf

    LEFT JOIN [OEBI_LA].[dbo].[lp2_person_detail] pd
        ON pd.[person_id] = sf.[studentId]

    LEFT JOIN [DWH].[dbo].[dim_program] dp
        ON dp.[product_category] = pd.[product_category]
        AND SYSUTCDATETIME() BETWEEN dp.[start_time] AND ISNULL(dp.[end_time], '2099-12-31')

)

UPDATE tgt
SET
      tgt.[max_pc_reservations] = src.[max_pc_reservations]
    , tgt.[modifiedAt] = SYSUTCDATETIME()
FROM [SUP].[ml].[oead_student_features] tgt
INNER JOIN src ON src.[PK] = tgt.[PK]
WHERE ISNULL(tgt.[max_pc_reservations], 0) <> ISNULL(src.[max_pc_reservations], 0);

PRINT 'Backfill complete. Rows updated: ' + CAST(@@ROWCOUNT AS varchar(20));
GO
