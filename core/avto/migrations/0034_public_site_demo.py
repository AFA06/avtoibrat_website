"""Demo content for the public home page, so it is never empty.

Everything here is marked as a sample (SchoolProfile.is_demo) and is replaced from the admin:
«Maktab ma’lumotlari», «Kurslar va narxlar» and «FAQ». Rows are only added when the table is empty,
so real content entered later is never overwritten.
"""
from django.db import migrations

COURSES = [
    dict(
        category="B", order=1, is_popular=True, price=4_500_000,
        title="Yengil avtomobil", title_kr="Енгил автомобил", title_ru="Легковой автомобиль",
        duration="2,5 oy", duration_kr="2,5 ой", duration_ru="2,5 месяца",
        features="Nazariy darslar\n40 soat amaliy haydash\nOnlayn imtihon platformasi\nImtihonga tayyorlov",
        features_kr="Назарий дарслар\n40 соат амалий ҳайдаш\nОнлайн имтиҳон платформаси\nИмтиҳонга тайёрлов",
        features_ru="Теоретические занятия\n40 часов вождения\nОнлайн-платформа для экзамена\nПодготовка к экзамену",
    ),
    dict(
        category="A", order=2, price=2_000_000,
        title="Mototsikl", title_kr="Мотоцикл", title_ru="Мотоцикл",
        duration="1 oy", duration_kr="1 ой", duration_ru="1 месяц",
        features="Nazariy darslar\n12 soat amaliy haydash\nOnlayn imtihon platformasi",
        features_kr="Назарий дарслар\n12 соат амалий ҳайдаш\nОнлайн имтиҳон платформаси",
        features_ru="Теоретические занятия\n12 часов вождения\nОнлайн-платформа для экзамена",
    ),
    dict(
        category="BC", order=3, price=6_500_000,
        title="Yengil va yuk avtomobili", title_kr="Енгил ва юк автомобили", title_ru="Легковой и грузовой",
        duration="3,5 oy", duration_kr="3,5 ой", duration_ru="3,5 месяца",
        features="Nazariy darslar\n60 soat amaliy haydash\nOnlayn imtihon platformasi\nImtihonga tayyorlov",
        features_kr="Назарий дарслар\n60 соат амалий ҳайдаш\nОнлайн имтиҳон платформаси\nИмтиҳонга тайёрлов",
        features_ru="Теоретические занятия\n60 часов вождения\nОнлайн-платформа для экзамена\nПодготовка к экзамену",
    ),
    dict(
        category="C", order=4, price=5_500_000,
        title="Yuk avtomobili", title_kr="Юк автомобили", title_ru="Грузовой автомобиль",
        duration="3 oy", duration_kr="3 ой", duration_ru="3 месяца",
        features="Nazariy darslar\n50 soat amaliy haydash\nOnlayn imtihon platformasi",
        features_kr="Назарий дарслар\n50 соат амалий ҳайдаш\nОнлайн имтиҳон платформаси",
        features_ru="Теоретические занятия\n50 часов вождения\nОнлайн-платформа для экзамена",
    ),
]

FAQS = [
    ("O‘qishni qachon boshlasam bo‘ladi?",
     "Yangi guruhlar har oy ochiladi. Ariza qoldiring — administrator eng yaqin guruh sanasini aytadi."),
    ("Onlayn imtihon platformasi nima?",
     "O‘quvchilarimiz rasmiy imtihon savollari bilan uyda va o‘quv xonasida mashq qiladi: real imtihon, "
     "marafon, mavzulashtirilgan testlar va yo‘l belgilari. Kirish ma’lumotlarini o‘qishga yozilgach olasiz."),
    ("To‘lovni bo‘lib to‘lash mumkinmi?",
     "Ha, kurs narxini ikki yoki uch qismga bo‘lib to‘lash mumkin. Batafsil ma’lumotni administrator beradi."),
    ("Amaliy darslar qaysi mashinada o‘tadi?",
     "Amaliy darslar o‘quv avtomobilida, ikki pedalli tizim bilan, tajribali instruktor yonida o‘tadi."),
]


def add_demo(apps, schema_editor):
    SchoolProfile = apps.get_model("avto", "SchoolProfile")
    Course = apps.get_model("avto", "Course")
    FAQ = apps.get_model("avto", "FAQ")

    if not SchoolProfile.objects.exists():
        SchoolProfile.objects.create(
            instructor_name="Ibrat",
            headline="Ishonchli haydovchi bo‘lishni biz bilan boshlang",
            headline_kr="Ишончли ҳайдовчи бўлишни биз билан бошланг",
            headline_ru="Станьте уверенным водителем вместе с нами",
            intro="Toshkentdagi haydovchilik maktabi: tajribali instruktor, aniq dastur va o‘quvchilar uchun "
                  "onlayn imtihon platformasi — rasmiy savollar bilan uyda ham mashq qilasiz.",
            intro_kr="Тошкентдаги ҳайдовчилик мактаби: тажрибали инструктор, аниқ дастур ва ўқувчилар учун "
                     "онлайн имтиҳон платформаси — расмий саволлар билан уйда ҳам машқ қиласиз.",
            intro_ru="Автошкола в Ташкенте: опытный инструктор, понятная программа и онлайн-платформа "
                     "для учеников — тренируйтесь на официальных вопросах даже дома.",
            years_experience=12,
            graduates=3000,
            pass_rate=92,
            phone="+998 94 627 41 11",
            telegram="https://t.me/",
            instagram="https://instagram.com/",
            address="Toshkent shahri",
            address_kr="Тошкент шаҳри",
            address_ru="г. Ташкент",
            hours="Du–Sha, 9:00–19:00",
            hours_kr="Ду–Ша, 9:00–19:00",
            hours_ru="Пн–Сб, 9:00–19:00",
            is_demo=True,
        )

    if not Course.objects.exists():
        for course in COURSES:
            Course.objects.create(**course)

    if not FAQ.objects.exists():
        for order, (question, answer) in enumerate(FAQS, start=1):
            FAQ.objects.create(question=question, answer=answer, order=order)


class Migration(migrations.Migration):
    dependencies = [("avto", "0033_public_site")]
    operations = [migrations.RunPython(add_demo, migrations.RunPython.noop)]
