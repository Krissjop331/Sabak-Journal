from django import forms
from django.contrib.auth import get_user_model
from .models import Student, Teacher, Parent, Group, Subject, Role, Attendance
from django.core.exceptions import ValidationError

User = get_user_model()

class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(attrs={"placeholder": "Введите пароль"})
    )
    password_confirm = forms.CharField(
        label="Подтверждение пароля",
        widget=forms.PasswordInput(attrs={"placeholder": "Повторите пароль"})
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'role']
        widgets = {
            'username': forms.TextInput(attrs={"placeholder": "Введите логин"}),
            'email': forms.EmailInput(attrs={"placeholder": "Введите email"}),
            'first_name': forms.TextInput(attrs={"placeholder": "Введите имя"}),
            'last_name': forms.TextInput(attrs={"placeholder": "Введите фамилию"}),
            'role': forms.CheckboxSelectMultiple(),
        }

    def clean_password_confirm(self):
        password = self.cleaned_data.get('password')
        password_confirm = self.cleaned_data.get('password_confirm')

        if password and password_confirm and password != password_confirm:
            raise ValidationError("Пароли не совпадают")

        return password_confirm

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError("Пользователь с таким логином уже существует")
        return username

class StudentRegistrationForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ['group']
        widgets = {
            'group': forms.Select(attrs={"class": "form-control"})
        }

class TeacherRegistrationForm(forms.ModelForm):
    class Meta:
        model = Teacher
        fields = ['main_group', 'additional_groups', 'subjects']
        widgets = {
            'main_group': forms.Select(attrs={"class": "form-control"}),
            'additional_groups': forms.CheckboxSelectMultiple(),
            'subjects': forms.CheckboxSelectMultiple(),
        }

class ParentRegistrationForm(forms.ModelForm):
    class Meta:
        model = Parent
        fields = ['parent_type', 'children']
        widgets = {
            'parent_type': forms.Select(attrs={"class": "form-control"}),
            'children': forms.CheckboxSelectMultiple(),
        }

class LoginForm(forms.Form):
    username = forms.CharField(
        label="Имя пользователя",
        widget=forms.TextInput(attrs={"placeholder": "Введите имя пользователя", "class": "form-control"})
    )
    password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(attrs={"placeholder": "Введите пароль", "class": "form-control"})
    )

class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance # type: ignore
        fields = ['attended', 'grade']
        widgets = {
            'attended': forms.CheckboxInput(attrs={"class": "form-check-input"}),
            'grade': forms.NumberInput(attrs={"class": "form-control", "min": "2", "max": "5"}),
        }
