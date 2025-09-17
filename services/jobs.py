\
    from typing import List, Dict
    import time
    import requests
    import pandas as pd

    API_URL = "https://arbeitnow.com/api/job-board-api"

    def fetch_arbeitnow() -> pd.DataFrame:
        """Fetch jobs from Arbeitnow API with simple retry & dedupe."""
        jobs: List[Dict] = []
        url = API_URL
        tries = 0
        while url and tries < 5:
            tries += 1
            try:
                r = requests.get(url, timeout=10)
                r.raise_for_status()
                data = r.json()
                items = data.get("data", [])
                for it in items:
                    jobs.append({
                        "job_title": it.get("title"),
                        "company_name": it.get("company_name"),
                        "location": it.get("location"),
                        "url": it.get("url"),
                        "job_description": it.get("description"),
                        "source": "arbeitnow",
                    })
                url = data.get("links", {}).get("next")
                time.sleep(0.2)
            except Exception:
                break
        if not jobs:
            return pd.DataFrame(columns=["job_title", "company_name", "location", "url", "job_description", "source"]) 
        df = pd.DataFrame(jobs)
        df.drop_duplicates(subset=["url"], inplace=True)
        return df
