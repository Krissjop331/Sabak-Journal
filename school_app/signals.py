from django.db.models.signals import post_migrate, m2m_changed, post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Role, Group, Subject, Teacher, Student, Parent, Lesson, Attendance
from django.utils import timezone
from django.db import IntegrityError
import random
import datetime

User = get_user_model()

@receiver(m2m_changed, sender=User.role.through)
def create_role_based_records(sender, instance, action, pk_set, **kwargs):
    """
    Автоматически создает записи Student/Teacher/Parent при назначении ролей
    """
    if action == 'post_add':  # Когда роль добавлена к пользователю
        for role_id in pk_set:
            try:
                role = Role.objects.get(id=role_id)
                print(f"🔄 Назначена роль '{role.name}' пользователю {instance.username}")

                if role.name.lower() in ['студент', 'студенты']:
                    # Создаем запись Student, если её нет
                    if not hasattr(instance, 'student'):
                        # Назначаем случайную группу или первую доступную
                        default_group = Group.objects.first()
                        if default_group:
                            student = Student.objects.create(
                                user=instance,
                                group=default_group
                            )
                            print(f"✅ Создан студент для {instance.username} в группе {default_group.name}")
                        else:
                            print(f"❌ Нет доступных групп для создания студента {instance.username}")

                elif role.name.lower() in ['учитель', 'преподаватель', 'teacher']:
                    # Создаем запись Teacher, если её нет
                    if not hasattr(instance, 'teacher'):
                        # Назначаем случайную группу как основную
                        default_group = Group.objects.first()
                        if default_group:
                            teacher = Teacher.objects.create(
                                user=instance,
                                main_group=default_group
                            )
                            print(f"✅ Создан учитель для {instance.username} с основной группой {default_group.name}")
                        else:
                            print(f"❌ Нет доступных групп для создания учителя {instance.username}")

                elif role.name.lower() in ['родитель', 'родители', 'parent']:
                    # Создаем запись Parent, если её нет
                    if not hasattr(instance, 'parent'):
                        parent = Parent.objects.create(
                            user=instance,
                            parent_type='other'  # По умолчанию "другой"
                        )
                        print(f"✅ Создан родитель для {instance.username}")

            except Role.DoesNotExist:
                print(f"❌ Роль с ID {role_id} не найдена")
            except IntegrityError as e:
                print(f"❌ Ошибка создания записи для {instance.username}: {e}")
            except Exception as e:
                print(f"❌ Неожиданная ошибка для {instance.username}: {e}")

@receiver(m2m_changed, sender=User.role.through)
def remove_role_based_records(sender, instance, action, pk_set, **kwargs):
    """
    Удаляет записи Student/Teacher/Parent при удалении ролей
    """
    if action == 'post_remove':  # Когда роль удалена у пользователя
        for role_id in pk_set:
            try:
                role = Role.objects.get(id=role_id)
                print(f"🔄 Удалена роль '{role.name}' у пользователя {instance.username}")

                if role.name.lower() in ['студент', 'студенты']:
                    if hasattr(instance, 'student'):
                        instance.student.delete()
                        print(f"🗑️ Удалена запись студента для {instance.username}")

                elif role.name.lower() in ['учитель', 'преподаватель', 'teacher']:
                    if hasattr(instance, 'teacher'):
                        instance.teacher.delete()
                        print(f"🗑️ Удалена запись учителя для {instance.username}")

                elif role.name.lower() in ['родитель', 'родители', 'parent']:
                    if hasattr(instance, 'parent'):
                        instance.parent.delete()
                        print(f"🗑️ Удалена запись родителя для {instance.username}")

            except Role.DoesNotExist:
                print(f"❌ Роль с ID {role_id} не найдена")
            except Exception as e:
                print(f"❌ Ошибка при удалении записи для {instance.username}: {e}")

@receiver(post_migrate)
def create_initial_data(sender, **kwargs):
    if sender.name == 'school_app':
        print("🚀 Создание начальных данных...")

        # Создание ролей
        roles = ['студенты', 'учитель', 'родители', 'администратор', 'пользователь']
        for role_name in roles:
            role, created = Role.objects.get_or_create(name=role_name)
            if created:
                print(f"✅ Создана роль: {role_name}")

        # Создание групп
        group_names = [f'Группа {chr(65 + i)}' for i in range(12)]  # Группы от A до L
        for group_name in group_names:
            group, created = Group.objects.get_or_create(
                name=group_name,
                defaults={'course': random.randint(1, 3)}
            )
            if created:
                print(f"✅ Создана группа: {group_name}")

        # Создание предметов
        subject_names = [
            'Математика', 'Физика', 'Химия', 'Биология',
            'История', 'География', 'Литература', 'Иностранный язык',
            'Информатика', 'Музыка', 'Искусство', 'Физкультура'
        ]
        for subject_name in subject_names:
            subject, created = Subject.objects.get_or_create(name=subject_name)
            if created:
                print(f"✅ Создан предмет: {subject_name}")

        # Создание администратора
        admin_username = 'admin'
        if not User.objects.filter(username=admin_username).exists():
            try:
                admin_user = User.objects.create_superuser(
                    username=admin_username,
                    password='admin',
                    email='admin@gmail.com',
                    first_name='Admin',
                    last_name='Administrator'
                )
                admin_role = Role.objects.get(name='администратор')
                admin_user.role.add(admin_role)
                print(f"✅ Создан администратор: {admin_username}")
            except Exception as e:
                print(f"❌ Ошибка при создании администратора: {e}")

        # Создание тестовых данных только если их нет
        if User.objects.filter(username__startswith='student').count() < 5:
            create_sample_users()

        # Создание уроков
        if Lesson.objects.count() < 10:
            create_sample_lessons()

        print("🎉 Инициализация данных завершена!")

def create_sample_users():
    """Создает примерных пользователей"""
    print("👥 Создание примерных пользователей...")

    # Создание студентов
    for i in range(1, 11):
        student_username = f'student{i}'
        if not User.objects.filter(username=student_username).exists():
            try:
                student_user = User.objects.create_user(
                    username=student_username,
                    password='password',
                    email=f'student{i}@example.com',
                    first_name=f'Студент{i}',
                    last_name=f'Фамилия{i}'
                )

                # Добавляем роль студента (автоматически создастся запись Student)
                student_role = Role.objects.get(name='студенты')
                student_user.role.add(student_role)

                print(f"✅ Создан пользователь-студент: {student_username}")

            except Exception as e:
                print(f"❌ Ошибка при создании студента {student_username}: {e}")

    # Создание учителей
    for i in range(1, 6):
        teacher_username = f'teacher{i}'
        if not User.objects.filter(username=teacher_username).exists():
            try:
                teacher_user = User.objects.create_user(
                    username=teacher_username,
                    password='password',
                    email=f'teacher{i}@example.com',
                    first_name=f'Учитель{i}',
                    last_name=f'Фамилия{i}'
                )

                # Добавляем роль учителя (автоматически создастся запись Teacher)
                teacher_role = Role.objects.get(name='учитель')
                teacher_user.role.add(teacher_role)

                print(f"✅ Создан пользователь-учитель: {teacher_username}")

            except Exception as e:
                print(f"❌ Ошибка при создании учителя {teacher_username}: {e}")

    # Создание родителей
    for i in range(1, 6):
        parent_username = f'parent{i}'
        if not User.objects.filter(username=parent_username).exists():
            try:
                parent_user = User.objects.create_user(
                    username=parent_username,
                    password='password',
                    email=f'parent{i}@example.com',
                    first_name=f'Родитель{i}',
                    last_name=f'Фамилия{i}'
                )

                # Добавляем роль родителя (автоматически создастся запись Parent)
                parent_role = Role.objects.get(name='родители')
                parent_user.role.add(parent_role)

                print(f"✅ Создан пользователь-родитель: {parent_username}")

            except Exception as e:
                print(f"❌ Ошибка при создании родителя {parent_username}: {e}")

def create_sample_lessons():
    """Создает примерные уроки без дублирования"""
    print("📚 Создание примерных уроков...")

    groups = Group.objects.all()
    subjects = Subject.objects.all()

    if not groups.exists() or not subjects.exists():
        print("❌ Нет групп или предметов для создания уроков")
        return

    # Создаем уроки на следующие 14 дней
    base_date = timezone.now().date()

    lessons_created = 0
    max_lessons = 50  # Ограничиваем количество

    for group in groups:
        students = Student.objects.filter(group=group)
        if not students.exists():
            continue

        for subject in subjects[:3]:  # Только первые 3 предмета для каждой группы
            if lessons_created >= max_lessons:
                break

            # Создаем 2-3 урока для каждой пары группа-предмет
            lessons_count = random.randint(2, 3)

            for lesson_num in range(lessons_count):
                if lessons_created >= max_lessons:
                    break

                # Случайная дата в течение следующих 14 дней
                days_offset = random.randint(1, 14)
                lesson_date = base_date + datetime.timedelta(days=days_offset)

                try:
                    # Используем get_or_create для предотвращения дублирования
                    lesson, created = Lesson.objects.get_or_create(
                        subject=subject,
                        date=lesson_date,
                        group=group
                    )

                    if created:
                        lessons_created += 1
                        # Создаем записи посещаемости для всех студентов группы
                        for student in students:
                            attended = random.choice([True, False, True])  # 66% шанс присутствия
                            grade = None

                            if attended and random.choice([True, False]):  # 50% шанс получить оценку
                                grade = random.randint(2, 5)

                            Attendance.objects.get_or_create(
                                lesson=lesson,
                                student=student,
                                defaults={
                                    'attended': attended,
                                    'grade': grade
                                }
                            )

                        print(f"✅ Создан урок: {subject.name} - {lesson_date} - {group.name}")

                except IntegrityError:
                    # Урок уже существует, пропускаем
                    pass
                except Exception as e:
                    print(f"❌ Ошибка при создании урока: {e}")

        if lessons_created >= max_lessons:
            break

    print(f"📚 Создано {lessons_created} уроков")
