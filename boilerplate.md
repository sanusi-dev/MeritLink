# Django HTMX Boilerplate Setup

## Conventions

- The Django project name is the name of the current working directory. Detect it from the filesystem before proceeding.
- The core app is always named `core`.

## Goal

Set up a Django project with the following stack:

- Django
- django-htmx (middleware + utilities)
- HTMX served from local static files
- Tailwind CSS compiled via PostCSS
- SweetAlert2 served from local static files, toasts driven by Django messages on both full page loads and HTMX requests

All JavaScript and CSS assets must be local. No CDN links anywhere.

---

## Step 1: Detect Project Name

Read the current working directory name. Use it as `<project_name>` in every step below.

---

## Step 2: Install Python Dependencies

```bash
uv init --no-readme
uv add django django-htmx
```

---

## Step 3: Create Django Project and Core App

```bash
uv run django-admin startproject <project_name> .
uv run python manage.py startapp core
```

---

## Step 4: Configure `<project_name>/settings.py`

### INSTALLED_APPS

```python
INSTALLED_APPS = [
    # ... default apps ...
    "django_htmx",
    "core",
]
```

### MIDDLEWARE

Add `django_htmx.middleware.HtmxMiddleware` immediately after `SecurityMiddleware`, and `core.middleware.HtmxMessageMiddleware` immediately after `MessageMiddleware`:

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "core.middleware.HtmxMessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
```

### TEMPLATES

```python
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
```

### Static files

```python
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
```

### MESSAGE_TAGS

Add at the bottom of `settings.py`:

```python
from django.contrib.messages import constants as messages

MESSAGE_TAGS = {
    messages.DEBUG: "debug",
    messages.INFO: "info",
    messages.SUCCESS: "success",
    messages.WARNING: "warning",
    messages.ERROR: "error",
}
```

---

## Step 5: Create `core/middleware.py`

This middleware intercepts HTMX responses and moves any pending Django messages into an `HX-Trigger` response header as a `showMessages` event. The client-side handler in `base.html` listens for this event and fires the SweetAlert2 toasts without a full page reload.

```python
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

        # Merge with any existing HX-Trigger value so other triggers are preserved
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
```

---

## Step 6: Set Up Node, Tailwind, and Vendor Assets

```bash
npm init -y
npm install -D tailwindcss postcss autoprefixer postcss-cli
npm install htmx.org sweetalert2
npx tailwindcss init
```

### `tailwind.config.js`

```js
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./core/templates/**/*.html",
    "./**/templates/**/*.html",
    "./**/*.py",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};
```

### `postcss.config.js`

```js
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

### Static directory structure

```bash
mkdir -p static/css/src
mkdir -p static/js
```

### `static/css/src/input.css`

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

### `package.json` scripts

```json
"scripts": {
  "vendor:copy": "cp node_modules/htmx.org/dist/htmx.min.js static/js/htmx.min.js && cp node_modules/sweetalert2/dist/sweetalert2.min.js static/js/sweetalert2.min.js && cp node_modules/sweetalert2/dist/sweetalert2.min.css static/css/sweetalert2.min.css",
  "build:css": "postcss static/css/src/input.css -o static/css/output.css",
  "watch:css": "postcss static/css/src/input.css -o static/css/output.css --watch",
  "build": "npm run vendor:copy && npm run build:css"
}
```

### Run the build

```bash
npm run build
```

Verify these four files exist before continuing:
- `static/js/htmx.min.js`
- `static/js/sweetalert2.min.js`
- `static/css/sweetalert2.min.css`
- `static/css/output.css`

---

## Step 7: Create `templates/base.html`

The toast logic handles two cases:
- Full page load: reads messages rendered into the template by Django's messages context processor.
- HTMX request: listens for the `showMessages` custom event emitted via `HX-Trigger` by `HtmxMessageMiddleware`.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{% block title %}App{% endblock %}</title>

  {% load static %}

  <link rel="stylesheet" href="{% static 'css/output.css' %}" />
  <link rel="stylesheet" href="{% static 'css/sweetalert2.min.css' %}" />

  {% block extra_css %}{% endblock %}
</head>
<body class="bg-gray-50 text-gray-900 min-h-screen">

  {% block navbar %}{% endblock %}

  <main class="container mx-auto px-4 py-8">
    {% block content %}{% endblock %}
  </main>

  <script src="{% static 'js/htmx.min.js' %}"></script>
  <script src="{% static 'js/sweetalert2.min.js' %}"></script>

  <script>
    const validIcons = ["success", "error", "warning", "info", "question"];

    function showToastQueue(messages) {
      if (!messages.length) return;
      (function showNext(queue) {
        if (!queue.length) return;
        const { icon, title } = queue.shift();
        Swal.fire({
          toast: true,
          position: "top-end",
          icon: validIcons.includes(icon) ? icon : "info",
          title: title,
          showConfirmButton: false,
          timer: 3500,
          timerProgressBar: true,
        }).then(() => showNext(queue));
      })([...messages]);
    }

    // Full page load: messages rendered by Django template context processor
    document.addEventListener("DOMContentLoaded", function () {
      const messages = [
        {% for message in messages %}
        { icon: "{{ message.tags }}", title: "{{ message|escapejs }}" },
        {% endfor %}
      ];
      showToastQueue(messages);
    });

    // HTMX requests: messages delivered via HX-Trigger → showMessages event
    document.addEventListener("showMessages", function (e) {
      showToastQueue(e.detail.value || e.detail || []);
    });
  </script>

  {% block extra_js %}{% endblock %}
</body>
</html>
```

---

## Step 8: Create Core App Files

```bash
mkdir -p core/templates/core
```

### `core/templates/core/index.html`

```html
{% extends "base.html" %}

{% block title %}Home{% endblock %}

{% block content %}
<div class="text-center py-16">
  <h1 class="text-4xl font-bold text-gray-800 mb-4">Welcome</h1>
  <p class="text-gray-500 text-lg">Your Django + HTMX project is ready.</p>
</div>
{% endblock %}
```

### `core/views.py`

```python
from django.shortcuts import render


def index(request):
    return render(request, "core/index.html")
```

### `core/urls.py`

```python
from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.index, name="index"),
]
```

---

## Step 9: Configure `<project_name>/urls.py`

```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls", namespace="core")),
]
```

---

## Step 10: Create `.gitignore`

```
__pycache__/
*.pyc
*.pyo
*.pyd
.env
db.sqlite3
node_modules/
static/css/output.css
static/css/sweetalert2.min.css
static/js/htmx.min.js
static/js/sweetalert2.min.js
```

---

## Step 11: Run Migrations

```bash
uv run python manage.py migrate
```

---

## Constraints

- Use `uv run python` for all `manage.py` commands.
- Do not use CDN links anywhere. Every `<script>` and `<link>` must use `{% static '...' %}`.
- Do not use the Tailwind CDN Play script.
- Re-run `npm run vendor:copy` only when upgrading `htmx.org` or `sweetalert2` versions.
- All HTMX partial responses must branch on `request.htmx` to return either a full page or a fragment.
- Use `{% url 'core:index' %}` syntax for URL reversals in templates.