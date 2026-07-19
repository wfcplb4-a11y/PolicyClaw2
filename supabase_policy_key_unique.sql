-- Run this in Supabase SQL Editor before enabling UPSERT writes.
-- It verifies duplicate policy_key values first, then creates the unique index
-- required by db_utils.py upsert(..., on_conflict="policy_key").

select
    policy_key,
    count(*) as duplicate_count
from policyclaw2
where policy_key is not null
group by policy_key
having count(*) > 1
order by duplicate_count desc;

create unique index if not exists policyclaw2_policy_key_full_unique_idx
on policyclaw2 (policy_key);
