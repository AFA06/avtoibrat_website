# AvtoIbrat

Website for the AvtoIbrat driving school (Tashkent): a public personal-brand site plus an exam-practice platform for enrolled students. Student accounts are created by the admin only — there is no public registration.

## Stack

- Python 3.12, Django 6.0, django-jazzmin (admin theme)
- SQLite in development
- Languages: Uzbek (latin), Uzbek (cyrillic), Russian

## Project structure

```
avtoibrat/
├── requirements.txt
└── core/                     Django project root (manage.py)
    ├── core/                 settings, root urls
    ├── avto/                 main app: models, views, admin, tests
    ├── templates/
    │   ├── exam/exam.html    exam page (practice + real exam)
    │   └── dashboard/        student cabinet pages, result page
    ├── static/
    │   ├── exam/             exam page CSS + JS
    │   └── dashboard/        result page CSS
    └── locale/               ru, uz_KR translations
```

## Run locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd core
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Site: http://127.0.0.1:8000/uz/ · Admin: http://127.0.0.1:8000/admin/

## Exam engine

- Each test session gets a fixed, randomly picked set of questions (`TestSession.question_order`); the count and time limit come from `TestCategory`.
- Layout: image on the left, answer options (F1…Fn) on the right, numbered question navigator at the bottom.
- When a student returns to an unanswered question, its options are reshuffled so every option moves to a different key — students must read the question instead of memorising positions.
- Correct answers are never sent to the browser. `submit_answer` grades on the server and rejects late, duplicate, or out-of-session answers. Finishing a test is POST-only and idempotent.

Keyboard: F1…F9 choose an option, Enter confirm, ← → previous/next question, L fullscreen, Esc finish.

## Tests

```bash
cd core
python manage.py test avto
```

## Translations

After editing `locale/*/LC_MESSAGES/django.po`:

```bash
cd core
python manage.py compilemessages
```
