WITH deletedfiles AS (select a.bucketname, a.key, a.version, a.eventname, a.eventtime
FROM   ( select key, bucketname, max(eventtime) maxeventtime
            FROM "$TABLE_NAME" WHERE eventtime <= '$END_TIME' AND eventname like 'Object Deleted'
            group by key, bucketname) b,
    "$TABLE_NAME" a
WHERE  a.key = b.key and a.bucketname = b.bucketname
AND a.eventtime = b.maxeventtime
order by key asc), 
newfiles
AS
(SELECT distinct bucketname, key FROM "$TABLE_NAME" WHERE (EventName like 'Object Created') and 
key not in (select key FROM "$TABLE_NAME" where eventtime <= '$END_TIME' ))
SELECT bucketname, key FROM deletedfiles WHERE key in (select key FROM "$TABLE_NAME" WHERE eventtime > '$END_TIME'  AND eventname like 'Object Created') UNION SELECT * FROM newfiles