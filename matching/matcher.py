from typing import Dict, Any
import pandas as pd

def candidate_text(candidate: Dict[str, Any]) -> str:
    parts = []
    parts.append(candidate.get("summary", ""))

    skills = candidate.get("skills", {})
    for k in ["hard", "tools", "soft", "languages"]:
        parts.append(" ".join(skills.get(k, [])))

    for r in candidate.get("experience", []):
        parts.append(" ".join([r.get("title", ""), r.get("company", ""), r.get("location", "")]))
        parts.extend(r.get("bullets", []))

    for e in candidate.get("education", []):
        parts.append(" ".join([e.get("degree", ""), e.get("institution", ""), e.get("location", "")]))

    return "\n".join([p for p in parts if p])

def compute_matches(candidate: Dict[str, Any], jobs_df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    text = candidate_text(candidate)
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except Exception:
        return _fallback_matches(text, jobs_df, top_n)

    docs = [text] + (jobs_df["job_title"].fillna("") + "\n" + jobs_df["job_description"].fillna("")).tolist()
    vectorizer = TfidfVectorizer(max_features=30000, ngram_range=(1, 2), stop_words="english")
    X = vectorizer.fit_transform(docs)
    sims = cosine_similarity(X[0:1], X[1:]).flatten()

    out = jobs_df.copy().reset_index(drop=True)
    out["match_score"] = sims
    out.sort_values("match_score", ascending=False, inplace=True)
    return out.head(top_n)

def _fallback_matches(text: str, jobs_df: pd.DataFrame, top_n: int) -> pd.DataFrame:
    import re
    def toks(s: str):
        return set(re.findall(r"[a-zA-Z0-9_]+", (s or "").lower()))
    a = toks(text)
    sims = []
    for _, row in jobs_df.iterrows():
        b = toks((row.get("job_title") or "") + " " + (row.get("job_description") or ""))
        sims.append(0.0 if not a or not b else len(a & b) / len(a | b))
    out = jobs_df.copy().reset_index(drop=True)
    out["match_score"] = sims
    out.sort_values("match_score", ascending=False, inplace=True)
    return out.head(top_n)

