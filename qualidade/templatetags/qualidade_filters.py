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