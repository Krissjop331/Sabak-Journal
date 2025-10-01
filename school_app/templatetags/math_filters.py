# Создайте файл school_app/templatetags/math_filters.py

from django import template

register = template.Library()

@register.filter
def subtract(value, arg):
    """Вычитание: {{ value|subtract:arg }}"""
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def multiply(value, arg):
    """Умножение: {{ value|multiply:arg }}"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def divide(value, arg):
    """Деление: {{ value|divide:arg }}"""
    try:
        if float(arg) == 0:
            return 0
        return float(value) / float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def percentage(value, total):
    """Процент: {{ value|percentage:total }}"""
    try:
        if int(total) == 0:
            return 0
        return round((int(value) / int(total)) * 100, 1)
    except (ValueError, TypeError):
        return 0
