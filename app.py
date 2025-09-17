\
    import io
import os
import uuid
from typing import List, Dict, Any

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from parsing.cv_parser import extract_cv_structured
from matching.matcher import compute_matches, candidate_text
from services.jobs import fetch_arbeitnow
from services.db import get_supabase, ensure_candidate, log_interest


    # --- Page Config & Theme ---
    st.set_page_config(page_title="AI Talent Marketplace — Candidate", layout="wide")

    CUSTOM_CSS = """
    <style>
    :root { --radius: 14px; }
    .block-container { padding-top: 1.5rem; }
    .kpi { border-radius: var(--radius); padding: 0.75rem 1rem; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); }
    .job-card { border-radius: var(--radius); padding: 1rem; border: 1px solid rgba(255,255,255,0.08); background: rgba(255,255,255,0.02); }
    .step { padding: 0.5rem 0.75rem; border-radius: 999px; margin-right: 0.5rem; font-weight: 600; opacity: 0.7; border: 1px solid rgba(255,255,255,0.12); }
    .step.active { opacity: 1; background: linear-gradient(90deg, rgba(0,150,255,0.25), rgba(114,137,218,0.25)); }
    .badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 999px; border: 1px solid rgba(255,255,255,0.12); font-size: 0.8rem; opacity: 0.85; }
    .small { opacity: 0.75; font-size: 0.9rem; }
    </style>
    """
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    load_dotenv()

    # --- Session State ---
    def _init_state():
        ss = st.session_state
        ss.setdefault("step", 1)
        ss.setdefault("raw_text", "")
        ss.setdefault("candidate", None)
        ss.setdefault("candidate_id", str(uuid.uuid4()))
        ss.setdefault("jobs_df", None)
        ss.setdefault("matches_df", None)
        ss.setdefault("interests", [])
        ss.setdefault("sb", get_supabase())

    _init_state()

    # --- Helpers ---
    STEPS = [
        (1, "Upload"), (2, "Review & Fix"), (3, "Matches"), (4, "Interests")
    ]

    def stepper():
        cols = st.columns(len(STEPS))
        for i, (num, label) in enumerate(STEPS):
            with cols[i]:
                cls = "step active" if st.session_state.step == num else "step"
                st.markdown(f"<div class='{cls}'> {num}. {label} </div>", unsafe_allow_html=True)


    def microcopy():
        st.info("We never share your CV. You’ll review everything before matching.")


    # --- Step 1: Upload ---

    def step_upload():
        st.subheader("1) Upload your CV")
        microcopy()
        file = st.file_uploader("Drop your CV (PDF/CSV/TXT)", type=["pdf", "csv", "txt"], accept_multiple_files=False)

        if file is not None:
            kind = file.type
            size = file.size
            text = ""

            if file.name.lower().endswith(".pdf"):
                from pypdf import PdfReader
                try:
                    reader = PdfReader(file)
                    pages = [p.extract_text() or "" for p in reader.pages]
                    text = "\n".join(pages)
                    st.toast("PDF parsed with pypdf", icon="✅")
                except Exception:
                    st.toast("Switched to pdfminer (better for this file)", icon="🛠️")
                    try:
                        text = _pdfminer_extract(file)
                    except Exception as e:
                        st.error(f"PDF parsing failed: {e}")
                        return
                if len(text.strip()) < 500:
                    # try pdfminer fallback if pypdf too short
                    try:
                        alt = _pdfminer_extract(file)
                        if len(alt.strip()) > len(text.strip()):
                            text = alt
                            st.toast("Used pdfminer for richer text", icon="🔁")
                    except Exception:
                        pass
                if len(text.strip()) < 200 and size > 200_000:
                    st.warning("This PDF looks scanned; please upload .txt or a PDF with selectable text.")

            elif file.name.lower().endswith(".csv"):
                try:
                    df = pd.read_csv(file)
                except Exception:
                    file.seek(0)
                    df = pd.read_csv(file, sep=";")
                text_col = None
                for c in df.columns:
                    if c.lower() in {"text", "cv_text", "resume", "profile"}:
                        text_col = c
                        break
                if text_col:
                    text = "\n\n".join(str(x) for x in df[text_col].fillna("").tolist())
                else:
                    text = "\n\n".join([" ".join(str(v) for v in row if pd.notna(v)) for row in df.values])
                st.toast("CSV ingested", icon="📄")

            elif file.name.lower().endswith(".txt"):
                bytes_data = file.read()
                try:
                    text = bytes_data.decode("utf-8")
                except UnicodeDecodeError:
                    text = bytes_data.decode("latin-1", errors="ignore")
                st.toast("TXT ingested", icon="📄")

            else:
                st.error("Unsupported file type.")
                return

            st.session_state.raw_text = text

            with st.expander("Preview extracted text", expanded=False):
                st.text_area("Raw CV Text", text, height=240)

            if st.button("Extract structured data", type="primary"):
                with st.spinner("Parsing your CV…"):
                    candidate = extract_cv_structured(text)
                # attach raw text for the editor
                candidate["raw_text"] = text
                st.session_state.candidate = candidate
                # optional Supabase upsert
                if st.session_state.sb:
                    try:
                        ensure_candidate(st.session_state.sb, st.session_state.candidate_id, text)
                    except Exception as e:
                        st.warning(f"Supabase upsert skipped: {e}")
                st.session_state.step = 2
                st.toast("Parsed! Review & fix next.", icon="📝")


    def _pdfminer_extract(file) -> str:
        file.seek(0)
        data = file.read()
        fh = io.BytesIO(data)
        from pdfminer.high_level import extract_text
        return extract_text(fh)


    # --- Step 2: Review & Fix ---

    def step_review():
        st.subheader("2) Review & Fix")
        cand = st.session_state.candidate
        if not cand:
            st.info("Upload a CV first.")
            return

        tab_struct, tab_raw = st.tabs(["Structured", "Raw text"])

        with tab_struct:
            _edit_structured(cand)
        with tab_raw:
            rt = st.text_area("Raw CV text", cand.get("raw_text", ""), height=300)
            st.session_state.candidate["raw_text"] = rt


    def _edit_structured(cand: Dict[str, Any]):
        with st.form(key="structured_form", clear_on_submit=False):
            st.markdown("### Personal info")
            pi = cand.get("personal_info", {})
            col1, col2, col3 = st.columns(3)
            with col1:
                pi["full_name"] = st.text_input("Full name", pi.get("full_name", ""))
                pi["email"] = st.text_input("Email", pi.get("email", ""))
            with col2:
                pi["phone"] = st.text_input("Phone", pi.get("phone", ""))
                pi["location"] = st.text_input("Location", pi.get("location", ""))
            with col3:
                links_str = ", ".join(pi.get("links", []))
                links_edit = st.text_input("Links (comma-separated)", links_str)
                pi["links"] = [x.strip() for x in links_edit.split(",") if x.strip()]
            cand["personal_info"] = pi

            st.markdown("### Summary")
            cand["summary"] = st.text_area("Professional summary", cand.get("summary", ""), height=100)

            st.markdown("### Experience")
            exp: List[Dict[str, Any]] = cand.get("experience", [])
            new_exp: List[Dict[str, Any]] = []
            for i, role in enumerate(exp):
                with st.expander(f"{role.get('title','(role)')} @ {role.get('company','')} ({role.get('start_date','?')} – {role.get('end_date','now')})", expanded=False):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        role["title"] = st.text_input(f"Title {i}", role.get("title", ""), key=f"t_{i}")
                        role["start_date"] = st.text_input(f"Start YYYY-MM {i}", role.get("start_date", ""), key=f"sd_{i}")
                    with c2:
                        role["company"] = st.text_input(f"Company {i}", role.get("company", ""), key=f"c_{i}")
                        role["end_date"] = st.text_input(f"End YYYY-MM or null {i}", str(role.get("end_date", "")), key=f"ed_{i}")
                    with c3:
                        role["location"] = st.text_input(f"Location {i}", role.get("location", ""), key=f"loc_{i}")
                        role["current"] = st.checkbox("Current role", value=bool(role.get("current", False)), key=f"cur_{i}")
                    bullets_text = "\n".join(role.get("bullets", []))
                    role["bullets"] = st.text_area("Impact bullets (one per line)", bullets_text, key=f"b_{i}").splitlines()
                    new_exp.append(role)
            if st.checkbox("Add a new experience role"):
                new_exp.append({"title": "", "company": "", "location": "", "start_date": "", "end_date": "", "current": False, "bullets": []})
            cand["experience"] = new_exp

            st.markdown("### Education")
            edu: List[Dict[str, Any]] = cand.get("education", [])
            new_edu: List[Dict[str, Any]] = []
            for i, ed in enumerate(edu):
                with st.expander(f"{ed.get('degree','(degree)')} – {ed.get('institution','')} ({ed.get('start_date','?')} – {ed.get('end_date','?')})", expanded=False):
                    cc1, cc2, cc3 = st.columns(3)
                    with cc1:
                        ed["degree"] = st.text_input(f"Degree {i}", ed.get("degree", ""), key=f"deg_{i}")
                        ed["start_date"] = st.text_input(f"Start YYYY-MM {i}", str(ed.get("start_date", "")), key=f"esd_{i}")
                    with cc2:
                        ed["field"] = st.text_input(f"Field {i}", ed.get("field", ""), key=f"fld_{i}")
                        ed["end_date"] = st.text_input(f"End YYYY-MM or null {i}", str(ed.get("end_date", "")), key=f"eed_{i}")
                    with cc3:
                        ed["institution"] = st.text_input(f"Institution {i}", ed.get("institution", ""), key=f"ins_{i}")
                        ed["location"] = st.text_input(f"Location {i}", ed.get("location", ""), key=f"eloc_{i}")
                    new_edu.append(ed)
            if st.checkbox("Add a new education block"):
                new_edu.append({"degree": "", "field": "", "institution": "", "start_date": "", "end_date": "", "location": ""})
            cand["education"] = new_edu

            st.markdown("### Skills & Languages")
            skills = cand.get("skills", {"hard": [], "tools": [], "soft": [], "languages": []})
            colh, colt = st.columns(2)
            with colh:
                hard_str = ", ".join(skills.get("hard", []))
                tools_str = ", ".join(skills.get("tools", []))
                skills["hard"] = [x.strip() for x in st.text_input("Hard skills (comma-separated)", hard_str).split(",") if x.strip()]
                skills["tools"] = [x.strip() for x in st.text_input("Tools (comma-separated)", tools_str).split(",") if x.strip()]
            with colt:
                soft_str = ", ".join(skills.get("soft", []))
                langs_str = ", ".join(skills.get("languages", []))
                skills["soft"] = [x.strip() for x in st.text_input("Soft skills (comma-separated)", soft_str).split(",") if x.strip()]
                skills["languages"] = [x.strip() for x in st.text_input("Languages (comma-separated)", langs_str).split(",") if x.strip()]
            cand["skills"] = skills

            st.markdown("### Certifications")
            certs_str = "\n".join(cand.get("certifications", []))
            cand["certifications"] = st.text_area("Certifications (one per line)", certs_str, height=80).splitlines()

            # Confidence notes
            meta = cand.get("meta", {"parser_version": "v1", "confidence_notes": []})
            if meta.get("confidence_notes"):
                st.markdown("**Confidence notes:**")
                for n in meta["confidence_notes"]:
                    st.markdown(f"- {n}")
            cand["meta"] = meta

            submitted = st.form_submit_button("Save & Continue →", type="primary")
            if submitted:
                st.session_state.candidate = cand
                if st.session_state.sb:
                    try:
                        ensure_candidate(st.session_state.sb, st.session_state.candidate_id, cand.get("raw_text", ""))
                    except Exception as e:
                        st.warning(f"Supabase upsert skipped: {e}")
                st.session_state.step = 3
                st.toast("Saved. Let’s find matches.", icon="✨")


    # --- Step 3: Matches ---

    def step_matches():
        st.subheader("3) Matches")
        cand = st.session_state.candidate
        if not cand:
            st.info("Upload a CV first.")
            return

        left, right = st.columns([1, 2])
        with left:
            st.markdown("#### Filters")
            top_n = st.slider("Top N", min_value=5, max_value=30, value=10, step=1)
            min_pct = st.slider("Min match %", min_value=0, max_value=100, value=40, step=5)
            loc_contains = st.text_input("Location contains", "")
            kw_contains = st.text_input("Keyword in title/desc", "")
            if st.button("Refresh matches"):
                st.session_state.matches_df = None

        with right:
            if st.session_state.jobs_df is None:
                with st.spinner("Fetching jobs from Arbeitnow…"):
                    st.session_state.jobs_df = fetch_arbeitnow()
            jobs_df = st.session_state.jobs_df
            if jobs_df is None or jobs_df.empty:
                st.warning("No jobs available right now. Try again later.")
                return

            if st.session_state.matches_df is None:
                with st.spinner("Computing scores…"):
                    matches = compute_matches(cand, jobs_df, top_n=100)
                st.session_state.matches_df = matches
            matches = st.session_state.matches_df.copy()

            # apply filters
            if loc_contains:
                matches = matches[matches["location"].str.contains(loc_contains, case=False, na=False)]
            if kw_contains:
                mask = matches["job_title"].str.contains(kw_contains, case=False, na=False) | matches["job_description"].str.contains(kw_contains, case=False, na=False)
                matches = matches[mask]
            matches = matches[matches["match_score"] * 100 >= min_pct]
            matches = matches.head(top_n)

            if matches.empty:
                st.info("Nothing hit your minimum match yet. Try lowering the threshold or clearing filters.")
                return

            for _, row in matches.iterrows():
                with st.container():
                    st.markdown(
                        """
                        <div class='job-card'>
                            <div style='display:flex; justify-content:space-between; align-items:center;'>
                                <div>
                                    <div style='font-size:1.1rem; font-weight:700;'>%s @ %s</div>
                                    <div class='small'>%s</div>
                                </div>
                                <div class='badge'>Match: %d%%</div>
                            </div>
                        </div>
                        """ % (row.job_title, row.company_name, row.location or "", int(row.match_score * 100)),
                        unsafe_allow_html=True,
                    )
                    st.write((row.job_description or "").strip()[:320] + ("…" if len((row.job_description or "")) > 320 else ""))
                    c1, c2, c3 = st.columns([1,1,6])
                    with c1:
                        st.link_button("View job", url=row.url, use_container_width=True)
                    with c2:
                        if st.button("I'm Interested", key=f"int_{hash(row.url)}"):
                            st.session_state.interests.append({
                                "job_title": row.job_title,
                                "company": row.company_name,
                                "url": row.url,
                                "location": row.location,
                                "source": row.source,
                                "match_score": float(row.match_score),
                            })
                            if st.session_state.sb:
                                try:
                                    log_interest(st.session_state.sb, st.session_state.candidate_id, row)
                                except Exception as e:
                                    st.warning(f"Supabase insert skipped: {e}")
                            st.toast("Interest logged", icon="📬")
                    st.divider()

            st.caption("Source: Arbeitnow API")

            st.markdown("### Why these matches?")
            st.write("We compute a TF‑IDF cosine similarity between your consolidated profile text and each job’s title+description. In Phase‑2 this will expand to an explainable breakdown by skills, experience, education, and location.")

            with st.expander("Show my profile text used for matching"):
                st.text_area("Profile text", candidate_text(cand), height=200)

            st.markdown("\n")


    # --- Step 4: Interests ---

    def step_interests():
        st.subheader("4) Interests")
        items = st.session_state.interests
        if not items:
            st.info("You haven’t expressed interest in any roles yet.")
            return
        df = pd.DataFrame(items)
        st.dataframe(df, use_container_width=True, hide_index=True)


    # --- Router ---
    stepper()

    if st.session_state.step == 1:
        step_upload()
    elif st.session_state.step == 2:
        step_review()
    elif st.session_state.step == 3:
        step_matches()
    else:
        step_interests()

    # Footer note
    st.caption("No feed, no spam, no friction — just high‑signal matches.")
