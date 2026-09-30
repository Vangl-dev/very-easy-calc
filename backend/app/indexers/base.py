from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Callable, Iterable, Mapping

from app.core.competencia import Competencia
from app.core.money import to_decimal

KIND_CORRECAO = "correcao"
KIND_JUROS = "juros"
KIND_SALARIO = "salario"
KINDS = (KIND_CORRECAO, KIND_JUROS, KIND_SALARIO)


class IndexerError(Exception):
    pass


class SeriesIntegrityError(IndexerError):
    pass


class CoverageError(IndexerError):
    def __init__(self, nome: str, solicitado: Competencia, cobertura: "Cobertura") -> None:
        self.nome = nome
        self.solicitado = solicitado
        self.cobertura = cobertura
        super().__init__(
            f"A base '{nome}' não cobre a competência {solicitado.label}. "
            f"Cobertura disponível: {cobertura.inicio.label} a {cobertura.fim.label}."
        )


@dataclass(frozen=True)
class Cobertura:
    inicio: Competencia
    fim: Competencia

    @property
    def total(self) -> int:
        return ((self.fim.year - self.inicio.year) * 12) + (self.fim.month - self.inicio.month) + 1

    def contem(self, competencia: Competencia) -> bool:
        return self.inicio <= competencia <= self.fim


@dataclass(frozen=True)
class IndexerMetadata:
    key: str
    name: str
    kind: str
    source: str
    source_url: str
    version: str
    updated_at: str
    cobertura: Cobertura
    total_records: int
    note: str = ""

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"kind inválido: {self.kind!r} (esperado um de {KINDS})")

    def as_dict(self) -> dict:
        dados = asdict(self)
        dados["cobertura"] = {
            "inicio": self.cobertura.inicio.label,
            "fim": self.cobertura.fim.label,
            "total": self.cobertura.total,
        }
        return dados


def validar_serie(
    series: Mapping[Competencia, Decimal], nome: str, *, permitir_zero: bool = False
) -> Cobertura:
    if not series:
        raise SeriesIntegrityError(f"série vazia para '{nome}'")
    ordenadas = sorted(series)
    inicio, fim = ordenadas[0], ordenadas[-1]
    esperado = inicio
    vistos: set[Competencia] = set()
    for competencia in ordenadas:
        if competencia in vistos:
            raise SeriesIntegrityError(f"competência duplicada em '{nome}': {competencia.label}")
        vistos.add(competencia)
        if competencia != esperado:
            raise SeriesIntegrityError(
                f"descontinuidade em '{nome}': esperado {esperado.label}, encontrado {competencia.label}"
            )
        esperado = competencia.proxima
        valor = series[competencia]
        if not isinstance(valor, Decimal):
            raise SeriesIntegrityError(f"valor não decimal em '{nome}' na competência {competencia.label}")
        if valor < 0 or (valor == 0 and not permitir_zero):
            raise SeriesIntegrityError(
                f"valor inválido em '{nome}' na competência {competencia.label}: {valor}"
            )
    return Cobertura(inicio=inicio, fim=fim)


class MonthlyIndexer(ABC):
    def __init__(self, metadata: IndexerMetadata, series: Mapping[Competencia, Decimal]) -> None:
        self._metadata = metadata
        self._series = dict(sorted(series.items()))
        self._arquivo_dados: Path | None = None
        cobertura = validar_serie(
            self._series,
            metadata.name,
            permitir_zero=metadata.kind == KIND_JUROS,
        )
        if cobertura != metadata.cobertura:
            raise SeriesIntegrityError(
                f"cobertura declarada ({metadata.cobertura.inicio.label} a "
                f"{metadata.cobertura.fim.label}) difere da série real "
                f"({cobertura.inicio.label} a {cobertura.fim.label}) em '{metadata.name}'"
            )
        if len(self._series) != metadata.total_records:
            raise SeriesIntegrityError(
                f"total_records declarado ({metadata.total_records}) difere da série "
                f"({len(self._series)}) em '{metadata.name}'"
            )

    @property
    def metadata(self) -> IndexerMetadata:
        return self._metadata

    @property
    def cobertura(self) -> Cobertura:
        return self._metadata.cobertura

    @property
    def series(self) -> Mapping[Competencia, Decimal]:
        return self._series

    def contem(self, competencia: Competencia) -> bool:
        return Competencia.parse(competencia) in self._series

    def valor(self, competencia: Competencia) -> Decimal:
        comp = Competencia.parse(competencia)
        try:
            return self._series[comp]
        except KeyError as exc:
            raise CoverageError(self._metadata.name, comp, self._metadata.cobertura) from exc

    @property
    def arquivo_dados(self) -> Path | None:
        return self._arquivo_dados

    @abstractmethod
    def unidade(self) -> str:
        raise NotImplementedError


def arquivo_hash(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def carregar_json(caminho: Path) -> dict:
    with caminho.open("r", encoding="utf-8") as handle:
        dados = json.load(handle)
    if not isinstance(dados, dict):
        raise IndexerError(f"JSON inválido em {caminho}")
    return dados


_FABRICAS: dict[str, Callable[[], MonthlyIndexer]] = {}


def registrar(key: str, fabrica: Callable[[], MonthlyIndexer]) -> None:
    if key in _FABRICAS:
        raise IndexerError(f"indexador já registrado: {key}")
    _FABRICAS[key] = fabrica


def obter(key: str) -> MonthlyIndexer:
    try:
        fabrica = _FABRICAS[key]
    except KeyError as exc:
        raise IndexerError(f"indexador desconhecido: {key}") from exc
    return fabrica()


def chaves() -> list[str]:
    return sorted(_FABRICAS)


def listar_metadata() -> list[IndexerMetadata]:
    return [obter(key).metadata for key in chaves()]


def metadados_de_arquivo(dados: dict, key: str, nome: str, kind: str) -> IndexerMetadata:
    meta = dados.get("metadata")
    if not isinstance(meta, dict):
        raise IndexerError(f"metadata ausente para '{key}'")
    fatores = dados.get("factors")
    if not isinstance(fatores, list) or not fatores:
        raise IndexerError(f"factors ausente para '{key}'")
    inicio = Competencia(fatores[0]["year"], fatores[0]["month"])
    ultimo = fatores[-1]
    fim = Competencia(ultimo["year"], ultimo["month"])
    return IndexerMetadata(
        key=key,
        name=nome,
        kind=kind,
        source=str(meta.get("source", "")),
        source_url=str(meta.get("sourceUrl", "")),
        version=str(meta.get("version", "")),
        updated_at=str(meta.get("updatedAt", "")),
        cobertura=Cobertura(inicio=inicio, fim=fim),
        total_records=len(fatores),
        note=str(meta.get("note", "")),
    )


def serie_de_fatores(fatores: Iterable[Mapping[str, object]]) -> dict[Competencia, Decimal]:
    serie: dict[Competencia, Decimal] = {}
    for registro in fatores:
        comp = Competencia(int(registro["year"]), int(registro["month"]))
        if comp in serie:
            raise SeriesIntegrityError(f"competência duplicada na origem: {comp.label}")
        serie[comp] = to_decimal(registro["factor"])
    return serie
