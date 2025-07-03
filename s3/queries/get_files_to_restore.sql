WITH versionAtTS AS 
(select a.bucketname, a.key, a.version, a.eventname, a.eventtime, a.sequencer
from   ( select key, bucketname, max(eventtime) maxeventtime
        from "$TABLE_NAME" where eventtime <= '$SNAPSHOT_END_TIME'
        group by key, bucketname) b,
    "$TABLE_NAME" a
where  a.key = b.key and a.bucketname = b.bucketname
and a.eventtime = b.maxeventtime order by key asc),
latestVersion AS
(select a.bucketname, a.key, a.version, a.eventname, a.eventtime, a.sequencer
from   ( select key, bucketname, max(eventtime) maxeventtime
        from "$TABLE_NAME"
        group by key, bucketname) b,
    "$TABLE_NAME" a
where  a.key = b.key and a.bucketname = b.bucketname
and a.eventtime = b.maxeventtime order by key asc),
copylist AS
(select bucketname, key, version, sequencer from versionAtTS where key not like '' and eventname not like 'Object Deleted' and version not in (select version from latestVersion))
select * from copylist