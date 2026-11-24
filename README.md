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

## Deploy on a Linux VPS

Run Django with Gunicorn behind an HTTPS reverse proxy such as Nginx. Keep the application, PostgreSQL, and persistent upload directories in the chosen region. Set these variables in the service or deployment environment:

| Variable | Example or purpose |
| --- | --- |
| `DJANGO_SETTINGS_MODULE` | `core.settings_prod` |
| `DJANGO_ALLOWED_HOSTS` | `avtoibrat.uz,www.avtoibrat.uz` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://avtoibrat.uz,https://www.avtoibrat.uz` |
| `SECRET_KEY` | Private Django signing key |
| `DATABASE_URL` | Private PostgreSQL connection URL |
| `AVTO_MEDIA_ROOT` | `/var/lib/avtoibrat/media` |
| `AVTO_PRIVATE_MEDIA_ROOT` | `/var/lib/avtoibrat/private_media` |

Use Python 3.12 or newer and install FFmpeg for audio uploads. Create both upload directories with write access for the service account. Keep the private directory outside the public one and let Django serve its files through the existing permission checks.

From the repository root, run `./core/build.sh` in the production virtual environment. It installs dependencies, collects static assets, runs migrations, and imports bundled exam content. For a new database, set `ADMIN_USERNAME` and `ADMIN_PASSWORD` during the initial build or create the admin with `python manage.py createsuperuser`. The demo account is seeded only when `DEMO_PASSWORD` is set.

Run `gunicorn core.wsgi:application --bind 127.0.0.1:8000` from the `core/` directory under a service manager such as systemd. Have the reverse proxy forward the original hostname and overwrite `X-Forwarded-Proto` with its own request scheme. Forward public requests to Gunicorn, or serve `/media/` from the public upload directory through Nginx. Keep Gunicorn on loopback and PostgreSQL on a private listener.

For a host migration, restore the PostgreSQL dump into the destination database and copy both upload directories before running the build and switching DNS. Test staff sign-in and password changes, a complete student exam, and protected audio playback on the destination first. Schedule encrypted off-server backups of the database and both upload directories. If PostgreSQL is reachable only from the VPS, run the backup job there and send its encrypted output to separate storage.

## Login and roles

- **Students** log in with their phone number and password. Teachers can create and manage students in their assigned groups under **Admin → Talabalar**. Administrators can also archive and restore accounts. On creation or reset, share the temporary password shown on the confirmation page. The account holder must replace it before using the platform.
- **Staff** (instructors, teachers, admins) log in with their username and password, and are sent to the Django admin. The staff profile on the login page only accepts accounts with `is_staff=True`.
- The login page (`templates/dashboard/login.html`) is a two-step flow: pick a profile (Student/Staff), then enter credentials. `Parolni unutdingizmi?` links to `forgotlogin.html`, which lists the stored active contacts from `ContactPerson` for the student to call — there is no self-service password reset.
- The student support page uses `SCHOOL_CONTACT_PHONE`. Set the optional `SCHOOL_SUPPORT_TELEGRAM_URL` environment variable to the school administrator's Telegram link to show a direct-message button.
- A student's exam/question language (`User.group_language`: uz / uz-kr / ru) is independent of the site's UI language switcher — set per student in the admin to match the group they study in.

## Student profile

`/profile/` (linked from the top-bar user menu, `templates/dashboard/profile.html`) shows the student's photo, school, branch, study category (A/B/BC/C/D), group, teacher, study dates, birth date and passport number — all read-only. Password changes are admin-only. Fields live on `Branch`, `StudyGroup` and `User` in `avto/models.py` and are edited from the admin panel.

## Panel sidebar

The left sidebar (`static/dashboard/sidebar.js` + `sidebar.css`, included via `base_panel.html` and each panel template) only opens or collapses when the hamburger button is clicked — hovering never changes its state. Collapsed, it shows icons only; hovering an icon shows a tooltip with the page name. The open/closed choice is remembered per browser (`localStorage`). Below 992px it becomes an off-canvas drawer instead.

## Marathon

Students choose sections of 50 / 300 / 500 / 700 questions, or the whole enabled mixed bank, at `/marafon/` (`avto/marathon.py`, `marathon_views.py`). Sections follow the stored question order; the real exam samples randomly from this bank. Each question gets one minute. An unfinished marathon can be resumed; starting a new one finishes the previous one. Only questions enabled for mixed exams/marathon enter this pool.

The student sidebar lives in one place, `templates/dashboard/_sidebar_nav.html`, included by every panel page.

## Question placement and ordering

In **Admin → Savollar**, each question has independent switches for bilet tests, topic tests, the mixed real-exam/marathon bank, and automatic similar-question grouping. A category is still retained as the question’s organizational parent; switching off bilet use excludes it from bilet tests. A main topic is required only when topic tests are enabled. Defaults preserve the existing question bank.

Use **Shundan keyin qo‘shish** in the question list, or enter **Joylashuv raqami = 13** to insert between the current 12th and 13th questions. Choose whether the position is in the selected bilet or primary topic. Topic positions are stored independently, so editing them does not rearrange bilets. Blank position appends new questions and preserves ordinary edits. Bilet practice and full-topic mode follow the stored order; quick-topic and mixed exams remain random. When a bilet was using every available question, its question limit follows additions/removals. Existing attempt snapshots and historical score denominators are preserved.

The editor can also select existing O‘xshash/aralash collections and their insertion position, or create a named mixed collection (Russian name optional). Membership changes create a new active collection version and retire the previous one; saved attempts retain the old group and question IDs/order. The automatic rebuild respects manually overridden collection/topic scopes and does not recreate or retire them. Manual mixed collections appear alongside similar-question tests. Automatic grouping is optional and still runs through `build_similar_groups`; explicit assignments take effect immediately.

## O‘xshash savollar (similar questions)

`/ohshash_savollar/` offers collections for similar road signs, identical pictures, matching answer sets, and teacher-created mixed sets. Older situation collections remain available to historical attempts but are not listed. `python manage.py build_similar_groups` rebuilds automatic collections from enabled questions; `build.sh` runs it on deployment. Explicit manual assignments are protected from this rebuild.

Every included question needs a matching partner. Images use a 256-bit difference hash: distance ≤ 20 links near-identical pictures; distance ≤ 35 additionally requires TF-IDF wording similarity ≥ 0.4. Situation pairs must share a topic. Wording alone (cosine ≥ 0.6, at least eight words) is accepted only when neither question has a picture, so generic wording cannot override different scenes. Blank/missing images cannot enter the road-sign test. Matched families stay together in a deterministic order; unrelated questions are never added to fill a test. Duplicate detection compares normalized full questions, every translated answer option and its correctness (ignoring option order), then the image. Resized/watermarked copies use the image distance limit of 35; different wording, numbers, choices, correct answers or dissimilar pictures remain separate. A discarded copy never acts as a match for discarding another question.

The road-sign test uses the `yol-belgilari` topic section. The situation test uses intersections, signals/markings, manoeuvres, special road situations, general rules and transport. Medical/technical sections are excluded. The grouping is a conservative automatic heuristic based on existing topic assignments, not manual verification of every pair.

A collection whose questions did not change keeps its ID and results on rebuild. Replaced groups are switched off (`aktiv=False`), never deleted; previous attempts remain readable. `TestSession.similar_group` runs are not counted as bilet runs on the season road.

## Road signs

Students browse `/road_signs/`; teachers manage the content in **Admin → Belgilar** (`/admin/road-signs/`, `avto/road_sign_views.py`): add a category (cover picture optional), add signs to it (image PNG/JPG/GIF/WEBP/SVG, number, name, description) with «Saqlash va yana qo‘shish» for batches, and reorder categories with the arrows. Signs are shown sorted by number part by part (1.2 before 1.10, `avto/road_signs.py`); categories follow their `order`. Annotated queries ignore `Meta.ordering`, so category lists always use `ordered_categories()`.

## Student lecture notes

**O‘quv materiallar → Dars konspektlari** (`/uz/konspekt/`, `/ru/konspekt/`) contains the seven supplied road-sign lectures. Russian uses the Russian decks; both Uzbek interface modes use the original Uzbek Cyrillic decks. The existing Shpargalka remains available.

Students can search all slide text (including Uzbek Latin searches against Cyrillic text), choose a topic, filter rules/examples, jump to a page, enlarge diagrams, open the slide text, and bookmark pages. Previous/next follows the selected filter. Reading position, viewed-page counts and bookmarks are stored per student and deck language in that browser; they are reading history, not test scores or proof of mastery. The site's language switch keeps the current page number. Embedded video is included; the original presentation's animations and unavailable external video files are not reproduced.

**Admin → Konspektlar** (`/admin/lectures/`, school administrators only) manages topics and their Uzbek/Russian pages. Create a topic, choose its language, add individual pages or import a PDF/batch of images, review drafts, then select pages and press **Ko‘rsatish**. Hide, reorder, edit text, replace images/video, and recover deleted topics or pages from **Savatcha**. PowerPoint presentations must first be saved as PDF; uploads append pages and never silently replace existing content. Text edits affect the searchable/readable text; replacing the picture changes the slide itself.

The authoritative content is now `LectureTopic` / `LecturePage` in the database. Migration 0041 imports all 1,049 original pages exactly once; subsequent deployments do not overwrite edits. The original JSON snapshots retain source filenames/hashes, and original static assets remain available. Uploaded files use lecture-specific database storage (`LectureUpload`), so they survive ephemeral deployment disks and are included in database backups. Upload URLs are immutable random IDs, with byte-range support for video. Deleted and replaced files are retained for recovery. Reading progress and bookmarks follow stable page IDs when pages are reordered or edited. Hidden/deleted page bookmarks remain available if the page is restored; old ordinal bookmarks are upgraded on first use, or reset if the structure already changed.

Imports allow up to 50 MB per request, 100 input files and 200 output pages; PDFs must be unencrypted. Imported pages are drafts, each language is managed independently, and empty/hidden content never appears in the student library. New topics start hidden. Russian topics require a Russian title before appearing to Russian students. No migration removes existing tables or exam history.

To rebuild, export all 14 decks as PDFs at their native slide dimensions, named `uz-1.pdf` … `uz-7.pdf` and `ru-1.pdf` … `ru-7.pdf`, then run `python scripts/build_lectures.py --slides 'Slides ' --pdfs /path/to/pdfs` with Pillow and Poppler installed. The script checks source/rendered page counts before writing the original snapshots; it does not overwrite the editable database library. No PowerPoint converter is needed in production.

## Exam engine

One template (`templates/exam/exam.html`) serves both practice tests (Shablon, Mavzulashtirilgan, O'xshash — `practice: true`) and the real exam (`practice: false`), with different layouts and behaviour:

**Shared logic**
- Each test session keeps a fixed snapshot (`TestSession.question_order`). Bilet practice follows admin order; real/quick tests sample randomly. Category settings control bilet count/time.
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

The admin sidebar contains only Dashboard, Talabalar, Guruhlar, Express, Vazifalar, Savollar, Konspektlar, Belgilar, Monitoring, O‘qituvchilar and Reyting, with administrator-only sections hidden from teachers. The retired model-admin pages, global contact-message search and dashboard inbox have been removed. Branch and topic forms remain as helpers linked from Guruhlar and Savollar. Public-site content, study materials, exam history and login protection still use their existing models and data; this admin cleanup does not drop database tables.

1. **O‘qituvchilar** (`/admin/teachers/`, superusers only): create a teacher and share their username and temporary password. Teachers log in through the **Xodim** profile.
2. **Talabalar** (`/admin/students/`): create a student with a phone login and temporary password. Teachers must choose one of their assigned groups. Administrators can leave the group empty.
3. **Guruhlar** (`/admin/groups/`): administrators create groups, assign teachers, configure lesson schedules and move students between groups. Teachers see only their assigned groups and related monitoring data.
4. **Changing a student's group**: open the student → «Boshqa guruhga o‘tkazish» → pick the new group → save. The group, teacher and lesson time on the student's profile update automatically; no remove/re-add.
5. **Access window (when a student can log in):** a new student is *open-ended* — active until the teacher ends it, because nobody knows in advance when they will pass the exam. Instead of guessing a date, use the student's ⋮ menu → **Kirish muddati**: `+2 hafta`, `+1 oy`, `+2 oy` (added on top of the current end date, or from today if it already expired) or `Muddatsiz qilish`. When the date passes the student can no longer log in; extending reopens the account instantly. **Bloklash** is a separate manual switch that overrides everything. Status labels and filters share one rule (`User.access_state`), so they can never disagree; students with no end date are open-ended (migration `0014`). The Talabalar filters are exact: *Faol* (not blocked, not expired), *Muddati tugagan*, *Bloklangan*.
6. The student's `/profile/` shows group, teacher, lesson time, branch and category.

## Assigning tests (Vazifalar)

In **Admin → Vazifalar → Yangi vazifa**, choose the recipients, select **Biletlar** or **Mavzulashtirilgan testlar**, tick the exact tests and save. Search and select-all controls work on the filtered list. A title is optional; the form generates one when omitted. The start date and optional final submission date apply to the whole selection.

- **Express:** all Express students or explicitly selected Express students. A teacher's choices include only Express students in their own groups; the teacher's “all” choice saves that bounded selection. An administrator's all-Express task also reaches students added to Express later.
- **Guruh:** every current student in the chosen group, including Express members of that group. Teachers can choose only their own groups.
- **Alohida talabalar:** explicitly selected students with neither a group nor Express membership. Administrators manage this audience. Moving a recipient into a group or Express removes their access to this individual task.

Students open **Vazifalar** to see the exact assigned tests and open/resume each one directly. A topic assignment includes all its active questions. Finishing every question counts that test once; correctness is shown separately. Unrelated practice, unfinished attempts and repeats do not complete other assigned tests. Each assignment has its own attempts and completion records. Results return to the assignment, and completion survives practice-statistics resets. Removing a task preserves exam history. Existing daily-count tasks keep their original behavior and remain editable; use **Aniq bilet yoki mavzularga o‘tkazish** in their editor to convert them explicitly. New tasks require exact content selections.

## Groups & leaderboard

- **Admin → Reyting** is the global leaderboard (filter by group/period, sort); each group page has its own.
- **Students → Reyting** (`/leaderboard/`, `avto/leaderboard_views.py`): a «my rank» card (rank in group, rank among all students, points), a search box, a **Mening guruhim / Barcha talabalar** switch, a metric selector (ball / aniqlik / yechilgan / testlar / **faollik** = number of days with a finished test, so regular students rank high even with fewer points), a period filter and Top 10/20/50. The top three by rank always get a podium (crown for #1) under every filter and sort; the student's own row is always shown, even outside the top N. Other students appear as «Ali T.» only.
- The leaderboard UI is one shared component: `templates/leaderboard/` + `static/dashboard/leaderboard.css`, used by the student page and by the admin group page / **Reyting** page (`.lb--admin` maps the colours to the admin theme).
- Scoring lives in `avto/leaderboard.py`: points = unique questions answered correctly + 20 per passed real exam (finished tests only). Ranking follows the selected metric; equal rows share a rank.

## Monitoring (teacher view of student practice)

**Admin → Monitoring** (`/admin/monitoring/`, `avto/monitoring.py` + `monitoring_views.py`), three steps so the list never gets huge:

1. **Pick a group** — cards show students, tests in the last 7 days, average accuracy and a red «N ta yechmayapti» badge. A «Guruhsiz talabalar» card covers students without a group.
2. **Group page** — every student with last activity, a 7-day strip (green = solved a test, yellow = only logged in, grey = absent), tests, accuracy, time spent, active days and a status: **Faol / Kam faol / Yechmayapti** (no test in the period; «kam faol» = tests on fewer than 25% of the days). Filter by status, search, choose 7/30/90 days and sort («Diqqat talab qiladi» puts the least active first).
3. **Student page** — KPI cards (tests, answered questions, accuracy, real exams passed, time spent, average time per question, days with a test, streak, logins), a daily activity chart, the hours of day the student practises (and, if the group has a schedule, how much happens on lesson days and in the 3 hours before the lesson — flags «darsdan oldin shoshilib yechmoqda»), accuracy per topic (weakest first), the most-missed questions, the test history and a day-by-day table. **Ko‘rish** opens a test question by question: the chosen answer, the correct one, time per question.

How it is measured
- *Time spent* is **active time**: the gap between two answers, with a pause longer than 5 minutes counted as 5 minutes (so a tab left open never inflates it). Answers saved before this feature have no timestamp (`UserAnswer.answered_at`); for those the session length is used, capped at 2 hours.
- *Entries* come from `LoginEvent`, written on every student sign-in (`avto/signals.py`). History starts from the day this feature was deployed.
- If a student presses «clear statistics», their sessions are deleted as before, but a `StatisticsReset` row is written and the student page shows a warning, so a teacher can see that history was wiped.
- Only students (not staff) are monitored; all queries are bulk (`collect()`), not per-student loops.

## Database backups

A GitHub Action (`.github/workflows/backup.yml`) copies the production database every night at
02:00 (Tashkent), encrypts it with `BACKUP_PASSPHRASE` and keeps it for 30 days under
**Actions → Database backup → a run → Artifacts**. «Run workflow» on that page makes a backup on demand.

It needs two repository secrets (**Settings → Secrets and variables → Actions → New repository secret**):

- `DATABASE_URL` — the Neon connection string, the same value as on Render
- `BACKUP_PASSPHRASE` — a long password. Keep a copy somewhere safe: without it no backup can be opened.

### Restoring a backup

1. Download the artifact (a zip holding `avtoibrat-YYYY-MM-DD.dump.gpg`) and unzip it.
2. Decrypt: `gpg --decrypt avtoibrat-YYYY-MM-DD.dump.gpg > backup.dump` (asks for the passphrase).
3. Create an empty PostgreSQL database or a separate database branch and restore into it:
   `pg_restore --no-owner --no-privileges -d "<connection string of the new database>" backup.dump`
4. Point the application service's `DATABASE_URL` at the restored database and restart or redeploy the service.

Restoring into a new database, never over the live one, keeps today's data in case the wrong day was picked.
