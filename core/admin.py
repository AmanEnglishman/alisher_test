from django.contrib import admin

from .models import (
    AnswerOption,
    Question,
    TestAnswer,
    TestAttempt,
    TestConfig,
    User,
)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "phone", "email", "first_name", "user_type", "is_staff")
    search_fields = ("phone", "email", "first_name")


class AnswerOptionInline(admin.TabularInline):
    model = AnswerOption
    extra = 1


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "level", "text_ru", "is_active")
    list_filter = ("level", "is_active")
    inlines = [AnswerOptionInline]


@admin.register(TestConfig)
class TestConfigAdmin(admin.ModelAdmin):
    list_display = ("level", "duration_minutes")


@admin.register(TestAttempt)
class TestAttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "level", "percent", "knowledge_level", "started_at", "finished_at")
    list_filter = ("level", "knowledge_level")


@admin.register(TestAnswer)
class TestAnswerAdmin(admin.ModelAdmin):
    list_display = ("id", "attempt", "question", "selected_option", "is_correct", "order_index")
