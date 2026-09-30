from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

CENTAVOS = Decimal("0.01")
ZERO = Decimal("0")
FACTOR_QUANTUM = Decimal("0.000001")


def to_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise TypeError("bool não é um valor monetário válido")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, str):
        return parse_brl(value)
    raise TypeError(f"tipo não suportado: {type(value).__name__}")


def parse_brl(text: str) -> Decimal:
    raw = text.strip().replace("R$", "").replace("\u00a0", "").strip()
    if not raw:
        raise ValueError("valor vazio")
    negativo = raw.startswith("(") and raw.endswith(")") or raw.startswith("-")
    raw = raw.strip("()").lstrip("-").strip()
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        partes = raw.split(",")
        if len(partes) > 2 or (len(partes) == 2 and len(partes[1]) != 3):
            raw = raw.replace(",", ".")
        else:
            raw = raw.replace(",", "")
    try:
        resultado = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(f"valor monetário inválido: {text!r}") from exc
    return -resultado if negativo else resultado


def round_brl(value: object) -> Decimal:
    return to_decimal(value).quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def round_factor(value: object, places: int = 6) -> Decimal:
    quantum = Decimal(1).scaleb(-places)
    return to_decimal(value).quantize(quantum, rounding=ROUND_HALF_UP)


def brl(value: object) -> str:
    numero = round_brl(value)
    sinal = "-" if numero < 0 else ""
    inteiro, centavos = f"{abs(numero):.2f}".split(".")
    grupos = []
    while len(inteiro) > 3:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    grupos.insert(0, inteiro)
    return f"{sinal}R$ {'.'.join(grupos)},{centavos}"
