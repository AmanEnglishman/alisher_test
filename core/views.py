from django.db import transaction
from django.utils import timezone
from rest_framework import generics, permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    AnswerOption,
    Question,
    TestAnswer,
    TestAttempt,
    TestConfig,
    User,
    KnowledgeLevel,
)
from .serializers import (
    AdminLoginSerializer,
    AdminTestAttemptSerializer,
    AdminUserSerializer,
    QuestionSerializer,
    StartTestSerializer,
    SubmitAnswerSerializer,
    TestAttemptDetailSerializer,
    TestAttemptSerializer,
    TestConfigSerializer,
    UserLoginSerializer,
    UserProfileSerializer,
    UserRegisterSerializer,
    TestQuestionForAttemptSerializer,
)


class UserRegisterView(generics.CreateAPIView):
    serializer_class = UserRegisterSerializer
    permission_classes = [permissions.AllowAny]


class UserLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        return Response(
            {
                "token": serializer.validated_data["token"],
                "user": UserProfileSerializer(serializer.validated_data["user"]).data,
            }
        )


class AdminLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = AdminLoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        return Response(
            {
                "token": serializer.validated_data["token"],
                "user": UserProfileSerializer(serializer.validated_data["user"]).data,
            }
        )


class MeView(generics.RetrieveAPIView):
    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user


class StartTestView(APIView):
    """
    Начать тест для конкретного уровня.
    Возвращает список вопросов и attempt_id.
    """

    def post(self, request):
        serializer = StartTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        level = serializer.validated_data["level"]
        language = serializer.validated_data["language"]

        # Prefetch options to ensure serializer returns options reliably
        questions = list(
            Question.objects.filter(level=level, is_active=True).prefetch_related("options")
        )
        if not questions:
            return Response(
                {"detail": "Нет вопросов для выбранного уровня."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            attempt = TestAttempt.objects.create(
                user=request.user,
                level=level,
                total_questions=len(questions),
            )
            # фиксируем порядок
            test_answers = []
            for idx, q in enumerate(questions, start=1):
                test_answers.append(
                    TestAnswer(
                        attempt=attempt,
                        question=q,
                        order_index=idx,
                    )
                )
            TestAnswer.objects.bulk_create(test_answers)

        question_serializer = TestQuestionForAttemptSerializer(
            questions,
            many=True,
            context={"language": language},
        )

        config = TestConfig.objects.filter(level=level).first()
        duration_minutes = config.duration_minutes if config else None

        return Response(
            {
                "attempt_id": attempt.id,
                "level": attempt.level,
                "duration_minutes": duration_minutes,
                "questions": question_serializer.data,
            }
        )


class SubmitAnswerView(APIView):
    """
    Отправка ответа на вопрос.
    Бэкенд контролирует последовательность: нельзя отвечать «вперёд или назад».
    """

    def post(self, request):
        serializer = SubmitAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attempt_id = serializer.validated_data["attempt_id"]
        question_id = serializer.validated_data["question_id"]
        selected_option_id = serializer.validated_data["selected_option_id"]

        try:
            attempt = TestAttempt.objects.get(id=attempt_id, user=request.user)
        except TestAttempt.DoesNotExist:
            return Response(
                {"detail": "Попытка не найдена."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if attempt.finished_at:
            return Response(
                {"detail": "Тест уже завершён."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            answer = TestAnswer.objects.select_related("question").get(
                attempt=attempt, question_id=question_id
            )
        except TestAnswer.DoesNotExist:
            return Response(
                {"detail": "Вопрос не принадлежит этой попытке."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # запрещаем перепроходить предыдущие вопросы:
        last_answered = (
            TestAnswer.objects.filter(attempt=attempt, selected_option__isnull=False)
            .order_by("-order_index")
            .first()
        )
        if last_answered and answer.order_index != last_answered.order_index + 1:
            return Response(
                {"detail": "Нельзя переходить к предыдущим или пропускать вопросы."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not last_answered and answer.order_index != 1:
            return Response(
                {"detail": "Нужно начать с первого вопроса."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            selected_option = AnswerOption.objects.get(
                id=selected_option_id, question_id=question_id
            )
        except AnswerOption.DoesNotExist:
            return Response(
                {"detail": "Некорректный вариант ответа."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        answer.selected_option = selected_option
        answer.is_correct = selected_option.is_correct
        answer.save()

        # Если это был последний вопрос — подсчитать результат и завершить попытку.
        total_answered = TestAnswer.objects.filter(
            attempt=attempt, selected_option__isnull=False
        ).count()
        if total_answered == attempt.total_questions:
            correct = TestAnswer.objects.filter(
                attempt=attempt, is_correct=True
            ).count()
            percent = (correct / attempt.total_questions) * 100 if attempt.total_questions else 0

            if 0 <= percent <= 40:
                k_level = KnowledgeLevel.WEAK
            elif 41 <= percent <= 70:
                k_level = KnowledgeLevel.MEDIUM
            else:
                k_level = KnowledgeLevel.HIGH

            attempt.correct_answers = correct
            attempt.percent = percent
            # запрещаем перепроходить предыдущие вопросы: считаем вопрос отвеченным
            # если выбран вариант или заполнён текстовый ответ
            from django.db.models import Q

            last_answered = (
                TestAnswer.objects.filter(
                    attempt=attempt
                ).filter(Q(selected_option__isnull=False) | Q(text_answer__isnull=False))
                .order_by("-order_index")
                .first()
            )


class TestHistoryView(generics.ListAPIView):
    serializer_class = TestAttemptSerializer

    def get_queryset(self):
        return TestAttempt.objects.filter(user=self.request.user).order_by("-started_at")


class TestAttemptDetailView(generics.RetrieveAPIView):
    serializer_class = TestAttemptDetailSerializer
    lookup_url_kwarg = "attempt_id"

    def get_queryset(self):
        return TestAttempt.objects.filter(user=self.request.user)


class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_staff)


class AdminUserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.all().order_by("id")
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdmin]


class QuestionViewSet(viewsets.ModelViewSet):
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer
    permission_classes = [IsAdmin]


class TestConfigViewSet(viewsets.ModelViewSet):
    queryset = TestConfig.objects.all()
    serializer_class = TestConfigSerializer
    permission_classes = [IsAdmin]


class AdminTestAttemptViewSet(viewsets.ReadOnlyModelViewSet):
            # Count answers where either selected_option or text_answer is present
            total_answered = TestAnswer.objects.filter(
                attempt=attempt
            ).filter(Q(selected_option__isnull=False) | Q(text_answer__isnull=False)).count()

