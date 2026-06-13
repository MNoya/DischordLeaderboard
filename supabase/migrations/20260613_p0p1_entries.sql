create table p0p1_entries (
  user_id    uuid        not null references auth.users(id) on delete cascade,
  set_code   text        not null,
  slot       text        not null,
  card_name  text        not null,
  updated_at timestamptz not null default now(),
  primary key (user_id, set_code, slot)
);

alter table p0p1_entries enable row level security;

create policy "Users can read own entries"
  on p0p1_entries for select
  using (auth.uid() = user_id);

create policy "Users can insert own entries"
  on p0p1_entries for insert
  with check (auth.uid() = user_id);

create policy "Users can update own entries"
  on p0p1_entries for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy "Users can delete own entries"
  on p0p1_entries for delete
  using (auth.uid() = user_id);
