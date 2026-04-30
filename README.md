<div align="center">

<img src="https://img.shields.io/badge/status-in%20development-yellow?style=for-the-badge" alt="Status" />
<img src="https://img.shields.io/badge/version-0.1.0-blue?style=for-the-badge" alt="Version" />
<img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="License" />

# 🎓 MeritLink

**Connecting students to scholarships they actually deserve — intelligently.**

MeritLink is a smart scholarship discovery platform that matches students to funding opportunities based on their academic profiles. It goes beyond simple search by helping students not just find scholarships, but genuinely compete for them.

[Features](#-features) · [How It Works](#-how-it-works) · [Tech Stack](#-tech-stack) · [Roadmap](#-roadmap) · [Contributing](#-contributing)

</div>

---

## ✨ Features

### 🧑‍🎓 Student Academic Profiles
Students build a rich, structured academic profile covering their educational background, GPA, field of study, extracurriculars, skills, nationality, financial need, and more. This profile is the engine that powers all intelligent matching on the platform.

### 🔍 Smart Scholarship Matching
MeritLink automatically fetches and surfaces scholarship opportunities that align with each student's unique profile. No more sifting through hundreds of irrelevant listings — students see only what they're actually eligible for.

### 📚 Profile Optimization Resources
Beyond discovery, MeritLink equips students with practical guidance on how to build a standout application. For every scholarship a student pursues, the platform provides tailored advice on strengthening their profile to become the most competitive candidate possible.

### 📋 Application Tracker
Students can track the status of every scholarship they've applied to — deadlines, required documents, submission status, and outcomes — all in one place.

### 🔔 Deadline & Opportunity Alerts
Timely notifications ensure students never miss a scholarship deadline or a newly added opportunity that matches their profile.

### 📈 Profile Completeness Score
A dynamic score shows students how complete and competitive their profile is, with actionable suggestions to improve it.

### 🌍 Diverse Scholarship Coverage
MeritLink aggregates scholarships across a wide range — undergraduate, postgraduate, research grants, country-specific, international, merit-based, need-based, and more.

---

## ⚙️ How It Works

```
1. Student creates an account and builds their academic profile
       ↓
2. MeritLink analyses the profile against a curated scholarship database
       ↓
3. Matched scholarships are surfaced on the student's personalised dashboard
       ↓
4. Student accesses resources to strengthen their application for each opportunity
       ↓
5. Student applies, tracks progress, and receives outcome notifications
```

---

## 🛠 Tech Stack

> The stack below reflects the planned architecture. This will be updated as implementation progresses.

| Layer | Technology |
|---|---|
| **Backend** | Python / Django |
| **Frontend** | HTMX + Tailwind CSS |
| **Database** | PostgreSQL |
| **Authentication** | django-allauth (Email, Google OAuth) |
| **Task Queue** | Celery + Redis *(for scholarship fetching & notifications)* |
| **Deployment** | TBD |

---

## 🗺 Roadmap

### Phase 1 — Foundation
- [ ] Project setup and architecture
- [ ] User authentication (email + OAuth)
- [ ] Student academic profile model and forms
- [ ] Basic dashboard UI

### Phase 2 — Core Matching Engine
- [ ] Scholarship database schema and seed data
- [ ] Profile-to-scholarship matching algorithm
- [ ] Personalised scholarship feed on dashboard
- [ ] Search and filter interface

### Phase 3 — Profile Optimization & Resources
- [ ] Per-scholarship application tips and guidance
- [ ] Profile completeness scoring system
- [ ] Resource library (writing personal statements, CVs, etc.)

### Phase 4 — Notifications & Tracking
- [ ] Application status tracker
- [ ] Deadline reminder system
- [ ] Email / in-app notifications

### Phase 5 — External Integrations & Growth
- [ ] Automated scholarship data fetching from external sources
- [ ] Admin panel for scholarship curation
- [ ] Analytics dashboard for users

---

## 🏗 Project Structure

> To be updated as the codebase grows.

```
meritlink/
├── accounts/          # User auth and profile management
├── scholarships/      # Scholarship models, matching engine, feeds
├── resources/         # Profile tips and optimization content
├── notifications/     # Alerts and deadline reminders
├── templates/         # HTML templates (HTMX-powered)
├── static/            # CSS, JS, assets
├── config/            # Django settings and project configuration
└── manage.py
```

---

## 🚀 Getting Started

> Setup instructions will be added once the initial codebase is in place.

```bash
# Clone the repository
git clone https://github.com/your-username/meritlink.git
cd meritlink

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Start the development server
python manage.py runserver
```

---

## 🤝 Contributing

MeritLink is currently in early development. Contributions, ideas, and feedback are welcome once the initial foundation is laid. Watch this repo to stay updated.

If you have suggestions or want to get involved early, feel free to open an issue.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

<div align="center">

Built with purpose — to make scholarships accessible to every deserving student.

</div>
