-- ============================================================================
-- Oracle Database Analysis — Complete SQL Query Reference
-- ============================================================================
-- Use with the temp-file+pipe pattern from the windows-infra-debugging skill:
--   1. Write SQL to temp file on remote server
--   2. Pipe content to: sqlplus -S / as sysdba
--   3. Clean up temp file
-- ============================================================================

-- ── Section 1: Instance & Database Status ──────────────────────────────────

SELECT INSTANCE_NAME, HOST_NAME, VERSION, STATUS, DATABASE_STATUS,
       ARCHIVER, LOG_MODE, OPEN_MODE, PROTECTION_MODE,
       DATABASE_ROLE, STARTUP_TIME
FROM V$INSTANCE, V$DATABASE;

-- ── Section 2: Total Database Size ─────────────────────────────────────────

SELECT ROUND(SUM(BYTES)/1024/1024/1024, 2) AS TOTAL_DB_SIZE_GB
FROM V$DATAFILE;

-- ── Section 3: Tablespace Configuration ────────────────────────────────────

-- All tablespaces with properties
SELECT TABLESPACE_NAME, STATUS, CONTENTS, EXTENT_MANAGEMENT,
       ALLOCATION_TYPE, SEGMENT_SPACE_MANAGEMENT, BIGFILE
FROM DBA_TABLESPACES
ORDER BY TABLESPACE_NAME;

-- Tablespace sizes (allocated + maxsize)
SELECT TABLESPACE_NAME,
       ROUND(SUM(BYTES)/1024/1024/1024, 2) AS ALLOCATED_GB,
       ROUND(SUM(DECODE(MAXBYTES,0,BYTES,MAXBYTES))/1024/1024/1024, 2) AS MAXSIZE_GB,
       COUNT(*) AS DATA_FILES
FROM DBA_DATA_FILES
GROUP BY TABLESPACE_NAME
UNION ALL
SELECT TABLESPACE_NAME || ' (TEMP)',
       ROUND(SUM(BYTES)/1024/1024/1024, 2),
       ROUND(SUM(DECODE(MAXBYTES,0,BYTES,MAXBYTES))/1024/1024/1024, 2),
       COUNT(*)
FROM DBA_TEMP_FILES
GROUP BY TABLESPACE_NAME
ORDER BY TABLESPACE_NAME;

-- ── Section 4: Data File Locations ─────────────────────────────────────────

SELECT FILE#, NAME, STATUS, ENABLED,
       BYTES/1024/1024/1024 AS SIZE_GB
FROM V$DATAFILE
ORDER BY FILE#;

-- Temp file locations
SELECT FILE#, NAME, BYTES/1024/1024/1024 AS SIZE_GB, STATUS
FROM V$TEMPFILE
ORDER BY FILE#;

-- ── Section 5: Control Files ───────────────────────────────────────────────

SELECT NAME, STATUS, IS_RECOVERY_DEST_FILE, BLOCK_SIZE, FILE_SIZE_BLKS
FROM V$CONTROLFILE;

-- ── Section 6: Redo Logs ───────────────────────────────────────────────────

-- Configuration
SELECT GROUP#, SEQUENCE#, BYTES/1024/1024/1024 AS SIZE_GB,
       MEMBERS, STATUS, ARCHIVED, THREAD#
FROM V$LOG
ORDER BY GROUP#;

-- Physical member locations
SELECT GROUP#, MEMBER, STATUS, TYPE, IS_RECOVERY_DEST_FILE
FROM V$LOGFILE
ORDER BY GROUP#, MEMBER;

-- ── Section 7: Archive Log Configuration ───────────────────────────────────

-- Archive destinations (only active ones)
SELECT DEST_ID, DEST_NAME, STATUS, DESTINATION, BINDING, TARGET, SCHEDULE
FROM V$ARCHIVE_DEST
WHERE STATUS != 'INACTIVE'
ORDER BY DEST_ID;

-- Archive-related parameters
SELECT NAME, VALUE
FROM V$PARAMETER
WHERE UPPER(NAME) LIKE '%ARCHIVE%'
  AND UPPER(NAME) NOT LIKE '%ARCHIVE_LAG%'
  AND UPPER(NAME) NOT LIKE '%STANDBY_ARCHIVE%'
  AND UPPER(NAME) NOT LIKE '%ARCHIVE_TARGET%';

-- Archive format
SELECT NAME, VALUE FROM V$PARAMETER
WHERE NAME = 'log_archive_format';

-- Recent archive logs (last 10)
SELECT SEQUENCE#, FIRST_TIME, NAME
FROM (SELECT SEQUENCE#, FIRST_TIME, NAME
      FROM V$ARCHIVED_LOG
      ORDER BY SEQUENCE# DESC)
WHERE ROWNUM <= 10;

-- Archive log count and total size
SELECT COUNT(*) AS ARCHIVE_COUNT,
       ROUND(SUM(BLOCKS*BLOCK_SIZE)/1024/1024/1024, 2) AS TOTAL_GB,
       MIN(FIRST_TIME) AS OLDEST,
       MAX(FIRST_TIME) AS NEWEST
FROM V$ARCHIVED_LOG;

-- ── Section 8: Fast Recovery Area (FRA) ────────────────────────────────────

SELECT NAME,
       ROUND(SPACE_USED/1024/1024/1024, 2) AS USED_GB,
       ROUND(SPACE_LIMIT/1024/1024/1024, 2) AS LIMIT_GB,
       ROUND(SPACE_USED/SPACE_LIMIT*100, 1) AS PCT_USED
FROM V$RECOVERY_FILE_DEST;

SELECT NAME, VALUE, ISDEFAULT
FROM V$PARAMETER
WHERE UPPER(NAME) LIKE '%DB_RECOVERY%'
   OR UPPER(NAME) LIKE '%RECOVERY_FILE_DEST%'
   OR UPPER(NAME) LIKE '%LOG_ARCHIVE_DEST%';

-- ── Section 9: RMAN Configuration ──────────────────────────────────────────

SELECT NAME, VALUE
FROM V$RMAN_CONFIGURATION
ORDER BY NAME;

-- Recent RMAN backup jobs (last 10)
SELECT SESSION_KEY, INPUT_TYPE, STATUS, START_TIME, END_TIME,
       ELAPSED_SECONDS/3600 AS ELAPSED_HOURS,
       INPUT_BYTES/1024/1024/1024 AS INPUT_GB,
       OUTPUT_BYTES/1024/1024/1024 AS OUTPUT_GB
FROM V$RMAN_BACKUP_JOB_DETAILS
ORDER BY START_TIME DESC
FETCH FIRST 10 ROWS ONLY;

-- ── Section 10: Non-Oracle Users ───────────────────────────────────────────

SELECT USERNAME, ACCOUNT_STATUS, DEFAULT_TABLESPACE,
       TEMPORARY_TABLESPACE, CREATED, PROFILE
FROM DBA_USERS
WHERE ORACLE_MAINTAINED = 'N'
ORDER BY USERNAME;

-- ── Section 11: ADR / Diagnostics ──────────────────────────────────────────

SELECT NAME, VALUE
FROM V$PARAMETER
WHERE UPPER(NAME) LIKE '%DIAGNOSTIC%'
   OR UPPER(NAME) LIKE '%ADR%';

-- ── Section 12: DBID ───────────────────────────────────────────────────────

-- DBID is visible in control file autobackup filenames:
-- Format: C-<DBID>-<YYYYMMDD>-<QQ>
-- E.g., C-3980112667-20260714-00 → DBID = 3980112667
-- Also available via:
-- SELECT DBID, NAME FROM V$DATABASE;
