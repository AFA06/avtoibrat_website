"""The school's original lecture decks, prepared for reading on the web."""
import json
from functools import lru_cache
from pathlib import Path

SLUGS = ("warning", "priority", "prohibition", "mandatory", "information", "service", "additional")
TITLES = {
    "uz": ("Ogohlantiruvchi belgilar", "Imtiyoz belgilari", "Taqiqlovchi belgilar", "Buyuruvchi belgilar", "Axborot-ishora belgilari", "Servis belgilari", "Qo‘shimcha axborot belgilari"),
    "uz-kr": ("Огоҳлантирувчи белгилар", "Имтиёз белгилари", "Тақиқловчи белгилар", "Буюрувчи белгилар", "Ахборот-ишора белгилари", "Сервис белгилари", "Қўшимча ахборот белгилари"),
    "ru": ("Предупреждающие знаки", "Знаки приоритета", "Запрещающие знаки", "Предписывающие знаки", "Информационно-указательные знаки", "Знаки сервиса", "Знаки дополнительной информации"),
}
DESCRIPTIONS = {
    "uz": ("Oldindagi xavfni tanib oling va unga tayyorlaning.", "Chorraha va tor yo‘llarda kim birinchi o‘tishini eslang.", "Cheklovlar, istisnolar va belgilarning ta’sir doirasini takrorlang.", "Qaysi yo‘nalishda va qanday harakatlanish kerakligini ko‘rib chiqing.", "Yo‘l tartibi, yo‘nalishlar va aholi punktlari haqidagi belgilar.", "Yo‘ldagi yordam, yonilg‘i va dam olish joylarini tanib oling.", "Asosiy belgining masofasi, vaqti va ta’sirini aniqlashtiruvchi lavhalar."),
    "uz-kr": ("Олдиндаги хавфни таниб олинг ва унга тайёрланинг.", "Чорраҳа ва тор йўлларда ким биринчи ўтишини эсланг.", "Чекловлар, истиснолар ва белгиларнинг таъсир доирасини такрорланг.", "Қайси йўналишда ва қандай ҳаракатланиш кераклигини кўриб чиқинг.", "Йўл тартиби, йўналишлар ва аҳоли пунктлари ҳақидаги белгилар.", "Йўлдаги ёрдам, ёнилғи ва дам олиш жойларини таниб олинг.", "Асосий белгининг масофаси, вақти ва таъсирини аниқлаштирувчи лавҳалар."),
    "ru": ("Распознавайте опасность впереди и готовьтесь к ней.", "Вспомните очерёдность проезда перекрёстков и узких участков.", "Повторите ограничения, исключения и зоны действия знаков.", "Разберите разрешённые направления и порядок движения.", "Знаки режимов движения, направлений и населённых пунктов.", "Находите помощь, заправки и места отдыха в пути.", "Таблички, уточняющие расстояние, время и действие основного знака."),
}
# Explicit copy keeps every reader control in the selected language.
COPY = {
    "uz": {
        "video": "Video misoli", "title": "Dars konspektlari", "eyebrow": "O‘quv materiallari", "intro": "Unutilgan qoidani eslang. Kerakli mavzuni oching, belgilar va yo‘l vaziyatlarini darsdagi misollar bilan takrorlang.",
        "topics": "Mavzular", "slides": "sahifa", "examples": "Misollar va savollar", "rule": "Qoida", "example": "Misol / savol", "all": "Barchasi", "rules": "Qoidalar", "saved": "Belgilanganlar", "search": "Belgi raqami yoki so‘z bo‘yicha qidirish", "search_hint": "Masalan: 3.1, quvib o‘tish, чорраҳа", "open": "Mavzuni ochish", "resume": "Davom etish", "viewed": "Ko‘rilgan", "empty": "Hech narsa topilmadi. Boshqa so‘z bilan urinib ko‘ring.", "clear": "Qidiruvni tozalash", "back": "Barcha mavzular", "contents": "Mavzu sahifalari", "prev": "Oldingi", "next": "Keyingi", "page": "Sahifa", "of": "/", "save": "Belgilash", "unsave": "Belgini olib tashlash", "text": "Sahifa matni", "enlarge": "Rasmni kattalashtirish", "close": "Yopish", "zoom_in": "Kattalashtirish", "zoom_out": "Kichraytirish", "reset_zoom": "O‘lchamni tiklash", "focus": "Keng ko‘rinish", "exit_focus": "Oddiy ko‘rinish", "help": "← → sahifalarni almashtirish · Esc yopish", "local": "O‘qish joyi va belgilangan sahifalar shu brauzerda saqlanadi.", "source": "Dars taqdimotidan. Savolni o‘qing, javobni o‘zingiz o‘ylab ko‘ring va oldingi qoida bilan solishtiring.", "language_note": "O‘zbekcha dars slaydlari asl nusxadagi kirill yozuvida berilgan.", "image_error": "Rasm yuklanmadi. Sahifa matnini quyida o‘qishingiz mumkin.", "retry": "Qayta yuklash", "saved_empty": "Hali sahifa belgilanmagan. Kerakli sahifada yulduzchani bosing.", "matches": "Topilgan sahifalar", "read": "O‘qish", "first": "Boshidan o‘qish", "end": "Mavzu oxiriga yetdingiz. Kerakli sahifalarni yana ko‘ring yoki boshqa mavzuni tanlang.", "no_text": "Bu sahifada ko‘rgazmali misol berilgan. Rasmni kattalashtirib ko‘ring.", "noscript": "Sahifalar ro‘yxatidan kerakli sahifani tanlang. Qidiruv va belgilar uchun JavaScript yoqilgan bo‘lishi kerak.",
    },
    "ru": {
        "video": "Видеопример", "title": "Конспекты уроков", "eyebrow": "Учебные материалы", "intro": "Вспомните забытое правило. Откройте нужную тему и повторите знаки и дорожные ситуации на примерах из урока.",
        "topics": "Темы", "slides": "страниц", "examples": "Примеры и вопросы", "rule": "Правило", "example": "Пример / вопрос", "all": "Все", "rules": "Правила", "saved": "Закладки", "search": "Поиск по номеру знака или слову", "search_hint": "Например: 3.1, обгон, перекрёсток", "open": "Открыть тему", "resume": "Продолжить", "viewed": "Просмотрено", "empty": "Ничего не найдено. Попробуйте другое слово.", "clear": "Очистить поиск", "back": "Все темы", "contents": "Страницы темы", "prev": "Назад", "next": "Далее", "page": "Страница", "of": "/", "save": "В закладки", "unsave": "Убрать закладку", "text": "Текст страницы", "enlarge": "Увеличить изображение", "close": "Закрыть", "zoom_in": "Увеличить", "zoom_out": "Уменьшить", "reset_zoom": "Сбросить масштаб", "focus": "Широкий вид", "exit_focus": "Обычный вид", "help": "← → сменить страницу · Esc закрыть", "local": "Место чтения и закладки сохраняются в этом браузере.", "source": "Из учебной презентации. Прочитайте вопрос, обдумайте ответ и сравните с предыдущим правилом.", "language_note": "", "image_error": "Изображение не загрузилось. Текст страницы доступен ниже.", "retry": "Повторить загрузку", "saved_empty": "Закладок пока нет. Нажмите звёздочку на нужной странице.", "matches": "Найденные страницы", "read": "Читать", "first": "Читать с начала", "end": "Вы дошли до конца темы. Повторите нужные страницы или выберите другую тему.", "no_text": "На этой странице — наглядный пример. Откройте изображение крупнее.", "noscript": "Выберите страницу в списке. Для поиска и закладок нужен JavaScript.",
    },
    "uz-kr": {
        "video": "Видео мисоли", "title": "Дарс конспектлари", "eyebrow": "Ўқув материаллари", "intro": "Унутилган қоидани эсланг. Керакли мавзуни очинг, белгилар ва йўл вазиятларини дарсдаги мисоллар билан такрорланг.",
        "topics": "Мавзулар", "slides": "саҳифа", "examples": "Мисоллар ва саволлар", "rule": "Қоида", "example": "Мисол / савол", "all": "Барчаси", "rules": "Қоидалар", "saved": "Белгиланганлар", "search": "Белги рақами ёки сўз бўйича қидириш", "search_hint": "Масалан: 3.1, қувиб ўтиш, чорраҳа", "open": "Мавзуни очиш", "resume": "Давом этиш", "viewed": "Кўрилган", "empty": "Ҳеч нарса топилмади. Бошқа сўз билан уриниб кўринг.", "clear": "Қидирувни тозалаш", "back": "Барча мавзулар", "contents": "Мавзу саҳифалари", "prev": "Олдинги", "next": "Кейинги", "page": "Саҳифа", "of": "/", "save": "Белгилаш", "unsave": "Белгини олиб ташлаш", "text": "Саҳифа матни", "enlarge": "Расмни катталаштириш", "close": "Ёпиш", "zoom_in": "Катталаштириш", "zoom_out": "Кичрайтириш", "reset_zoom": "Ўлчамни тиклаш", "focus": "Кенг кўриниш", "exit_focus": "Оддий кўриниш", "help": "← → саҳифаларни алмаштириш · Esc ёпиш", "local": "Ўқиш жойи ва белгиланган саҳифалар шу браузерда сақланади.", "source": "Дарс тақдимотидан. Саволни ўқинг, жавобни ўзингиз ўйлаб кўринг ва олдинги қоида билан солиштиринг.", "language_note": "", "image_error": "Расм юкланмади. Саҳифа матнини қуйида ўқишингиз мумкин.", "retry": "Қайта юклаш", "saved_empty": "Ҳали саҳифа белгиланмаган. Керакли саҳифада юлдузчани босинг.", "matches": "Топилган саҳифалар", "read": "Ўқиш", "first": "Бошидан ўқиш", "end": "Мавзу охирига етдингиз. Керакли саҳифаларни яна кўринг ёки бошқа мавзуни танланг.", "no_text": "Бу саҳифада кўргазмали мисол берилган. Расмни катталаштириб кўринг.", "noscript": "Саҳифалар рўйхатидан керакли саҳифани танланг. Қидирув ва белгилар учун JavaScript ёқилган бўлиши керак.",
    },
}


def language(code):
    return code if code in COPY else "uz"


@lru_cache(maxsize=2)
def load_decks(code):
    source = "ru" if code == "ru" else "uz"
    return json.loads((Path(__file__).parent / "data" / "lectures" / f"{source}.json").read_text())


def asset_url(name):
    from .lecture_storage import LectureStorage
    from django.templatetags.static import static
    return LectureStorage().url(name[6:]) if name.startswith("media:") else static(name)


def topics_for(code):
    from django.db.models import Prefetch
    from .lecture_models import LectureTopic, LecturePage
    code = language(code)
    lang = "ru" if code == "ru" else "uz"
    pages = LecturePage.objects.filter(language=lang, published=True, deleted=False)
    topics = []
    for topic in LectureTopic.objects.filter(published=True, deleted=False).prefetch_related(Prefetch("pages", queryset=pages, to_attr="visible_pages")):
        visible = [p for p in topic.visible_pages if p.image_name]
        if not visible or (lang == "ru" and not topic.title_ru):
            continue
        slides = [{"id": p.pk, "number": n, "title": p.title, "paragraphs": [line.strip() for line in p.text.splitlines() if line.strip()], "kind": p.kind, "image": p.image_name, "thumbnail": p.thumbnail_name, "video": p.video_name} for n, p in enumerate(visible, 1)]
        suffix = {"ru": "_ru", "uz-kr": "_kr"}.get(code, "")
        start = next((n for n, page in enumerate(visible, 1) if not page.is_cover), 1)
        topics.append({"slug": topic.slug, "number": len(topics)+1, "title": getattr(topic, "title"+suffix) or topic.title,
                       "description": getattr(topic, "description"+suffix) or topic.description,
                       "slides": slides, "count": len(slides), "examples": sum(s["kind"] == "example" for s in slides),
                       "source": next((d["source"] for d in load_decks(lang) if d["slug"] == topic.slug), ""), "ratio": 1.77778, "start_page": start, "preview": slides[start-1]["thumbnail"], "revision": topic.revision})
    return topics
