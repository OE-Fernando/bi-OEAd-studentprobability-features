USE [SUP]
GO

/****** Object:  Table [ml].[oead_student_features]    Script Date: 6/2/2026 4:26:22 AM ******/

-- ============================================================================
-- This is a full schema SNAPSHOT (SSMS "Script Table as > CREATE To"), kept
-- for provisioning a fresh environment or as a reference of the current
-- definition. DO NOT run this against an environment where the table already
-- has data -- the DROP TABLE IF EXISTS below will destroy it.
--
-- To change the live table's schema, write/use an ALTER TABLE script instead,
-- e.g. SQL/oead_student_features_ALTER_ADD_max_pc_reservations.sql, then
-- update this snapshot to match for documentation purposes.
-- ============================================================================

SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO

DROP TABLE IF EXISTS [ml].[oead_student_features];

CREATE TABLE [ml].[oead_student_features](
	[PK] [varchar](32) NOT NULL,
	[studentId] [int] NOT NULL,
	[active_level] [tinyint] NULL,
	[enrollment] [varchar](5) NULL,
	[country_iso] [varchar](2) NULL,
	[Is_B2B__c] [varchar](5) NULL,
	[gender] [nvarchar](255) NULL,
	[ageGroup] [varchar](5) NULL,
	[studentHistory] [varchar](5) NULL,
	[language] [varchar](2) NULL,
	[max_pc_reservations] [tinyint] NULL,
	[n_pc_reserved_45] [int] NULL,
	[n_pc_attended_45] [int] NULL,
	[createdAt] [datetime2](3) NOT NULL,
	[modifiedAt] [datetime2](3) NOT NULL,
 CONSTRAINT [PK_oead_student_features] PRIMARY KEY CLUSTERED 
(
	[PK] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO

ALTER TABLE [ml].[oead_student_features] ADD  CONSTRAINT [DF_oead_student_features_createdAt]  DEFAULT (sysutcdatetime()) FOR [createdAt]
GO

ALTER TABLE [ml].[oead_student_features] ADD  CONSTRAINT [DF_oead_student_features_modifiedAt]  DEFAULT (sysutcdatetime()) FOR [modifiedAt]
GO

CREATE NONCLUSTERED INDEX [IX_oead_student_features_modifiedAt] ON [ml].[oead_student_features] ([modifiedAt])
GO

CREATE NONCLUSTERED INDEX [IX_oead_student_features_modifiedAt_studentId] ON [ml].[oead_student_features] ([modifiedAt], [studentId])
GO

