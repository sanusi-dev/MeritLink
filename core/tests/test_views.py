from django.test import TestCase


class IndexViewTests(TestCase):
    def test_index_returns_200(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_index_uses_correct_template(self) -> None:
        response = self.client.get("/")
        self.assertTemplateUsed(response, "core/index.html")
