from django.templatetags.static import static


SCENARIO_KEY = "bilet-16-question-14"
QUESTION_TEXT = "Avtomobillar chorrahani quyidagi tartibda kesib o'tadilar:"


def scenario_for(question):
    """Return the public animation config only for the verified proof-of-concept question."""
    if (
        question.matn_uzb != QUESTION_TEXT
        or question.kategoriya.tartib != 16
        or question.kategoriya.nomi != "Bilet 16"
    ):
        return None

    return {
        "id": SCENARIO_KEY,
        "duration": 7600,
        "viewBox": "0 0 945 530",
        "background": static("exam/animation/bilet-16-question-14-scene.svg"),
        "explanations": {
            "uz": (
                "Qizil avtomobil chorrahaga kirib, ko‘k avtomobilga yo‘l berish uchun to‘xtaydi. "
                "Shu paytda yashil avtomobil o‘tadi, keyin ko‘k avtomobil o‘tadi. "
                "Oxirida qizil avtomobil burilishni tugatadi."
            ),
            "uz-kr": (
                "Қизил автомобиль чорраҳага кириб, кўк автомобилга йўл бериш учун тўхтайди. "
                "Шу пайтда яшил автомобиль ўтади, кейин кўк автомобиль ўтади. "
                "Охирида қизил автомобиль бурилишни тугаллайди."
            ),
            "ru": (
                "Красный автомобиль выезжает на перекрёсток и останавливается, чтобы уступить синему. "
                "В это время проезжает зелёный автомобиль, затем синий. "
                "После этого красный завершает поворот."
            ),
        },
        "steps": [
            {
                "start": 0,
                "end": 1500,
                "labels": {
                    "uz": "Qizil avtomobil chorrahaga kiradi va to‘xtaydi.",
                    "uz-kr": "Қизил автомобиль чорраҳага киради ва тўхтайди.",
                    "ru": "Красный автомобиль выезжает на перекрёсток и останавливается.",
                },
            },
            {
                "start": 350,
                "end": 2850,
                "labels": {
                    "uz": "Shu paytda yashil avtomobil chorrahani kesib o‘tadi.",
                    "uz-kr": "Шу пайтда яшил автомобиль чорраҳани кесиб ўтади.",
                    "ru": "В это время зелёный автомобиль пересекает перекрёсток.",
                },
            },
            {
                "start": 2900,
                "end": 5100,
                "labels": {
                    "uz": "Keyin ko‘k avtomobil o‘tadi.",
                    "uz-kr": "Кейин кўк автомобиль ўтади.",
                    "ru": "Затем проезжает синий автомобиль.",
                },
            },
            {
                "start": 5250,
                "end": 7500,
                "labels": {
                    "uz": "Qizil avtomobil burilishni tugatadi.",
                    "uz-kr": "Қизил автомобиль бурилишни тугаллайди.",
                    "ru": "Красный автомобиль завершает поворот.",
                },
            },
        ],
        "vehicles": [
            {
                "id": "red",
                "color": "#ef4444",
                "labels": {"uz": "Qizil", "uz-kr": "Қизил", "ru": "Красный"},
                "segments": [
                    {"start": 0, "duration": 1500, "path": "M 70 310 C 190 310, 330 310, 455 310"},
                    {
                        "start": 5250,
                        "duration": 2250,
                        "path": "M 455 310 C 535 310, 550 260, 550 200 C 550 120, 550 45, 550 -70",
                    },
                ],
            },
            {
                "id": "green",
                "color": "#22c55e",
                "labels": {"uz": "Yashil", "uz-kr": "Яшил", "ru": "Зелёный"},
                "segments": [
                    {"start": 350, "duration": 2500, "path": "M 405 55 C 405 150, 405 330, 405 595"}
                ],
            },
            {
                "id": "blue",
                "color": "#2563eb",
                "labels": {"uz": "Ko‘k", "uz-kr": "Кўк", "ru": "Синий"},
                "segments": [
                    {"start": 2900, "duration": 2200, "path": "M 875 220 C 720 220, 480 220, -75 220"}
                ],
            },
        ],
    }
