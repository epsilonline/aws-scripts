WITH StateAtSnapshot AS (
    SELECT bucketname, key, eventname AS last_event_type_at_snapshot, eventtime AS last_event_time_at_snapshot
    FROM (
        SELECT bucketname, key, eventname, eventtime, ROW_NUMBER() OVER (PARTITION BY bucketname, key ORDER BY eventtime DESC) as rn
        FROM "$TABLE_NAME"
        WHERE eventtime <= '$SNAPSHOT_END_TIME'
    ) AS sub
    WHERE rn = 1
),
CurrentState AS (
    SELECT bucketname, key, eventname AS current_last_event_type, eventtime AS current_last_event_time
    FROM (
        SELECT bucketname, key, eventname, eventtime, ROW_NUMBER() OVER (PARTITION BY bucketname, key ORDER BY eventtime DESC) as rn
        FROM "$TABLE_NAME"
    ) AS sub
    WHERE rn = 1
)
SELECT
    cs.bucketname, cs.key, 'DELETED_SINCE_SNAPSHOT' AS status
FROM CurrentState cs LEFT JOIN StateAtSnapshot sas ON cs.bucketname = sas.bucketname AND cs.key = sas.key
WHERE cs.current_last_event_type LIKE 'Object Deleted' AND (sas.key IS NOT NULL AND sas.last_event_type_at_snapshot LIKE 'Object Created') AND cs.current_last_event_time > '2025-07-01T08:32:47Z'
UNION ALL
SELECT
    cs.bucketname,
    cs.key,
    'NEWLY_CREATED_SINCE_SNAPSHOT' AS status
FROM CurrentState cs
LEFT JOIN StateAtSnapshot sas
    ON cs.bucketname = sas.bucketname AND cs.key = sas.key
WHERE cs.current_last_event_type LIKE 'Object Created'
  AND (sas.key IS NULL OR sas.last_event_type_at_snapshot LIKE 'Object Deleted')
  AND cs.current_last_event_time > '$SNAPSHOT_END_TIME'