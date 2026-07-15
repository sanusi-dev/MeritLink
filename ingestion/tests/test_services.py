from datetime import date, datetime

from django.test import SimpleTestCase, TestCase

from ingestion.services.cleaning import (
    _clean_text,
    _normalize_countries,
    _normalize_date,
    _normalize_list,
    _normalize_study_levels,
    _parse_amount,
    _strip_ordinal_suffix,
    clean_extracted_data,
)
from ingestion.services.deduplication import find_existing_record, is_duplicate
from scholarships.models import Scholarship


class CleanExtractedDataTests(SimpleTestCase):
    def test_full_valid_input_returns_all_fields_cleaned(self) -> None:
        raw = {
            "application_deadline": "  2025-12-31  ",
            "program_start_date": "  2025-09-01  ",
            "eligible_nationalities": ["  Nigeria  ", "Kenya", ""],
            "eligible_study_levels": "Bachelors, Masters, PhD",
            "eligible_fields_of_study": ["Engineering", "Medicine"],
            "study_destinations": "USA, UK, Canada",
            "tags": ["  stem  ", "merit"],
            "funding_amount_approx": {"type": None, "amount_usd": 5000, "max_amount_usd": None, "stipend_usd": None, "currency": "USD", "raw": None},
            "description": "  Great    scholarship. apply now  ",
            "eligibility_details": "  Must be    a student  ",
            "benefits": "Full tuition. click here",
            "status": "open",
        }
        cleaned = clean_extracted_data(raw)

        self.assertEqual(cleaned["application_deadline"], "2025-12-31")
        self.assertEqual(cleaned["program_start_date"], "2025-09-01")
        self.assertEqual(cleaned["eligible_nationalities"], ["Nigeria", "Kenya"])
        self.assertEqual(cleaned["eligible_study_levels"], ["Bachelors", "Masters", "PhD"])
        self.assertEqual(cleaned["eligible_fields_of_study"], ["Engineering", "Medicine"])
        self.assertEqual(cleaned["study_destinations"], ["United States", "United Kingdom", "Canada"])
        self.assertEqual(cleaned["tags"], ["stem", "merit"])
        self.assertEqual(cleaned["funding_amount_approx"]["amount_usd"], 5000)
        self.assertEqual(cleaned["description"], "Great scholarship.")
        self.assertEqual(cleaned["eligibility_details"], "Must be a student")
        self.assertEqual(cleaned["benefits"], "Full tuition.")
        self.assertEqual(cleaned["status"], "open")

    def test_empty_dict_returns_defaults(self) -> None:
        cleaned = clean_extracted_data({})
        self.assertEqual(cleaned["_quality_status"], "fail")
        self.assertEqual(cleaned["extraction_confidence"], 0.2)

    def test_extraction_confidence_derived_from_quality_ok(self) -> None:
        cleaned = clean_extracted_data({
            "title": "Test",
            "source_url": "https://example.com",
            "application_deadline": "2026-06-15",
            "eligible_study_levels": ["Masters"],
        })
        self.assertEqual(cleaned["_quality_status"], "ok")
        self.assertEqual(cleaned["extraction_confidence"], 1.0)

    def test_extraction_confidence_derived_from_quality_warn(self) -> None:
        cleaned = clean_extracted_data({
            "title": "Test",
            "source_url": "https://example.com",
            "eligible_study_levels": ["Masters"],
        })
        self.assertEqual(cleaned["_quality_status"], "warn")
        self.assertEqual(cleaned["extraction_confidence"], 0.6)

    def test_extraction_confidence_derived_from_quality_fail(self) -> None:
        cleaned = clean_extracted_data({})
        self.assertEqual(cleaned["_quality_status"], "fail")
        self.assertEqual(cleaned["extraction_confidence"], 0.2)

    def test_normalizes_all_list_fields(self) -> None:
        raw = {
            "eligible_nationalities": ["  Nigeria  ", ""],
            "eligible_study_levels": "Bachelors, Masters",
            "eligible_fields_of_study": ["Engineering"],
            "study_destinations": "USA, UK",
            "tags": ["  stem  ", "merit"],
        }
        cleaned = clean_extracted_data(raw)
        self.assertEqual(cleaned["eligible_nationalities"], ["Nigeria"])
        self.assertEqual(cleaned["eligible_study_levels"], ["Bachelors", "Masters"])
        self.assertEqual(cleaned["eligible_fields_of_study"], ["Engineering"])
        self.assertEqual(cleaned["study_destinations"], ["United States", "United Kingdom"])
        self.assertEqual(cleaned["tags"], ["stem", "merit"])

    def test_cleans_all_text_fields(self) -> None:
        raw = {
            "description": "  hello   world  ",
            "eligibility_details": "  must   qualify  ",
            "benefits": "  full   tuition  ",
            "short_summary": "  great   opportunity  ",
            "funding_details": "  covers   tuition  ",
            "required_documents": "  submit   transcript  ",
            "selection_criteria": "  based   on   merit  ",
            "notes_for_applicants": "  apply   early  ",
        }
        cleaned = clean_extracted_data(raw)
        self.assertEqual(cleaned["description"], "hello world")
        self.assertEqual(cleaned["eligibility_details"], "must qualify")
        self.assertEqual(cleaned["benefits"], "full tuition")
        self.assertEqual(cleaned["short_summary"], "great opportunity")
        self.assertEqual(cleaned["funding_details"], "covers tuition")
        self.assertEqual(cleaned["required_documents"], "submit transcript")
        self.assertEqual(cleaned["selection_criteria"], "based on merit")
        self.assertEqual(cleaned["notes_for_applicants"], "apply early")

    def test_normalizes_program_start_date(self) -> None:
        raw = {"program_start_date": "  2025-09-01  "}
        cleaned = clean_extracted_data(raw)
        self.assertEqual(cleaned["program_start_date"], "2025-09-01")

    def test_status_preserved_from_input(self) -> None:
        cleaned = clean_extracted_data({"status": "closed"})
        self.assertEqual(cleaned["status"], "closed")

    def test_amount_from_non_dict_stored_with_schema_keys(self) -> None:
        cleaned = clean_extracted_data({"funding_amount_approx": 5000})
        self.assertEqual(cleaned["funding_amount_approx"]["raw"], "5000")
        self.assertIsNone(cleaned["funding_amount_approx"]["amount_usd"])


class CleanExtractedDataNormalizationTests(SimpleTestCase):
    def test_applies_country_normalization_to_nationalities(self) -> None:
        raw = {
            "title": "Test",
            "source_url": "https://example.com",
            "eligible_nationalities": ["usa", "uk", "nigeria"],
        }
        cleaned = clean_extracted_data(raw)
        self.assertEqual(
            cleaned["eligible_nationalities"],
            ["United States", "United Kingdom", "Nigeria"],
        )

    def test_applies_country_normalization_to_destinations(self) -> None:
        raw = {
            "title": "Test",
            "source_url": "https://example.com",
            "study_destinations": ["canada", "germany", "australia"],
        }
        cleaned = clean_extracted_data(raw)
        self.assertEqual(
            cleaned["study_destinations"],
            ["Canada", "Germany", "Australia"],
        )

    def test_applies_level_normalization(self) -> None:
        raw = {
            "title": "Test",
            "source_url": "https://example.com",
            "eligible_study_levels": ["msc", "phd", "bsc"],
        }
        cleaned = clean_extracted_data(raw)
        self.assertEqual(cleaned["eligible_study_levels"], ["Masters", "PhD", "Bachelors"])

    def test_adds_quality_gates_ok(self) -> None:
        raw = {
            "title": "Test Scholarship",
            "source_url": "https://example.com",
            "application_deadline": "2026-06-15",
            "eligible_study_levels": ["Masters"],
        }
        cleaned = clean_extracted_data(raw)
        self.assertEqual(cleaned["_quality_status"], "ok")
        self.assertNotIn("_quality_issues", cleaned)

    def test_adds_quality_gates_fail(self) -> None:
        raw = {"application_deadline": "2026-06-15", "eligible_study_levels": ["Masters"]}
        cleaned = clean_extracted_data(raw)
        self.assertEqual(cleaned["_quality_status"], "fail")
        self.assertIn("_quality_issues", cleaned)


class NormalizeDateTests(SimpleTestCase):
    def test_none_returns_none(self) -> None:
        self.assertIsNone(_normalize_date(None))

    def test_empty_string_returns_none(self) -> None:
        self.assertIsNone(_normalize_date(""))

    def test_string_returns_stripped_string(self) -> None:
        self.assertEqual(_normalize_date("  2025-01-01  "), "2025-01-01")

    def test_non_string_returns_str_value(self) -> None:
        self.assertEqual(_normalize_date(12345), "12345")

    def test_non_string_object_returns_str(self) -> None:
        self.assertEqual(_normalize_date(3.14), "3.14")

    def test_iso_format(self) -> None:
        self.assertEqual(_normalize_date("2026-06-15"), "2026-06-15")

    def test_d_space_B_space_Y(self) -> None:
        self.assertEqual(_normalize_date("15 June 2026"), "2026-06-15")

    def test_B_d_comma_Y(self) -> None:
        self.assertEqual(_normalize_date("June 15, 2026"), "2026-06-15")

    def test_d_slash_m_slash_Y(self) -> None:
        self.assertEqual(_normalize_date("15/06/2026"), "2026-06-15")

    def test_d_dash_m_dash_Y(self) -> None:
        self.assertEqual(_normalize_date("15-06-2026"), "2026-06-15")

    def test_Y_slash_m_slash_d(self) -> None:
        self.assertEqual(_normalize_date("2026/06/15"), "2026-06-15")

    def test_d_space_b_space_Y(self) -> None:
        self.assertEqual(_normalize_date("15 Jun 2026"), "2026-06-15")

    def test_b_d_comma_Y(self) -> None:
        self.assertEqual(_normalize_date("Jun 15, 2026"), "2026-06-15")

    def test_m_slash_d_slash_Y(self) -> None:
        self.assertEqual(_normalize_date("06/15/2026"), "2026-06-15")

    def test_d_space_B_comma_Y(self) -> None:
        self.assertEqual(_normalize_date("15 June, 2026"), "2026-06-15")

    def test_B_space_d_space_Y(self) -> None:
        self.assertEqual(_normalize_date("June 15 2026"), "2026-06-15")

    def test_ordinal_suffix_1st(self) -> None:
        self.assertEqual(_normalize_date("1st June 2026"), "2026-06-01")

    def test_ordinal_suffix_2nd(self) -> None:
        self.assertEqual(_normalize_date("2nd June 2026"), "2026-06-02")

    def test_ordinal_suffix_3rd(self) -> None:
        self.assertEqual(_normalize_date("3rd June 2026"), "2026-06-03")

    def test_ordinal_suffix_4th(self) -> None:
        self.assertEqual(_normalize_date("4th June 2026"), "2026-06-04")

    def test_ordinal_suffix_15th(self) -> None:
        self.assertEqual(_normalize_date("15th June 2026"), "2026-06-15")

    def test_ordinal_suffix_21st(self) -> None:
        self.assertEqual(_normalize_date("21st June 2026"), "2026-06-21")

    def test_ordinal_suffix_23rd(self) -> None:
        self.assertEqual(_normalize_date("23rd June 2026"), "2026-06-23")

    def test_returns_iso_format(self) -> None:
        result = _normalize_date("15 June 2026")
        self.assertEqual(result, "2026-06-15")
        self.assertRegex(result, r"^\d{4}-\d{2}-\d{2}$")

    def test_preserves_unparseable_string(self) -> None:
        self.assertEqual(_normalize_date("sometime in July"), "sometime in July")

    def test_date_object_returns_iso(self) -> None:
        self.assertEqual(_normalize_date(date(2026, 6, 15)), "2026-06-15")

    def test_datetime_object_returns_iso(self) -> None:
        self.assertEqual(
            _normalize_date(datetime(2026, 6, 15, 10, 30)), "2026-06-15"
        )


class StripOrdinalSuffixTests(SimpleTestCase):
    def test_strips_st(self) -> None:
        self.assertEqual(_strip_ordinal_suffix("1st"), "1")

    def test_strips_nd(self) -> None:
        self.assertEqual(_strip_ordinal_suffix("2nd"), "2")

    def test_strips_rd(self) -> None:
        self.assertEqual(_strip_ordinal_suffix("3rd"), "3")

    def test_strips_th(self) -> None:
        self.assertEqual(_strip_ordinal_suffix("4th"), "4")

    def test_strips_th_from_double_digit(self) -> None:
        self.assertEqual(_strip_ordinal_suffix("15th"), "15")

    def test_preserves_no_suffix(self) -> None:
        self.assertEqual(_strip_ordinal_suffix("15"), "15")

    def test_strips_from_full_string(self) -> None:
        self.assertEqual(_strip_ordinal_suffix("15th June 2026"), "15 June 2026")


class NormalizeListTests(SimpleTestCase):
    def test_list_returns_cleaned_list(self) -> None:
        result = _normalize_list(["  a  ", "", "b", None, "c"])
        self.assertEqual(result, ["a", "b", "c"])

    def test_comma_separated_string_returns_list(self) -> None:
        self.assertEqual(_normalize_list("a, b, , c"), ["a", "b", "c"])

    def test_empty_string_returns_empty_list(self) -> None:
        self.assertEqual(_normalize_list(""), [])

    def test_none_returns_empty_list(self) -> None:
        self.assertEqual(_normalize_list(None), [])

    def test_other_type_returns_empty_list(self) -> None:
        self.assertEqual(_normalize_list(123), [])

    def test_list_strips_and_converts_items(self) -> None:
        self.assertEqual(_normalize_list([1, 2, 3]), ["1", "2", "3"])


class NormalizeCountriesTests(SimpleTestCase):
    def test_uk_maps_to_united_kingdom(self) -> None:
        self.assertEqual(_normalize_countries(["UK"]), ["United Kingdom"])

    def test_usa_maps_to_united_states(self) -> None:
        self.assertEqual(_normalize_countries(["USA"]), ["United States"])

    def test_nigeria_maps_to_nigeria(self) -> None:
        self.assertEqual(_normalize_countries(["Nigeria"]), ["Nigeria"])

    def test_unknown_country_title_cased(self) -> None:
        self.assertEqual(_normalize_countries(["brazil"]), ["Brazil"])

    def test_deduplicates(self) -> None:
        result = _normalize_countries(["UK", "uk", "United Kingdom"])
        self.assertEqual(result, ["United Kingdom"])

    def test_all_maps_to_all(self) -> None:
        self.assertEqual(_normalize_countries(["all"]), ["all"])

    def test_worldwide_maps_to_all(self) -> None:
        self.assertEqual(_normalize_countries(["worldwide"]), ["all"])

    def test_international_maps_to_all(self) -> None:
        self.assertEqual(_normalize_countries(["international"]), ["all"])

    def test_mixed_known_and_unknown(self) -> None:
        result = _normalize_countries(["nigeria", "brazil", "ghana"])
        self.assertEqual(result, ["Nigeria", "Brazil", "Ghana"])

    def test_non_list_returns_empty(self) -> None:
        self.assertEqual(_normalize_countries("not a list"), [])

    def test_strips_whitespace(self) -> None:
        self.assertEqual(_normalize_countries(["  nigeria  "]), ["Nigeria"])


class NormalizeStudyLevelsTests(SimpleTestCase):
    def test_msc_maps_to_masters(self) -> None:
        self.assertEqual(_normalize_study_levels(["MSc"]), ["Masters"])

    def test_phd_maps_to_phd(self) -> None:
        self.assertEqual(_normalize_study_levels(["PhD"]), ["PhD"])

    def test_bsc_maps_to_bachelors(self) -> None:
        self.assertEqual(_normalize_study_levels(["BSc"]), ["Bachelors"])

    def test_deduplicates(self) -> None:
        result = _normalize_study_levels(["MSc", "msc", "Masters"])
        self.assertEqual(result, ["Masters"])

    def test_unknown_level_title_cased(self) -> None:
        self.assertEqual(_normalize_study_levels(["some level"]), ["Some Level"])

    def test_non_list_returns_empty(self) -> None:
        self.assertEqual(_normalize_study_levels("not a list"), [])

    def test_strips_whitespace(self) -> None:
        self.assertEqual(_normalize_study_levels(["  phd  "]), ["PhD"])

    def test_mixed_known_and_unknown(self) -> None:
        result = _normalize_study_levels(["bsc", "diploma", "some level"])
        self.assertEqual(result, ["Bachelors", "Diploma", "Some Level"])


class ParseAmountTests(SimpleTestCase):
    def test_dict_returns_dict_as_is(self) -> None:
        value = {"type": None, "amount_usd": 5000, "max_amount_usd": None, "stipend_usd": None, "currency": "USD", "raw": None}
        self.assertEqual(_parse_amount(value), value)

    def test_non_dict_returns_all_schema_keys(self) -> None:
        result = _parse_amount(5000)
        self.assertEqual(result["raw"], "5000")
        self.assertIsNone(result["type"])
        self.assertIsNone(result["amount_usd"])
        self.assertIsNone(result["currency"])

    def test_string_returns_raw_wrapped(self) -> None:
        result = _parse_amount("5000 USD")
        self.assertEqual(result["raw"], "5000 USD")
        self.assertIsNone(result["type"])

    def test_full_tuition_plus_stipend(self) -> None:
        result = _parse_amount("Full tuition + $15,000 stipend")
        self.assertEqual(result["raw"], "Full tuition + $15,000 stipend")
        self.assertEqual(result["type"], "full_tuition_plus_stipend")
        self.assertEqual(result["stipend_usd"], 15000)
        self.assertEqual(result["currency"], "USD")

    def test_up_to_amount(self) -> None:
        result = _parse_amount("up to $50,000")
        self.assertEqual(result["raw"], "up to $50,000")
        self.assertEqual(result["max_amount_usd"], 50000)
        self.assertEqual(result["currency"], "USD")

    def test_gbp_amount_does_not_populate_usd_fields(self) -> None:
        result = _parse_amount("£5,000")
        self.assertEqual(result["raw"], "£5,000")
        self.assertEqual(result["currency"], "GBP")
        self.assertIsNone(result["amount_usd"])

    def test_usd_amount_populates_usd_field(self) -> None:
        result = _parse_amount("$5,000")
        self.assertEqual(result["raw"], "$5,000")
        self.assertEqual(result["currency"], "USD")
        self.assertEqual(result["amount_usd"], 5000)

    def test_unparseable_string(self) -> None:
        result = _parse_amount("various benefits")
        self.assertEqual(result["raw"], "various benefits")
        self.assertIsNone(result["type"])
        self.assertIsNone(result["amount_usd"])
        self.assertIsNone(result["currency"])

    def test_dict_passthrough(self) -> None:
        value = {"type": "full_tuition", "amount_usd": None, "max_amount_usd": None, "stipend_usd": None, "currency": None, "raw": "Full tuition"}
        self.assertEqual(_parse_amount(value), value)

    def test_full_tuition_only(self) -> None:
        result = _parse_amount("Full tuition coverage")
        self.assertEqual(result["raw"], "Full tuition coverage")
        self.assertEqual(result["type"], "full_tuition")
        self.assertIsNone(result["amount_usd"])


class QualityGatesTests(SimpleTestCase):
    def test_fail_when_title_missing(self) -> None:
        cleaned = clean_extracted_data({
            "source_url": "https://example.com",
            "application_deadline": "2026-06-15",
            "eligible_study_levels": ["Masters"],
        })
        self.assertEqual(cleaned["_quality_status"], "fail")
        self.assertIn("Missing title", cleaned["_quality_issues"])

    def test_fail_when_source_url_missing(self) -> None:
        cleaned = clean_extracted_data({
            "title": "Test Scholarship",
            "application_deadline": "2026-06-15",
            "eligible_study_levels": ["Masters"],
        })
        self.assertEqual(cleaned["_quality_status"], "fail")
        self.assertIn("Missing source_url", cleaned["_quality_issues"])

    def test_warn_when_deadline_missing(self) -> None:
        cleaned = clean_extracted_data({
            "title": "Test Scholarship",
            "source_url": "https://example.com",
            "eligible_study_levels": ["Masters"],
        })
        self.assertEqual(cleaned["_quality_status"], "warn")
        self.assertIn("Missing application_deadline", cleaned["_quality_issues"])

    def test_warn_when_study_levels_missing(self) -> None:
        cleaned = clean_extracted_data({
            "title": "Test Scholarship",
            "source_url": "https://example.com",
            "application_deadline": "2026-06-15",
        })
        self.assertEqual(cleaned["_quality_status"], "warn")
        self.assertIn("Missing eligible_study_levels", cleaned["_quality_issues"])

    def test_ok_when_all_present(self) -> None:
        cleaned = clean_extracted_data({
            "title": "Test Scholarship",
            "source_url": "https://example.com",
            "application_deadline": "2026-06-15",
            "eligible_study_levels": ["Masters"],
        })
        self.assertEqual(cleaned["_quality_status"], "ok")
        self.assertNotIn("_quality_issues", cleaned)


class CleanTextTests(SimpleTestCase):
    def test_strips_whitespace_and_collapses_multiple_spaces(self) -> None:
        self.assertEqual(_clean_text("  hello   world  "), "hello world")

    def test_removes_boilerplate_apply_now(self) -> None:
        self.assertEqual(_clean_text("apply now"), "")
        self.assertEqual(_clean_text("Read the details. apply now"), "Read the details.")

    def test_removes_boilerplate_click_here(self) -> None:
        self.assertEqual(_clean_text("click here"), "")

    def test_removes_boilerplate_for_more_information_visit(self) -> None:
        self.assertEqual(_clean_text("for more information visit"), "")
        self.assertEqual(
            _clean_text("for more information visit our website"),
            "our website",
        )

    def test_empty_string_returns_empty_string(self) -> None:
        self.assertEqual(_clean_text(""), "")

    def test_none_returns_empty_string(self) -> None:
        self.assertEqual(_clean_text(None), "")

    def test_caps_at_8000_characters(self) -> None:
        self.assertEqual(len(_clean_text("x" * 9000)), 8000)

    def test_preserves_text_under_cap(self) -> None:
        self.assertEqual(_clean_text("x" * 100), "x" * 100)


class FindExistingRecordTests(TestCase):
    def setUp(self) -> None:
        self.scholarship = Scholarship.objects.create(
            title="Test Scholarship",
            source_url="https://example.com/scholarship/1",
        )

    def test_returns_scholarship_when_url_matches(self) -> None:
        result = find_existing_record("https://example.com/scholarship/1")
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.scholarship.pk)

    def test_returns_none_when_no_matching_url(self) -> None:
        self.assertIsNone(find_existing_record("https://example.com/missing"))

    def test_returns_none_on_empty_db(self) -> None:
        Scholarship.objects.all().delete()
        self.assertIsNone(find_existing_record("https://example.com/scholarship/1"))


class IsDuplicateTests(SimpleTestCase):
    def test_returns_false_current_stub_behavior(self) -> None:
        self.assertFalse(is_duplicate({"title": "Anything"}))

    def test_returns_false_for_empty_dict(self) -> None:
        self.assertFalse(is_duplicate({}))
