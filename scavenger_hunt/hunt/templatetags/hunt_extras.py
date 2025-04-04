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
        result = {}
        for item in items:
            try:
                # Try to get the attribute directly (for model instances)
                key_value = getattr(item, field_name)
            except (AttributeError, TypeError):
                try:
                    # Try dictionary access for dict-like objects
                    key_value = item[field_name] if field_name in item else ''
                except (TypeError, KeyError):
                    # If all fails, use empty string as key
                    key_value = ''
            result[key_value] = item
        return result
    
    # Filter items where the specified field equals the value
    filtered_items = []
    for item in items:
        try:
            # Try to get the attribute directly (for model instances)
            item_value = getattr(item, field_name)
            if item_value == value:
                filtered_items.append(item)
        except (AttributeError, TypeError):
            try:
                # Try dictionary access for dict-like objects
                if field_name in item and item[field_name] == value:
                    filtered_items.append(item)
            except (TypeError, KeyError):
                pass
    return filtered_items

@register.filter
def get(items, key):
    """
    Get an item from a dictionary or object by key.
    Usage: {{ my_dict|get:key_var }}
    """
    if hasattr(items, 'get'):
        return items.get(key)
    return items[key] if key in items else None 