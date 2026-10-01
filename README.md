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
    ├── avto/                 main app: models, views, admin, tests, storage.py (versioned static URLs)
    ├── templates/
    │   ├── dashboard/
    │   │   ├── auth_base.html      shared layout for login.html + forgotlogin.html
    │   │   ├── base_panel.html     shared layout for the logged-in panel pages
    │   │   ├── _user_menu.html     top-bar profile/logout dropdown, included by every panel page
    │   │   ├── login.html          two-step login (choose profile → phone/username + password)
    │   │   ├── profile.html        read-only student profile page
    │   │   ├── shablon-test.html   Shablon testlar list with the per-category progress bar
    │   │   └── result.html         test result page (shared by all test kinds)
    │   └── exam/exam.html    exam page — practice tests and the real exam share this template,
    │                         switched by the `practice` flag (see Exam engine below)
    ├── static/
    │   ├── exam/              exam page CSS + JS
    │   ├── dashboard/         login, profile, sidebar, user-menu, practice-list CSS/JS
    │   └── assets_dashboard/  third-party admin theme (Unikit); do not add page-specific
    │                          styles here, use static/dashboard/*.css instead
    └── locale/               ru, uz_KR translations (uz is the source language)
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

Static file URLs are automatically suffixed with the file's modification time (`avto.storage.VersionedStaticFilesStorage`), so editing a CSS/JS file and reloading always gets the new version — the dev server sends no cache headers, so without this a browser can keep an old cached copy indefinitely.

## Login and roles

- **Students** log in with their phone number (any format, with or without `+998`) and password. The login form fixes `+998` and masks the rest as `99-999-99-99`. Teachers manage students in **Admin → Talabalar** (`/admin/students/`, `avto/student_views.py`): create/edit, search, group filter, auto-generated passwords (name + birth year, e.g. `Abdu2006`), visible passwords (`User.initial_password`), reset, block/unblock (`User.is_blocked`) and delete. Students cannot change their password.
- **Staff** (instructors, teachers, admins) log in with their username and password, and are sent to the Django admin. The staff profile on the login page only accepts accounts with `is_staff=True`.
- The login page (`templates/dashboard/login.html`) is a two-step flow: pick a profile (Student/Staff), then enter credentials. `Parolni unutdingizmi?` links to `forgotlogin.html`, which lists the active contacts from `ContactPerson` (admin panel) for the student to call — there is no self-service password reset.
- A student's exam/question language (`User.group_language`: uz / uz-kr / ru) is independent of the site's UI language switcher — set per student in the admin to match the group they study in.

## Student profile

`/profile/` (linked from the top-bar user menu, `templates/dashboard/profile.html`) shows the student's photo, school, branch, study category (A/B/BC/C/D), group, teacher, study dates, birth date and passport number — all read-only. Password changes are admin-only. Fields live on `Branch`, `StudyGroup` and `User` in `avto/models.py` and are edited from the admin panel.

## Panel sidebar

The left sidebar (`static/dashboard/sidebar.js` + `sidebar.css`, included via `base_panel.html` and each panel template) only opens or collapses when the hamburger button is clicked — hovering never changes its state. Collapsed, it shows icons only; hovering an icon shows a tooltip with the page name. The open/closed choice is remembered per browser (`localStorage`). Below 992px it becomes an off-canvas drawer instead.

## Exam engine

One template (`templates/exam/exam.html`) serves both practice tests (Shablon, Mavzulashtirilgan, O'xshash — `practice: true`) and the real exam (`practice: false`), with different layouts and behaviour:

**Shared logic**
- Each test session gets a fixed, randomly picked set of questions (`TestSession.question_order`); the count and time limit come from `TestCategory`.
- When a student returns to an unanswered question, its options are reshuffled so every option moves to a different key — students must read the question instead of memorising positions.
- Correct answers are never sent to the browser. `submit_answer` grades on the server and rejects late, duplicate, or out-of-session answers. Finishing a test is POST-only and idempotent.

**Real exam** (image left, options right, square number cells): selecting an option opens a "Javobni tasdiqlaysizmi?" confirmation before it's submitted; after confirming, correctness shows briefly and it auto-advances to the next question.

**Practice tests** (options left, image right, circular number cells): selecting an option submits immediately — no confirmation — and shows the result in place (correct option turns green with a ✓, a wrong pick turns red with a ✕). A header toggle, "Avtomatik o'tish" (off by default, remembered per browser), controls whether it then auto-advances like the real exam or stays on the question. A+/A− controls scale question and option text up to 175% / down to 73%, remembered per browser; the page layout never lets the image, header or navigator scroll off screen.

Keyboard: F1…F9 choose an option, Enter confirm (real exam only), ← → previous/next question, L fullscreen, Esc finish.

## Result page and Shablon testlar list

- The result page (`templates/dashboard/result.html`) shows the score, a per-question grid, "Bosh sahifa" (primary button — returns to the list page for whichever test kind was just finished: Shablon testlar, Real imtihon, Mavzulashtirilgan or O'xshash) and "Qayta boshlash" (secondary — restarts the same category). This mapping is `LIST_URL_NAMES` / `RESTART_URL_NAMES` in `avto/views.py`.
- The Shablon testlar list (`templates/dashboard/shablon-test.html`) shows a single segmented progress bar per started category — correct (green) / wrong (red) / skipped (amber), sized exactly proportional to the counts via CSS `flex-grow` — plus a small count legend. Not-started categories show a neutral "Hali boshlanmagan" placeholder. Styles: `static/dashboard/practice-list.css`.

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

## Admin workflow (Students → Teachers → Groups)

1. **O‘qituvchilar** (`/admin/teachers/`, superusers only): create a teacher (login + generated password). Teachers are staff accounts and log in via the «Xodim» profile.
2. **Talabalar** (`/admin/students/`): create a student (phone login + generated password). A group can be chosen right away or left empty.
3. **Guruhlar** (`/admin/groups/`): create a group (name, category, branch, **teacher picked from the list**, lesson time). Open the group → **Talaba qo‘shish** lists existing students (search, multi-select; students already in another group are moved). The ✕ button removes a student from the group.
4. **Changing a student's group**: open the student → «Boshqa guruhga o‘tkazish» → pick the new group → save. The group, teacher and lesson time on the student's profile update automatically; no remove/re-add.
5. **Access window (when a student can log in):** a new student is *open-ended* — active until the teacher ends it, because nobody knows in advance when they will pass the exam. Instead of guessing a date, use the student's ⋮ menu → **Kirish muddati**: `+2 hafta`, `+1 oy`, `+2 oy` (added on top of the current end date, or from today if it already expired) or `Muddatsiz qilish`. When the date passes the student can no longer log in; extending reopens the account instantly. **Bloklash** is a separate manual switch that overrides everything. Status labels and filters share one rule (`User.access_state`), so they can never disagree; students with no end date are open-ended (migration `0014`). The Talabalar filters are exact: *Faol* (not blocked, not expired), *Muddati tugagan*, *Bloklangan*.
6. The student's `/profile/` shows group, teacher, lesson time, branch and category.

## Groups & leaderboard

- **Admin → Reyting** is the global leaderboard (filter by group/period, sort); each group page has its own.
- **Students → Reyting** (`/leaderboard/`): own rank in the group and among all students, top 10/20/50, period filter. Other students are shown as «Ali T.» only.
- Scoring lives in `avto/leaderboard.py`: points = unique questions answered correctly + 20 per passed real exam (finished tests only); ties broken by accuracy.
