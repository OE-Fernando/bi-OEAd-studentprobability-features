USE [LK]
GO

-- ============================================================================
-- Finds students with the most PC (private class) activity in the trailing
-- 45 days -- useful for picking a test studentId when spot-checking
-- n_pc_reserved_45 / n_pc_attended_45, e.g.:
--
--   .venv\Scripts\python.exe get_dynamodb_item.py S#<studentId>
--
-- Confirm n_pc_reserved_45 ~= qtyReserved_45, n_pc_attended_45 ~=
-- qtyAttended_45, and n_pc_attended_45 <= n_pc_reserved_45 for that student.
--
-- Same 45-day window and source table as STEP 4 of
-- usp_UPDATE_oead_student_features.sql / the BI-8174 backfill script.
-- ============================================================================

SELECT TOP 10
      ra.[studentId]
    , COUNT(1) AS qtyReserved_45
    , SUM(CASE WHEN ra.[attended] = 1 THEN 1 ELSE 0 END) AS qtyAttended_45
FROM [LK].[dbo].[oead_reservations_attendance] ra
WHERE ra.[startTime] >= DATEADD(DAY, -45, SYSUTCDATETIME())
GROUP BY ra.[studentId]
HAVING SUM(CASE WHEN ra.[attended] = 1 THEN 1 ELSE 0 END) > 0
ORDER BY qtyAttended_45 DESC, qtyReserved_45 DESC;
