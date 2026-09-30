from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

MESES = (
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
)

_PADRAO_ISO = re.compile(r"^(\d{4})-(\d{1,2})$")
_PADRAO_BR = re.compile(r"^(\d{1,2})/(\d{4})$")
_PADRAO_BARRA = re.compile(r"^(\d{4})/(\d{1,2})$")


@dataclass(frozen=True, order=True)
class Competencia:
    year: int
    month: int

    def __post_init__(self) -> None:
        if not 1 <= self.month <= 12:
            raise ValueError(f"mês inválido: {self.month}")
        if not 1900 <= self.year <= 2200:
            raise ValueError(f"ano fora do intervalo suportado: {self.year}")

    @classmethod
    def parse(cls, value: object) -> "Competencia":
        if isinstance(value, Competencia):
            return value
        if isinstance(value, datetime):
            return cls(value.year, value.month)
        if isinstance(value, date):
            return cls(value.year, value.month)
        if isinstance(value, (tuple, list)) and len(value) == 2:
            return cls(int(value[0]), int(value[1]))
        if isinstance(value, int):
            texto = str(value)
            if len(texto) == 6:
                return cls(int(texto[:4]), int(texto[4:6]))
            raise TypeError(f"inteiro não identificado como competência: {value}")
        if isinstance(value, str):
            texto = value.strip()
            if m := _PADRAO_ISO.match(texto):
                return cls(int(m.group(1)), int(m.group(2)))
            if m := _PADRAO_BR.match(texto):
                return cls(int(m.group(2)), int(m.group(1)))
            if m := _PADRAO_BARRA.match(texto):
                return cls(int(m.group(1)), int(m.group(2)))
            raise ValueError(f"competência inválida: {value!r}")
        raise TypeError(f"tipo não suportado: {type(value).__name__}")

    @property
    def key(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    @property
    def label(self) -> str:
        return f"{self.month:02d}/{self.year}"

    @property
    def long_label(self) -> str:
        return f"{MESES[self.month - 1]}/{self.year}"

    @property
    def inicio(self) -> date:
        return date(self.year, self.month, 1)

    @property
    def proxima(self) -> "Competencia":
        if self.month == 12:
            return Competencia(self.year + 1, 1)
        return Competencia(self.year, self.month + 1)

    @property
    def anterior(self) -> "Competencia":
        if self.month == 1:
            return Competencia(self.year - 1, 12)
        return Competencia(self.year, self.month - 1)

    def __str__(self) -> str:
        return self.label
