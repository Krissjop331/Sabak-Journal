# school_app/templatetags/custom_filters.py
from django import template

register = template.Library()

@register.filter
def get_item(list, index):
    try:
        return list[index]
    except IndexError:
        return None