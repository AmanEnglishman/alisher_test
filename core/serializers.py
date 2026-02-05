from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework.authtoken.models import Token

from .models import (
    AnswerOption,
    Question,
    TestAnswer,
    TestAttempt,
    TestConfig,
    User,
    KnowledgeLevel,
)


class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("id", "first_name", "phone", "age", "password")

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User.objects.create_user(
            phone=validated_data["phone"],
            email=None,
            password=password,
            first_name=validated_data.get("first_name", ""),
            age=validated_data.get("age"),
            user_type="user",
        )
        return user


class UserLoginSerializer(serializers.Serializer):
    phone = serializers.CharField()
    password = serializers.CharField(write_only=True)
    token = serializers.CharField(read_only=True)

    def validate(self, attrs):
        phone = attrs.get("phone")
        password = attrs.get("password")
        user = authenticate(request=self.context.get("request"), phone=phone, password=password)
        if not user:
            raise serializers.ValidationError("Неверный телефон или пароль")
        if user.user_type != "user":
            raise serializers.ValidationError("Это не пользовательский аккаунт")
        token, _ = Token.objects.get_or_create(user=user)
        attrs["user"] = user
        attrs["token"] = token.key
        return attrs


class AdminLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    token = serializers.CharField(read_only=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")
        user = None
        if email:
            user = User.objects.filter(email__iexact=email).first()
        if not user or not user.check_password(password):
            raise serializers.ValidationError("Неверный email или пароль")
        if not user.is_staff:
            raise serializers.ValidationError("Пользователь не является администратором")
        token, _ = Token.objects.get_or_create(user=user)
        attrs["user"] = user
        attrs["token"] = token.key
        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "first_name", "phone", "age", "email", "user_type")


class AnswerOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnswerOption
        fields = ("id", "text_ru", "text_kg")


class QuestionSerializer(serializers.ModelSerializer):
    options = AnswerOptionSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = (
            "id",
            "level",
            "text_ru",
            "text_kg",
            "image",
            "is_active",
            "options",
        )


class TestConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestConfig
        fields = ("id", "level", "duration_minutes")


class StartTestSerializer(serializers.Serializer):
    level = serializers.ChoiceField(choices=("easy", "medium", "hard"))
    language = serializers.ChoiceField(choices=("ru", "kg"))


class TestQuestionForAttemptSerializer(serializers.ModelSerializer):
    options = serializers.SerializerMethodField()
    text = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = ("id", "text", "image", "options")

    def get_text(self, obj):
        lang = self.context.get("language", "ru")
        return obj.text_kg if lang == "kg" else obj.text_ru

    def get_options(self, obj):
        lang = self.context.get("language", "ru")
        options = obj.options.all()
        if lang == "kg":
            return [{"id": o.id, "text": o.text_kg} for o in options]
        return [{"id": o.id, "text": o.text_ru} for o in options]


class SubmitAnswerSerializer(serializers.Serializer):
    attempt_id = serializers.IntegerField()
    question_id = serializers.IntegerField()
    selected_option_id = serializers.IntegerField()


class TestAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestAttempt
        fields = (
            "id",
            "level",
            "started_at",
            "finished_at",
            "total_questions",
            "correct_answers",
            "score",
            "percent",
            "knowledge_level",
        )


class TestAttemptDetailSerializer(serializers.ModelSerializer):
    answers = serializers.SerializerMethodField()

    class Meta:
        model = TestAttempt
        fields = (
            "id",
            "level",
            "started_at",
            "finished_at",
            "total_questions",
            "correct_answers",
            "score",
            "percent",
            "knowledge_level",
            "answers",
        )

    def get_answers(self, obj):
        items = obj.answers.select_related("question", "selected_option")
        return [
            {
                "question_id": a.question_id,
                "selected_option_id": a.selected_option_id,
                "is_correct": a.is_correct,
                "order_index": a.order_index,
            }
            for a in items
        ]


class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "first_name", "phone", "age", "email", "user_type", "is_staff")


class AdminTestAttemptSerializer(serializers.ModelSerializer):
    user = UserProfileSerializer(read_only=True)

    class Meta:
        model = TestAttempt
        fields = "__all__"


