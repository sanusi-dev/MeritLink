import json
import os
import sys
import time
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from google.genai.errors import APIError
from groq import Groq
from groq import APIStatusError
from scripts.extraction_prompt import EXTRACTION_PROMPT


class FundingAmountDetails(BaseModel):
    type: Optional[str] = Field(None, description="e.g. 'full_tuition_plus_stipend'")
    amount_usd: Optional[float] = Field(None, description="Precise amount in USD")
    max_amount_usd: Optional[float] = Field(None, description="Maximum amount in USD")
    stipend_usd: Optional[float] = Field(None, description="Stipend value in USD")
    currency: Optional[str] = Field(None, description="Currency denomination")
    raw: Optional[str] = Field(None, description="Unquantifiable string statement")


class ScholarshipSchema(BaseModel):
    title: str = Field(description="The name of the scholarship.")
    provider: str = Field(description="The organisation offering the scholarship.")
    source_url: str = Field(description="Must match the original URL input.")
    application_url: Optional[str] = Field(
        None, description="Direct application link if different from source_url."
    )
    description: str = Field(description="Full description of the scholarship.")
    short_summary: str = Field(
        description="A 1-3 sentence summary. Write one from description if absent."
    )
    application_deadline: str = Field(
        description="ISO date 'YYYY-MM-DD' if parseable, otherwise the raw text."
    )
    program_start_date: Optional[str] = Field(
        None, description="ISO date 'YYYY-MM-DD' if parseable, otherwise raw text."
    )
    status: Literal["open", "closed", "results_out", "unknown"] = Field(
        description="Inferred status."
    )
    eligible_nationalities: List[str] = Field(
        default_factory=list,
        description="List of eligible countries. Use ['all'] if open to everyone.",
    )
    eligible_study_levels: List[str] = Field(
        default_factory=list,
        description="e.g. ['Bachelors', 'Masters', 'PhD', 'Postdoc'].",
    )
    min_gpa: Optional[float] = Field(None, description="Minimum GPA requirement.")
    gpa_scale: Optional[str] = Field(
        None, description="The GPA scale, e.g. '4.0' or '5.0'."
    )
    eligible_fields_of_study: List[str] = Field(
        default_factory=list,
        description="List of eligible fields. Use ['any'] if no restriction.",
    )
    age_limit_max: Optional[float] = Field(None, description="Maximum age if stated.")
    financial_need_required: bool = Field(
        description="True if need-based, false otherwise."
    )
    study_destinations: List[str] = Field(
        default_factory=list, description="Countries where the scholarship can be used."
    )
    funding_details: str = Field(
        description="What is covered (tuition, stipend, travel, etc.)."
    )
    funding_amount_approx: FundingAmountDetails = Field(
        default_factory=FundingAmountDetails,
        description="Structured funding info mapping the nested rules.",
    )
    number_of_awards: Optional[int] = Field(
        None, description="How many awards/scholarships are given."
    )
    eligibility_details: str = Field(description="Full eligibility text.")
    required_documents: str = Field(description="Documents required to apply.")
    selection_criteria: str = Field(description="How candidates are selected.")
    benefits: str = Field(description="What the scholarship provides.")
    notes_for_applicants: str = Field(
        description="Any extra notes or warnings for applicants."
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Useful tags e.g. ['fully_funded', 'masters'].",
    )


def extract_with_llm(html: str, url: str) -> dict[str, Any]:
    """
    Extract scholarship data from HTML using Gemini (primary) with Groq fallback.
    Returns parsed JSON dict. Raises RuntimeError if both providers fail completely.
    """
    prompt = EXTRACTION_PROMPT.format(html=html, url=url)

    gemini_error: str | None = None
    try:
        # Retries schema validation up to 3 times; bypasses immediately on rate limit
        return _extract_with_gemini(prompt, url, max_retries=3)
    except Exception as exc:
        gemini_error = f"{type(exc).__name__}: {exc}"
        print(f"Gemini pipeline failed: {gemini_error}", file=sys.stderr)

    try:
        # Secondary fallback engine if Gemini goes offline or runs dry
        return _extract_with_groq(prompt, url, max_retries=3)
    except Exception as exc:
        groq_error = f"{type(exc).__name__}: {exc}"
        print(f"Groq pipeline failed: {groq_error}", file=sys.stderr)
        raise RuntimeError(
            f"Both LLM providers failed. Gemini: {gemini_error} | Groq: {groq_error}"
        )


def _extract_with_gemini(prompt: str, url: str, max_retries: int) -> dict[str, Any]:
    """Extract scholarship data using Gemini with format retries & immediate quota failover."""
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ScholarshipSchema,
                ),
            )
            return _parse_json_response(response.text, provider="gemini", url=url)

        except (ValueError, TypeError) as schema_err:
            print(
                f"Gemini validation error (Attempt {attempt}/{max_retries}): {schema_err}",
                file=sys.stderr,
            )
            if attempt == max_retries:
                raise
            time.sleep(1)

        except APIError as api_err:
            # Catch 429 Rate limits and Quota Exhausted immediately, no retry
            print(
                f"Gemini API quota/network error, swapping provider instantly: {api_err}",
                file=sys.stderr,
            )
            raise

    raise RuntimeError(
        f"Gemini extraction exhausted without a result (max_retries={max_retries})"
    )


def _extract_with_groq(prompt: str, url: str, max_retries: int) -> dict[str, Any]:
    """Extract scholarship data using Groq Llama 3.3 with format retries & immediate quota failover."""
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    for attempt in range(1, max_retries + 1):
        try:
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a scholarship data extraction engine. "
                            "Return ONLY a valid JSON object matching requested parameters. "
                            "No markdown, no explanations."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            # Use choice elements securely
            return _parse_json_response(
                completion.choices[0].message.content, provider="groq", url=url
            )

        except (ValueError, TypeError) as schema_err:
            print(
                f"Groq validation error (Attempt {attempt}/{max_retries}): {schema_err}",
                file=sys.stderr,
            )
            if attempt == max_retries:
                raise
            time.sleep(1)

        except APIStatusError as api_err:
            # Catch 429/413 Groq limits instantly, no retry
            print(f"Groq API quota/network error: {api_err}", file=sys.stderr)
            raise

    raise RuntimeError(
        f"Groq extraction exhausted without a result (max_retries={max_retries})"
    )


def _parse_json_response(text: str, provider: str, url: str) -> dict[str, Any]:
    """Parse text block, strip markdown fences, override source_url, and validate against schema."""
    if not text:
        raise ValueError(f"Empty response from {provider}")

    stripped = text.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        if first_newline != -1:
            stripped = stripped[first_newline + 1 :]
        if stripped.endswith("```"):
            stripped = stripped[:-3]
        stripped = stripped.strip()

    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as err:
        raise ValueError(
            f"Invalid JSON payload returned from {provider}: {err}"
        ) from err

    if not isinstance(data, dict):
        raise TypeError(
            f"Expected dict structure from {provider}, got {type(data).__name__}"
        )

    # Force the source_url to the input URL rather than trusting the model's echo
    data["source_url"] = url

    try:
        return ScholarshipSchema(**data).model_dump()
    except Exception as err:
        raise TypeError(
            f"Data parsed from {provider} broke schema constraints: {err}"
        ) from err
