from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Get an item from a dictionary using a key.
    Usage in template: {{ my_dict|get_item:key_variable }}
    """
    return dictionary.get(key, [])

@register.filter
def filter_by(items, field_value):
    """
    Filter a list of items by a field:value pair.
    Usage: {{ my_list|filter_by:'field_name' }}
    """
    field_name, value = field_value.split(':') if ':' in field_value else (field_value, None)
    
    if value is None:
        # Return a dictionary of items indexed by the specified field
        return {getattr(item, field_name, item.get(field_name, '')): item for item in items}
    
    # Filter items where the specified field equals the value
    return [item for item in items if getattr(item, field_name, item.get(field_name, '')) == value]

@register.filter
def get(items, key):
    """
    Get an item from a dictionary or object by key.
    Usage: {{ my_dict|get:key_var }}
    """
    if hasattr(items, 'get'):
        return items.get(key)
    return items[key] if key in items else None 