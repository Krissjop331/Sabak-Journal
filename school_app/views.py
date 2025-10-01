from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.core.exceptions import ValidationError  # ДОБАВЛЕНО
from django.views.decorators.http import require_POST
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from django.conf import settings
from django.utils import timezone
import jwt, datetime

from .forms import LoginForm
from .models import Student, Teacher, Parent, Attendance, Lesson, Subject, Group, Schedule
from .utils import get_user_role

User = get_user_model()

def generate_jwt(user):
    payload = {
        'id': user.id,
        'username': user.username,
        'role': get_user_role(user),
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        'iat': datetime.datetime.utcnow()
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = authenticate(
            request,
            username=form.cleaned_data["username"],
            password=form.cleaned_data["password"]
        )
        if user:
            login(request, user)
            messages.success(request, "Вы успешно вошли в систему!")
            return redirect("home")
        messages.error(request, "Неверное имя пользователя или пароль.")

    return render(request, "login.html", {"form": form})

def logout_view(request):
    logout(request)
    messages.info(request, "Вы вышли из системы.")
    return redirect("login")

@api_view(['GET'])
@permission_classes([AllowAny])
def check_auth(request):
    token = request.headers.get('Authorization')
    if not token:
        return JsonResponse({'error': 'Токен отсутствует'}, status=401)

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user = User.objects.get(id=payload['id'])
        return JsonResponse({'id': user.id, 'username': user.username, 'role': payload['role']})
    except jwt.ExpiredSignatureError:
        return JsonResponse({'error': 'Токен истек'}, status=401)
    except jwt.DecodeError:
        return JsonResponse({'error': 'Неверный токен'}, status=401)

@login_required
def home_view(request):
    user = request.user
    is_student = Student.objects.filter(user=user).exists()
    is_teacher = Teacher.objects.filter(user=user).exists()
    is_parent = Parent.objects.filter(user=user).exists()
    is_admin = user.is_superuser or user.groups.filter(name="admin").exists()

    if is_admin:
        return redirect('/admin/')

    context = {
        'user': user,
        'is_student': is_student,
        'is_teacher': is_teacher,
        'is_parent': is_parent,
        'is_admin': is_admin,
        'today': timezone.now(),
    }

    if is_student:
        student = get_object_or_404(Student.objects.select_related('group'), user=user)
        attendance_records = Attendance.objects.filter(student=student).select_related('lesson__subject').order_by('-lesson__date')

        total_lessons = attendance_records.count()
        attended_lessons = attendance_records.filter(attended=True).count()
        late_lessons = attendance_records.filter(late=True).count()  # НОВАЯ СТАТИСТИКА
        absent_lessons = attendance_records.filter(attended=False).count()

        attendance_percentage = (attended_lessons / total_lessons * 100) if total_lessons > 0 else 0
        late_percentage = (late_lessons / total_lessons * 100) if total_lessons > 0 else 0  # НОВАЯ СТАТИСТИКА

        subjects = Subject.objects.all()
        grades = {subject.name: attendance_records.filter(lesson__subject=subject) for subject in subjects}

        context.update({
            'student': student,
            'group': student.group,
            'attendance_records': attendance_records,
            'total_lessons': total_lessons,
            'attended_lessons': attended_lessons,
            'late_lessons': late_lessons,  # НОВАЯ СТАТИСТИКА
            'absent_lessons': absent_lessons,
            'attendance_percentage': attendance_percentage,
            'late_percentage': late_percentage,  # НОВАЯ СТАТИСТИКА
            'grades': grades,
            'lessons': Lesson.objects.filter(group=student.group).select_related('subject'),
        })

    elif is_teacher:
        teacher = get_object_or_404(Teacher.objects.prefetch_related('additional_groups'), user=user)
        groups = {teacher.main_group.id: teacher.main_group}
        for group in teacher.additional_groups.all():
            groups[group.id] = group
        students_by_group = {
            group.id: Student.objects.filter(group=group).select_related('user')
            for group in groups.values()
        }
        context.update({
            'teacher': teacher,
            'groups': groups.values(),
            'students_by_group': students_by_group,
        })

    elif is_parent:
        parent = get_object_or_404(Parent.objects.prefetch_related('children'), user=user)
        children = parent.children.all()

        child_statistics = []
        for child in children:
            total_classes = Attendance.objects.filter(student=child).count()
            attended_classes = Attendance.objects.filter(student=child, attended=True).count()
            late_classes = Attendance.objects.filter(student=child, late=True).count()  # НОВАЯ СТАТИСТИКА
            attendance_percentage = (attended_classes / total_classes * 100) if total_classes > 0 else 0
            late_percentage = (late_classes / total_classes * 100) if total_classes > 0 else 0  # НОВАЯ СТАТИСТИКА

            # Получаем данные по предметам
            subjects = Subject.objects.all()
            subject_data = {}
            for subject in subjects:
                subject_attendance = Attendance.objects.filter(student=child, lesson__subject=subject)
                subject_attended = subject_attendance.filter(attended=True).count()
                subject_late = subject_attendance.filter(late=True).count()  # НОВАЯ СТАТИСТИКА
                subject_missed = subject_attendance.filter(attended=False).count()
                subject_grades = subject_attendance.values_list('grade', flat=True)

                subject_data[subject.name] = {
                    'attended': subject_attended,
                    'late': subject_late,  # НОВАЯ СТАТИСТИКА
                    'missed': subject_missed,
                    'grades': list(subject_grades),
                    'attendance_percentage': (subject_attended / subject_attendance.count() * 100) if subject_attendance.count() > 0 else 0,
                    'late_percentage': (subject_late / subject_attendance.count() * 100) if subject_attendance.count() > 0 else 0,  # НОВАЯ СТАТИСТИКА
                }

            child_statistics.append({
                'child': child,
                'attendance_percentage': attendance_percentage,
                'late_percentage': late_percentage,  # НОВАЯ СТАТИСТИКА
                'attendance_data': {
                    'attended': attended_classes,
                    'late': late_classes,  # НОВАЯ СТАТИСТИКА
                    'missed': total_classes - attended_classes,
                },
                'subject_data': subject_data,
            })

        context.update({
            'parent': parent,
            'children': children,
            'child_statistics': child_statistics,
        })

    return render(request, 'home.html', context)

# ИСПРАВЛЕННАЯ ФУНКЦИЯ edit_attendance - замените в views.py строки 89-200

@login_required
def edit_attendance(request, student_id):
    """Исправленная функция редактирования посещаемости"""
    student = get_object_or_404(Student, id=student_id)

    # Проверяем права доступа
    has_access = False

    # Проверка для учителя
    if hasattr(request.user, 'teacher'):
        teacher = request.user.teacher
        # Проверяем, что учитель работает с группой этого студента
        if (teacher.main_group == student.group or
            teacher.additional_groups.filter(id=student.group.id).exists()):
            has_access = True

    # Проверка для родителя
    elif hasattr(request.user, 'parent'):
        parent = request.user.parent
        if parent.children.filter(id=student.id).exists():
            has_access = True

    # Проверка для админа или самого студента
    elif request.user.is_superuser or request.user == student.user:
        has_access = True

    if not has_access:
        messages.error(request, "У вас нет прав для редактирования этого студента.")
        return redirect('home')

    # Получаем все уроки группы студента
    lessons = Lesson.objects.filter(group=student.group).select_related('subject').order_by('-date')

    # Получаем существующие записи посещаемости
    records = Attendance.objects.filter(student=student).select_related('lesson__subject')
    records_dict = {record.lesson.id: record for record in records}

    if request.method == 'POST':
        changes_made = False

        for lesson in lessons:
            attended_key = f'attended_{lesson.id}'
            late_key = f'late_{lesson.id}'
            grade_key = f'grade_{lesson.id}'

            # Получаем данные из формы
            attended = attended_key in request.POST
            late = late_key in request.POST
            grade_str = request.POST.get(grade_key, '').strip()

            # Если студент не посещал, опоздание автоматически false
            if not attended:
                late = False

            # Обработка оценки
            grade = None
            if grade_str:
                try:
                    grade = int(grade_str)
                    if grade < 2 or grade > 5:
                        grade = None
                except ValueError:
                    grade = None

            # Обновляем или создаем запись
            if lesson.id in records_dict:
                # Обновляем существующую запись
                attendance = records_dict[lesson.id]
                if (attendance.attended != attended or
                    attendance.late != late or
                    attendance.grade != grade):
                    attendance.attended = attended
                    attendance.late = late
                    attendance.grade = grade
                    try:
                        attendance.save()
                        changes_made = True
                    except ValidationError as e:
                        messages.error(request, f"Ошибка при сохранении: {e}")
                        continue
            else:
                # Создаем новую запись
                try:
                    Attendance.objects.create(
                        student=student,
                        lesson=lesson,
                        attended=attended,
                        late=late,
                        grade=grade
                    )
                    changes_made = True
                except ValidationError as e:
                    messages.error(request, f"Ошибка при создании записи: {e}")
                    continue

        if changes_made:
            messages.success(request, f"Посещаемость и оценки для {student.user.get_full_name()} успешно обновлены!")
        else:
            messages.info(request, 'Нет изменений для сохранения.')

        return redirect('home')

    # GET запрос - подготавливаем данные для отображения
    attendance_data = []
    for lesson in lessons:
        record = records_dict.get(lesson.id, None)
        attendance_data.append({
            'lesson': lesson,
            'attendance': record,
        })

    # Подсчитываем статистику
    total_lessons = records.count()
    attended_lessons = records.filter(attended=True).count()
    late_lessons = records.filter(late=True).count()
    absent_lessons = records.filter(attended=False).count()

    # Средняя оценка
    grades = [record.grade for record in records if record.grade is not None]
    average_grade = sum(grades) / len(grades) if grades else 0

    context = {
        'student': student,
        'attendance_data': attendance_data,
        'records': records,
        'total_lessons': total_lessons,
        'attended_lessons': attended_lessons,
        'late_lessons': late_lessons,
        'absent_lessons': absent_lessons,
        'attendance_percentage': (attended_lessons / total_lessons * 100) if total_lessons > 0 else 0,
        'late_percentage': (late_lessons / total_lessons * 100) if total_lessons > 0 else 0,
        'average_grade': average_grade,
    }

    return render(request, 'edit_student.html', context)

@login_required
def edit_student_marks_view(request, student_id):
    student = get_object_or_404(Student, pk=student_id)

    # Проверяем, имеет ли учитель доступ к группе этого студента
    try:
        teacher = Teacher.objects.get(user=request.user)
        # Проверка доступа к группе студента
        if teacher.main_group != student.group and not teacher.additional_groups.filter(id=student.group.id).exists():
            messages.error(request, "У вас нет прав для редактирования этого студента.")
            return redirect('home')
    except Teacher.DoesNotExist:
        # Если пользователь не учитель, проверяем, является ли он родителем этого студента
        is_parent = Parent.objects.filter(user=request.user, children=student).exists()
        is_admin = request.user.is_superuser or request.user.groups.filter(name="admin").exists()

        if not is_parent and not is_admin and request.user != student.user:
            messages.error(request, "У вас нет прав для редактирования этого студента.")
            return redirect('home')

    records = Attendance.objects.filter(student=student).select_related('lesson')

    total_classes = records.count()
    attended_classes = records.filter(attended=True).count()
    attendance_percentage = (attended_classes / total_classes * 100) if total_classes > 0 else 0

    # Вычисление средней оценки
    total_grades = sum(record.grade or 0 for record in records)  # Используем 0 для None
    average_grade = total_grades / total_classes if total_classes > 0 else 0

    if request.method == 'POST':
        changes_made = False
        for record in records:
            grade_key = f'grade_{record.id}'
            attended_key = f'attended_{record.id}'
            new_grade_str = request.POST.get(grade_key, '').strip()

            if new_grade_str:
                new_grade_str = new_grade_str.replace(',', '.')
                try:
                    new_grade = float(new_grade_str)
                except ValueError:
                    new_grade = None
            else:
                new_grade = None

            new_attended = attended_key in request.POST

            if record.grade != new_grade or record.attended != new_attended:
                record.grade = new_grade
                record.attended = new_attended
                record.save()
                changes_made = True

        if changes_made:
            messages.success(request, f'Оценки и посещаемость студента {student.user.get_full_name()} обновлены!')
        else:
            messages.info(request, 'Нет изменений для сохранения.')

        return redirect('home')

    return render(request, 'edit_student.html', {
        'student': student,
        'records': records,
        'attendance_percentage': attendance_percentage,
        'average_grade': average_grade,
        'attended_classes': attended_classes,
        'total_classes': total_classes,
    })

# ЗАМЕНИТЕ функцию update_user_image в views.py

@login_required
@require_POST
def update_user_image(request):
    """Исправленная функция обновления изображения профиля"""
    user = request.user

    print(f"🔍 UPDATE IMAGE DEBUG: User={user.username}")
    print(f"🔍 FILES: {request.FILES}")
    print(f"🔍 POST: {request.POST}")

    if request.method == 'POST':
        # Проверяем наличие файла
        if 'image' not in request.FILES:
            messages.error(request, "Файл изображения не выбран.")
            return redirect('home')

        uploaded_file = request.FILES['image']
        print(f"🔍 Uploaded file: {uploaded_file.name}, size: {uploaded_file.size}")

        # Проверяем размер файла (максимум 5MB)
        if uploaded_file.size > 5 * 1024 * 1024:
            messages.error(request, "Файл слишком большой. Максимальный размер: 5MB")
            return redirect('home')

        # Проверяем тип файла
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif']
        if uploaded_file.content_type not in allowed_types:
            messages.error(request, "Недопустимый тип файла. Разрешены: JPG, PNG, GIF")
            return redirect('home')

        try:
            # Сохраняем старое изображение для удаления
            old_image = user.image

            # Обновляем изображение
            user.image = uploaded_file
            user.save()

            # Удаляем старое изображение если оно не дефолтное
            if (old_image and
                old_image.name != 'school_app/static/images/default_image.png' and
                old_image.name != user.image.name):
                try:
                    old_image.delete(save=False)
                    print(f"✅ Старое изображение удалено: {old_image.name}")
                except Exception as e:
                    print(f"⚠️ Не удалось удалить старое изображение: {e}")

            messages.success(request, "Изображение успешно обновлено!")
            print(f"✅ Изображение обновлено для {user.username}: {user.image.name}")

        except Exception as e:
            messages.error(request, f"Ошибка при сохранении изображения: {e}")
            print(f"❌ Ошибка сохранения изображения: {e}")
    else:
        messages.error(request, "Неверный метод запроса.")

    return redirect('home')

# ЗАМЕНИТЕ функцию add_lesson в views.py

@login_required
def add_lesson(request):
    """Новая логика добавления урока: выбор из расписания или создание вручную"""
    try:
        teacher = Teacher.objects.get(user=request.user)
    except Teacher.DoesNotExist:
        messages.error(request, "У вас нет прав для добавления уроков.")
        return redirect('home')

    if request.method == 'POST':
        # Получаем данные из формы
        lesson_type = request.POST.get('lesson_type')  # 'from_schedule' или 'manual'
        schedule_id = request.POST.get('schedule_id')
        date = request.POST.get('date')

        # Данные для ручного создания
        subject_id = request.POST.get('subject')
        group_id = request.POST.get('group')
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')
        classroom = request.POST.get('classroom', '')
        notes = request.POST.get('notes', '')

        print(f"🔍 DEBUG: lesson_type={lesson_type}, schedule_id={schedule_id}, date={date}")

        if not date:
            messages.error(request, "Выберите дату урока.")
            return redirect('add_lesson')

        try:
            from datetime import datetime
            lesson_date = datetime.strptime(date, '%Y-%m-%d').date()

            if lesson_type == 'from_schedule':
                # СОЗДАНИЕ УРОКА ИЗ РАСПИСАНИЯ
                if not schedule_id:
                    messages.error(request, "Выберите занятие из расписания.")
                    return redirect('add_lesson')

                schedule = get_object_or_404(Schedule, id=schedule_id)

                # Проверяем права доступа
                if (teacher.main_group != schedule.group and
                    not teacher.additional_groups.filter(id=schedule.group.id).exists()):
                    messages.error(request, "У вас нет прав для создания урока для этой группы.")
                    return redirect('add_lesson')

                # Проверяем, что день недели соответствует расписанию
                if lesson_date.weekday() != schedule.weekday:
                    day_names = ['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье']
                    messages.error(request, f"Выбранная дата ({lesson_date.strftime('%d.%m.%Y')}) не соответствует дню расписания ({day_names[schedule.weekday]}).")
                    return redirect('add_lesson')

                # Проверяем уникальность
                existing_lesson = Lesson.objects.filter(
                    schedule=schedule,
                    date=lesson_date
                ).first()

                if existing_lesson:
                    messages.error(request, f"Урок из этого расписания на {lesson_date.strftime('%d.%m.%Y')} уже существует!")
                    return redirect('add_lesson')

                # Создаем урок из расписания
                lesson = Lesson.objects.create(
                    schedule=schedule,
                    subject=schedule.subject,
                    date=lesson_date,
                    group=schedule.group,
                    teacher=schedule.teacher,
                    classroom=classroom or schedule.classroom,
                    start_time=schedule.start_time,
                    end_time=schedule.end_time,
                    is_from_schedule=True,
                    notes=notes
                )

                messages.success(request,
                    f"✅ Урок создан из расписания: {schedule.subject.name} "
                    f"для группы {schedule.group.name} на {lesson_date.strftime('%d.%m.%Y')} "
                    f"в {schedule.get_time_range()}")

            else:
                # РУЧНОЕ СОЗДАНИЕ УРОКА
                if not all([subject_id, group_id]):
                    messages.error(request, "Выберите предмет и группу.")
                    return redirect('add_lesson')

                subject = get_object_or_404(Subject, id=subject_id)
                group = get_object_or_404(Group, id=group_id)

                # Проверяем права доступа
                if (teacher.main_group.id != int(group_id) and
                    not teacher.additional_groups.filter(id=group_id).exists()):
                    messages.error(request, "У вас нет прав для создания урока для этой группы.")
                    return redirect('add_lesson')

                # Проверяем уникальность
                existing_lesson = Lesson.objects.filter(
                    subject=subject,
                    group=group,
                    date=lesson_date
                ).first()

                if existing_lesson:
                    messages.error(request, f"Урок '{subject.name}' для группы '{group.name}' на {lesson_date.strftime('%d.%m.%Y')} уже существует!")
                    return redirect('add_lesson')

                # Создаем урок вручную
                lesson = Lesson.objects.create(
                    subject=subject,
                    date=lesson_date,
                    group=group,
                    teacher=teacher,
                    classroom=classroom,
                    start_time=start_time if start_time else None,
                    end_time=end_time if end_time else None,
                    is_from_schedule=False,
                    notes=notes
                )

                time_info = f" в {lesson.get_time_range()}" if lesson.start_time else ""
                messages.success(request,
                    f"✅ Урок создан вручную: {subject.name} "
                    f"для группы {group.name} на {lesson_date.strftime('%d.%m.%Y')}{time_info}")

            # Создаем записи посещаемости для всех студентов группы
            students = Student.objects.filter(group=lesson.group)
            attendance_records = []
            for student in students:
                attendance_records.append(
                    Attendance(
                        lesson=lesson,
                        student=student,
                        attended=False,
                        late=False,
                        grade=None
                    )
                )

            Attendance.objects.bulk_create(attendance_records)

            messages.info(request, f"Создано записей посещаемости: {students.count()}")
            return redirect('home')  # Успешное перенаправление

        except Exception as e:
            print(f"❌ ERROR: {e}")
            messages.error(request, f"Ошибка при создании урока: {str(e)}")
            return redirect('add_lesson')

    # GET запрос - подготавливаем данные для формы
    subjects = teacher.subjects.all()
    groups = list(teacher.additional_groups.all())
    groups.insert(0, teacher.main_group)

    # Получаем активное расписание учителя
    teacher_schedule = Schedule.objects.filter(
        teacher=teacher,
        is_active=True
    ).select_related('subject', 'group').order_by('weekday', 'start_time')

    context = {
        'subjects': subjects,
        'groups': groups,
        'teacher': teacher,
        'teacher_schedule': teacher_schedule,
        'today': timezone.now().date(),
        'weekdays': Schedule.WEEKDAYS,
    }

    return render(request, 'add_lesson.html', context)

@login_required
def create_missing_attendance_records(request):
    """
    Создает недостающие записи посещаемости для всех существующих уроков
    Полезно для исправления ситуаций, когда уроки были созданы без записей посещаемости
    """
    if not request.user.is_superuser:
        messages.error(request, "У вас нет прав для выполнения этой операции.")
        return redirect('home')

    if request.method == 'POST':
        created_count = 0

        # Получаем все уроки
        lessons = Lesson.objects.all()

        for lesson in lessons:
            # Получаем всех студентов группы
            students = Student.objects.filter(group=lesson.group)

            # Находим студентов, для которых нет записей посещаемости для этого урока
            existing_attendance = Attendance.objects.filter(lesson=lesson).values_list('student_id', flat=True)
            students_without_attendance = students.exclude(id__in=existing_attendance)

            # Создаем недостающие записи
            attendance_records = []
            for student in students_without_attendance:
                attendance_record = Attendance(
                    lesson=lesson,
                    student=student,
                    attended=False,
                    late=False,
                    grade=None
                )
                attendance_records.append(attendance_record)

            if attendance_records:
                Attendance.objects.bulk_create(attendance_records)
                created_count += len(attendance_records)

        messages.success(request, f"Создано {created_count} недостающих записей посещаемости.")
        return redirect('home')

    # GET запрос - показываем информацию
    lessons_without_full_attendance = []
    lessons = Lesson.objects.all()

    for lesson in lessons:
        students_count = Student.objects.filter(group=lesson.group).count()
        attendance_count = Attendance.objects.filter(lesson=lesson).count()

        if students_count != attendance_count:
            lessons_without_full_attendance.append({
                'lesson': lesson,
                'students_count': students_count,
                'attendance_count': attendance_count,
                'missing_count': students_count - attendance_count
            })

    return render(request, 'create_missing_attendance.html', {
        'lessons_without_full_attendance': lessons_without_full_attendance
    })


# ЗАМЕНИТЕ функцию schedule_view в views.py

@login_required
def schedule_view(request):
    """Исправленное отображение расписания с группировкой по дням"""
    user = request.user

    print(f"=== SCHEDULE VIEW DEBUG ===")
    print(f"User: {user.username}")

    # Получаем все активные расписания
    all_schedules = Schedule.objects.filter(is_active=True).select_related('subject', 'teacher__user', 'group')
    print(f"Total active schedules: {all_schedules.count()}")

    # Определяем роль пользователя и фильтруем данные
    role = 'admin'
    context_extra = {}

    if hasattr(user, 'student'):
        role = 'student'
        student = user.student
        schedules = all_schedules.filter(group=student.group)
        context_extra = {
            'student': student,
            'group': student.group,
        }
        print(f"Student mode: {schedules.count()} schedules for group {student.group.name}")

    elif hasattr(user, 'teacher'):
        role = 'teacher'
        teacher = user.teacher
        schedules = all_schedules.filter(teacher=teacher)
        context_extra = {
            'teacher': teacher,
            'teacher_groups': [teacher.main_group] + list(teacher.additional_groups.all()),
        }
        print(f"Teacher mode: {schedules.count()} schedules for teacher {teacher.user.get_full_name()}")

    elif hasattr(user, 'parent'):
        role = 'parent'
        parent = user.parent
        children = parent.children.all()
        child_groups = [child.group for child in children]
        schedules = all_schedules.filter(group__in=child_groups)
        context_extra = {
            'parent': parent,
            'children': children,
        }
        print(f"Parent mode: {schedules.count()} schedules for {len(child_groups)} groups")

    else:
        # Админ или суперпользователь
        schedules = all_schedules
        print(f"Admin mode: {schedules.count()} total schedules")

    # ИСПРАВЛЕНО: Правильная группировка по дням недели
    schedule_by_day = {}

    # Инициализируем все дни недели пустыми списками
    for day_num, day_name in Schedule.WEEKDAYS:
        schedule_by_day[day_num] = []

    # Группируем расписания по дням
    for schedule in schedules.order_by('weekday', 'start_time'):
        schedule_by_day[schedule.weekday].append(schedule)
        print(f"Added to day {schedule.weekday}: {schedule}")

    print(f"Schedule grouped by days: {dict((k, len(v)) for k, v in schedule_by_day.items())}")

    context = {
        'user': user,
        'role': role,
        'today': timezone.now().date(),
        'weekdays': Schedule.WEEKDAYS,
        'schedule_by_day': schedule_by_day,
        'total_schedules': schedules.count(),
        **context_extra
    }

    print(f"Context prepared with {len(schedule_by_day)} days")
    print(f"=== END DEBUG ===")

    return render(request, 'schedule.html', context)

@login_required
def add_schedule(request):
    """Исправленная функция добавления расписания с правильными редиректами"""
    user = request.user

    # Проверяем права доступа
    if not (user.is_superuser or hasattr(user, 'teacher')):
        messages.error(request, "У вас нет прав для добавления расписания.")
        return redirect('schedule')

    if request.method == 'POST':
        group_id = request.POST.get('group')
        subject_id = request.POST.get('subject')
        teacher_id = request.POST.get('teacher')
        weekday = request.POST.get('weekday')
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')
        classroom = request.POST.get('classroom', '')

        print(f"🔍 ADD_SCHEDULE POST: group={group_id}, subject={subject_id}, teacher={teacher_id}")
        print(f"🔍 ADD_SCHEDULE POST: weekday={weekday}, times={start_time}-{end_time}")

        # Проверяем обязательные поля
        missing_fields = []
        if not group_id: missing_fields.append('группа')
        if not subject_id: missing_fields.append('предмет')
        if not teacher_id: missing_fields.append('преподаватель')
        if not weekday: missing_fields.append('день недели')
        if not start_time: missing_fields.append('время начала')
        if not end_time: missing_fields.append('время окончания')

        if missing_fields:
            messages.error(request, f"Заполните обязательные поля: {', '.join(missing_fields)}")
            # ВАЖНО: используем redirect вместо render для предотвращения повторной отправки
            return redirect('add_schedule')

        try:
            # Получаем объекты
            group = get_object_or_404(Group, id=group_id)
            subject = get_object_or_404(Subject, id=subject_id)
            teacher = get_object_or_404(Teacher, id=teacher_id)

            print(f"✅ Объекты получены: {group}, {subject}, {teacher}")

            # Проверка прав для учителей
            if hasattr(user, 'teacher') and not user.is_superuser:
                if user.teacher != teacher:
                    messages.error(request, "Вы можете создавать расписание только для себя.")
                    return redirect('add_schedule')

            # Валидация времени
            if start_time >= end_time:
                messages.error(request, "Время окончания должно быть больше времени начала.")
                return redirect('add_schedule')

            # Проверяем, что преподаватель ведет этот предмет
            if not teacher.subjects.filter(id=subject.id).exists():
                messages.error(request,
                    f"Преподаватель {teacher.user.get_full_name()} не ведет предмет {subject.name}. "
                    f"Добавьте предмет в профиль преподавателя в админке.")
                return redirect('add_schedule')

            # Проверяем, что преподаватель работает с этой группой
            if (teacher.main_group != group and
                not teacher.additional_groups.filter(id=group.id).exists()):
                messages.error(request,
                    f"Преподаватель {teacher.user.get_full_name()} не работает с группой {group.name}. "
                    f"Добавьте группу в профиль преподавателя в админке.")
                return redirect('add_schedule')

            # Проверяем дублирование по времени и группе
            existing_time_conflict = Schedule.objects.filter(
                group=group,
                weekday=int(weekday),
                is_active=True
            ).exclude(
                end_time__lte=start_time
            ).exclude(
                start_time__gte=end_time
            ).first()

            if existing_time_conflict:
                messages.error(request,
                    f"Конфликт времени! У группы {group.name} уже есть занятие "
                    f"на {existing_time_conflict.get_weekday_display()} "
                    f"с {existing_time_conflict.get_time_range()}: "
                    f"{existing_time_conflict.subject.name}")
                return redirect('add_schedule')

            # Проверяем конфликты времени для преподавателя
            teacher_time_conflict = Schedule.objects.filter(
                teacher=teacher,
                weekday=int(weekday),
                is_active=True
            ).exclude(
                end_time__lte=start_time
            ).exclude(
                start_time__gte=end_time
            ).first()

            if teacher_time_conflict:
                messages.error(request,
                    f"Конфликт времени! У преподавателя {teacher.user.get_full_name()} "
                    f"уже есть занятие в это время: {teacher_time_conflict.subject.name} "
                    f"({teacher_time_conflict.get_time_range()}) с группой {teacher_time_conflict.group.name}")
                return redirect('add_schedule')

            # Все проверки пройдены - создаем расписание
            schedule = Schedule.objects.create(
                group=group,
                subject=subject,
                teacher=teacher,
                weekday=int(weekday),
                start_time=start_time,
                end_time=end_time,
                classroom=classroom,
                is_active=True
            )

            print(f"✅ Расписание создано: {schedule}")

            messages.success(request,
                f"✅ Расписание успешно добавлено: {schedule.subject.name} "
                f"для группы {schedule.group.name} на {schedule.get_weekday_display()} "
                f"с {schedule.get_time_range()}")

            # ВАЖНО: После успешного создания перенаправляем на страницу расписания
            return redirect('schedule')

        except ValidationError as e:
            messages.error(request, f"Ошибка валидации: {e}")
            print(f"❌ ValidationError: {e}")
            return redirect('add_schedule')
        except Exception as e:
            messages.error(request, f"Неожиданная ошибка: {e}")
            print(f"❌ Exception: {e}")
            return redirect('add_schedule')

    # GET запрос - показываем форму
    context = {
        'weekdays': Schedule.WEEKDAYS,
    }

    if user.is_superuser:
        # Админ видит все
        context.update({
            'groups': Group.objects.all(),
            'subjects': Subject.objects.all(),
            'teachers': Teacher.objects.all().select_related('user'),
        })
        print(f"🔍 GET (admin): {Group.objects.count()} групп, {Subject.objects.count()} предметов, {Teacher.objects.count()} учителей")
    elif hasattr(user, 'teacher'):
        # Учитель видит только свои данные
        teacher = user.teacher
        teacher_groups = [teacher.main_group] + list(teacher.additional_groups.all())
        context.update({
            'groups': teacher_groups,
            'subjects': teacher.subjects.all(),
            'teachers': [teacher],
            'current_teacher': teacher,
        })
        print(f"🔍 GET (teacher): {len(teacher_groups)} групп, {teacher.subjects.count()} предметов")

    return render(request, 'add_schedule.html', context)

@login_required
def delete_schedule(request, schedule_id):
    """Удаление расписания"""
    schedule = get_object_or_404(Schedule, id=schedule_id)

    # Проверяем права доступа
    if not (request.user.is_superuser or
            (hasattr(request.user, 'teacher') and request.user.teacher == schedule.teacher)):
        messages.error(request, "У вас нет прав для удаления этого расписания.")
        return redirect('schedule')

    if request.method == 'POST':
        schedule_str = str(schedule)
        schedule.delete()
        messages.success(request, f"Расписание '{schedule_str}' успешно удалено.")
        return redirect('schedule')

    return render(request, 'confirm_delete_schedule.html', {'schedule': schedule})

@login_required
def create_lesson_from_schedule(request, schedule_id):
    """Создание урока из конкретного элемента расписания"""
    schedule = get_object_or_404(Schedule, id=schedule_id)

    # Проверяем права доступа
    try:
        teacher = Teacher.objects.get(user=request.user)
        if teacher != schedule.teacher and not request.user.is_superuser:
            messages.error(request, "У вас нет прав для создания урока из этого расписания.")
            return redirect('schedule')
    except Teacher.DoesNotExist:
        if not request.user.is_superuser:
            messages.error(request, "У вас нет прав для создания уроков.")
            return redirect('schedule')
        teacher = schedule.teacher

    if request.method == 'POST':
        date = request.POST.get('date')
        classroom = request.POST.get('classroom', '')
        notes = request.POST.get('notes', '')

        if not date:
            messages.error(request, "Выберите дату урока.")
            return redirect('create_lesson_from_schedule', schedule_id=schedule_id)

        try:
            from datetime import datetime
            lesson_date = datetime.strptime(date, '%Y-%m-%d').date()

            # Проверяем, что день недели соответствует расписанию
            if lesson_date.weekday() != schedule.weekday:
                day_names = ['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье']
                messages.error(request,
                    f"Выбранная дата ({lesson_date.strftime('%d.%m.%Y')}) не соответствует "
                    f"дню расписания ({day_names[schedule.weekday]}).")
                return redirect('create_lesson_from_schedule', schedule_id=schedule_id)

            # Проверяем уникальность
            existing_lesson = Lesson.objects.filter(
                schedule=schedule,
                date=lesson_date
            ).first()

            if existing_lesson:
                messages.error(request,
                    f"Урок из этого расписания на {lesson_date.strftime('%d.%m.%Y')} уже существует!")
                return redirect('create_lesson_from_schedule', schedule_id=schedule_id)

            # Создаем урок из расписания
            lesson = Lesson.objects.create(
                schedule=schedule,
                subject=schedule.subject,
                date=lesson_date,
                group=schedule.group,
                teacher=schedule.teacher,
                classroom=classroom or schedule.classroom,
                start_time=schedule.start_time,
                end_time=schedule.end_time,
                is_from_schedule=True,
                notes=notes
            )

            # Создаем записи посещаемости для всех студентов группы
            students = Student.objects.filter(group=schedule.group)
            attendance_records = []
            for student in students:
                attendance_records.append(
                    Attendance(
                        lesson=lesson,
                        student=student,
                        attended=False,
                        late=False,
                        grade=None
                    )
                )

            Attendance.objects.bulk_create(attendance_records)

            messages.success(request,
                f"✅ Урок создан: {schedule.subject.name} для группы {schedule.group.name} "
                f"на {lesson_date.strftime('%d.%m.%Y')} в {schedule.get_time_range()}. "
                f"Создано записей посещаемости: {students.count()}")

            return redirect('schedule')

        except Exception as e:
            print(f"❌ ERROR: {e}")
            messages.error(request, f"Ошибка при создании урока: {str(e)}")
            return redirect('create_lesson_from_schedule', schedule_id=schedule_id)

    # GET запрос - показываем форму
    context = {
        'schedule': schedule,
        'today': timezone.now().date(),
        'weekdays': Schedule.WEEKDAYS,
    }

    return render(request, 'create_lesson_from_schedule.html', context)
