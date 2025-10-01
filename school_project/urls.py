from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from school_app import views

urlpatterns = [
    # Основные страницы
    path('', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Работа с студентами
    path('edit_attendance/<int:student_id>/', views.edit_attendance, name='edit_attendance'),
    path('edit_student/<int:student_id>/', views.edit_attendance, name='edit_student_marks'),

    # Уроки
    path('add-lesson/', views.add_lesson, name='add_lesson'),
    # НОВЫЙ URL: создание урока из конкретного расписания
    path('create-lesson-from-schedule/<int:schedule_id>/', views.create_lesson_from_schedule, name='create_lesson_from_schedule'),

    # Расписание
    path('schedule/', views.schedule_view, name='schedule'),
    path('schedule/add/', views.add_schedule, name='add_schedule'),
    path('delete-schedule/<int:schedule_id>/', views.delete_schedule, name='delete_schedule'),

    # Служебные
    path('update_user_image/', views.update_user_image, name='update_user_image'),
    path('create-missing-attendance/', views.create_missing_attendance_records, name='create_missing_attendance'),
    path('admin/', admin.site.urls),
]

# Настройка для отображения медиа файлов в режиме разработки
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
