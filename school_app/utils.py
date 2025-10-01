def get_user_role(user):
    if hasattr(user, 'student'):
        return 'студенты'
    elif hasattr(user, 'teacher'):
        return 'учитель'
    elif hasattr(user, 'parent'):
        return 'родители'
    elif user.is_superuser:
        return 'администратор'
    return 'USER'