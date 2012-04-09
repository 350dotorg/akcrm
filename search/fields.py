from search.models import SearchField

def get_fields():
    _fields = {}
    for field in SearchField.objects.all():
        if field.category not in _fields:
            _fields[field.category] = []
        _fields[field.category].append((field.name, field.display_name))
    return _fields

