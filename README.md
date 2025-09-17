# AI Talent Marketplace — Streamlit Candidate MVP

## Quickstart
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # add Supabase creds (optional)
streamlit run app.py
```

## Deploy to Streamlit Community Cloud
1. Push this folder to a new GitHub repo.
2. On https://share.streamlit.io, deploy the repo. Set:
   - Main file: `app.py`
   - Python version: 3.10+
   - Secrets: add `SUPABASE_URL` and `SUPABASE_KEY` (optional)
3. Click **Deploy**.

## Supabase (optional)
Run the following SQL in the Supabase SQL editor:
```sql
create table if not exists candidates (
  id uuid primary key,
  cv_text text,
  created_at timestamptz default now()
);

create table if not exists interests (
  id bigserial primary key,
  candidate_id uuid references candidates(id),
  job_title text,
  company text,
  url text,
  location text,
  source text,
  match_score double precision,
  created_at timestamptz default now()
);

create index if not exists interests_candidate_created_idx on interests (candidate_id, created_at desc);
```

## Notes
- If Supabase creds are not set, the app still works; interest logs stay in session only.
- Arbeitnow API is fetched with a light retry and dedupe.
