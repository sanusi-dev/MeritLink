import json
from django.contrib.messages import get_messages


class HtmxMessageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if not getattr(request, "htmx", False):
            return response

        messages = [
            {"icon": m.tags, "title": str(m)}
            for m in get_messages(request)
        ]

        if not messages:
            return response

        existing = response.headers.get("HX-Trigger")
        if existing:
            try:
                trigger = json.loads(existing)
            except (json.JSONDecodeError, TypeError):
                trigger = {existing: True}
        else:
            trigger = {}

        trigger["showMessages"] = messages
        response["HX-Trigger"] = json.dumps(trigger)

        return response
