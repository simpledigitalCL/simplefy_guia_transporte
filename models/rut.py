"""RUT chileno, patentes y nombres propios: validación y forma canónica, sin librerías externas."""
import re


def _limpiar_rut(rut):
    return re.sub(r"[^0-9K]", "", (rut or "").upper())


def rut_es_valido(rut):
    """True si el dígito verificador calza (módulo 11). Acepta puntos, guion y prefijo «CL»."""
    limpio = _limpiar_rut(rut)
    if len(limpio) < 2:
        return False
    cuerpo, dv = limpio[:-1], limpio[-1]
    if not cuerpo.isdigit() or int(cuerpo) == 0:
        return False
    suma, factor = 0, 2
    for digito in reversed(cuerpo):
        suma += int(digito) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - suma % 11
    esperado = {11: "0", 10: "K"}.get(resto, str(resto))
    return dv == esperado


def rut_canonico(rut):
    """«12.345.678-k» → «12345678-K», como guarda los RUT la localización chilena de Odoo."""
    limpio = _limpiar_rut(rut)
    if len(limpio) < 2 or not limpio[:-1].isdigit():
        return False
    return "%s-%s" % (int(limpio[:-1]), limpio[-1])


def rut_con_puntos(rut):
    """«12345678-5» → «12.345.678-5», para mostrar e imprimir."""
    canonico = rut_canonico(rut)
    if not canonico:
        return rut or ""
    cuerpo, dv = canonico.split("-")
    return "%s-%s" % ("{:,}".format(int(cuerpo)).replace(",", "."), dv)


def normalizar_patente(patente):
    """«cyzx-40 » → «CYZX40»: sin espacios, puntos ni guiones, en mayúsculas."""
    return re.sub(r"[\s.\-]", "", patente or "").upper() or False


# Palabras que van en minúscula dentro de un nombre (salvo al comienzo).
_PARTICULAS = {"de", "del", "la", "las", "los", "y", "e", "da", "das", "do", "dos", "van", "von", "di"}
# Tipos de sociedad, con su escritura habitual.
_SOCIEDADES = {
    "spa": "SpA", "ltda": "Ltda.", "ltda.": "Ltda.", "limitada": "Limitada",
    "sa": "S.A.", "s.a": "S.A.", "s.a.": "S.A.", "eirl": "EIRL", "e.i.r.l.": "E.I.R.L.",
    "cia": "Cía.", "cia.": "Cía.", "cía": "Cía.", "cía.": "Cía.",
}


def _capitalizar(palabra):
    # «o'higgins» → «O'Higgins», «pérez-cotapos» → «Pérez-Cotapos».
    return re.sub(r"[^\W\d_]+", lambda m: m.group(0).capitalize(), palabra)


def nombre_propio(texto, empresa=False):
    """«JUAN carlos  DE la fuente» → «Juan Carlos de la Fuente». Con `empresa`, también ordena el
    tipo de sociedad: «TRANSPORTES SUR SPA» → «Transportes Sur SpA»."""
    palabras = (texto or "").split()
    resultado = []
    for i, palabra in enumerate(palabras):
        baja = palabra.lower()
        if empresa and baja in _SOCIEDADES:
            resultado.append(_SOCIEDADES[baja])
        elif i and baja in _PARTICULAS:
            resultado.append(baja)
        else:
            resultado.append(_capitalizar(baja))
    return " ".join(resultado)
