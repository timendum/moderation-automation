--.mode table
--.header on
select
   m.created_utc as created_utc,
   m.target as comment_id,
   m.post as post_id,
   '0' as reddit
from mod_removed as m
   left join banned as b 
      on b.username = m.username
   where
      m.username = ?
      and m.created_utc > max(unixepoch('now', '-50 days'), coalesce(b.created_utc, 0)) 
      and not exists 
        (select id from reddit_removed where reddit_removed.username = m.username and reddit_removed.target = m.target)
UNION
select
   m.created_utc as created_utc,
   m.target as comment_id,
   m.post as post_id,
   '1' as reddit
from reddit_removed as m
   left join banned as b 
      on b.username = m.username
   where
      m.username = ?
      and m.created_utc > max(unixepoch('now', '-50 days'), coalesce(b.created_utc, 0));