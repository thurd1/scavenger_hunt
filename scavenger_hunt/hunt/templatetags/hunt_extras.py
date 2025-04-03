from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Get an item from a dictionary using a key.
    Usage in template: {{ my_dict|get_item:key_variable }}
    """
    return dictionary.get(key, []) 

# Add an alias for get_item as 'get'
@register.filter
def get(dictionary, key):
    """
    Alias for get_item. Gets an item from a dictionary using a key.
    Usage in template: {{ my_dict|get:key_variable }}
    """
    return get_item(dictionary, key)

@register.filter
def filter_by(items, field_name):
    """
    Filter a list of items by a field name to create a dictionary
    where the keys are the values of the specified field.
    
    Usage in template: {{ my_list|filter_by:'field_name'|get:value }}
    """
    result = {}
    for item in items:
        # Get the value of the field for this item
        value = getattr(item, field_name, None)
        if value is not None:
            result[value] = item
    return result 