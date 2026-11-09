"""RUT chileno y patentes: validación y forma canónica, sin depender de librerías externas."""
import re


def rut_es_valido(rut):
    """True si el dígito verificador calza (módulo 11). Acepta puntos, guion y prefijo «CL»."""
    limpio = re.sub(r"[^0-9K]", "", (rut or "").upper())
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


def normalizar_patente(patente):
    """«cyzx-40 » → «CYZX40»: sin espacios, puntos ni guiones, en mayúsculas."""
    return re.sub(r"[\s.\-]", "", patente or "").upper() or False
