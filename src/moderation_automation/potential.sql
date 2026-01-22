--.mode table
--.header on
with users as 
(
   select
      m.username as username,
      coalesce(max(b.created_utc), 0) as last_ban
   from mod_removed as m
   left join banned as b 
      on m.username = b.username
   where
      m.created_utc > unixepoch('now', '-30 days') 
      and m.username != "[deleted]" 
   group by m.username
)
select
   u.username,
   u.last_ban,
   count(distinct b.created_utc) as n_ban,
   count(distinct m.target) as mod_count,
   count(distinct m.post) as mod_count_post,
   count(distinct r.target) as reddit_count,
   count(distinct r.post) as reddit_count_post,
   count(distinct r.target) + count(distinct m.target) as total_count
   -- I2-(1-J2/I2)*(I2+J2)/2
from users as u 
   left join banned as b 
      on b.username = u.username
   left join reddit_removed as r 
      on r.username = u.username 
      and r.created_utc > max(unixepoch('now', '-50 days'), last_ban) 
   left join mod_removed as m 
      on m.username = u.username 
      and m.created_utc > max(unixepoch('now', '-50 days'), last_ban) 
      and not exists (
         select id
         from reddit_removed
         where reddit_removed.username = m.username
            and reddit_removed.target = m.target
      )
group by u.username 
having
   count(distinct m.target) + count(distinct r.target) > 3;