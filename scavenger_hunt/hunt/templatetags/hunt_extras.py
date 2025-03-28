from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Gets an item from a dictionary by key.
    Usage: {{ dictionary|get_item:key }}
    """
    return dictionary.get(key, []) 