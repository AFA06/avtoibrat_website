"""Student page «Imtihonga yo‘l»: the season map, readiness and the final certificate."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _

from . import journey, real_exam


def _texts():
    """Words the map script draws itself (stage cards, ceremonies)."""
    return {
        "bilet": _("Bilet"),
        "start": _("Boshlash"),
        "again": _("Qayta yechish"),
        "best": _("Eng yaxshi natija"),
        "attempts": _("Urinishlar"),
        "none": _("Hali yechilmagan"),
        "cleared": _("Bosqich o‘tildi"),
        "open": _("Ochiq bosqich"),
        "next": _("Navbatdagi bosqich"),
        "locked": _("Avvalgi faslni yakunlang"),
        "rule": _("O‘tish uchun: ko‘pi bilan 2 ta xato"),
        "perfect": _("Xatosiz — 3 yulduz"),
        "close": _("Yopish"),
        "you": _("Siz shu yerdasiz"),
        "finish": _("Marra"),
        "season_label": _("Fasl"),
        "final_title": _("Yakuniy marra"),
        "final_motto": _("Ketma-ket ikki real imtihon"),
        "season_done": _("fasli yakunlandi"),
        "season_next": _("Keyingi fasl ochildi"),
        "continue": _("Davom etish"),
        "stage_done": _("yakunlandi"),
        "stars": _("yulduz"),
        "certified": _("Siz imtihonga tayyorsiz!"),
        "certified_sub": _("Barcha fasllar va ketma-ket ikki real imtihon topshirildi."),
        "see_cert": _("Sertifikatni ko‘rish"),
    }


@login_required
def journey_page(request):
    data = journey.build(request.user)
    return render(request, "dashboard/journey.html", {
        "journey": data,
        "client": {
            **journey.client_data(data),
            "user": request.user.pk,
            "start_url": reverse("start_shablon_test", args=[0]),
            "t": _texts(),
        },
        "real_size": real_exam.SIZES[0],
    })
