
from django import template

register = template.Library()

@register.filter
def joined_by(list, string):
    return string.join(str(i) for i in list)
