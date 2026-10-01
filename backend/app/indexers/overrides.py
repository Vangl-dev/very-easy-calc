from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.competencia import Competencia
from app.core.money import round_brl, round_factor, to_decimal
from app.indexers.base import KIND_CORRECAO, KIND_JUROS, IndexerError, obter
from app.models.entities import IndexerOverride

__all__ = [
    "OverrideAtivo",
    "cadastrar_override",
    "carregar_overrides_da_sessao",
    "cobertura_efetiva",
    "definir_overrides_ativos",
    "limpar_overrides_ativos",
    "listar_overrides",
    "override_ativo",
    "overrides_utilizados",
]


@dataclass(frozen=True)
class OverrideAtivo:
    key: str
    competencia: Competencia
    valor: Decimal
    fonte: str
    observacao: str = ""
    id: int | None = None

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "competencia": self.competencia.key,
            "competencia_rotulo": self.competencia.label,
            "valor": str(self.valor),
            "fonte": self.fonte,
            "observacao": self.observacao,
        }


_ATIVOS: dict[str, dict[Competencia, OverrideAtivo]] = {}
_USADOS: set[tuple[str, str]] = set()


def definir_overrides_ativos(overrides: list[OverrideAtivo]) -> None:
    _ATIVOS.clear()
    _USADOS.clear()
    for item in overrides:
        _ATIVOS.setdefault(item.key, {})[item.competencia] = item


def limpar_overrides_ativos() -> None:
    _ATIVOS.clear()
    _USADOS.clear()


def override_ativo(key: str, competencia: Competencia) -> OverrideAtivo | None:
    item = _ATIVOS.get(key, {}).get(competencia)
    if item is not None:
        _USADOS.add((key, competencia.key))
    return item


def overrides_utilizados() -> list[OverrideAtivo]:
    encontrados: list[OverrideAtivo] = []
    for key, comp_key in sorted(_USADOS):
        comp = Competencia.parse(comp_key)
        item = _ATIVOS.get(key, {}).get(comp)
        if item is not None:
            encontrados.append(item)
    return encontrados


def _para_ativo(linha: IndexerOverride) -> OverrideAtivo:
    return OverrideAtivo(
        key=linha.key,
        competencia=Competencia.parse(linha.competencia),
        valor=to_decimal(linha.valor),
        fonte=linha.fonte,
        observacao=linha.observacao or "",
        id=linha.id,
    )


def listar_overrides(session: Session, key: str | None = None) -> list[OverrideAtivo]:
    stmt = select(IndexerOverride).order_by(IndexerOverride.key, IndexerOverride.competencia)
    if key is not None:
        stmt = stmt.where(IndexerOverride.key == key)
    return [_para_ativo(linha) for linha in session.scalars(stmt).all()]


def carregar_overrides_da_sessao(session: Session) -> list[OverrideAtivo]:
    return listar_overrides(session)


def cadastrar_override(
    session: Session,
    *,
    key: str,
    competencia: object,
    valor: object,
    fonte: str,
    observacao: str = "",
) -> OverrideAtivo:
    """Cadastra valor manual. Nunca substitui valor oficial da mesma competência."""
    try:
        indexador = obter(key)
    except IndexerError as exc:
        raise ValueError(str(exc)) from exc

    comp = Competencia.parse(competencia)
    if indexador.contem(comp):
        raise ValueError(
            f"já existe valor oficial para {comp.label} em '{key}' "
            f"(cobertura {indexador.cobertura.inicio.label} a "
            f"{indexador.cobertura.fim.label}); cadastro manual não substitui histórico oficial"
        )

    valor_bruto = to_decimal(valor)
    if indexador.metadata.kind in (KIND_CORRECAO, KIND_JUROS):
        valor_dec = round_factor(valor_bruto, 6)
        if valor_dec < 0:
            raise ValueError("o valor do cadastro manual não pode ser negativo")
    else:
        valor_dec = round_brl(valor_bruto)
        if valor_dec <= 0:
            raise ValueError("o valor do cadastro manual deve ser maior que zero")

    fonte_limpa = (fonte or "").strip()
    if not fonte_limpa:
        raise ValueError("fonte/observação é obrigatória no cadastro manual")

    existente = session.scalar(
        select(IndexerOverride).where(
            IndexerOverride.key == key,
            IndexerOverride.competencia == comp.key,
        )
    )
    if existente is not None:
        raise ValueError(
            f"já existe cadastro manual para {key} em {comp.label}; "
            "histórico manual preservado (sem substituição silenciosa)"
        )

    linha = IndexerOverride(
        key=key,
        competencia=comp.key,
        valor=str(valor_dec),
        fonte=fonte_limpa,
        observacao=(observacao or "").strip(),
        created_at=datetime.now(timezone.utc),
    )
    session.add(linha)
    session.flush()
    return _para_ativo(linha)


def cobertura_efetiva(session: Session, key: str) -> dict:
    try:
        indexador = obter(key)
    except IndexerError as exc:
        raise ValueError(str(exc)) from exc

    oficial = {
        "inicio": indexador.cobertura.inicio.key,
        "fim": indexador.cobertura.fim.key,
        "inicio_rotulo": indexador.cobertura.inicio.label,
        "fim_rotulo": indexador.cobertura.fim.label,
        "total": indexador.cobertura.total,
        "version": indexador.metadata.version,
        "name": indexador.metadata.name,
        "kind": indexador.metadata.kind,
        "source": indexador.metadata.source,
    }
    manuais = listar_overrides(session, key)
    fim_efetivo = indexador.cobertura.fim
    inicio_efetivo = indexador.cobertura.inicio
    for item in manuais:
        if item.competencia > fim_efetivo:
            fim_efetivo = item.competencia
        if item.competencia < inicio_efetivo:
            inicio_efetivo = item.competencia

    return {
        "key": key,
        "oficial": oficial,
        "manual": [item.as_dict() for item in manuais],
        "cobertura_efetiva": {
            "inicio": inicio_efetivo.key,
            "fim": fim_efetivo.key,
            "inicio_rotulo": inicio_efetivo.label,
            "fim_rotulo": fim_efetivo.label,
            "total": (
                (fim_efetivo.year - inicio_efetivo.year) * 12
                + (fim_efetivo.month - inicio_efetivo.month)
                + 1
            ),
            "inclui_manual": bool(manuais),
        },
        "nota": (
            "Cobertura efetiva considera cadastros manuais que apenas preenchem "
            "fora da série oficial; valores oficiais não são substituídos."
        ),
    }
