\
    import re
    from parsing.cv_parser import extract_cv_structured

    SAMPLE = """
    HIPPOLYTE GUERMONPREZ
    Paris, France
    Email: guermonprez.hippolyte@gmail.com  |  Phone: +33 7 45 22 25 97
    LinkedIn: linkedin.com/in/hippolyte-guermonprez

    SUMMARY
    Second-year BBA at Paris School of Business; bilingual FR/EN; sales development and client relationship; seeking part-time fintech sales role.

    PROFESSIONAL EXPERIENCE
    Sales Development Representative (Intern) – Lemonway – Paris
    APR 2025 – AUG 2025
    - Built and enriched prospect lists with Salesforce & LinkedIn Sales Navigator
    - Cleaned CRM data (DQI) to improve data quality

    Community Manager (Intern) – Intello – Paris
    FEB 2024 – FEB 2024
    - Community growth and engagement

    Association Founder | Social Pets UAE – Dubai, UAE
    2019 – 2021
    - Built a 3,000+ member adoption community during COVID

    EDUCATION
    Paris School of Business – BBA – Paris
    JAN 2024 –
    EU Business School – Business Bridging Program – Barcelona
    2023 – 2024

    COMPETENCE
    B2B sales, Lead generation, Cold emailing, Digital marketing
    Salesforce, LinkedIn Sales Navigator, Lemlist

    LANGUAGES
    French (mother tongue), English (perfectly fluent), Spanish (B1)

    AWARD
    1st Place – Techstars Startup Weekend – NOV 2023
    """

    def test_parser_core():
        d = extract_cv_structured(SAMPLE)
        assert d["personal_info"]["email"] == "guermonprez.hippolyte@gmail.com"
        assert any(r["company"].lower() == "lemonway" for r in d["experience"])  # finds Lemonway
        assert len(d["skills"]["hard"]) >= 2
        # Dates normalized
        lemon = [r for r in d["experience"] if r["company"].lower() == "lemonway"][0]
        assert re.match(r"\d{4}-\d{2}", lemon["start_date"]) or lemon["start_date"] is None
