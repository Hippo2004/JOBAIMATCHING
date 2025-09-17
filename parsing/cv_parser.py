\
    import re
    from typing import Dict, Any, List

    from .normalizers import normalize_text, normalize_date_range

    SECTION_HEADERS = {
        "experience": re.compile(r"^(experience|professional experience|work|employment|expérience|stages|internships)$", re.IGNORECASE),
        "education": re.compile(r"^(education|academic|études|formation)$", re.IGNORECASE),
        "skills": re.compile(r"^(skills|technical|competence|compétences|competences)$", re.IGNORECASE),
        "certifications": re.compile(r"^(certifications?|licenses?)$", re.IGNORECASE),
        "summary": re.compile(r"^(summary|profile)$", re.IGNORECASE),
        "languages": re.compile(r"^(languages?|langues?)$", re.IGNORECASE),
    }

    EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    PHONE_RE = re.compile(r"(?:(?:\+\d{1,3}[\s-]?)?(?:\(\d{1,4}\)[\s-]?)?\d[\d\s-]{7,}\d)")
    URL_RE = re.compile(r"https?://[^\s)]+|(?:www\.)?linkedin\.com/[^\s)]+|(?:www\.)?github\.com/[^\s)]+", re.IGNORECASE)
    NAME_LINE_RE = re.compile(r"^[A-Z][A-Za-z\-']+(?:\s+[A-Z][A-Za-z\-']+){1,3}$")
    LOC_LINE_RE = re.compile(r"^[A-Z][a-zA-Z\-\' ]+,\s*[A-Z][a-zA-Z\-\' ]+$")

    ROLE_SPLIT_RE = re.compile(r"\n\n+")
    TITLE_PATTERNS = [
        re.compile(r"^(?P<title>[^@\-|•\n]+?)\s*[–\-—|@]\s*(?P<company>[^\n|\-–—]+?)(?:\s*[–\-—|]\s*(?P<location>[^\n]+))?$"),
        re.compile(r"^(?P<title>.+?)\s+at\s+(?P<company>[^,\n]+)(?:,\s*(?P<location>[^\n]+))?", re.IGNORECASE),
    ]

    def extract_cv_structured(raw_text: str) -> Dict[str, Any]:
        text = normalize_text(raw_text or "")

        sections = split_sections(text)

        personal_info = parse_personal_info(text)
        summary = sections.get("summary", "") or infer_summary(text)
        experience = parse_experience(sections.get("experience", ""))
        education = parse_education(sections.get("education", ""))
        skills = parse_skills(sections.get("skills", ""), sections.get("languages", ""))
        certifications = parse_certifications(sections.get("certifications", ""))

        confidence_notes = []
        if not experience and not education:
            confidence_notes.append("No clear experience or education section detected.")
        for r in experience:
            sd, ed = r.get("start_date"), r.get("end_date")
            if sd and ed and ed < sd:
                r["end_date"] = None
                confidence_notes.append(f"Swapped invalid date range for {r.get('title','a role')} at {r.get('company','?')}")
            if not ed and not r.get("current"):
                confidence_notes.append(f"End date missing for {r.get('title','a role')} at {r.get('company','?')}")

        candidate: Dict[str, Any] = {
            "personal_info": personal_info,
            "summary": summary,
            "experience": experience,
            "education": education,
            "skills": skills,
            "certifications": certifications,
            "raw_text": text,
            "meta": {"parser_version": "v1", "confidence_notes": confidence_notes},
        }
        return candidate

    def split_sections(text: str) -> Dict[str, str]:
        lines = [l.strip() for l in text.splitlines()]
        buckets: Dict[str, List[str]] = {k: [] for k in SECTION_HEADERS}
        current = None
        for i, line in enumerate(lines):
            if not line:
                continue
            # detect header
            for key, rx in SECTION_HEADERS.items():
                if rx.match(line):
                    current = key
                    # add a visual separator in bucket
                    if buckets[current] and buckets[current][-1] != "":
                        buckets[current].append("")
                    break
            else:
                if current:
                    buckets[current].append(line)
        return {k: "\n".join(v).strip() for k, v in buckets.items() if v}

    def infer_summary(text: str) -> str:
        # first 10-12 non-empty lines
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        return " ".join(lines[:12])

    def parse_personal_info(text: str) -> Dict[str, Any]:
        email = (EMAIL_RE.search(text) or [None])[0]
        phone = (PHONE_RE.search(text) or [None])[0]
        links = list(dict.fromkeys(URL_RE.findall(text)))
        # name: guess from first 10 lines
        name = None
        location = None
        for l in text.splitlines()[:12]:
            if not name and NAME_LINE_RE.match(l):
                name = l
            if not location and LOC_LINE_RE.match(l):
                location = l
        return {
            "full_name": name or "",
            "email": email or "",
            "phone": phone or "",
            "location": location or "",
            "links": links,
        }

    def parse_experience(block: str) -> List[Dict[str, Any]]:
        if not block:
            return []
        roles: List[Dict[str, Any]] = []
        chunks = [c.strip() for c in re.split(r"\n\n+", block) if c.strip()]
        for ch in chunks:
            lines = ch.splitlines()
            header = lines[0]
            title, company, location = None, None, None
            for pat in TITLE_PATTERNS:
                m = pat.match(header)
                if m:
                    gd = m.groupdict()
                    title = gd.get("title")
                    company = gd.get("company")
                    location = gd.get("location")
                    break
            if not title:
                # try alternative: first line as title, next as company
                title = header
                if len(lines) > 1:
                    company = lines[1]
            sd, ed = normalize_date_range(ch)
            current = (ed is None and ("present" in ch.lower() or "current" in ch.lower()))
            bullets = [l[2:].strip() if l.strip().startswith("- ") else l.strip() for l in lines[1:]]
            bullets = [b for b in bullets if b]
            roles.append({
                "title": (title or "").strip(),
                "company": (company or "").strip(),
                "location": (location or "").strip(),
                "start_date": sd,
                "end_date": ed,
                "current": current,
                "bullets": bullets,
            })
        return roles

    def parse_education(block: str) -> List[Dict[str, Any]]:
        if not block:
            return []
        entries: List[Dict[str, Any]] = []
        chunks = [c.strip() for c in re.split(r"\n\n+", block) if c.strip()]
        for ch in chunks:
            lines = [l.strip() for l in ch.splitlines() if l.strip()]
            text = " ".join(lines)
            sd, ed = normalize_date_range(text)
            # heuristics: find degree and institution
            degree = None
            inst = None
            deg_tokens = ["bsc", "msc", "mba", "ba", "phd", "bachelor", "master", "licence", "bba", "ib", "myp"]
            for l in lines:
                if any(t in l.lower() for t in deg_tokens):
                    degree = l
                    break
            inst_candidates = [l for l in lines if any(x in l.lower() for x in ["university", "school", "college", "institut", "école", "ecole"])]
            if inst_candidates:
                inst = inst_candidates[0]
            entries.append({
                "degree": degree or (lines[0] if lines else ""),
                "field": "",
                "institution": inst or (lines[1] if len(lines) > 1 else ""),
                "start_date": sd,
                "end_date": ed,
                "location": "",
            })
        return entries

    def parse_skills(sk_block: str, lang_block: str) -> Dict[str, List[str]]:
        hard, tools, soft, langs = [], [], [], []
        def _split(text: str) -> List[str]:
            items = re.split(r",|\n|•|-|—|;|/|\\|", text)
            return [i.strip() for i in items if i and len(i.strip()) < 64]

        if sk_block:
            items = _split(sk_block)
            for it in items:
                low = it.lower()
                if any(k in low for k in ["excel", "salesforce", "python", "sql", "powerpoint", "word", "notion", "figma", "tensorflow", "pytorch", "streamlit", "sklearn", "lemlist"]):
                    tools.append(it)
                elif any(k in low for k in ["communication", "leadership", "team", "problem", "organized", "creative"]):
                    soft.append(it)
                else:
                    hard.append(it)
        if lang_block:
            langs.extend(_split(lang_block))
        return {"hard": dedupe(hard), "tools": dedupe(tools), "soft": dedupe(soft), "languages": dedupe(langs)}

    def parse_certifications(block: str) -> List[str]:
        if not block:
            return []
        items = [l.strip("- •\t ") for l in block.splitlines() if l.strip()]
        return dedupe(items)

    def dedupe(xs: List[str]) -> List[str]:
        seen = set()
        out = []
        for x in xs:
            xl = x.lower()
            if xl not in seen:
                out.append(x)
                seen.add(xl)
        return out
