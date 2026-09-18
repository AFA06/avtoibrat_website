# avto/middleware.py
from django.shortcuts import redirect
from django.contrib.auth import logout
from django.http import HttpResponseForbidden


class AccountExpirationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        # Ochiq sahifalar
        if request.path.startswith("/static/"):
            return self.get_response(request)

        if request.path in ["/", "/login/", "/forgot-login/"]:
            return self.get_response(request)

        user = request.user

        if user.is_authenticated:
            user.sync_active_status()

            # ✅ FAQAT SUPERUSER ISTISNO
            if user.is_superuser:
                return self.get_response(request)

            # ❌ VAQTI TUGAGAN
            if not user.is_active:
                logout(request)
                request.session.flush()

                # Admin bo‘lsa ham chiqar
                if request.path.startswith("/admin/"):
                    return redirect("/admin/login/")

                return redirect("/")

        return self.get_response(request)
