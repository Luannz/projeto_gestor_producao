from django import template
register = template.Library()

@register.filter(name='lookup')
def lookup(dictionary, key):
    """Obtém um item de um dicionário"""
    if dictionary is None:
        return None
    return dictionary.get(key)

@register.filter(name='get_registro_total')
def get_registro_total(registro):
    """Obtém o total de um registro"""
    if registro is None:
        return 0
    try:
        return registro.total()
    except:
        return 0

@register.filter
def sum_values(value):
    """Soma os valores de um dicionário ou lista."""
    if isinstance(value, dict):
        return sum(value.values())
    elif isinstance(value, (list, tuple)):
        return sum(value)
    return 0

@register.filter
def map_attr(value, attr):
    """Retorna lista com o valor de um atributo ou chave em cada item"""
    try:
        return [v.get(attr) if isinstance(v, dict) else getattr(v, attr, None) for v in value]
    except Exception:
        return []


