from django.urls import path
from .views import *
from .leaderboard_views import student_leaderboard
from .task_views import student_tasks


urlpatterns = [
    # ===== ASOSIY SAHIFALAR =====
    path('', index, name="home"),
    path('error/', error, name="error"),
    path('contact/', contact, name="contact"),
    path('faq/', faq, name="faq"),
    path('team/', team, name="team"),

    # ===== AUTH / DASHBOARD =====
    path('login/', login_view, name="login"),
    path('forgot-login/', forgot_login, name="forgot_login"),
    path('logout/', user_logout, name="logout"),
    path('profile/', profile, name="profile"),
    path('dashboard/', dashboard, name="dashboard"),
    path('leaderboard/', student_leaderboard, name="leaderboard"),
    path('vazifalar/', student_tasks, name="tasks"),
    path('contact_list/', contact_list, name="contact_list"),
    path('manular/', manular, name="manular"),


    path('mavzulashtirilgan/', mavzulashtirilgan, name="mavzulashtirilgan"),
    path('ohshash_savollar/', ohshash_savollar, name="ohshash_savollar"),

    path(
            'mavzu/start/<int:category_id>/',
            start_mavzu_test,
            name='start_mavzu_test'
        ),
    path(
        'ohshash/start/<int:category_id>/',
        start_ohshash_test,
        name='start_ohshash_test'
    ),


    path('saqlangan/', saqlangan, name="saqlangan"),
    path('saqlangan/start/', start_saqlangan_test, name="start_saqlangan_test"),
    path(
        "toggle-save-question/",
        toggle_save_question,
        name="toggle_save_question"
    ),
    path(
        "delete-saved-question/",
        delete_saved_question,
        name="delete_saved_question"
    ),


    path('result/', result, name="result"),

    # ===== SHABLON TEST =====
    path("clear-statistics/", clear_statistics, name="clear_statistics"),


    path(
        'shablon-test/',
        shablon_test,
        name='shablon_test'
    ),
    path(
        'shablon-test/start/<int:category_id>/',
        start_shablon_test,
        name='start_shablon_test'
    ),
    # ===== REAL / SINOV TEST =====
    path(
        'real_imtihon/',
        real_imtihon,
        name="real_imtihon"
    ),
    path(
        'test/<int:category_id>/',
        start_test,          # session yaratadi
        name="start_test"
    ),
    path(
        'test-session/<int:session_id>/',
        test_page,            # test oynasi
        name="test_page"
    ),
    path(
        'test-finish/<int:session_id>/',
        finish_test,
        name="finish_test"
    ),
    path(
        'test-result/<int:session_id>/',
        test_result,
        name="test_result"
    ),
    path(
        'submit-answer/',
        submit_answer,
        name="submit_answer"
    ),

    # ===== YO‘L BELGILARI =====
    path('road_signs/', road_signs, name='road_signs'),
    path(
        'road_signs/<slug:category_slug>/',
        road_signs_two,
        name='road_signs_two'
    ),
]
