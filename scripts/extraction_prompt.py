EXTRACTION_PROMPT = """\
You are a scholarship data extraction engine. Extract structured scholarship
information from the provided HTML page and return it as a single valid JSON
object.

Return ONLY the JSON object. Do not wrap it in markdown code fences.
Do not add any explanation, preamble, or trailing text. The first character
of your response must be "{{" and the last must be "}}".

If a field cannot be found on the page, use null for scalar fields and an
empty array [] for list fields. Never invent values.

The source URL of the page is:
{url}

Extract the following fields:

- title: string. The name of the scholarship.
- provider: string. The organisation offering the scholarship.
- source_url: string. Must be exactly: {url}
- application_url: string. Direct apply/application link if different from source_url, else null.
- description: string. Full description of the scholarship.
- short_summary: string. A 1-3 sentence summary. If absent, write one yourself from the description.
- application_deadline: string. ISO date "YYYY-MM-DD" if parseable, otherwise the raw text as seen on the page.
- program_start_date: string. ISO date "YYYY-MM-DD" if parseable, otherwise raw text, else null.
- status: string. One of "open", "closed", "results_out", "unknown". Infer from deadline and page wording.
- eligible_nationalities: array of strings. List of eligible countries. Use ["all"] if open to everyone.
- eligible_study_levels: array of strings. e.g. ["Bachelors", "Masters", "PhD", "Postdoc"].
- min_gpa: number. Minimum GPA requirement, else null.
- gpa_scale: string. The GPA scale, e.g. "4.0" or "5.0", else null.
- eligible_fields_of_study: array of strings. List of eligible fields. Use ["any"] if no restriction.
- age_limit_max: number. Maximum age if stated, else null.
- financial_need_required: boolean. true if need-based, false otherwise.
- study_destinations: array of strings. Countries where the scholarship can be used.
- funding_details: string. What is covered (tuition, stipend, travel, accommodation, etc.).
- funding_amount_approx: object. Structured funding info. Use one of:
    - {{"raw": "Full tuition + $15,000 stipend"}} when you cannot quantify precisely, OR
    - {{"type": "full_tuition_plus_stipend", "stipend_usd": 15000}} when you can break it down.
  Include any keys that apply: type, amount_usd, max_amount_usd, stipend_usd, currency, raw.
- number_of_awards: number. How many awards/scholarships are given, else null.
- eligibility_details: string. Full eligibility text.
- required_documents: string. Documents required to apply.
- selection_criteria: string. How candidates are selected.
- benefits: string. What the scholarship provides.
- notes_for_applicants: string. Any extra notes or warnings for applicants.
- tags: array of strings. Useful tags e.g. ["fully_funded", "masters", "developing_countries"].

Remember: ONLY valid JSON. No markdown. No explanation. null for unknown scalars, [] for unknown lists.

HTML:
{html}
"""
