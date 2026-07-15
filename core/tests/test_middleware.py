import json

from django.contrib.messages import INFO, add_message
from django.contrib.messages.storage.fallback import FallbackStorage
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from core.middleware import HtmxMessageMiddleware


class HtmxMessageMiddlewareTests(TestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()

    def _make_request(self, htmx: bool = False):
        request = self.factory.get("/")
        request.htmx = htmx
        setattr(request, "session", "session")
        messages = FallbackStorage(request)
        setattr(request, "_messages", messages)
        return request

    def _get_response(self, existing_trigger: str | None = None):
        def response_fn(request):
            response = HttpResponse("test")
            if existing_trigger is not None:
                response["HX-Trigger"] = existing_trigger
            return response

        return response_fn

    def test_non_htmx_request_has_no_hx_trigger(self) -> None:
        request = self._make_request(htmx=False)
        add_message(request, INFO, "Test message")
        middleware = HtmxMessageMiddleware(self._get_response())
        response = middleware(request)
        self.assertNotIn("HX-Trigger", response)

    def test_htmx_request_with_messages_has_hx_trigger(self) -> None:
        request = self._make_request(htmx=True)
        add_message(request, INFO, "Test message")
        middleware = HtmxMessageMiddleware(self._get_response())
        response = middleware(request)
        self.assertIn("HX-Trigger", response)
        trigger = json.loads(response["HX-Trigger"])
        self.assertIn("showMessages", trigger)
        self.assertEqual(len(trigger["showMessages"]), 1)
        self.assertEqual(trigger["showMessages"][0]["title"], "Test message")

    def test_htmx_request_without_messages_has_no_hx_trigger(self) -> None:
        request = self._make_request(htmx=True)
        middleware = HtmxMessageMiddleware(self._get_response())
        response = middleware(request)
        self.assertNotIn("HX-Trigger", response)

    def test_existing_hx_trigger_preserved_and_showmessages_added(self) -> None:
        request = self._make_request(htmx=True)
        add_message(request, INFO, "Test message")
        middleware = HtmxMessageMiddleware(
            self._get_response(existing_trigger='{"customEvent": true}')
        )
        response = middleware(request)
        self.assertIn("HX-Trigger", response)
        trigger = json.loads(response["HX-Trigger"])
        self.assertIn("customEvent", trigger)
        self.assertTrue(trigger["customEvent"])
        self.assertIn("showMessages", trigger)
        self.assertEqual(len(trigger["showMessages"]), 1)
        self.assertEqual(trigger["showMessages"][0]["title"], "Test message")
