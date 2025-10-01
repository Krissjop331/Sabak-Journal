from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Получает элемент словаря по ключу"""
    return dictionary.get(key)

@register.filter
def default_if_none(value, default):
    """Возвращает default если value равно None"""
    return default if value is None else value
