\
    import re
    from typing import Tuple, Optional
    import dateparser

    HYPHEN_RE = re.compile(r"(\w)-\n(\w)")
    BULLET_VARIANTS = ["•", "-", "—", "–", "*", "·"]
    BULLET_RE = re.compile(r"^[\s]*[" + "".join(re.escape(b) for b in BULLET_VARIANTS) + r"]\s+", re.MULTILINE)
    MULTISPACES_RE = re.compile(r"[ \t]+")
    NEWLINES_RE = re.compile(r"\n{3,}")
    SMART_QUOTES = {
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-"
    }

    MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|janvier|février|mars|avril|mai|juin|juil|août|septembre|octobre|novembre|décembre"
    DATE_RANGE_RE = re.compile(
        rf"((?:{MONTHS})?\s?\d{{4}}|(?:{MONTHS})\s\d{{4}})\s*(?:–|-|to|—)\s*(present|ongoing|now|today|(?:{MONTHS})?\s?\d{{4}})",
        re.IGNORECASE,
    )
    DATE_SINGLE_RE = re.compile(rf"(?:{MONTHS})\s\d{{4}}|\d{{4}}", re.IGNORECASE)

    def normalize_quotes_dashes(txt: str) -> str:
        for k, v in SMART_QUOTES.items():
            txt = txt.replace(k, v)
        return txt

    def fix_hyphenation(txt: str) -> str:
        return HYPHEN_RE.sub(r"\1\2", txt)

    def unify_bullets(txt: str) -> str:
        # Replace any bullet char at line start with a single '- '
        return BULLET_RE.sub("- ", txt)

    def collapse_whitespace(txt: str) -> str:
        txt = MULTISPACES_RE.sub(" ", txt)
        txt = NEWLINES_RE.sub("\n\n", txt)
        return txt.strip()

    def normalize_text(txt: str) -> str:
        return collapse_whitespace(unify_bullets(fix_hyphenation(normalize_quotes_dashes(txt))))

    def parse_ym(s: str) -> Optional[str]:
        if not s:
            return None
        dt = dateparser.parse(s, settings={"PREFER_DAY_OF_MONTH": "first"})
        if not dt:
            return None
        return f"{dt.year:04d}-{dt.month:02d}"

    def normalize_date_range(text: str) -> Tuple[Optional[str], Optional[str]]:
        # Finds first range; callers can run per block
        m = DATE_RANGE_RE.search(text)
        if not m:
            # try single date extraction
            singles = DATE_SINGLE_RE.findall(text)
            if not singles:
                return None, None
            start = parse_ym(singles[0])
            end = parse_ym(singles[1]) if len(singles) > 1 else None
            return start, end
        start_raw, end_raw = m.group(1), m.group(2)
        start = parse_ym(start_raw)
        end = None if end_raw.lower() in {"present", "ongoing", "now", "today"} else parse_ym(end_raw)
        return start, end
