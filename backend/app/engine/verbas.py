from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.core.money import round_brl, to_decimal

TIPO_VALOR = "valor"
TIPO_PERCENTUAL = "percentual"
TIPOS_VERBA = (TIPO_VALOR, TIPO_PERCENTUAL)


@dataclass(frozen=True)
class EntradaVerba:
    """Verba do payload já com id interno e tipo normalizado."""

    id: str
    nome: str
    tipo: str
    data_base: str
    descricao: str
    valor: str | None
    base_verba_id: str | None
    percentual: str | None
    indice: int
    entra_no_total: bool | None = None


@dataclass(frozen=True)
class VerbaResolvida:
    id: str
    nome: str
    tipo: str
    data_base: str
    descricao: str
    principal: Decimal
    base_verba_id: str | None
    percentual: Decimal | None
    valor_entrada: str | None
    indice: int
    entra_no_total: bool = True
    """Composição no total da execução, já resolvida (explícita ou padrão)."""
    referencia: bool = False
    """Usada como base por outra verba — informativo, não decide o total."""


def _falha(mensagem: str) -> ValueError:
    return ValueError(mensagem)


def preparar_verbas(verbas: list) -> list[EntradaVerba]:
    """Normaliza ids e tipos das verbas do payload."""
    preparadas: list[EntradaVerba] = []
    ids_usados: set[str] = set()

    for indice, item in enumerate(verbas, start=1):
        nome = str(item.nome or "").strip() or f"Verba {indice}"
        tipo = (getattr(item, "tipo", None) or TIPO_VALOR).strip().lower()
        if tipo not in TIPOS_VERBA:
            raise _falha(
                f"verba '{nome}': tipo inválido {tipo!r} "
                f"(esperado 'valor' ou 'percentual')"
            )

        id_informado = str(getattr(item, "id", None) or "").strip()
        verba_id = id_informado or f"verba-{indice}"
        if verba_id in ids_usados:
            raise _falha(f"id de verba duplicado: '{verba_id}'")
        ids_usados.add(verba_id)

        base_verba_id = str(getattr(item, "base_verba_id", None) or "").strip() or None
        percentual = str(getattr(item, "percentual", None) or "").strip() or None
        valor = str(getattr(item, "valor", None) or "").strip() or None
        data_base = str(getattr(item, "data_base", None) or "").strip()
        if not data_base:
            raise _falha(f"verba '{nome}' ({verba_id}): data_base é obrigatória")

        entra_no_total = getattr(item, "entra_no_total", None)
        if entra_no_total is not None and not isinstance(entra_no_total, bool):
            raise _falha(
                f"verba '{nome}' ({verba_id}): entra_no_total deve ser verdadeiro "
                f"ou falso (recebido {entra_no_total!r})"
            )

        preparadas.append(
            EntradaVerba(
                id=verba_id,
                nome=nome,
                tipo=tipo,
                data_base=data_base,
                descricao=str(getattr(item, "descricao", None) or ""),
                valor=valor,
                base_verba_id=base_verba_id,
                percentual=percentual,
                indice=indice,
                entra_no_total=entra_no_total,
            )
        )

    return preparadas


def _validar_dependencias(preparadas: list[EntradaVerba]) -> dict[str, tuple[str, Decimal] | None]:
    """Valida regras de verbas derivadas e devolve dependências (id → base, pct)."""
    mapa = {v.id: v for v in preparadas}
    dependencias: dict[str, tuple[str, Decimal] | None] = {}

    for verba in preparadas:
        if verba.tipo == TIPO_PERCENTUAL:
            if not verba.base_verba_id:
                raise _falha(
                    f"verba '{verba.nome}' ({verba.id}): tipo percentual exige base_verba_id"
                )
            base_id = verba.base_verba_id
            if base_id not in mapa:
                raise _falha(
                    f"verba '{verba.nome}' ({verba.id}): base_verba_id '{base_id}' não existe"
                )
            if base_id == verba.id:
                raise _falha(
                    f"verba '{verba.nome}' ({verba.id}): referência circular — "
                    f"a verba não pode ter ela mesma como base"
                )
            if not verba.percentual:
                raise _falha(
                    f"verba '{verba.nome}' ({verba.id}): tipo percentual exige percentual"
                )
            try:
                percentual = to_decimal(verba.percentual)
            except (ValueError, TypeError) as exc:
                raise _falha(
                    f"verba '{verba.nome}' ({verba.id}): percentual inválido: "
                    f"{verba.percentual!r}"
                ) from exc
            if not percentual.is_finite() or percentual <= 0:
                raise _falha(
                    f"verba '{verba.nome}' ({verba.id}): percentual deve ser maior que zero "
                    f"(use fração, ex.: 0.12 para 12%); recebido {verba.percentual!r}"
                )
            if percentual > 1:
                raise _falha(
                    f"verba '{verba.nome}' ({verba.id}): percentual deve ser fração entre 0 e 1 "
                    f"(12% = '0.12'); recebido {verba.percentual!r}"
                )
            dependencias[verba.id] = (base_id, percentual)
        else:
            if not verba.valor:
                raise _falha(f"verba '{verba.nome}' ({verba.id}): tipo valor exige valor")
            try:
                principal = to_decimal(verba.valor)
            except (ValueError, TypeError) as exc:
                raise _falha(
                    f"verba '{verba.nome}' ({verba.id}): valor inválido: {verba.valor!r}"
                ) from exc
            if not principal.is_finite():
                raise _falha(
                    f"verba '{verba.nome}' ({verba.id}): valor inválido: {verba.valor!r}"
                )
            dependencias[verba.id] = None

    _detectar_ciclos(preparadas, dependencias, mapa)
    return dependencias


def _detectar_ciclos(
    preparadas: list[EntradaVerba],
    dependencias: dict[str, tuple[str, Decimal] | None],
    mapa: dict[str, EntradaVerba],
) -> None:
    BRANCO, CINZA, PRETO = 0, 1, 2
    cor: dict[str, int] = {v.id: BRANCO for v in preparadas}

    def visitar(verba_id: str, caminho: list[str]) -> None:
        cor[verba_id] = CINZA
        caminho.append(verba_id)
        dep = dependencias.get(verba_id)
        if dep is not None:
            base_id = dep[0]
            estado = cor.get(base_id, BRANCO)
            if estado == CINZA:
                inicio = caminho.index(base_id) if base_id in caminho else 0
                ciclo = caminho[inicio:] + [base_id]
                nomes = " → ".join(
                    f"{mapa[c].nome} ({c})" if c in mapa else c for c in ciclo
                )
                raise _falha(
                    f"referência circular entre verbas: {nomes}"
                )
            if estado == BRANCO:
                visitar(base_id, caminho)
        caminho.pop()
        cor[verba_id] = PRETO

    for verba in preparadas:
        if cor[verba.id] == BRANCO:
            visitar(verba.id, [])


def _composicao_no_total(verba: EntradaVerba, referenciada: bool) -> bool:
    """Decisão de composição do total: explícita prevalece; ausente, padrão."""
    if verba.entra_no_total is not None:
        return verba.entra_no_total
    return not referenciada


def resolver_verbas(verbas: list) -> list[VerbaResolvida]:
    """Resolve dependências e calcula o principal de cada verba.

    - tipo valor: principal = valor informado
    - tipo percentual: principal = principal_da_base × percentual (fração)
    A verba derivada não herda datas de correção/juros da base.

    Composição no total: ``entra_no_total`` é a fonte única da decisão.
    Quando ausente (payload antigo / cálculo salvo), vale o padrão histórico —
    a verba usada como base por outra fica fora do total — apenas para não
    alterar resultados já validados. O campo explícito sempre prevalece.
    """
    preparadas = preparar_verbas(verbas)
    dependencias = _validar_dependencias(preparadas)
    mapa = {v.id: v for v in preparadas}
    # informativo: verba usada como base de outra; não decide a soma sozinho
    referenciadas = {dep[0] for dep in dependencias.values() if dep is not None}

    principais: dict[str, Decimal] = {}

    def resolver(verba_id: str, pilha: set[str]) -> Decimal:
        if verba_id in principais:
            return principais[verba_id]
        if verba_id in pilha:
            raise _falha(f"referência circular entre verbas ao resolver '{verba_id}'")
        verba = mapa[verba_id]
        dep = dependencias[verba_id]
        if dep is None:
            principal = round_brl(to_decimal(verba.valor))
        else:
            base_id, percentual = dep
            pilha.add(verba_id)
            base_principal = resolver(base_id, pilha)
            pilha.discard(verba_id)
            principal = round_brl(base_principal * percentual)
        principais[verba_id] = principal
        return principal

    resolvidas: list[VerbaResolvida] = []
    for verba in preparadas:
        principal = resolver(verba.id, set())
        dep = dependencias[verba.id]
        referenciada = verba.id in referenciadas
        resolvidas.append(
            VerbaResolvida(
                id=verba.id,
                nome=verba.nome,
                tipo=verba.tipo,
                data_base=verba.data_base,
                descricao=verba.descricao,
                principal=principal,
                base_verba_id=verba.base_verba_id if dep else None,
                percentual=dep[1] if dep else None,
                valor_entrada=verba.valor,
                indice=verba.indice,
                entra_no_total=_composicao_no_total(verba, referenciada),
                referencia=referenciada,
            )
        )
    return resolvidas
