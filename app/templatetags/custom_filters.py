from django import template
import datetime
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.safestring import mark_safe
import json

register = template.Library()

@register.filter
def month_name(date_str):
    date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d')
    return date_obj.strftime('%B')

@register.filter(name='startswith')
def startswith(value, arg):
    return value.startswith(arg)

def serialize_obj(obj):
    if hasattr(obj, 'to_dict'):
        return obj.to_dict()
    if hasattr(obj, '_meta'):
        data = {}
        for field in obj._meta.get_fields():
            if field.is_relation:
                if field.many_to_many or field.one_to_many:
                    data[field.name] = [serialize_obj(related_obj) for related_obj in getattr(obj, field.name).all()]
                elif field.many_to_one or field.one_to_one:
                    related_obj = getattr(obj, field.name)
                    data[field.name] = serialize_obj(related_obj) if related_obj else None
            else:
                data[field.name] = getattr(obj, field.name)
        return data
    return obj

@register.filter
def to_json(obj):
    return mark_safe(json.dumps(serialize_obj(obj), cls=DjangoJSONEncoder))