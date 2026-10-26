from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .cheatsheet import SECTIONS


@login_required
def cheatsheet_page(request):
    return render(request, "dashboard/cheatsheet.html", {"sections": SECTIONS})
