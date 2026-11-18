# avto/middleware.py
from django.shortcuts import redirect
from django.contrib.auth import logout
from django.urls import reverse


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

            # ❌ VAQTI TUGAGAN
            if not user.is_superuser and not user.is_active:
                logout(request)
                request.session.flush()

                # Admin bo‘lsa ham chiqar
                if request.path.startswith("/admin/"):
                    return redirect("/admin/login/")

                return redirect("/")

            if user.must_change_password:
                password_path = reverse("change_temporary_password")
                if request.path not in (password_path, reverse("logout"), reverse("admin:logout")):
                    return redirect(password_path)

        return self.get_response(request)
