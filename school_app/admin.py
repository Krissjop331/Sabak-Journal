from django.contrib import admin
from django import forms
from .models import User, Role, Teacher, Student, Parent, Attendance, Group, Subject, Lesson, Schedule
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.core.exceptions import ValidationError

class RoleInline(admin.TabularInline):
    model = User.role.through
    extra = 1

class UserAdminForm(forms.ModelForm):
    """Кастомная форма для создания пользователей с автоматическим созданием связанных записей"""

    class Meta:
        model = User
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Делаем поле ролей более удобным
        if 'role' in self.fields:
            self.fields['role'].widget = forms.CheckboxSelectMultiple()
            self.fields['role'].help_text = "При выборе роли автоматически создается соответствующая запись (Студент/Учитель/Родитель)"

class CustomUserAdmin(BaseUserAdmin):
    form = UserAdminForm

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Персональная информация', {'fields': ('first_name', 'last_name', 'email', 'image')}),
        ('Права доступа', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        ('Роли', {'fields': ('role',)}),
        ('Важные даты', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'first_name', 'last_name', 'email', 'image', 'role'),
        }),
    )
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_active', 'get_roles', 'get_profile_type')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'role')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    filter_horizontal = ('role',)

    def get_roles(self, obj):
        return ", ".join([role.name for role in obj.role.all()])
    get_roles.short_description = 'Роли'

    def get_profile_type(self, obj):
        """Показывает, какой тип профиля создан для пользователя"""
        profiles = []
        if hasattr(obj, 'student'):
            profiles.append('Студент')
        if hasattr(obj, 'teacher'):
            profiles.append('Учитель')
        if hasattr(obj, 'parent'):
            profiles.append('Родитель')
        return ", ".join(profiles) if profiles else "Нет профиля"
    get_profile_type.short_description = 'Тип профиля'

    class Media:
        css = {
            'all': ('css/admin_custom.css',)
        }

# Кастомный админ для редактирования посещений и оценок
class AttendanceInline(admin.TabularInline):
    model = Attendance
    extra = 1
    fields = ('lesson', 'attended', 'grade')
    readonly_fields = ('lesson',)

class StudentAdminForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.instance.pk:
            # Для нового студента - показываем неиспользованных пользователей
            used_user_ids = Student.objects.values_list('user_id', flat=True)
            available_users = User.objects.exclude(id__in=used_user_ids)

            # Опционально фильтруем по роли студента
            student_role = Role.objects.filter(name__icontains='студент').first()
            if student_role:
                users_with_student_role = available_users.filter(role=student_role)
                if users_with_student_role.exists():
                    available_users = users_with_student_role

            self.fields['user'].queryset = available_users

            if not available_users.exists():
                self.fields['user'].help_text = (
                    "Нет доступных пользователей. Создайте пользователя с ролью 'студенты' "
                    "или убедитесь, что пользователь еще не назначен студентом."
                )
        else:
            # Для редактирования - показываем текущего + доступных
            used_user_ids = Student.objects.exclude(id=self.instance.id).values_list('user_id', flat=True)
            available_users = User.objects.exclude(id__in=used_user_ids)
            self.fields['user'].queryset = available_users

class StudentAdmin(admin.ModelAdmin):
    form = StudentAdminForm
    list_display = ('get_full_name', 'get_username', 'group', 'get_attendance_stats')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    list_filter = ('group',)
    inlines = [AttendanceInline]

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
    get_full_name.short_description = 'Имя студента'

    def get_username(self, obj):
        return obj.user.username
    get_username.short_description = 'Логин'

    def get_attendance_stats(self, obj):
        total = obj.attendance_set.count()
        attended = obj.attendance_set.filter(attended=True).count()
        if total > 0:
            percentage = round((attended / total) * 100, 1)
            return f"{attended}/{total} ({percentage}%)"
        return "Нет данных"
    get_attendance_stats.short_description = 'Посещаемость'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        # Автоматически назначаем роль студента
        student_role = Role.objects.filter(name__icontains='студент').first()
        if student_role and not obj.user.role.filter(id=student_role.id).exists():
            obj.user.role.add(student_role)

class TeacherAdminForm(forms.ModelForm):
    class Meta:
        model = Teacher
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Если это новый учитель (создание)
        if not self.instance.pk:
            # Показываем пользователей, которые еще не являются учителями
            # и имеют роль "учитель" (или можем показать всех доступных)
            used_user_ids = Teacher.objects.values_list('user_id', flat=True)
            available_users = User.objects.exclude(id__in=used_user_ids)

            # Опционально: фильтруем только пользователей с ролью учителя
            teacher_role = Role.objects.filter(name__icontains='учитель').first()
            if teacher_role:
                users_with_teacher_role = available_users.filter(role=teacher_role)
                if users_with_teacher_role.exists():
                    available_users = users_with_teacher_role

            self.fields['user'].queryset = available_users

            if not available_users.exists():
                self.fields['user'].help_text = (
                    "Нет доступных пользователей. Создайте пользователя с ролью 'учитель' "
                    "или убедитесь, что пользователь еще не назначен учителем."
                )
        else:
            # Если это редактирование существующего учителя
            # Показываем текущего пользователя + доступных для замены
            used_user_ids = Teacher.objects.exclude(id=self.instance.id).values_list('user_id', flat=True)
            available_users = User.objects.exclude(id__in=used_user_ids)
            self.fields['user'].queryset = available_users

class TeacherAdmin(admin.ModelAdmin):
    form = TeacherAdminForm
    list_display = ('get_full_name', 'get_username', 'main_group', 'get_subjects', 'get_additional_groups')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    list_filter = ('main_group', 'subjects')
    filter_horizontal = ('additional_groups', 'subjects')

    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'main_group')
        }),
        ('Дополнительные данные', {
            'fields': ('additional_groups', 'subjects'),
            'classes': ('wide',)
        }),
    )

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
    get_full_name.short_description = 'Имя учителя'

    def get_username(self, obj):
        return obj.user.username
    get_username.short_description = 'Логин'

    def get_subjects(self, obj):
        subjects = obj.subjects.all()
        return ", ".join([subject.name for subject in subjects]) if subjects else "Нет предметов"
    get_subjects.short_description = 'Предметы'

    def get_additional_groups(self, obj):
        groups = obj.additional_groups.all()
        return ", ".join([group.name for group in groups]) if groups else "Нет"
    get_additional_groups.short_description = 'Доп. группы'

    def save_model(self, request, obj, form, change):
        """Переопределяем сохранение для автоматического назначения роли"""
        super().save_model(request, obj, form, change)

        # Автоматически назначаем роль учителя, если её нет
        teacher_role = Role.objects.filter(name__icontains='учитель').first()
        if teacher_role and not obj.user.role.filter(id=teacher_role.id).exists():
            obj.user.role.add(teacher_role)
    form = TeacherAdminForm
    list_display = ('get_full_name', 'get_username', 'main_group', 'get_subjects', 'get_additional_groups')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    list_filter = ('main_group', 'subjects')
    filter_horizontal = ('additional_groups', 'subjects')

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
    get_full_name.short_description = 'Имя учителя'

    def get_username(self, obj):
        return obj.user.username
    get_username.short_description = 'Логин'

    def get_subjects(self, obj):
        subjects = obj.subjects.all()
        return ", ".join([subject.name for subject in subjects]) if subjects else "Нет предметов"
    get_subjects.short_description = 'Предметы'

    def get_additional_groups(self, obj):
        groups = obj.additional_groups.all()
        return ", ".join([group.name for group in groups]) if groups else "Нет"
    get_additional_groups.short_description = 'Доп. группы'

class ParentAdminForm(forms.ModelForm):
    class Meta:
        model = Parent
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.instance.pk:
            # Для нового родителя
            used_user_ids = Parent.objects.values_list('user_id', flat=True)
            available_users = User.objects.exclude(id__in=used_user_ids)

            # Опционально фильтруем по роли родителя
            parent_role = Role.objects.filter(name__icontains='родител').first()
            if parent_role:
                users_with_parent_role = available_users.filter(role=parent_role)
                if users_with_parent_role.exists():
                    available_users = users_with_parent_role

            self.fields['user'].queryset = available_users

            if not available_users.exists():
                self.fields['user'].help_text = (
                    "Нет доступных пользователей. Создайте пользователя с ролью 'родители' "
                    "или убедитесь, что пользователь еще не назначен родителем."
                )
        else:
            # Для редактирования
            used_user_ids = Parent.objects.exclude(id=self.instance.id).values_list('user_id', flat=True)
            available_users = User.objects.exclude(id__in=used_user_ids)
            self.fields['user'].queryset = available_users

class ParentAdmin(admin.ModelAdmin):
    form = ParentAdminForm
    list_display = ('get_full_name', 'get_username', 'parent_type', 'get_children_count', 'get_children_list')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    list_filter = ('parent_type',)
    filter_horizontal = ('children',)

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
    get_full_name.short_description = 'Имя родителя'

    def get_username(self, obj):
        return obj.user.username
    get_username.short_description = 'Логин'

    def get_children_count(self, obj):
        return obj.children.count()
    get_children_count.short_description = 'Количество детей'

    def get_children_list(self, obj):
        children = obj.children.all()
        return ", ".join([f"{child.user.get_full_name()} ({child.group.name})" for child in children]) if children else "Нет детей"
    get_children_list.short_description = 'Дети'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        # Автоматически назначаем роль родителя
        parent_role = Role.objects.filter(name__icontains='родител').first()
        if parent_role and not obj.user.role.filter(id=parent_role.id).exists():
            obj.user.role.add(parent_role)

class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('lesson', 'get_student_name', 'attended', 'late', 'grade', 'get_date')
    search_fields = ('student__user__username', 'student__user__first_name', 'student__user__last_name')
    list_filter = ('attended', 'late', 'lesson__subject', 'lesson__group', 'lesson__date')

    def get_student_name(self, obj):
        return obj.student.user.get_full_name() or obj.student.user.username
    get_student_name.short_description = 'Имя студента'

    def get_date(self, obj):
        return obj.lesson.date.strftime('%d.%m.%Y')
    get_date.short_description = 'Дата урока'

class LessonAdmin(admin.ModelAdmin):
    list_display = ('subject', 'formatted_date', 'group', 'get_attendance_count', 'get_attendance_rate')
    search_fields = ('subject__name', 'group__name')
    list_filter = ('subject', 'group', 'date')
    date_hierarchy = 'date'

    def formatted_date(self, obj):
        return obj.date.strftime('%d.%m.%Y')
    formatted_date.short_description = 'Дата'

    def get_attendance_count(self, obj):
        return obj.attendance_set.count()
    get_attendance_count.short_description = 'Записей посещений'

    def get_attendance_rate(self, obj):
        total = obj.attendance_set.count()
        attended = obj.attendance_set.filter(attended=True).count()
        if total > 0:
            rate = round((attended / total) * 100, 1)
            return f"{rate}%"
        return "0%"
    get_attendance_rate.short_description = 'Процент посещений'

class GroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'course', 'get_students_count', 'get_teachers_count')
    search_fields = ('name',)
    list_filter = ('course',)

    def get_students_count(self, obj):
        return obj.student_set.count()
    get_students_count.short_description = 'Количество студентов'

    def get_teachers_count(self, obj):
        main_teachers = obj.main_teachers.count()
        additional_teachers = obj.additional_teachers.count()
        return f"{main_teachers} осн. + {additional_teachers} доп."
    get_teachers_count.short_description = 'Учителя'

class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_users_count')
    search_fields = ('name',)

    def get_users_count(self, obj):
        return obj.users.count()
    get_users_count.short_description = 'Количество пользователей'

class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_teachers_count', 'get_lessons_count')
    search_fields = ('name',)

    def get_teachers_count(self, obj):
        return obj.teachers.count()
    get_teachers_count.short_description = 'Количество учителей'

    def get_lessons_count(self, obj):
        return obj.lesson_set.count()
    get_lessons_count.short_description = 'Количество уроков'

class ScheduleAdmin(admin.ModelAdmin):
    list_display = ('get_schedule_info', 'get_weekday_display', 'get_time_range', 'classroom', 'is_active')
    list_filter = ('weekday', 'is_active', 'group', 'subject', 'teacher')
    search_fields = ('group__name', 'subject__name', 'teacher__user__first_name', 'teacher__user__last_name', 'classroom')
    ordering = ['weekday', 'start_time']

    # УБИРАЕМ ПОЛЯ start_date, end_date
    fieldsets = (
        ('Основная информация', {
            'fields': ('group', 'subject', 'teacher', 'classroom')
        }),
        ('Время и день', {
            'fields': ('weekday', 'start_time', 'end_time')
        }),
        ('Статус', {
            'fields': ('is_active',),
        }),
    )

    def get_schedule_info(self, obj):
        return f"{obj.group.name} - {obj.subject.name}"
    get_schedule_info.short_description = 'Группа - Предмет'

    def get_time_range(self, obj):
        return obj.get_time_range()
    get_time_range.short_description = 'Время'

    def get_weekday_display(self, obj):
        return obj.get_weekday_display()
    get_weekday_display.short_description = 'День недели'

    # Фильтрация для учителей
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request.user, 'teacher') and not request.user.is_superuser:
            return qs.filter(teacher=request.user.teacher)
        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if hasattr(request.user, 'teacher') and not request.user.is_superuser:
            teacher = request.user.teacher

            if db_field.name == "teacher":
                kwargs["queryset"] = Teacher.objects.filter(id=teacher.id)
            elif db_field.name == "group":
                teacher_groups = [teacher.main_group] + list(teacher.additional_groups.all())
                kwargs["queryset"] = Group.objects.filter(id__in=[g.id for g in teacher_groups])
            elif db_field.name == "subject":
                kwargs["queryset"] = teacher.subjects.all()

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# Регистрация моделей
admin.site.register(User, CustomUserAdmin)
admin.site.register(Role, RoleAdmin)
admin.site.register(Teacher, TeacherAdmin)
admin.site.register(Student, StudentAdmin)
admin.site.register(Parent, ParentAdmin)
admin.site.register(Subject, SubjectAdmin)
admin.site.register(Lesson, LessonAdmin)
admin.site.register(Attendance, AttendanceAdmin)
admin.site.register(Group, GroupAdmin)
admin.site.register(Schedule, ScheduleAdmin)

# Настройки админки
admin.site.site_header = "Электронный журнал - Администрирование"
admin.site.site_title = "Электронный журнал"
admin.site.index_title = "Панель управления"
