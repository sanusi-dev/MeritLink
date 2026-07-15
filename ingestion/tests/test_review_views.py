from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from ingestion.forms import ReviewForm
from ingestion.models import ReviewItem
from scholarships.models import Scholarship

User = get_user_model()

VALID_FORM_DATA = {
    "title": "Test Scholarship",
    "provider": "Test Provider",
    "application_deadline": "2026-06-15",
    "status": "open",
    "description": "Test description",
    "eligible_nationalities": "Nigeria, Ghana, Kenya",
    "eligible_study_levels": "Masters, PhD",
    "eligible_fields_of_study": "",
    "study_destinations": "",
    "min_gpa": "",
    "gpa_scale": "",
    "funding_details": "",
    "number_of_awards": "",
    "eligibility_details": "",
    "benefits": "",
    "tags": "",
    "short_summary": "",
    "application_url": "",
    "program_start_date": "",
}


def make_review_item(**overrides) -> ReviewItem:
    defaults = {
        "source_url": "https://example.com/scholarship-1",
        "review_type": "new",
        "status": "pending",
        "raw_extraction": {
            "title": "Raw Title",
            "source_url": "https://example.com/scholarship-1",
        },
        "cleaned_data": {
            "title": "Cleaned Title",
            "source_url": "https://example.com/scholarship-1",
            "status": "open",
            "eligible_nationalities": ["Nigeria", "Ghana"],
        },
        "is_user_submitted": False,
    }
    defaults.update(overrides)
    return ReviewItem.objects.create(**defaults)


def make_staff_user(username: str = "reviewer", password: str = "testpass123") -> User:
    return User.objects.create_user(
        username=username,
        password=password,
        is_staff=True,
    )


class ReviewFormTests(SimpleTestCase):
    def test_prepare_initial_converts_list_fields_to_comma_separated(self) -> None:
        cleaned_data = {
            "title": "Test",
            "eligible_nationalities": ["Nigeria", "Ghana", "Kenya"],
            "eligible_study_levels": ["Masters", "PhD"],
            "tags": ["science", "engineering"],
        }
        initial = ReviewForm.prepare_initial(cleaned_data)
        self.assertEqual(initial["eligible_nationalities"], "Nigeria, Ghana, Kenya")
        self.assertEqual(initial["eligible_study_levels"], "Masters, PhD")
        self.assertEqual(initial["tags"], "science, engineering")

    def test_prepare_initial_handles_empty_or_none_cleaned_data(self) -> None:
        self.assertEqual(ReviewForm.prepare_initial(None), {})
        self.assertEqual(ReviewForm.prepare_initial({}), {})

    def test_prepare_initial_handles_dict_with_no_list_fields(self) -> None:
        cleaned_data = {"title": "Test", "provider": "Provider", "status": "open"}
        initial = ReviewForm.prepare_initial(cleaned_data)
        self.assertEqual(initial, cleaned_data)

    def test_get_overrides_converts_comma_separated_strings_to_lists(self) -> None:
        form = ReviewForm(VALID_FORM_DATA)
        self.assertTrue(form.is_valid())
        overrides = form.get_overrides()
        self.assertEqual(
            overrides["eligible_nationalities"], ["Nigeria", "Ghana", "Kenya"]
        )
        self.assertEqual(overrides["eligible_study_levels"], ["Masters", "PhD"])

    def test_get_overrides_skips_none_and_empty_string_values(self) -> None:
        form = ReviewForm(VALID_FORM_DATA)
        self.assertTrue(form.is_valid())
        overrides = form.get_overrides()
        self.assertNotIn("eligible_fields_of_study", overrides)
        self.assertNotIn("study_destinations", overrides)
        self.assertNotIn("min_gpa", overrides)
        self.assertNotIn("tags", overrides)
        self.assertNotIn("application_url", overrides)
        self.assertNotIn("program_start_date", overrides)
        self.assertNotIn("number_of_awards", overrides)

    def test_get_overrides_returns_date_objects_for_date_fields(self) -> None:
        form = ReviewForm(VALID_FORM_DATA)
        self.assertTrue(form.is_valid())
        overrides = form.get_overrides()
        self.assertIn("application_deadline", overrides)
        self.assertIsInstance(overrides["application_deadline"], date)
        self.assertEqual(overrides["application_deadline"], date(2026, 6, 15))

    def test_get_overrides_returns_non_list_fields_as_is(self) -> None:
        form = ReviewForm(VALID_FORM_DATA)
        self.assertTrue(form.is_valid())
        overrides = form.get_overrides()
        self.assertEqual(overrides["title"], "Test Scholarship")
        self.assertEqual(overrides["provider"], "Test Provider")
        self.assertEqual(overrides["status"], "open")
        self.assertEqual(overrides["description"], "Test description")


class ReviewListViewTests(TestCase):
    def setUp(self) -> None:
        self.user = make_staff_user()

    def test_non_authenticated_user_redirected_to_login(self) -> None:
        response = self.client.get(reverse("ingestion:review_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_staff_user_gets_200_with_pending_items(self) -> None:
        self.client.force_login(self.user)
        item = make_review_item()
        response = self.client.get(reverse("ingestion:review_list"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(item, list(response.context["pending"]))

    def test_view_only_shows_pending_items(self) -> None:
        self.client.force_login(self.user)
        pending = make_review_item(source_url="https://example.com/pending")
        approved = make_review_item(source_url="https://example.com/approved")
        approved.mark_approved()
        rejected = make_review_item(source_url="https://example.com/rejected")
        rejected.mark_rejected()
        response = self.client.get(reverse("ingestion:review_list"))
        pending_list = list(response.context["pending"])
        self.assertIn(pending, pending_list)
        self.assertNotIn(approved, pending_list)
        self.assertNotIn(rejected, pending_list)

    def test_view_shows_recently_approved_and_rejected(self) -> None:
        self.client.force_login(self.user)
        approved = make_review_item(source_url="https://example.com/approved")
        approved.mark_approved()
        rejected = make_review_item(source_url="https://example.com/rejected")
        rejected.mark_rejected()
        response = self.client.get(reverse("ingestion:review_list"))
        self.assertIn(approved, list(response.context["recently_approved"]))
        self.assertIn(rejected, list(response.context["recently_rejected"]))

    def test_empty_queue_renders_without_errors(self) -> None:
        self.client.force_login(self.user)
        response = self.client.get(reverse("ingestion:review_list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["pending"]), [])
        self.assertEqual(list(response.context["recently_approved"]), [])
        self.assertEqual(list(response.context["recently_rejected"]), [])

    def test_filter_type_new_shows_only_new_items(self) -> None:
        self.client.force_login(self.user)
        new_item = make_review_item(source_url="https://example.com/filter-new-1")
        update_item = make_review_item(
            source_url="https://example.com/filter-update-1", review_type="update"
        )
        response = self.client.get(reverse("ingestion:review_list") + "?type=new")
        self.assertEqual(response.status_code, 200)
        pending = list(response.context["pending"])
        self.assertIn(new_item, pending)
        self.assertNotIn(update_item, pending)

    def test_filter_type_update_shows_only_update_items(self) -> None:
        self.client.force_login(self.user)
        new_item = make_review_item(source_url="https://example.com/filter-new-2")
        update_item = make_review_item(
            source_url="https://example.com/filter-update-2", review_type="update"
        )
        response = self.client.get(reverse("ingestion:review_list") + "?type=update")
        self.assertEqual(response.status_code, 200)
        pending = list(response.context["pending"])
        self.assertIn(update_item, pending)
        self.assertNotIn(new_item, pending)

    def test_no_filter_shows_all_pending_items(self) -> None:
        self.client.force_login(self.user)
        new_item = make_review_item(source_url="https://example.com/filter-new-3")
        update_item = make_review_item(
            source_url="https://example.com/filter-update-3", review_type="update"
        )
        response = self.client.get(reverse("ingestion:review_list"))
        self.assertEqual(response.status_code, 200)
        pending = list(response.context["pending"])
        self.assertIn(new_item, pending)
        self.assertIn(update_item, pending)

    def test_counts_dict_has_correct_values(self) -> None:
        self.client.force_login(self.user)
        make_review_item(source_url="https://example.com/count-new-1")
        make_review_item(source_url="https://example.com/count-new-2")
        make_review_item(
            source_url="https://example.com/count-update-1", review_type="update"
        )
        response = self.client.get(reverse("ingestion:review_list"))
        counts = response.context["counts"]
        self.assertEqual(counts["all"], 3)
        self.assertEqual(counts["new"], 2)
        self.assertEqual(counts["update"], 1)

    def test_active_tab_is_all_when_no_query_param(self) -> None:
        self.client.force_login(self.user)
        response = self.client.get(reverse("ingestion:review_list"))
        self.assertEqual(response.context["active_tab"], "all")

    def test_active_tab_is_new_when_type_new(self) -> None:
        self.client.force_login(self.user)
        response = self.client.get(reverse("ingestion:review_list") + "?type=new")
        self.assertEqual(response.context["active_tab"], "new")

    def test_active_tab_is_update_when_type_update(self) -> None:
        self.client.force_login(self.user)
        response = self.client.get(reverse("ingestion:review_list") + "?type=update")
        self.assertEqual(response.context["active_tab"], "update")


class RunQueueViewTests(TestCase):
    """Test the run_queue view that triggers background processing."""

    def setUp(self) -> None:
        self.user = make_staff_user()

    def test_non_authenticated_user_redirected_to_login(self) -> None:
        response = self.client.post(reverse("ingestion:run_queue"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    @patch("ingestion.views.subprocess.Popen")
    @patch("scripts.lockfile.is_locked", return_value=False)
    def test_authenticated_staff_user_gets_redirect_to_review_list(
        self, mock_is_locked, mock_popen
    ) -> None:
        self.client.force_login(self.user)
        response = self.client.post(reverse("ingestion:run_queue"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("ingestion:review_list"))

    @patch("scripts.lockfile.is_locked", return_value=True)
    def test_already_in_progress_shows_message(self, mock_is_locked) -> None:
        self.client.force_login(self.user)
        response = self.client.post(reverse("ingestion:run_queue"), follow=True)
        self.assertEqual(response.status_code, 200)
        messages_list = list(get_messages(response.wsgi_request))
        self.assertTrue(any("already in progress" in str(m) for m in messages_list))


class ReviewDetailViewTests(TestCase):
    def setUp(self) -> None:
        self.user = make_staff_user()

    def test_non_authenticated_user_redirected_to_login(self) -> None:
        response = self.client.get(reverse("ingestion:review_detail", args=[1]))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_get_pending_item_shows_form_pre_populated(self) -> None:
        self.client.force_login(self.user)
        item = make_review_item()
        response = self.client.get(
            reverse("ingestion:review_detail", args=[item.pk])
        )
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(form.initial["title"], "Cleaned Title")
        self.assertEqual(form.initial["status"], "open")
        self.assertEqual(
            form.initial["eligible_nationalities"], "Nigeria, Ghana"
        )

    def test_get_shows_review_item_metadata(self) -> None:
        self.client.force_login(self.user)
        item = make_review_item()
        response = self.client.get(
            reverse("ingestion:review_detail", args=[item.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["review_item"], item)
        self.assertContains(response, item.source_url)
        self.assertContains(response, item.review_type)
        self.assertContains(response, item.status)

    def test_get_nonexistent_pk_returns_404(self) -> None:
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("ingestion:review_detail", args=[99999])
        )
        self.assertEqual(response.status_code, 404)

    def test_post_approve_creates_scholarship_and_marks_approved(self) -> None:
        self.client.force_login(self.user)
        item = make_review_item()
        response = self.client.post(
            reverse("ingestion:review_detail", args=[item.pk]),
            data={**VALID_FORM_DATA, "approve": ""},
        )
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.status, "approved")
        self.assertEqual(Scholarship.objects.count(), 1)
        scholarship = Scholarship.objects.first()
        self.assertEqual(scholarship.source_url, item.source_url)

    def test_post_approve_with_edited_fields_passes_overrides(self) -> None:
        self.client.force_login(self.user)
        item = make_review_item(
            cleaned_data={
                "title": "Original Title",
                "source_url": "https://example.com/scholarship-1",
                "status": "open",
            }
        )
        edited_data = {**VALID_FORM_DATA, "title": "Edited Title", "approve": ""}
        response = self.client.post(
            reverse("ingestion:review_detail", args=[item.pk]),
            data=edited_data,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Scholarship.objects.count(), 1)
        scholarship = Scholarship.objects.first()
        self.assertEqual(scholarship.title, "Edited Title")

    def test_post_reject_marks_rejected(self) -> None:
        self.client.force_login(self.user)
        item = make_review_item()
        response = self.client.post(
            reverse("ingestion:review_detail", args=[item.pk]),
            data={**VALID_FORM_DATA, "reject": ""},
        )
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.status, "rejected")
        self.assertEqual(Scholarship.objects.count(), 0)

    def test_post_approve_on_already_approved_shows_error_and_redirects(self) -> None:
        self.client.force_login(self.user)
        item = make_review_item()
        item.mark_approved()
        response = self.client.post(
            reverse("ingestion:review_detail", args=[item.pk]),
            data={**VALID_FORM_DATA, "approve": ""},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.redirect_chain), 1)
        self.assertIn("review/", response.redirect_chain[0][0])
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("no longer pending" in str(m) for m in messages))
        self.assertEqual(Scholarship.objects.count(), 0)

    def test_post_approve_on_update_with_no_existing_scholarship_shows_error(self) -> None:
        self.client.force_login(self.user)
        item = make_review_item(
            review_type="update",
            source_url="https://example.com/no-existing",
        )
        response = self.client.post(
            reverse("ingestion:review_detail", args=[item.pk]),
            data={**VALID_FORM_DATA, "approve": ""},
        )
        self.assertEqual(response.status_code, 200)
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(
            any("no existing Scholarship" in str(m) for m in messages)
        )
        item.refresh_from_db()
        self.assertEqual(item.status, "pending")
        self.assertEqual(Scholarship.objects.count(), 0)

    def test_get_on_approved_item_shows_already_approved_message(self) -> None:
        self.client.force_login(self.user)
        item = make_review_item()
        item.mark_approved()
        response = self.client.get(
            reverse("ingestion:review_detail", args=[item.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already been approved")
        self.assertNotContains(response, 'name="approve"')

    def test_get_on_rejected_item_shows_already_rejected_message(self) -> None:
        self.client.force_login(self.user)
        item = make_review_item()
        item.mark_rejected()
        response = self.client.get(
            reverse("ingestion:review_detail", args=[item.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already been rejected")
        self.assertNotContains(response, 'name="approve"')
