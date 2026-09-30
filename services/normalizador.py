"""Normalización de datos sucios (montos, cantidades, fechas) con convención es-CO.

Funciones puras, sin base de datos. Cada una devuelve (valor, calidad) para que el importador pueda
mostrar advertencias en vez de corregir en silencio. Calidad: OK | VACIO | GRATIS | INVALIDO | AMBIGUA.
"""
import re
import unicodedata
from datetime import datetime, date, timedelta


def _sin_acentos(s):
    return ''.join(c for c in unicodedata.normalize('NFD', str(s)) if unicodedata.category(c) != 'Mn')


_GRATIS = {'gratis', 'obsequio', 'cortesia', 'regalo', 'free', 'sin costo'}
_MINUS = '-−–—'


def _resolver_numero(tok):
    """Convierte '85.000,50' / '45000,00' / '18,500' / '61612.5' / ',500' en float."""
    tiene_punto, tiene_coma = '.' in tok, ',' in tok
    if tiene_punto and tiene_coma:
        dec = '.' if tok.rfind('.') > tok.rfind(',') else ','
        mil = ',' if dec == '.' else '.'
        t = tok.replace(mil, '').replace(dec, '.')
    elif tiene_punto or tiene_coma:
        sep = '.' if tiene_punto else ','
        partes = tok.split(sep)
        if len(partes) > 2:                      # 1.234.567 -> separador de miles
            t = ''.join(partes)
        else:
            ent, dec = partes
            if len(dec) == 3 and 1 <= len(ent) <= 3 and not ent.startswith('0'):
                t = ent + dec                    # 45.000 / 18,500 -> miles
            else:
                t = (ent or '0') + '.' + dec     # 45000,00 / 61612.5 / ,500 -> decimal
    else:
        t = tok
    return float(t)


def analizar_monto(v):
    """Devuelve (valor_float, calidad). Negativos se conservan (devoluciones / notas crédito)."""
    if v is None:
        return 0.0, 'VACIO'
    if isinstance(v, bool):
        return 0.0, 'INVALIDO'
    if isinstance(v, (int, float)):
        if v != v:  # NaN
            return 0.0, 'VACIO'
        return float(v), 'OK'
    s = str(v).strip()
    if not s:
        return 0.0, 'VACIO'
    if _sin_acentos(s).lower() in _GRATIS:
        return 0.0, 'GRATIS'
    m = re.search(r'[\d.,]*\d[\d.,]*', s)
    if not m:
        return 0.0, 'INVALIDO'
    previo = s[:m.start()]
    negativo = any(c in previo for c in _MINUS) or (s.startswith('(') and s.endswith(')')) or s.endswith(tuple(_MINUS))
    try:
        val = _resolver_numero(m.group(0))
    except ValueError:
        return 0.0, 'INVALIDO'
    return (-val if negativo else val), 'OK'


def parse_money(v):
    return analizar_monto(v)[0]


_NUM_PALABRAS = {
    'cero': 0, 'un': 1, 'uno': 1, 'una': 1, 'dos': 2, 'tres': 3, 'cuatro': 4, 'cinco': 5, 'seis': 6,
    'siete': 7, 'ocho': 8, 'nueve': 9, 'diez': 10, 'once': 11, 'doce': 12, 'trece': 13, 'catorce': 14,
    'quince': 15, 'veinte': 20, 'media': 0.5, 'medio': 0.5,
}


def analizar_cantidad(v):
    """(valor, calidad). Acepta números, '1.0', ' 2 ' y números escritos en español ('dos')."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return 0.0, 'VACIO'
    val, cal = analizar_monto(v)
    if cal in ('OK',):
        return val, 'OK'
    palabra = _sin_acentos(str(v)).strip().lower()
    if palabra in _NUM_PALABRAS:
        return float(_NUM_PALABRAS[palabra]), 'OK'
    return 0.0, 'INVALIDO'


_MESES = {
    'enero': 1, 'ene': 1, 'febrero': 2, 'feb': 2, 'marzo': 3, 'mar': 3, 'abril': 4, 'abr': 4, 'mayo': 5, 'may': 5,
    'junio': 6, 'jun': 6, 'julio': 7, 'jul': 7, 'agosto': 8, 'ago': 8, 'septiembre': 9, 'setiembre': 9,
    'sep': 9, 'sept': 9, 'set': 9, 'octubre': 10, 'oct': 10, 'noviembre': 11, 'nov': 11, 'diciembre': 12, 'dic': 12,
}


def _anio(a):
    a = int(a)
    return a if a >= 100 else (2000 + a if a <= 69 else 1900 + a)


def _armar(y, mo, d, hh=None, mi=None, ss=None):
    try:
        if hh is None:
            return date(y, mo, d).isoformat()
        return datetime(y, mo, d, int(hh), int(mi or 0), int(ss or 0)).strftime('%Y-%m-%d %H:%M:%S')
    except ValueError:
        return None


def analizar_fecha(v):
    """(texto_iso, calidad). 'YYYY-MM-DD' o 'YYYY-MM-DD HH:MM:SS' si trae hora.
    Formato local es-CO: día primero. Si ambos ≤ 12 y distintos la calidad es AMBIGUA (se asumió DD/MM)."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return '', 'VACIA'
    if isinstance(v, datetime):
        return (v.strftime('%Y-%m-%d') if (v.hour, v.minute, v.second) == (0, 0, 0) else v.strftime('%Y-%m-%d %H:%M:%S')), 'OK'
    if isinstance(v, date):
        return v.isoformat(), 'OK'
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if 20000 <= v <= 80000:                      # serial de Excel
            return (datetime(1899, 12, 30) + timedelta(days=float(v))).strftime('%Y-%m-%d'), 'OK'
        return '', 'INVALIDA'
    s = ' '.join(str(v).split())
    hora = r'(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?'
    m = re.match(r'^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})' + hora + r'$', s)
    if m:
        y, mo, d, hh, mi, ss = m.groups()
        r = _armar(int(y), int(mo), int(d), hh, mi, ss)
        return (r, 'OK') if r else ('', 'INVALIDA')
    m = re.match(r'^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})' + hora + r'$', s)
    if m:
        a, b, y, hh, mi, ss = m.groups()
        a, b, y = int(a), int(b), _anio(y)
        d, mo, cal = a, b, 'OK'
        if b > 12 >= a:                              # 03/25/2026 -> MM/DD
            d, mo = b, a
        elif a <= 12 and b <= 12 and a != b:
            cal = 'AMBIGUA'
        r = _armar(y, mo, d, hh, mi, ss)
        return (r, cal) if r else ('', 'INVALIDA')
    m = re.match(r'^(\d{1,2})[\s\-/]*(?:de\s+)?([A-Za-zñÑáéíóúÁÉÍÓÚ]+)\.?[\s\-/]*(?:(?:de|del)\s+)?(\d{2,4})' + hora + r'$', s, re.I)
    if m:
        d, mes, y, hh, mi, ss = m.groups()
        mo = _MESES.get(_sin_acentos(mes).lower())
        if mo:
            r = _armar(_anio(y), mo, int(d), hh, mi, ss)
            return (r, 'OK') if r else ('', 'INVALIDA')
    return '', 'INVALIDA'


def fecha_a_iso(v, por_defecto=''):
    iso, cal = analizar_fecha(v)
    return iso if iso else por_defecto
