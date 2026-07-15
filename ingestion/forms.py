from django import forms

from scholarships.models import Scholarship

_DATE_INPUT_FORMATS = (
    "%Y-%m-%d",
    "%d %B %Y",
    "%B %d, %Y",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y/%m/%d",
    "%d %b %Y",
    "%b %d, %Y",
    "%m/%d/%Y",
)

_LIST_FIELDS = (
    "eligible_nationalities",
    "eligible_study_levels",
    "eligible_fields_of_study",
    "study_destinations",
    "tags",
)

_FIELD_CLASS = (
    "w-full rounded-md border border-gray-300 px-3 py-2 text-sm "
    "focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
)
_AREA_CLASS = (
    "w-full rounded-md border border-gray-300 px-3 py-2 text-sm "
    "focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
)


class ReviewForm(forms.Form):
    """
    Form for reviewing and editing a ReviewItem's cleaned data before approval.
    Fields map to Scholarship model fields the reviewer is allowed to edit.
    Pre-populated from ReviewItem.cleaned_data via prepare_initial().
    On submit, get_overrides() returns the edited values formatted as
    overrides for approve_review_item().
    """

    title = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={"class": _FIELD_CLASS}),
    )
    provider = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={"class": _FIELD_CLASS}),
    )
    application_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={"class": _FIELD_CLASS}),
    )
    application_deadline = forms.DateField(
        required=False,
        input_formats=_DATE_INPUT_FORMATS,
        widget=forms.DateInput(attrs={"class": _FIELD_CLASS, "placeholder": "YYYY-MM-DD"}),
    )
    program_start_date = forms.DateField(
        required=False,
        input_formats=_DATE_INPUT_FORMATS,
        widget=forms.DateInput(attrs={"class": _FIELD_CLASS, "placeholder": "YYYY-MM-DD"}),
    )
    status = forms.ChoiceField(
        choices=Scholarship.STATUS_CHOICES,
        widget=forms.Select(attrs={"class": _FIELD_CLASS}),
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": _AREA_CLASS, "rows": 4}),
    )
    short_summary = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": _AREA_CLASS, "rows": 3}),
    )

    eligible_nationalities = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": _AREA_CLASS, "rows": 2}),
        help_text="Comma-separated, e.g. Nigeria, Ghana, Kenya",
    )
    eligible_study_levels = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": _AREA_CLASS, "rows": 2}),
        help_text="Comma-separated, e.g. Bachelors, Masters, PhD",
    )
    eligible_fields_of_study = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": _AREA_CLASS, "rows": 2}),
        help_text="Comma-separated",
    )
    study_destinations = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": _AREA_CLASS, "rows": 2}),
        help_text="Comma-separated",
    )
    min_gpa = forms.FloatField(required=False)
    gpa_scale = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={"class": _FIELD_CLASS, "placeholder": "e.g. 4.0, 5.0"}),
    )

    funding_details = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": _AREA_CLASS, "rows": 3}),
    )
    number_of_awards = forms.IntegerField(required=False)

    eligibility_details = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": _AREA_CLASS, "rows": 4}),
    )
    benefits = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": _AREA_CLASS, "rows": 3}),
    )
    tags = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": _AREA_CLASS, "rows": 2}),
        help_text="Comma-separated",
    )

    @staticmethod
    def prepare_initial(cleaned_data: dict) -> dict:
        """Convert a ReviewItem's cleaned_data JSON dict into form initial values."""
        initial = dict(cleaned_data or {})
        for field in _LIST_FIELDS:
            val = initial.get(field)
            if isinstance(val, list):
                initial[field] = ", ".join(val)
        return initial

    def get_overrides(self) -> dict:
        """Return cleaned form data formatted as overrides for approve_review_item()."""
        overrides = {}
        for key, value in self.cleaned_data.items():
            if value in (None, ""):
                continue
            if key in _LIST_FIELDS:
                overrides[key] = [v.strip() for v in value.split(",") if v.strip()]
            else:
                overrides[key] = value
        return overrides
