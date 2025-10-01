from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.exceptions import ValidationError

class Role(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name='Название роли')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Роль"
        verbose_name_plural = "Роли"

class User(AbstractUser):
    role = models.ManyToManyField(Role, related_name='users', blank=True, verbose_name='Роли')
    image = models.ImageField(
        upload_to='profile_images/',  # ИСПРАВЛЕНО: убрали статик путь
        null=True,
        blank=True,
        default='default_image.png',  # ИСПРАВЛЕНО: упростили путь
        verbose_name='Изображение пользователя'
    )

    def __str__(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name} ({self.username})"
        return self.username

    def get_main_role(self):
        """Возвращает основную роль пользователя"""
        roles = self.role.all()
        if roles:
            return roles[0].name
        return "Не назначена"

    def get_image_url(self):
        """Возвращает URL изображения пользователя"""
        if self.image and hasattr(self.image, 'url'):
            return self.image.url
        return '/static/images/default_image.png'  # Путь к изображению по умолчанию

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

class Group(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='Название группы')
    course = models.IntegerField(verbose_name='Курс')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Группа"
        verbose_name_plural = "Группы"

class Subject(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='Название предмета')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Предмет"
        verbose_name_plural = "Предметы"

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name='Пользователь')
    group = models.ForeignKey(Group, on_delete=models.CASCADE, verbose_name='Группа')

    def clean(self):
        if hasattr(self, 'user') and self.user:
            if hasattr(self.user, 'teacher'):
                raise ValidationError("Пользователь уже назначен как преподаватель")
            if hasattr(self.user, 'parent'):
                raise ValidationError("Пользователь уже назначен как родитель")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.user.username})"

    class Meta:
        verbose_name = "Студент"
        verbose_name_plural = "Студенты"

class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name='Пользователь')
    main_group = models.ForeignKey(Group, related_name='main_teachers', on_delete=models.CASCADE, verbose_name='Основная группа')
    additional_groups = models.ManyToManyField(Group, related_name='additional_teachers', blank=True, verbose_name='Дополнительные группы')
    subjects = models.ManyToManyField(Subject, related_name='teachers', blank=True, verbose_name='Предметы')

    def clean(self):
        if hasattr(self, 'user') and self.user:
            if hasattr(self.user, 'student'):
                raise ValidationError("Пользователь уже назначен как студент")
            if hasattr(self.user, 'parent'):
                raise ValidationError("Пользователь уже назначен как родитель")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.user.username})"

    class Meta:
        verbose_name = "Учитель"
        verbose_name_plural = "Учителя"

class Parent(models.Model):
    PARENT_TYPES = [
        ('mother', 'Мама'),
        ('father', 'Папа'),
        ('grandmother', 'Бабушка'),
        ('grandfather', 'Дедушка'),
        ('other', 'Другой'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name='Пользователь')
    children = models.ManyToManyField(Student, related_name='parents', blank=True, verbose_name='Дети')
    parent_type = models.CharField(max_length=20, choices=PARENT_TYPES, default='other', verbose_name='Тип родителя')

    def clean(self):
        if hasattr(self, 'user') and self.user:
            if hasattr(self.user, 'student'):
                raise ValidationError("Пользователь уже назначен как студент")
            if hasattr(self.user, 'teacher'):
                raise ValidationError("Пользователь уже назначен как преподаватель")

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.user.username})"

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Родитель"
        verbose_name_plural = "Родители"

class Schedule(models.Model):
    """Расписание - шаблон занятий по дням недели"""
    WEEKDAYS = [
        (0, 'Понедельник'),
        (1, 'Вторник'),
        (2, 'Среда'),
        (3, 'Четверг'),
        (4, 'Пятница'),
        (5, 'Суббота'),
        (6, 'Воскресенье'),
    ]

    group = models.ForeignKey(Group, on_delete=models.CASCADE, verbose_name='Группа')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, verbose_name='Предмет')
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, verbose_name='Преподаватель')
    weekday = models.IntegerField(choices=WEEKDAYS, verbose_name='День недели')
    start_time = models.TimeField(verbose_name='Время начала')
    end_time = models.TimeField(verbose_name='Время окончания')
    classroom = models.CharField(max_length=50, blank=True, null=True, verbose_name='Аудитория')
    is_active = models.BooleanField(default=True, verbose_name='Активно')

    def clean(self):
        # Проверяем время
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError("Время окончания должно быть больше времени начала")

        # Проверяем, что преподаватель ведет этот предмет
        if self.teacher and self.subject and not self.teacher.subjects.filter(id=self.subject.id).exists():
            raise ValidationError(f"Преподаватель {self.teacher.user.get_full_name()} не ведет предмет {self.subject.name}")

        # Проверяем, что преподаватель работает с этой группой
        if self.teacher and self.group:
            if (self.teacher.main_group != self.group and
                not self.teacher.additional_groups.filter(id=self.group.id).exists()):
                raise ValidationError(f"Преподаватель {self.teacher.user.get_full_name()} не работает с группой {self.group.name}")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def get_weekday_display_short(self):
        """Возвращает краткое название дня недели"""
        short_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        return short_names[self.weekday]

    def get_time_range(self):
        """Возвращает диапазон времени в удобном формате"""
        return f"{self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}"

    def __str__(self):
        return f"{self.group.name} - {self.subject.name} - {self.get_weekday_display()} {self.get_time_range()}"

    class Meta:
        verbose_name = "Расписание"
        verbose_name_plural = "Расписание"
        ordering = ['weekday', 'start_time']
        unique_together = ('group', 'weekday', 'start_time')

class Lesson(models.Model):
    """Урок - конкретное занятие на определенную дату"""
    # НОВОЕ ПОЛЕ: связь с расписанием
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Расписание')

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, verbose_name='Предмет')
    date = models.DateField(default=timezone.now, verbose_name='Дата')
    group = models.ForeignKey(Group, on_delete=models.CASCADE, verbose_name='Группа')
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Преподаватель')
    classroom = models.CharField(max_length=50, blank=True, null=True, verbose_name='Аудитория')
    start_time = models.TimeField(null=True, blank=True, verbose_name='Время начала')
    end_time = models.TimeField(null=True, blank=True, verbose_name='Время окончания')

    # НОВЫЕ ПОЛЯ
    is_from_schedule = models.BooleanField(default=False, verbose_name='Создан из расписания')
    notes = models.TextField(blank=True, verbose_name='Заметки к уроку')

    def clean(self):
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError("Время окончания должно быть больше времени начала")

    def save(self, *args, **kwargs):
        # Если урок создан из расписания, копируем данные
        if self.schedule and self.is_from_schedule:
            self.subject = self.schedule.subject
            self.group = self.schedule.group
            self.teacher = self.schedule.teacher
            self.start_time = self.schedule.start_time
            self.end_time = self.schedule.end_time
            if not self.classroom:
                self.classroom = self.schedule.classroom

        self.clean()
        super().save(*args, **kwargs)

    def get_time_range(self):
        """Возвращает диапазон времени"""
        if self.start_time and self.end_time:
            return f"{self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}"
        return "Время не указано"

    def get_source_info(self):
        """Возвращает информацию об источнике урока"""
        if self.is_from_schedule and self.schedule:
            return f"Из расписания ({self.schedule.get_weekday_display()})"
        return "Создан вручную"

    def __str__(self):
        time_info = f" {self.get_time_range()}" if self.start_time else ""
        source_info = " 📅" if self.is_from_schedule else " ✏️"
        return f"{self.subject.name} - {self.date.strftime('%d.%m.%Y')}{time_info} - {self.group.name}{source_info}"

    class Meta:
        verbose_name = "Урок"
        verbose_name_plural = "Уроки"
        ordering = ['-date', 'start_time']
        unique_together = ('subject', 'date', 'group', 'start_time')

class Attendance(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, verbose_name='Урок')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, verbose_name='Студент')
    attended = models.BooleanField(default=False, verbose_name='Посещал')
    late = models.BooleanField(default=False, verbose_name='Опоздал')
    grade = models.IntegerField(null=True, blank=True, verbose_name='Оценка')

    def clean(self):
        if self.grade is not None and (self.grade < 2 or self.grade > 5):
            raise ValidationError("Оценка должна быть от 2 до 5")

        if not self.attended and self.late:
            raise ValidationError("Студент не может опоздать, если он не посещал урок")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def get_attendance_status(self):
        """Возвращает статус посещения"""
        if not self.attended:
            return "Отсутствовал"
        elif self.late:
            return "Опоздал"
        else:
            return "Присутствовал"

    def get_status_class(self):
        """Возвращает CSS класс для стилизации"""
        if not self.attended:
            return "absent"
        elif self.late:
            return "late"
        else:
            return "present"

    def __str__(self):
        status = self.get_attendance_status()
        grade_info = f", оценка: {self.grade}" if self.grade else ""
        return f"{self.student} - {self.lesson} - {status}{grade_info}"

    class Meta:
        verbose_name = "Посещаемость"
        verbose_name_plural = "Посещаемость"
        unique_together = ('lesson', 'student')
