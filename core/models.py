from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, phone, password, **extra_fields):
        if not phone:
            raise ValueError("Phone number is required")
        email = self.normalize_email(email) if email else None
        user = self.model(email=email, phone=phone, **extra_fields)
        if password:
            user.set_password(password)
        else:
            # Allow phone-only auth for simple flows, but still hash something
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, email=None, phone=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, phone, password, **extra_fields)

    def create_superuser(self, email=None, phone=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, phone, password, **extra_fields)


class User(AbstractUser):
    """
    Custom user:
    - обычный пользователь заходит по телефону
    - администратор заходит по email и паролю (is_staff=True)
    """

    username = None  # we don't use username

    first_name = models.CharField("Имя", max_length=150)
    phone = models.CharField("Телефон", max_length=20, unique=True)
    age = models.PositiveIntegerField("Возраст", null=True, blank=True)
    email = models.EmailField("Email", unique=True, null=True, blank=True)

    USER_TYPE_CHOICES = (
        ("user", "Пользователь"),
        ("admin", "Администратор"),
    )
    user_type = models.CharField(
        "Тип пользователя", max_length=10, choices=USER_TYPE_CHOICES, default="user"
    )

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = ["email"]

    objects = UserManager()

    def __str__(self):
        return f"{self.phone} ({self.first_name})"


class TestLevel(models.TextChoices):
    EASY = "easy", "Лёгкий"
    MEDIUM = "medium", "Средний"
    HARD = "hard", "Сложный"


class KnowledgeLevel(models.TextChoices):
    WEAK = "weak", "Weak"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"


class TestConfig(models.Model):
    """
    Время прохождения теста по уровням сложности.
    Одна запись на каждый уровень.
    """

    level = models.CharField(
        "Уровень сложности", max_length=10, choices=TestLevel.choices, unique=True
    )
    duration_minutes = models.PositiveIntegerField("Длительность (минуты)", default=30)

    def __str__(self):
        return f"{self.get_level_display()} ({self.duration_minutes} мин)"


class Question(models.Model):
    """
    Тестовый вопрос с поддержкой RU/KG и опциональным изображением.
    """

    level = models.CharField(
        "Уровень сложности", max_length=10, choices=TestLevel.choices
    )
    text_ru = models.TextField("Текст вопроса (русский)")
    text_kg = models.TextField("Текст вопроса (кыргызский)")
    image = models.ImageField(
        "Изображение",
        upload_to="questions/",
        null=True,
        blank=True,
    )
    is_active = models.BooleanField("Активный", default=True)

    def __str__(self):
        return f"[{self.level}] {self.text_ru[:50]}"


class AnswerOption(models.Model):
    """
    Вариант ответа (множественный выбор, один правильный).
    """

    question = models.ForeignKey(
        Question, related_name="options", on_delete=models.CASCADE
    )
    text_ru = models.CharField("Ответ (русский)", max_length=255)
    text_kg = models.CharField("Ответ (кыргызский)", max_length=255)
    is_correct = models.BooleanField("Правильный", default=False)

    def __str__(self):
        return f"{self.text_ru} ({'+' if self.is_correct else '-'})"


class TestAttempt(models.Model):
    """
    Попытка прохождения теста пользователем.
    """

    user = models.ForeignKey(User, related_name="attempts", on_delete=models.CASCADE)
    level = models.CharField(
        "Уровень сложности", max_length=10, choices=TestLevel.choices
    )
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    total_questions = models.PositiveIntegerField(default=0)
    correct_answers = models.PositiveIntegerField(default=0)
    score = models.FloatField("Баллы", default=0)
    percent = models.FloatField("Процент правильных", default=0)
    knowledge_level = models.CharField(
        "Уровень знаний",
        max_length=10,
        choices=KnowledgeLevel.choices,
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.user} - {self.level} ({self.percent:.1f}%)"


class TestAnswer(models.Model):
    """
    Ответ пользователя на конкретный вопрос в рамках попытки.
    """

    attempt = models.ForeignKey(
        TestAttempt, related_name="answers", on_delete=models.CASCADE
    )
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_option = models.ForeignKey(
        AnswerOption, on_delete=models.CASCADE, null=True, blank=True
    )
    text_answer = models.TextField("Текстовый ответ", null=True, blank=True)
    is_correct = models.BooleanField(default=False)
    order_index = models.PositiveIntegerField(
        "Порядок вопроса в тесте",
    )

    class Meta:
        unique_together = ("attempt", "question")
        ordering = ["order_index"]

    def __str__(self):
        return f"{self.attempt_id} - {self.question_id} ({self.is_correct})"
