from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()

# Админские viewsets
router.register(r"admin/users", views.AdminUserViewSet, basename="admin-users")
router.register(r"admin/questions", views.QuestionViewSet, basename="admin-questions")
router.register(
    r"admin/test-configs", views.TestConfigViewSet, basename="admin-test-configs"
)
router.register(
    r"admin/attempts", views.AdminTestAttemptViewSet, basename="admin-attempts"
)

urlpatterns = [
    # Аутентификация
    path("auth/user/register/", views.UserRegisterView.as_view(), name="user-register"),
    path("auth/user/login/", views.UserLoginView.as_view(), name="user-login"),
    path("auth/admin/login/", views.AdminLoginView.as_view(), name="admin-login"),
    path("auth/me/", views.MeView.as_view(), name="me"),
    # Тестирование
    path("tests/start/", views.StartTestView.as_view(), name="start-test"),
    path("tests/answer/", views.SubmitAnswerView.as_view(), name="submit-answer"),
    path("tests/history/", views.TestHistoryView.as_view(), name="test-history"),
    path("tests/<int:attempt_id>/", views.TestAttemptDetailView.as_view(), name="test-detail"),
    # Router
    path("", include(router.urls)),
]


