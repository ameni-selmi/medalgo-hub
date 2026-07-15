from django import template

register = template.Library()


@register.filter
def dictget(d, key):
    if isinstance(d, dict):
        return d.get(key)
    return None


@register.filter
def multiply(value, arg):
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0
