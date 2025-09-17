\
    import os
    from typing import Optional

    import pandas as pd

    try:
        from supabase import create_client, Client
    except Exception:
        create_client = None
        Client = None  # type: ignore

    def get_supabase() -> Optional["Client"]:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key or not create_client:
            return None
        try:
            sb = create_client(url, key)
            return sb
        except Exception:
            return None

    def ensure_candidate(sb: "Client", candidate_id: str, cv_text: str) -> None:
        """Upsert candidate row. If table missing, this will raise; caller can ignore."""
        sb.table("candidates").upsert({"id": candidate_id, "cv_text": cv_text}).execute()

    def log_interest(sb: "Client", candidate_id: str, job_row: pd.Series) -> None:
        payload = {
            "candidate_id": candidate_id,
            "job_title": job_row.get("job_title"),
            "company": job_row.get("company_name"),
            "url": job_row.get("url"),
            "location": job_row.get("location"),
            "source": job_row.get("source", "arbeitnow"),
            "match_score": float(job_row.get("match_score", 0.0)),
        }
        sb.table("interests").insert(payload).execute()
