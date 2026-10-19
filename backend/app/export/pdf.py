from __future__ import annotations

import io
from decimal import Decimal
from typing import Callable, Iterable

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as canvas_pdf
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.engine.memoria import REGRA_TOTAL_DA_EXECUCAO
from app.export.comum import (
    brl_memoria,
    criterio_encargo_efetivo,
    dec_memoria,
    ids_verbas_fora_do_total,
    pct_memoria,
    pagamentos_efetivos,
    regra_parcela_txt,
    verbas_fora_do_total,
)

CABECALHO_APP = "Very Easy Calc"
MARGEM = 12 * mm
# O Cível privilegia leitura e cópia em editores de texto; Alimentos mantém
# paisagem pelas tabelas de competências. A escolha é interna ao módulo.
PAGINA_CIVEL = A4
PAGINA_ALIMENTOS = landscape(A4)
LARGURA = PAGINA_CIVEL[0] - 2 * MARGEM

VINHO = colors.HexColor("#6f263d")
VINHO_ESCURO = colors.HexColor("#5a1e31")
VINHO_CLARO = colors.HexColor("#f7f0f1")
TINTA = colors.HexColor("#252525")
TINTA_FRACA = colors.HexColor("#5c574e")
LINHA = colors.HexColor("#ddd9d0")
LINHA_CLARA = colors.HexColor("#efece5")
ZEBRA = colors.HexColor("#faf8f5")


def _estilos() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    normal = base["Normal"]
    return {
        "marca": ParagraphStyle(
            "marca",
            parent=normal,
            fontName="Times-Bold",
            fontSize=18,
            leading=21,
            alignment=TA_CENTER,
            textColor=VINHO,
        ),
        "titulo_doc": ParagraphStyle(
            "titulo_doc",
            parent=normal,
            fontName="Times-Bold",
            fontSize=12.5,
            leading=15,
            alignment=TA_CENTER,
            textColor=TINTA,
            spaceAfter=2 * mm,
        ),
        "meta": ParagraphStyle(
            "meta",
            parent=normal,
            fontSize=9.5,
            leading=13,
            alignment=TA_CENTER,
            textColor=TINTA_FRACA,
            spaceAfter=2 * mm,
        ),
        "secao": ParagraphStyle(
            "secao",
            parent=normal,
            fontName="Times-Bold",
            fontSize=12,
            leading=15,
            textColor=VINHO,
            spaceBefore=5 * mm,
            spaceAfter=0.5 * mm,
        ),
        "sub": ParagraphStyle(
            "sub",
            parent=normal,
            fontName="Times-Bold",
            fontSize=10.5,
            leading=13,
            textColor=TINTA,
            spaceBefore=3 * mm,
            spaceAfter=0.5 * mm,
        ),
        "corpo": ParagraphStyle(
            "corpo",
            parent=normal,
            fontSize=9.5,
            leading=13.5,
            textColor=TINTA,
        ),
        "corpo_fraco": ParagraphStyle(
            "corpo_fraco",
            parent=normal,
            fontSize=9.5,
            leading=13.5,
            textColor=TINTA_FRACA,
        ),
        "rotulo": ParagraphStyle(
            "rotulo",
            parent=normal,
            fontSize=9.5,
            leading=13,
            textColor=TINTA_FRACA,
        ),
        "valor": ParagraphStyle(
            "valor",
            parent=normal,
            fontSize=9.5,
            leading=13,
            textColor=TINTA,
        ),
        "valor_forte": ParagraphStyle(
            "valor_forte",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=13,
            textColor=TINTA,
        ),
        "valor_dir": ParagraphStyle(
            "valor_dir",
            parent=normal,
            fontSize=9.5,
            leading=13,
            alignment=TA_RIGHT,
            textColor=TINTA,
        ),
        "valor_dir_forte": ParagraphStyle(
            "valor_dir_forte",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=13,
            alignment=TA_RIGHT,
            textColor=VINHO,
        ),
        "geral": ParagraphStyle(
            "geral",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            alignment=TA_RIGHT,
            textColor=colors.white,
        ),
        "rotulo_grande": ParagraphStyle(
            "rotulo_grande",
            parent=normal,
            fontSize=10,
            leading=14,
            textColor=TINTA_FRACA,
        ),
        "numero": ParagraphStyle(
            "numero",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=13.5,
            leading=16,
            alignment=TA_RIGHT,
            textColor=TINTA,
        ),
        "numero_branco": ParagraphStyle(
            "numero_branco",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=13.5,
            leading=16,
            alignment=TA_RIGHT,
            textColor=colors.white,
        ),
        "celula_med": ParagraphStyle(
            "celula_med",
            parent=normal,
            fontSize=9.5,
            leading=12.5,
            alignment=TA_LEFT,
            textColor=TINTA,
        ),
        "celula_med_dir": ParagraphStyle(
            "celula_med_dir",
            parent=normal,
            fontSize=9.5,
            leading=12.5,
            alignment=TA_RIGHT,
            textColor=TINTA,
        ),
        "celula_med_cen": ParagraphStyle(
            "celula_med_cen",
            parent=normal,
            fontSize=9.5,
            leading=12.5,
            alignment=TA_CENTER,
            textColor=TINTA,
        ),
        "cab_med": ParagraphStyle(
            "cab_med",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12.5,
            alignment=TA_LEFT,
            textColor=colors.white,
        ),
        "cab_med_dir": ParagraphStyle(
            "cab_med_dir",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12.5,
            alignment=TA_RIGHT,
            textColor=colors.white,
        ),
        "cab_med_cen": ParagraphStyle(
            "cab_med_cen",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12.5,
            alignment=TA_CENTER,
            textColor=colors.white,
        ),
        "celula": ParagraphStyle(
            "celula",
            parent=normal,
            fontSize=9,
            leading=11.5,
            alignment=TA_LEFT,
            textColor=TINTA,
        ),
        "celula_dir": ParagraphStyle(
            "celula_dir",
            parent=normal,
            fontSize=9,
            leading=11.5,
            alignment=TA_RIGHT,
            textColor=TINTA,
        ),
        "celula_cen": ParagraphStyle(
            "celula_cen",
            parent=normal,
            fontSize=9,
            leading=11.5,
            alignment=TA_CENTER,
            textColor=TINTA,
        ),
        "cab": ParagraphStyle(
            "cab",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11.5,
            alignment=TA_LEFT,
            textColor=colors.white,
        ),
        "cab_dir": ParagraphStyle(
            "cab_dir",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11.5,
            alignment=TA_RIGHT,
            textColor=colors.white,
        ),
        "cab_cen": ParagraphStyle(
            "cab_cen",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11.5,
            alignment=TA_CENTER,
            textColor=colors.white,
        ),
        "verba_cab": ParagraphStyle(
            "verba_cab",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            alignment=TA_LEFT,
            textColor=colors.white,
        ),
        "verba_cab_esq": ParagraphStyle(
            "verba_cab_esq",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            alignment=TA_LEFT,
            textColor=colors.white,
        ),
        "verba_resumo": ParagraphStyle(
            "verba_resumo",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            alignment=TA_LEFT,
            textColor=VINHO,
        ),
        "nota": ParagraphStyle(
            "nota",
            parent=normal,
            fontSize=8.5,
            leading=11.5,
            textColor=TINTA_FRACA,
        ),
        "rodape": ParagraphStyle(
            "rodape",
            parent=normal,
            fontSize=8,
            leading=10,
            textColor=TINTA_FRACA,
        ),
    }


_TAMANHOS_ALIMENTOS: dict[str, tuple[float, float]] = {
    "marca": (15.5, 18),
    "titulo_doc": (11, 13),
    "secao": (11, 13.5),
    "sub": (9.5, 12),
    "corpo": (8.5, 11.5),
    "corpo_fraco": (8.5, 11.5),
    "rotulo": (8.5, 11),
    "valor": (8.5, 11),
    "valor_forte": (8.5, 11),
    "valor_dir": (8.5, 11),
    "valor_dir_forte": (8.5, 11),
    "geral": (9, 11.5),
    "rotulo_grande": (8.5, 12),
    "numero": (12, 14.5),
    "numero_branco": (12, 14.5),
    "celula_med": (8.25, 10.5),
    "celula_med_dir": (8.25, 10.5),
    "celula_med_cen": (8.25, 10.5),
    "cab_med": (8.25, 10.5),
    "cab_med_dir": (8.25, 10.5),
    "cab_med_cen": (8.25, 10.5),
    "celula": (8, 10.5),
    "celula_dir": (8, 10.5),
    "celula_cen": (8, 10.5),
    "cab": (8, 10.5),
    "cab_dir": (8, 10.5),
    "cab_cen": (8, 10.5),
    "verba_cab": (9, 11.5),
    "verba_cab_esq": (8, 10.5),
    "verba_resumo": (9, 11.5),
    "nota": (7.5, 10),
    "rodape": (7.5, 9.5),
}


def _estilos_alimentos() -> dict[str, ParagraphStyle]:
    """Mesma identidade visual, em escala reduzida para o A4 paisagem."""
    estilos = _estilos()
    for nome, (corpo, entrelinha) in _TAMANHOS_ALIMENTOS.items():
        base = estilos[nome]
        estilos[nome] = ParagraphStyle(
            f"{nome}_alimentos",
            parent=base,
            fontSize=corpo,
            leading=entrelinha,
        )
    estilos["marca"].spaceAfter = 0
    estilos["titulo_doc"].spaceAfter = 1.5 * mm
    # Compactação moderada para evitar uma página final com apenas uma linha
    # após tabelas extensas de competências.
    estilos["secao"].spaceBefore = 2.5 * mm
    estilos["secao"].spaceAfter = 0.5 * mm
    estilos["sub"].spaceBefore = 1.5 * mm
    estilos["faixa_rotulo"] = ParagraphStyle(
        "faixa_rotulo",
        parent=estilos["rotulo"],
        fontSize=8,
        leading=10,
        alignment=TA_CENTER,
        textColor=TINTA_FRACA,
    )
    estilos["faixa_rotulo_destaque"] = ParagraphStyle(
        "faixa_rotulo_destaque",
        parent=estilos["faixa_rotulo"],
        textColor=colors.white,
    )
    estilos["faixa_valor"] = ParagraphStyle(
        "faixa_valor",
        parent=estilos["valor"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14.5,
        alignment=TA_CENTER,
        textColor=TINTA,
    )
    estilos["faixa_valor_destaque"] = ParagraphStyle(
        "faixa_valor_destaque",
        parent=estilos["faixa_valor"],
        fontSize=13,
        leading=15.5,
        textColor=colors.white,
    )
    return estilos


def _p(texto: object, estilo: ParagraphStyle) -> Paragraph:
    valor = "" if texto is None else str(texto)
    valor = valor.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(valor, estilo)


def _data_br(valor: object) -> str:
    """Converte data/competência da memória para formato brasileiro (sem recálculo)."""
    if valor is None:
        return "—"
    texto = str(valor).strip()
    if not texto:
        return "—"
    if "T" in texto:
        texto = texto.split("T", 1)[0]
    partes = texto.split("-")
    if len(partes) == 3 and all(p.isdigit() for p in partes):
        return f"{partes[2]}/{partes[1]}/{partes[0]}"
    if len(partes) == 2 and all(p.isdigit() for p in partes):
        return f"{partes[1]}/{partes[0]}"
    return texto


def _periodo(inicio: object, fim: object) -> str:
    ini = _data_br(inicio)
    fim_txt = _data_br(fim)
    if ini == "—" and fim_txt == "—":
        return "—"
    return f"{ini} a {fim_txt}"


def _num_br(valor: object) -> str:
    """Troca o separador decimal, preservando as casas produzidas pelo motor."""
    if valor is None:
        return "—"
    texto = str(valor).strip()
    if not texto:
        return "—"
    return texto.replace(".", ",")


def _secao(titulo: str, estilos: dict[str, ParagraphStyle]) -> list:
    return [
        _p(titulo, estilos["secao"]),
        HRFlowable(
            width="100%",
            thickness=0.9,
            color=VINHO,
            spaceBefore=0.5 * mm,
            spaceAfter=1.5 * mm,
        ),
    ]


def _subsecao(titulo: str, estilos: dict[str, ParagraphStyle]) -> list:
    return [
        _p(titulo, estilos["sub"]),
        HRFlowable(
            width="100%",
            thickness=0.4,
            color=LINHA,
            spaceBefore=0.3 * mm,
            spaceAfter=1.2 * mm,
        ),
    ]


def _tabela_pares(
    pares: Iterable[tuple[str, str]],
    estilos: dict[str, ParagraphStyle],
    *,
    largura_rotulo: float = 42 * mm,
    largura_total: float | None = None,
) -> Table:
    total = largura_total if largura_total is not None else LARGURA
    dados = [[_p(k, estilos["rotulo"]), _p(v, estilos["valor"])] for k, v in pares]
    tabela = Table(dados, colWidths=[largura_rotulo, total - largura_rotulo], hAlign="LEFT")
    tabela.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, LINHA_CLARA),
            ]
        )
    )
    return tabela


def _estilo_tabela(linhas_cabecalho: int, padding: int = 3) -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, linhas_cabecalho - 1), VINHO),
            ("TEXTCOLOR", (0, 0), (-1, linhas_cabecalho - 1), colors.white),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), padding),
            ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
            ("ROWBACKGROUNDS", (0, linhas_cabecalho), (-1, -1), [colors.white, ZEBRA]),
            ("LINEBELOW", (0, linhas_cabecalho - 1), (-1, linhas_cabecalho - 1), 0.8, VINHO_ESCURO),
            ("LINEBELOW", (0, linhas_cabecalho), (-1, -1), 0.25, LINHA_CLARA),
            ("BOX", (0, 0), (-1, -1), 0.5, LINHA),
        ]
    )


def _nome_indexador(chave: object, bases: list[dict]) -> str:
    if not chave:
        return "—"
    for base in bases:
        if base.get("key") == chave:
            return str(base.get("nome") or chave)
    return str(chave).replace("_", " ")


def _base_por_chave(chave: object, bases: list[dict]) -> dict | None:
    for base in bases:
        if base.get("key") == chave:
            return base
    return None


def _modalidade_txt(modalidade: object) -> str:
    mapa = {
        "taxa_legal": "Taxa Legal",
        "fixa": "Taxa fixa",
        "nao_aplicar": "Não aplicada",
    }
    return mapa.get(str(modalidade or ""), str(modalidade or "—"))


def _base_incidencia_txt(base: object) -> str:
    mapa = {
        "corrigido": "valor corrigido",
        "principal": "principal histórico",
        "com_juros": "principal + correção + juros",
    }
    return mapa.get(str(base or "corrigido"), str(base or "corrigido"))


def _encargo_txt(config: dict | None) -> str:
    if not config or not config.get("aplicar"):
        return "não aplicada"
    sufixo = " — configurado por verba" if config.get("por_verba") else ""
    if config.get("variado_por_verba"):
        return f"aplicada{sufixo}; critérios distintos por verba"
    if config.get("percentual") is not None:
        return (
            f"{pct_memoria(config.get('percentual'))} sobre "
            f"{_base_incidencia_txt(config.get('base'))}{sufixo}"
        )
    if config.get("valor_fixo") is not None:
        return f"{brl_memoria(config.get('valor_fixo'))} ({_base_incidencia_txt(config.get('base'))}){sufixo}"
    return f"aplicada{sufixo}"


def _parcelas_da_verba(verba: dict, todas: list[dict]) -> list[dict]:
    numeros = {item.get("numero") for item in (verba.get("parcelas") or [])}
    if numeros:
        selecionadas = [p for p in todas if p.get("numero") in numeros]
        if selecionadas:
            return selecionadas
    verba_id = verba.get("id")
    return [
        p for p in todas if (p.get("verba") or {}).get("id") == verba_id
    ]


def _soma(parcelas: list[dict], obtido: Callable[[dict], object]) -> Decimal:
    total = Decimal("0")
    for parcela in parcelas:
        valor = dec_memoria(obtido(parcela))
        if valor is not None:
            total += valor
    return total


def _intervalo(valores: Iterable[object]) -> tuple[object | None, object | None]:
    validos = sorted({str(v) for v in valores if v})
    if not validos:
        return None, None
    return validos[0], validos[-1]


class _CanvasNumerado(canvas_pdf.Canvas):
    """Guarda cada página para desenhar o rodapé com a contagem total."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._paginas: list[dict] = []

    def showPage(self):
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            self._desenhar_rodape(total)
            super().showPage()
        super().save()

    def _desenhar_rodape(self, total: int):
        largura, altura = self._pagesize
        codigo = getattr(self, "_codigo_memoria", "")
        tamanho = getattr(self, "_rodape_fonte", 8)
        self.saveState()
        self.setStrokeColor(LINHA)
        self.setLineWidth(0.5)
        self.line(MARGEM, MARGEM + 3 * mm, largura - MARGEM, MARGEM + 3 * mm)
        self.setFont("Helvetica", tamanho)
        self.setFillColor(TINTA_FRACA)
        esquerda = f"{CABECALHO_APP} • Memória de cálculo"
        if codigo:
            esquerda += f" • {codigo}"
        self.drawString(MARGEM, MARGEM - 1.5 * mm, esquerda)
        self.drawRightString(
            largura - MARGEM, MARGEM - 1.5 * mm, f"Página {self._pageNumber} de {total}"
        )
        self.restoreState()


def _tabela_resumo(
    verbas: list[dict],
    parcelas: list[dict],
    resumo: dict,
    estilos: dict[str, ParagraphStyle],
) -> Table:
    # Em retrato, a agregação por verba em sete colunas quebra valores
    # monetários. O resumo é consolidado; a discriminação integral permanece
    # nos blocos por verba e na memória detalhada.
    return _tabela_resumo_sem_verbas(resumo, estilos)


def _estilo_resumo(linhas_cabecalho: int, geral: int) -> TableStyle:
    estilo = TableStyle(
        [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
            ("ROWBACKGROUNDS", (0, linhas_cabecalho), (-1, geral - 1), [colors.white, ZEBRA]),
            ("LINEBELOW", (0, linhas_cabecalho - 1), (-1, linhas_cabecalho - 1), 0.8, VINHO_ESCURO),
            ("LINEBELOW", (0, linhas_cabecalho), (-1, geral - 1), 0.25, LINHA_CLARA),
            ("BACKGROUND", (0, geral), (-1, geral), VINHO),
            ("LINEABOVE", (0, geral), (-1, geral), 0.6, VINHO_ESCURO),
            ("BOX", (0, 0), (-1, geral), 0.5, LINHA),
        ]
    )
    return estilo


def _grupos_de_verbas(verbas: list[dict], parcelas: list[dict]) -> list[dict]:
    """Soma das parcelas por verba, sem recalcular — apenas agrega a memória."""
    fora_do_total = ids_verbas_fora_do_total(verbas)
    grupos: list[dict] = []
    for indice, verba in enumerate(verbas, start=1):
        do_grupo = _parcelas_da_verba(verba, parcelas)
        grupos.append(
            {
                "id": verba.get("id"),
                "nome": (verba.get("nome") or f"Verba {indice}"),
                "fora_do_total": verba.get("id") in fora_do_total,
                "principal": _soma(do_grupo, lambda p: p.get("principal")),
                "correcao": _soma(do_grupo, lambda p: (p.get("correcao") or {}).get("correcao")),
                "juros": _soma(do_grupo, lambda p: (p.get("juros") or {}).get("juros")),
                "multa": _soma(do_grupo, lambda p: (p.get("multa") or {}).get("valor")),
                "honorarios": _soma(do_grupo, lambda p: (p.get("honorarios") or {}).get("valor")),
                "pagamentos": _soma(do_grupo, lambda p: p.get("total_pago")),
                "saldo": _soma(do_grupo, lambda p: p.get("saldo")),
                "total": _soma(do_grupo, lambda p: p.get("total")),
            }
        )
    return grupos


def _nota_verbas_fora_do_total(
    verbas: list[dict], estilos: dict[str, ParagraphStyle]
) -> list:
    """Nota auditável: quais verbas ficaram fora do total e por quê."""
    fora = verbas_fora_do_total(verbas)
    if not fora:
        return []
    nomes = ", ".join(str(v.get("nome") or v.get("id") or "—") for v in fora)
    verbo = "não compõe" if len(fora) == 1 else "não compõem"
    return [
        Spacer(1, 1 * mm),
        _p(
            f"Nota: {nomes} — {verbo} o total da execução. "
            f"{REGRA_TOTAL_DA_EXECUCAO}",
            estilos["nota"],
        ),
    ]


def _tabela_resumo_por_verba(
    verbas: list[dict],
    parcelas: list[dict],
    resumo: dict,
    estilos: dict[str, ParagraphStyle],
) -> Table:
    """Uma linha por verba: a página 1 já recebe a Configuração das verbas."""
    grupos: list[dict] = []
    for grupo in _grupos_de_verbas(verbas, parcelas):
        item = dict(grupo)
        nome = grupo["nome"].upper()
        if grupo.get("fora_do_total"):
            nome += " — FORA DO TOTAL"
        item["nome"] = nome
        grupos.append(item)

    colunas: list[tuple[str, float, bool]] = [
        # Cada coluna numérica preserva largura suficiente para R$ 999.999,99.
        # Valores nunca devem quebrar em várias linhas numa memória judicial.
        ("Verba", 21.3, True),
        ("Principal", 13.0, False),
        ("Correção monetária", 14.6, False),
        ("Juros", 13.0, False),
    ]
    if any(g["multa"] != 0 for g in grupos):
        colunas.append(("Multa", 11.7, False))
    if any(g["honorarios"] != 0 for g in grupos):
        colunas.append(("Honorários", 11.7, False))
    colunas.append(("Total", 14.7, False))

    dados: list[list] = [
        [
            _p(nome, estilos["cab"] if esquerda else estilos["cab_dir"])
            for nome, _, esquerda in colunas
        ]
    ]
    for grupo in grupos:
        valores = {
            "Verba": grupo["nome"],
            "Principal": brl_memoria(grupo["principal"]),
            "Correção monetária": brl_memoria(grupo["correcao"]),
            "Juros": brl_memoria(grupo["juros"]),
            "Multa": brl_memoria(grupo["multa"]),
            "Honorários": brl_memoria(grupo["honorarios"]),
            "Total": brl_memoria(grupo["total"]),
        }
        dados.append(
            [
                _p(valores[nome], estilos["celula"] if esquerda else estilos["celula_dir"])
                for nome, _, esquerda in colunas
            ]
        )

    dados.append(
        [_p("TOTAL GERAL", estilos["verba_cab"])]
        + [_p("", estilos["verba_cab"]) for _ in colunas[1:-1]]
        + [_p(brl_memoria(resumo.get("total")), estilos["geral"])]
    )
    geral = len(dados) - 1

    larguras = [LARGURA * larg / 100.0 for _, larg, _ in colunas]
    tabela = Table(dados, colWidths=larguras, repeatRows=1, hAlign="LEFT")
    estilo = _estilo_resumo(1, geral)
    estilo.add("BACKGROUND", (0, 0), (-1, 0), VINHO)
    estilo.add("TEXTCOLOR", (0, 0), (-1, 0), colors.white)
    tabela.setStyle(estilo)
    return tabela


def _tabela_resumo_sem_verbas(
    resumo: dict,
    estilos: dict[str, ParagraphStyle],
) -> Table:
    dados: list[list] = [
        [_p("Principal", estilos["rotulo"]), _p(brl_memoria(resumo.get("principal")), estilos["valor_dir"])],
        [_p("Correção monetária", estilos["rotulo"]), _p(brl_memoria(resumo.get("correcao")), estilos["valor_dir"])],
        [_p("Juros", estilos["rotulo"]), _p(brl_memoria(resumo.get("juros")), estilos["valor_dir"])],
    ]
    if dec_memoria(resumo.get("multa")):
        dados.append([_p("Multa", estilos["rotulo"]), _p(brl_memoria(resumo.get("multa")), estilos["valor_dir"])])
    if dec_memoria(resumo.get("honorarios")):
        dados.append([_p("Honorários adicionais", estilos["rotulo"]), _p(brl_memoria(resumo.get("honorarios")), estilos["valor_dir"])])
    dados.append([_p("Pagamentos", estilos["rotulo"]), _p(brl_memoria(resumo.get("pagamentos")), estilos["valor_dir"])])
    dados.append([_p("Saldo", estilos["rotulo"]), _p(brl_memoria(resumo.get("saldo")), estilos["valor_dir"])])
    dados.append(
        [
            _p("TOTAL GERAL", estilos["geral"]),
            _p(brl_memoria(resumo.get("total")), estilos["geral"]),
        ]
    )
    geral = len(dados) - 1

    largura_rotulo = LARGURA * 0.62
    tabela = Table(
        dados,
        colWidths=[largura_rotulo, LARGURA - largura_rotulo],
        hAlign="LEFT",
    )
    estilo = TableStyle(
        [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("BACKGROUND", (0, geral), (-1, geral), VINHO),
            ("LINEABOVE", (0, geral), (-1, geral), 0.6, VINHO_ESCURO),
            ("LINEBELOW", (0, 0), (-1, geral - 1), 0.3, LINHA_CLARA),
            ("BOX", (0, 0), (-1, geral), 0.5, LINHA),
        ]
    )
    tabela.setStyle(estilo)
    return tabela


def _encargos_aplicados(parcelas: list[dict], bases: list[dict]) -> list[tuple[str, str]]:
    linhas: list[tuple[str, str]] = []
    corrigidas = [
        c for c in ((p.get("correcao") or {}) for p in parcelas) if c.get("aplicado")
    ]
    if corrigidas:
        nomes = list(
            dict.fromkeys(_nome_indexador(c.get("indexador"), bases) for c in corrigidas)
        )
        inicio, _ = _intervalo(c.get("termo_inicial") for c in corrigidas)
        _, fim = _intervalo(c.get("termo_final") for c in corrigidas)
        linhas.append(("Correção monetária", f"{' / '.join(nomes)} — {_periodo(inicio, fim)}"))

    juros_aplicados = [
        j for j in ((p.get("juros") or {}) for p in parcelas) if j.get("aplicado")
    ]
    if juros_aplicados:
        if any(j.get("indexador") == "taxa_legal" for j in juros_aplicados):
            rotulo = "Taxa Legal"
        else:
            rotulo = " / ".join(
                dict.fromkeys(_modalidade_txt(j.get("modalidade")) for j in juros_aplicados)
            )
        trechos = [t for j in juros_aplicados for t in (j.get("trechos") or [])]
        inicio, _ = _intervalo(t.get("inicio") for t in trechos)
        _, fim = _intervalo(t.get("fim") for t in trechos)
        linhas.append(("Juros", f"{rotulo} — {_periodo(inicio, fim)}"))
    return linhas


def _tabela_trechos(
    trechos: list[dict],
    *,
    com_valor: bool,
    estilos: dict[str, ParagraphStyle],
) -> Table:
    vistos: set[tuple] = set()
    dados: list[list] = []
    cabecalho = [
        _p("Período", estilos["cab_cen"]),
        _p("Dias", estilos["cab_cen"]),
        _p("Regra", estilos["cab"]),
        _p("Taxa aplicada", estilos["cab"]),
    ]
    colunas = [36 * mm, 14 * mm, 62 * mm, 66 * mm]
    if com_valor:
        cabecalho.append(_p("Valor do período", estilos["cab_dir"]))
        colunas.append(34 * mm)
    # A tabela também é usada no A4 retrato. Mantém as proporções definidas
    # acima, mas nunca ultrapassa a área útil da página.
    largura_total = sum(colunas)
    if largura_total > LARGURA:
        fator = LARGURA / largura_total
        colunas = [largura * fator for largura in colunas]
    dados.append(cabecalho)

    for trecho in trechos:
        chave = (
            trecho.get("inicio"),
            trecho.get("fim"),
            trecho.get("rotulo"),
            trecho.get("taxa_rotulo"),
            trecho.get("valor"),
        )
        if chave in vistos:
            continue
        vistos.add(chave)
        linha = [
            _p(_periodo(trecho.get("inicio"), trecho.get("fim")), estilos["celula_cen"]),
            _p(str(trecho.get("dias") or "—"), estilos["celula_cen"]),
            _p(trecho.get("rotulo") or "—", estilos["celula"]),
            _p(trecho.get("taxa_rotulo") or "—", estilos["celula"]),
        ]
        if com_valor:
            linha.append(_p(brl_memoria(trecho.get("valor")), estilos["celula_dir"]))
        dados.append(linha)

    tabela = Table(dados, colWidths=colunas, repeatRows=1, hAlign="LEFT")
    tabela.setStyle(_estilo_tabela(1))
    return tabela


def _bloco_verba(
    indice: int,
    verba: dict,
    parcelas_da: list[dict],
    bases: list[dict],
    estilos: dict[str, ParagraphStyle],
) -> list:
    nome = verba.get("nome") or f"Verba {indice}"
    historia: list = []

    linhas_verba: list[tuple[str, str]] = [
        ("Valor principal", brl_memoria(verba.get("valor")) or "—"),
        ("Data do valor", _data_br(verba.get("data_base"))),
    ]
    if verba.get("tipo") == "percentual" and verba.get("base_verba_id"):
        base_nome = next(
            (
                v.get("nome")
                for v in (verba.get("base_nomes") or [])
                if v.get("id") == verba.get("base_verba_id")
            ),
            None,
        )
        percentual = pct_memoria(verba.get("percentual")) or "—"
        linhas_verba.append(
            (
                "Origem",
                f"{percentual} sobre {base_nome or verba.get('base_verba_id')}",
            )
        )
    if verba.get("descricao"):
        linhas_verba.append(("Descrição", str(verba.get("descricao"))))
    primeiro_bloco: list = [
        _p(f"{indice}. {nome}", estilos["sub"]),
        _tabela_pares(
            linhas_verba,
            estilos,
            largura_rotulo=34 * mm,
            largura_total=150 * mm,
        ),
    ]

    correcoes = [c for c in ((p.get("correcao") or {}) for p in parcelas_da)]
    aplicadas = [c for c in correcoes if c.get("aplicado")]
    conteudo_correcao: list = []
    if aplicadas:
        nomes = list(
            dict.fromkeys(_nome_indexador(c.get("indexador"), bases) for c in aplicadas)
        )
        inicio, _ = _intervalo(c.get("termo_inicial") for c in aplicadas)
        _, fim = _intervalo(c.get("termo_final") for c in aplicadas)
        linhas = [("Índice", " / ".join(nomes)), ("Período", _periodo(inicio, fim))]
        fatores_iniciais = {str(c.get("fator_inicial")) for c in aplicadas if c.get("fator_inicial")}
        fatores_finais = {str(c.get("fator_final")) for c in aplicadas if c.get("fator_final")}
        if len(fatores_iniciais) == 1 and len(fatores_finais) == 1:
            linhas.append(("Fator inicial", _num_br(next(iter(fatores_iniciais)))))
            linhas.append(("Fator final", _num_br(next(iter(fatores_finais)))))
        razoes = {c.get("fator_exibicao") for c in aplicadas if c.get("fator_exibicao")}
        if len(razoes) == 1:
            linhas.append(("Fator aplicado", _num_br(next(iter(razoes)))))
        valor_corrigido = _soma(
            parcelas_da, lambda p: (p.get("correcao") or {}).get("valor_corrigido")
        )
        linhas.append(("Valor corrigido", brl_memoria(valor_corrigido)))
        conteudo_correcao.append(
            _tabela_pares(linhas, estilos, largura_rotulo=34 * mm, largura_total=170 * mm)
        )
    else:
        motivos = list(
            dict.fromkeys(
                str(c.get("motivo")) for c in correcoes if c.get("motivo")
            )
        )
        conteudo_correcao.append(
            _p(
                f"Não aplicada. {' '.join(motivos) if motivos else ''}".strip(),
                estilos["corpo_fraco"],
            )
        )
    historia.append(KeepTogether(primeiro_bloco))
    historia.append(
        KeepTogether(
            _subsecao("Correção monetária", estilos) + conteudo_correcao
        )
    )

    juros_de = [j for j in ((p.get("juros") or {}) for p in parcelas_da)]
    aplicados = [j for j in juros_de if j.get("aplicado")]
    if aplicados:
        linhas = []
        modalidades = list(
            dict.fromkeys(_modalidade_txt(j.get("modalidade")) for j in aplicados)
        )
        linhas.append(("Modalidade", " / ".join(modalidades)))
        base_juros = _base_por_chave("taxa_legal", bases)
        if any(j.get("indexador") == "taxa_legal" for j in aplicados) and base_juros:
            linhas.append(("Série aplicada", str(base_juros.get("nome") or "—")))
            linhas.append(("Fonte", str(base_juros.get("fonte") or "—")))
        trechos = [t for j in aplicados for t in (j.get("trechos") or [])]
        inicio, _ = _intervalo(t.get("inicio") for t in trechos)
        _, fim = _intervalo(t.get("fim") for t in trechos)
        linhas.append(("Período", _periodo(inicio, fim)))
        incidencias = list(
            dict.fromkeys(str(j.get("incidencia")) for j in aplicados if j.get("incidencia"))
        )
        if incidencias:
            linhas.append(("Base de incidência", " / ".join(incidencias)))
        historia.append(
            KeepTogether(
                _subsecao("Juros", estilos)
                + [
                    _tabela_pares(
                        linhas,
                        estilos,
                        largura_rotulo=34 * mm,
                        largura_total=170 * mm,
                    )
                ]
            )
        )
        if trechos:
            historia.append(Spacer(1, 1.5 * mm))
            historia.append(
                _tabela_trechos(
                    trechos,
                    com_valor=len(parcelas_da) == 1,
                    estilos=estilos,
                )
            )
    else:
        motivos = list(
            dict.fromkeys(str(j.get("motivo")) for j in juros_de if j.get("motivo"))
        )
        historia.append(
            KeepTogether(
                _subsecao("Juros", estilos)
                + [
                    _p(
                        f"Não aplicados. {' '.join(motivos) if motivos else ''}".strip(),
                        estilos["corpo_fraco"],
                    )
                ]
            )
        )

    return historia


def _colunas_detalhe(
    parcelas: list[dict],
    tipo: str,
) -> list[tuple[str, float, str]]:
    alimentos = tipo == "alimentos" or any(p.get("regra") for p in parcelas)
    if not alimentos:
        # A configuração da verba já registra período e índice. Na memória
        # tabular, omiti-los libera largura para valores monetários íntegros.
        colunas: list[tuple[str, float, str]] = [
            ("Nº", 8, "cen"),
            ("Vencimento", 23, "cen"),
            ("Descrição", 34, "esq"),
        ]
    else:
        colunas = [
            ("Nº", 9, "cen"),
            ("Período", 17, "cen"),
            ("Vencimento", 24, "cen"),
            ("Regra / detalhe", 40, "esq"),
        ]
    if alimentos:
        colunas.extend([("Salário mín.", 22, "dir"), ("% / regra", 18, "cen")])
    colunas.extend(
        [
            ("Principal", 25 if not alimentos else 24, "dir"),
            *(([] if not alimentos else [("Índice", 18, "dir")])),
            ("Correção", 25 if not alimentos else 24, "dir"),
            ("Juros", 25 if not alimentos else 22, "dir"),
        ]
    )
    if any((dec_memoria(p.get("total_pago")) or Decimal("0")) > 0 for p in parcelas):
        colunas.append(("Pagto.", 25 if not alimentos else 20, "dir"))
    if any((p.get("multa") or {}).get("aplicado") for p in parcelas):
        colunas.append(("Multa", 25 if not alimentos else 18, "dir"))
    if any((p.get("honorarios") or {}).get("aplicado") for p in parcelas):
        colunas.append(("Hon.", 25 if not alimentos else 18, "dir"))
    if tipo == "alimentos":
        colunas.append(("Diferença", 22, "dir"))
    colunas.extend([
        ("Total", 29 if not alimentos else 25, "dir"),
        ("Saldo", 29 if not alimentos else 25, "dir"),
    ])
    return colunas


_ACESSORES: dict[str, Callable[[dict], object]] = {
    "Nº": lambda p: p.get("numero"),
    "Período": lambda p: p.get("competencia_rotulo") or _data_br(p.get("competencia")),
    "Competência": lambda p: p.get("competencia_rotulo") or _data_br(p.get("competencia")),
    "Vencimento": lambda p: _data_br(p.get("vencimento")),
    "Regra / detalhe": lambda p: p.get("detalhe")
    or regra_parcela_txt(p)
    or p.get("descricao")
    or "—",
    "Descrição": lambda p: p.get("descricao") or "—",
    "Salário mín.": lambda p: brl_memoria(p.get("salario_minimo")),
    "% / regra": lambda p: (
        pct_memoria(p.get("percentual"))
        if p.get("percentual") is not None
        else (p.get("detalhe") or "—")
    ),
    "%": lambda p: (
        pct_memoria(p.get("percentual")) if p.get("percentual") is not None else "—"
    ),
    "Devido": lambda p: brl_memoria(p.get("principal")),
    "Pago": lambda p: brl_memoria(p.get("total_pago")),
    "Total atualizado": lambda p: brl_memoria(p.get("total")),
    "Principal": lambda p: brl_memoria(p.get("principal")),
    "Índice": lambda p: _num_br(
        (p.get("correcao") or {}).get("fator_exibicao")
        or (p.get("correcao") or {}).get("razao")
    ),
    "Correção": lambda p: brl_memoria((p.get("correcao") or {}).get("correcao")),
    "Juros": lambda p: brl_memoria((p.get("juros") or {}).get("juros")),
    "Pagto.": lambda p: brl_memoria(p.get("total_pago")),
    "Multa": lambda p: brl_memoria((p.get("multa") or {}).get("valor")),
    "Hon.": lambda p: brl_memoria((p.get("honorarios") or {}).get("valor")),
    "Diferença": lambda p: brl_memoria(p.get("diferenca")),
    "Total": lambda p: brl_memoria(p.get("total")),
    "Saldo": lambda p: brl_memoria(p.get("saldo")),
}


def _tabela_detalhe(
    titulo: str,
    parcelas: list[dict],
    colunas: list[tuple[str, float, str]],
    estilos: dict[str, ParagraphStyle],
    *,
    largura: float = LARGURA,
    corpo_medio: bool = False,
) -> Table:
    if corpo_medio:
        estilo_celula = {
            "cen": estilos["celula_med_cen"],
            "dir": estilos["celula_med_dir"],
            "esq": estilos["celula_med"],
        }
        estilo_cab = {
            "cen": estilos["cab_med_cen"],
            "dir": estilos["cab_med_dir"],
            "esq": estilos["cab_med"],
        }
    else:
        estilo_celula = {
            "cen": estilos["celula_cen"],
            "dir": estilos["celula_dir"],
            "esq": estilos["celula"],
        }
        estilo_cab = {
            "cen": estilos["cab_cen"],
            "dir": estilos["cab_dir"],
            "esq": estilos["cab"],
        }

    dados: list[list] = [[_p(titulo, estilos["verba_cab"])]]
    dados.append([_p(nome, estilo_cab[alinhamento]) for nome, _, alinhamento in colunas])
    for parcela in parcelas:
        linha = []
        for nome, _, alinhamento in colunas:
            valor = _ACESSORES[nome](parcela)
            texto = "" if valor is None else str(valor)
            if not texto.strip():
                texto = "—"
            linha.append(_p(texto, estilo_celula[alinhamento]))
        dados.append(linha)

    larguras = [larg * mm for _, larg, _ in colunas]
    total = sum(larguras)
    if total and largura:
        fator = largura / total
        larguras = [w * fator for w in larguras]

    tabela = Table(
        dados,
        colWidths=larguras,
        repeatRows=2,
        splitByRow=1,
        hAlign="LEFT",
    )
    estilo = _estilo_tabela(2, padding=1.5 if corpo_medio else 3)
    estilo.add("SPAN", (0, 0), (-1, 0))
    estilo.add("BACKGROUND", (0, 0), (-1, 0), VINHO)
    tabela.setStyle(estilo)
    return tabela


def _tabelas_detalhe_civel(
    titulo: str,
    parcelas: list[dict],
    estilos: dict[str, ParagraphStyle],
) -> list[Table]:
    """Divide a memória financeira em retrato sem reduzir valores monetários."""
    principais = [
        ("Nº", 10, "cen"),
        ("Vencimento", 28, "cen"),
        ("Descrição", 48, "esq"),
        ("Principal", 31, "dir"),
        ("Correção", 31, "dir"),
        ("Juros", 31, "dir"),
    ]
    composicao = [("Nº", 10, "cen")]
    if any((p.get("multa") or {}).get("aplicado") for p in parcelas):
        composicao.append(("Multa", 31, "dir"))
    if any((p.get("honorarios") or {}).get("aplicado") for p in parcelas):
        composicao.append(("Hon.", 31, "dir"))
    if any((dec_memoria(p.get("total_pago")) or Decimal("0")) != 0 for p in parcelas):
        composicao.append(("Pagto.", 31, "dir"))
    composicao.extend([("Total", 34, "dir"), ("Saldo", 34, "dir")])
    return [
        _tabela_detalhe(f"{titulo} — valores principais", parcelas, principais, estilos),
        _tabela_detalhe(f"{titulo} — composição e saldo", parcelas, composicao, estilos),
    ]


def _criterios_pares(
    criterios: dict,
    parcelas: list[dict],
    bases: list[dict],
) -> list[tuple[str, str]]:
    linhas: list[tuple[str, str]] = [
        ("Atualização até", _data_br(criterios.get("data_base"))),
    ]

    cfg_correcao = criterios.get("correcao") or {}
    corrigidas = [
        c for c in ((p.get("correcao") or {}) for p in parcelas) if c.get("aplicado")
    ]
    if cfg_correcao.get("aplicar"):
        correcao_txt = _nome_indexador(cfg_correcao.get("indexador"), bases)
    elif corrigidas:
        nomes = list(
            dict.fromkeys(_nome_indexador(c.get("indexador"), bases) for c in corrigidas)
        )
        correcao_txt = f"{' / '.join(nomes)} — configurada por verba"
    else:
        correcao_txt = "não aplicada"
    linhas.append(("Correção monetária", correcao_txt))

    cfg_juros = criterios.get("juros") or {}
    aplicados = [j for j in ((p.get("juros") or {}) for p in parcelas) if j.get("aplicado")]
    if cfg_juros.get("aplicar") and aplicados:
        juros_txt = _modalidade_txt(cfg_juros.get("modalidade"))
    elif aplicados:
        juros_txt = " / ".join(
            dict.fromkeys(_modalidade_txt(j.get("modalidade")) for j in aplicados)
        )
        juros_txt += " — configurado por verba"
    else:
        juros_txt = "não aplicados"
    linhas.append(("Juros", juros_txt))

    linhas.append(("Multa", _encargo_txt(
        criterio_encargo_efetivo(criterios.get("multa"), parcelas, "multa")
    )))
    linhas.append(("Honorários adicionais", _encargo_txt(
        criterio_encargo_efetivo(criterios.get("honorarios"), parcelas, "honorarios")
    )))
    linhas.append(("Pagamentos informados", str(len(pagamentos_efetivos(criterios, parcelas)))))

    alimentos = criterios.get("alimentos")
    if alimentos:
        partes = []
        for regra in alimentos.get("regras") or []:
            if regra.get("tipo") == "salario_minimo":
                partes.append(
                    f"{_data_br(regra.get('inicio'))} a {_data_br(regra.get('fim')) or '...'}: "
                    f"{pct_memoria(regra.get('percentual'))} do salário mínimo"
                )
            else:
                partes.append(
                    f"{_data_br(regra.get('inicio'))} a {_data_br(regra.get('fim')) or '...'}: "
                    f"{brl_memoria(regra.get('valor'))} (fixo)"
                )
        if partes:
            linhas.append(("Regras de alimentos", "; ".join(partes)))
        linhas.append(("Período até", _data_br(alimentos.get("ate"))))
        if alimentos.get("dia_vencimento"):
            linhas.append(("Dia de vencimento", str(alimentos.get("dia_vencimento"))))
    return linhas


def _tabela_bases(
    bases: list[dict],
    estilos: dict[str, ParagraphStyle],
    *,
    largura: float = LARGURA,
) -> Table:
    cabecalho = [
        _p("Base", estilos["cab"]),
        _p("Versão", estilos["cab_cen"]),
        _p("Cobertura", estilos["cab_cen"]),
        _p("Papel", estilos["cab"]),
        _p("Fonte", estilos["cab"]),
    ]
    dados = [cabecalho]
    for base in bases:
        dados.append(
            [
                _p(base.get("nome") or base.get("key") or "—", estilos["celula"]),
                _p(base.get("versao") or "—", estilos["celula_cen"]),
                _p(base.get("cobertura") or "—", estilos["celula_cen"]),
                _p(base.get("papel") or "—", estilos["celula"]),
                _p(base.get("fonte") or "—", estilos["celula"]),
            ]
        )
    larguras = [58 * mm, 24 * mm, 48 * mm, 50 * mm, 60 * mm]
    total = sum(larguras)
    if total and largura:
        fator = largura / total
        larguras = [w * fator for w in larguras]
    tabela = Table(dados, colWidths=larguras, repeatRows=1, hAlign="LEFT")
    tabela.setStyle(_estilo_tabela(1))
    return tabela


def _chave_comp(competencia: object) -> str:
    """MM/AAAA ou YYYY-MM em chave ordenável (apenas comparação)."""
    texto = str(competencia or "").strip()
    if "/" in texto:
        mes, ano = texto.split("/", 1)
        if ano.isdigit() and mes.isdigit():
            return f"{ano}-{mes.zfill(2)}"
        return ""
    partes = texto.split("-")
    if len(partes) == 2 and partes[0].isdigit() and partes[1].isdigit():
        return f"{partes[0]}-{partes[1].zfill(2)}"
    return ""


def _periodo_regras(alimentos: dict) -> tuple[str, str]:
    """Início e fim do período da dívida (não confundir com a data de atualização)."""
    regras = [r for r in (alimentos.get("regras") or []) if r.get("inicio")]
    if not regras:
        return "", ""
    inicio = min((str(r.get("inicio")) for r in regras), key=_chave_comp)
    fims = [str(r.get("fim")) for r in regras if r.get("fim")]
    if fims and len(fims) == len(regras):
        fim: str = max(fims, key=_chave_comp)
    else:
        fim = str(alimentos.get("ate") or (max(fims, key=_chave_comp) if fims else ""))
    return inicio, fim


def _tabela_destaque(
    pares: list[tuple[str, str]],
    estilos: dict[str, ParagraphStyle],
    *,
    largura: float,
    realcar_ultima: bool = False,
) -> Table:
    dados = [
        [_p(rotulo, estilos["rotulo_grande"]), _p(valor, estilos["numero"])]
        for rotulo, valor in pares
    ]
    if realcar_ultima and dados:
        dados[-1] = [
            _p(pares[-1][0], estilos["verba_cab"]),
            _p(pares[-1][1], estilos["numero_branco"]),
        ]
    largura_rotulo = largura * 0.55
    tabela = Table(
        dados,
        colWidths=[largura_rotulo, largura - largura_rotulo],
        hAlign="LEFT",
    )
    estilo = TableStyle(
        [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, LINHA_CLARA),
            ("BOX", (0, 0), (-1, -1), 0.5, LINHA),
        ]
    )
    if realcar_ultima and dados:
        estilo.add("BACKGROUND", (0, len(dados) - 1), (-1, len(dados) - 1), VINHO)
        estilo.add("LINEBELOW", (0, len(dados) - 2), (-1, len(dados) - 2), 0.5, LINHA)
    tabela.setStyle(estilo)
    return tabela


def _tabela_pagamentos(
    pagamentos: list[dict],
    estilos: dict[str, ParagraphStyle],
    largura: float,
    *,
    como_abatimento: bool = False,
) -> Table:
    colunas = [
        ("Data", 34, "cen"),
        ("Valor", 34, "dir"),
        ("Competência / referência", 70, "esq"),
        ("Descrição", 48, "esq"),
    ]
    estilo_cab = {
        "cen": estilos["cab_med_cen"],
        "dir": estilos["cab_med_dir"],
        "esq": estilos["cab_med"],
    }
    estilo_celula = {
        "cen": estilos["celula_med_cen"],
        "dir": estilos["celula_med_dir"],
        "esq": estilos["celula_med"],
    }
    dados = [
        [_p(nome, estilo_cab[alinhamento]) for nome, _, alinhamento in colunas]
    ]
    for pagamento in pagamentos:
        valores = {
            "Data": _data_br(pagamento.get("data")),
            "Valor": _brl_negativo(pagamento.get("valor"))
            if como_abatimento
            else brl_memoria(pagamento.get("valor")),
            "Competência / referência": _data_br(pagamento.get("competencia")) or "—",
            "Descrição": pagamento.get("descricao") or "—",
        }
        dados.append(
            [
                _p(valores[nome], estilo_celula[alinhamento])
                for nome, _, alinhamento in colunas
            ]
        )
    larguras = [larg * mm for _, larg, _ in colunas]
    total = sum(larguras)
    if total:
        fator = largura / total
        larguras = [w * fator for w in larguras]
    tabela = Table(dados, colWidths=larguras, repeatRows=1, hAlign="LEFT")
    tabela.setStyle(_estilo_tabela(1))
    return tabela


def _brl_negativo(valor: object | None) -> str:
    decimal = dec_memoria(valor)
    if decimal is None:
        return "—"
    return brl_memoria(-abs(decimal))


def _linhas_aplicadas(parcelas: list[dict], chave: str) -> list[dict]:
    """Resultados efetivamente aplicados, inclusive em memórias anteriores."""
    return [
        dict(parcela.get(chave) or {})
        for parcela in parcelas
        if (parcela.get(chave) or {}).get("aplicado")
    ]


def _itens_unicos(itens: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in itens if item))


def _metodologia_calculo(memoria: dict, estilos: dict[str, ParagraphStyle], largura: float) -> list:
    """Fundamentação descritiva, derivada somente do que a memória registra.

    Esta função não completa lacunas de memórias antigas por inferência: quando
    um dado não foi guardado, limita-se a apontar o que é auditável no resultado.
    """
    criterios = memoria.get("criterios") or {}
    parcelas = memoria.get("parcelas") or []
    bases = memoria.get("bases") or []
    consolidados = memoria.get("encargos_consolidados") or []
    historia: list = _secao("Metodologia de Cálculo e Fundamentação Normativa", estilos)
    numero_secao = 1

    def proxima_secao(titulo: str) -> list:
        nonlocal numero_secao
        secao = _subsecao(f"{numero_secao}. {titulo}", estilos)
        numero_secao += 1
        return secao

    correcoes = _linhas_aplicadas(parcelas, "correcao")
    if correcoes:
        historia.extend(proxima_secao("Correção monetária"))
        linhas: list[tuple[str, str]] = []
        indexadores = _itens_unicos([
            _nome_indexador(c.get("indexador"), bases) for c in correcoes
        ])
        periodos = _itens_unicos([
            _periodo(c.get("termo_inicial"), c.get("termo_final")) for c in correcoes
        ])
        linhas.append(("Índice efetivamente utilizado", " / ".join(indexadores) or "registrado por parcela"))
        linhas.append(("Período de incidência", "; ".join(periodos) or "registrado por parcela"))
        linhas.append(("Método", "Para cada parcela, aplicou-se a razão entre o fator final e o fator inicial da série registrada na memória; nos segmentos, as razões foram encadeadas. O resultado foi arredondado a centavos após a atualização."))
        fontes = _itens_unicos([
            str(c.get("indexador_fonte")) for c in correcoes if c.get("indexador_fonte")
        ])
        if fontes:
            linhas.append(("Fonte registrada", " / ".join(fontes)))
        historia.append(_tabela_pares(linhas, estilos, largura_rotulo=44 * mm, largura_total=largura))
    else:
        historia.extend(proxima_secao("Correção monetária"))
        historia.append(_p("Não houve correção monetária efetivamente aplicada nas parcelas registradas nesta memória.", estilos["corpo_fraco"]))

    juros = _linhas_aplicadas(parcelas, "juros")
    if juros:
        historia.extend(proxima_secao("Juros"))
        modalidades = _itens_unicos([_modalidade_txt(j.get("modalidade")) for j in juros])
        incidencias = _itens_unicos([str(j.get("incidencia")) for j in juros if j.get("incidencia")])
        trechos = [t for j in juros for t in (j.get("trechos") or [])]
        periodos = _itens_unicos([_periodo(t.get("inicio"), t.get("fim")) for t in trechos])
        historia.append(_tabela_pares(
            [
                ("Modalidade efetivamente aplicada", " / ".join(modalidades) or "registrada por parcela"),
                ("Termo de incidência", "; ".join(periodos) or "registrado por parcela"),
                ("Base de incidência", " / ".join(incidencias) or "registrada por parcela"),
                ("Método", "Juros simples, apurados por trecho sobre a base registrada em cada parcela; taxas anuais são proporcionais aos dias (dias/365) e taxas mensais são proporcionais aos dias corridos de cada mês."),
            ], estilos, largura_rotulo=44 * mm, largura_total=largura
        ))
    else:
        historia.extend(proxima_secao("Juros"))
        historia.append(_p("Não houve juros efetivamente aplicados nas parcelas registradas nesta memória.", estilos["corpo_fraco"]))

    trechos_juros = [t for j in juros for t in (j.get("trechos") or [])]
    ha_taxa_legal = any("Taxa Legal" in str(t.get("rotulo")) for t in trechos_juros)
    ha_regime_pos_lei = any(
        "SELIC menos" in str(t.get("rotulo")) or "SELIC integral" in str(t.get("rotulo"))
        for t in trechos_juros
    )
    if ha_taxa_legal or ha_regime_pos_lei:
        historia.extend(proxima_secao("Taxa Legal e regimes temporais"))
        texto = (
            "Nos trechos posteriores efetivamente registrados, a referência normativa é o art. 406 do Código Civil, "
            "com redação da Lei nº 14.905/2024: a Taxa Legal corresponde à Selic deduzido o índice de atualização "
            "monetária do art. 389, parágrafo único; resultado negativo é tratado como zero. A Resolução CMN nº "
            "5.171/2024 disciplina a taxa mensal, divulgada pelo Banco Central, e determina juros simples, acumulação "
            "das taxas mensais e fração pro rata pelos dias corridos do mês."
        )
        historia.append(_p(texto, estilos["corpo"]))
        textos_trechos = _itens_unicos([
            f"{_periodo(t.get('inicio'), t.get('fim'))}: {t.get('rotulo') or t.get('taxa_rotulo') or 'critério registrado'}"
            for t in trechos_juros
        ])
        if textos_trechos:
            historia.append(Spacer(1, 1.2 * mm))
            historia.append(_tabela_pares(
                [("Regimes efetivamente apurados", "; ".join(textos_trechos))],
                estilos, largura_rotulo=44 * mm, largura_total=largura,
            ))
        historia.append(_p(
            "Eventuais trechos anteriores a 30/08/2024 são exibidos acima conforme a regra histórica gravada na memória; "
            "esta seção não lhes atribui a metodologia da Lei nº 14.905/2024.", estilos["nota"]
        ))

    historia.extend(proxima_secao("Multas e honorários"))
    encargos_por_parcela: list[tuple[str, list[dict]]] = [
        ("Multa", _linhas_aplicadas(parcelas, "multa")),
        ("Honorários", _linhas_aplicadas(parcelas, "honorarios")),
    ]
    linhas_encargos: list[tuple[str, str]] = []
    for nome, itens in encargos_por_parcela:
        if not itens:
            linhas_encargos.append((nome, "não aplicado nas parcelas registradas"))
            continue
        detalhes = _itens_unicos([
            "; ".join(filter(None, [
                pct_memoria(i.get("percentual")) if i.get("percentual") is not None else "",
                _base_incidencia_txt(i.get("base_nome") or i.get("base")) if (i.get("base_nome") or i.get("base")) else "",
                brl_memoria(i.get("base_valor")) if i.get("base_valor") is not None else "",
            ])) for i in itens
        ])
        linhas_encargos.append((nome, "por verba/parcela: " + (" | ".join(detalhes) or "critério registrado no resultado")))
    if consolidados:
        for encargo in sorted(consolidados, key=lambda e: (e.get("ordem", 0), str(e.get("id", "")))):
            base = encargo.get("base") or {}
            criterio = pct_memoria(encargo.get("percentual")) or brl_memoria(encargo.get("valor_fixo")) or "critério registrado"
            componentes = ", ".join(base.get("componentes") or []) or "base registrada"
            predecessores = ", ".join(p.get("id", "") for p in base.get("predecessores") or [])
            ordem = f"ordem {encargo.get('ordem')}"
            if predecessores:
                ordem += f"; após {predecessores}"
            linhas_encargos.append((f"{encargo.get('tipo', 'Encargo').capitalize()} consolidado", f"{ordem}; {criterio}; base {componentes}, {brl_memoria(base.get('valor'))}; resultado {brl_memoria(encargo.get('valor'))}."))
    historia.append(_tabela_pares(linhas_encargos, estilos, largura_rotulo=44 * mm, largura_total=largura))

    historia.extend(proxima_secao("Pagamentos e abatimentos"))
    pagamentos = pagamentos_efetivos(criterios, parcelas)
    if pagamentos:
        lista = "; ".join(
            f"{_data_br(p.get('data'))}: {brl_memoria(p.get('valor'))}"
            + (f" ({p.get('descricao')})" if p.get("descricao") else "")
            for p in pagamentos
        )
        historia.append(_tabela_pares([
            ("Lançamentos considerados", lista),
            ("Forma de dedução", "Cada pagamento foi somado aos pagamentos da respectiva parcela e deduzido diretamente do total já apurado; o saldo é o total menos os pagamentos registrados."),
        ], estilos, largura_rotulo=44 * mm, largura_total=largura))
    else:
        historia.append(_p("Não há pagamentos ou abatimentos individualizados na memória para dedução.", estilos["corpo_fraco"]))

    historia.extend(proxima_secao("Fontes, rastreabilidade e arredondamento"))
    if bases:
        fontes = "; ".join(
            f"{b.get('nome') or b.get('key')}: versão {b.get('versao') or 'não registrada'}, "
            f"cobertura {b.get('cobertura') or 'não registrada'}, fonte {b.get('fonte') or 'não registrada'}"
            + (f" ({b.get('fonte_url')})" if b.get("fonte_url") else "")
            + (f", atualização {b.get('atualizado_em')}" if b.get("atualizado_em") else "")
            for b in bases
        )
        historia.append(_p("Bases efetivamente registradas nesta memória: " + fontes + ".", estilos["corpo"]))
    else:
        historia.append(_p("A memória não registra bases indexadoras; não é possível complementar essa rastreabilidade sem alterar o registro histórico.", estilos["corpo_fraco"]))
    arredondamentos = _itens_unicos([
        str(e.get("arredondamento")) for e in consolidados if e.get("arredondamento")
    ])
    if arredondamentos:
        historia.append(_p(
            "Encargos consolidados: " + " / ".join(arredondamentos) + ".",
            estilos["nota"],
        ))
    return historia


def _tabela_identificacao_alimentos(
    pares: list[tuple[str, str]],
    estilos: dict[str, ParagraphStyle],
    *,
    largura: float,
) -> Table:
    """Cabeçalho compacto: quatro pares em duas linhas na largura da paisagem."""
    rotulo = 30 * mm
    coluna = largura / 2
    larguras = [rotulo, coluna - rotulo, rotulo, coluna - rotulo]
    meio = max(len(pares) // 2, 1)
    dados: list[list] = []
    for bloco in (pares[:meio], pares[meio:]):
        linha: list = []
        for chave, valor in bloco:
            linha.extend([_p(chave, estilos["rotulo"]), _p(valor, estilos["valor"])])
        while len(linha) < 4:
            linha.extend([_p("", estilos["rotulo"]), _p("", estilos["valor"])])
        dados.append(linha)
    tabela = Table(dados, colWidths=larguras, hAlign="LEFT")
    tabela.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
                ("LINEAFTER", (1, 0), (1, -1), 0.3, LINHA_CLARA),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, LINHA_CLARA),
            ]
        )
    )
    return tabela


def _tabela_destaque_faixa(
    pares: list[tuple[str, str]],
    estilos: dict[str, ParagraphStyle],
    *,
    largura: float,
    destaque: int | None = None,
) -> Table:
    """Faixa horizontal de resultados, com destaque opcional na última coluna."""
    total = max(len(pares), 1)
    coluna = largura / total
    rotulos = [
        _p(
            rotulo,
            estilos["faixa_rotulo_destaque"]
            if indice == destaque
            else estilos["faixa_rotulo"],
        )
        for indice, (rotulo, _) in enumerate(pares)
    ]
    valores = [
        _p(
            valor,
            estilos["faixa_valor_destaque"] if indice == destaque else estilos["faixa_valor"],
        )
        for indice, (_, valor) in enumerate(pares)
    ]
    tabela = Table([rotulos, valores], colWidths=[coluna] * total, hAlign="LEFT")
    estilo = TableStyle(
        [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LINEBELOW", (0, 0), (-1, 0), 0.3, LINHA_CLARA),
            ("LINEBELOW", (0, 1), (-1, 1), 0.5, LINHA),
            ("LINEAFTER", (0, 0), (-2, -1), 0.3, LINHA_CLARA),
            ("BOX", (0, 0), (-1, -1), 0.5, LINHA),
        ]
    )
    if destaque is not None and 0 <= destaque < total:
        estilo.add("BACKGROUND", (destaque, 0), (destaque, 1), VINHO)
    tabela.setStyle(estilo)
    return tabela


def _tem_valor(valor: object) -> bool:
    """True quando a memória traz valor diferente de zero (sem recálculo)."""
    dec = dec_memoria(valor)
    return dec is not None and dec != Decimal("0")


def _tabela_peticao_pares(
    pares: list[tuple[str, str]],
    estilos: dict[str, ParagraphStyle],
    *,
    largura: float,
    destaque: int | None = None,
) -> Table:
    """Bloco rotulo/valor do resumo para petição, com realce no saldo."""
    dados: list[list] = [
        [_p(rotulo, estilos["rotulo"]), _p(valor, estilos["valor_dir"])]
        for rotulo, valor in pares
    ]
    if destaque is not None and dados:
        dados[destaque] = [
            _p(pares[destaque][0], estilos["verba_cab"]),
            _p(pares[destaque][1], estilos["geral"]),
        ]
    largura_rotulo = largura * 0.55
    tabela = Table(
        dados,
        colWidths=[largura_rotulo, largura - largura_rotulo],
        hAlign="LEFT",
    )
    estilo = TableStyle(
        [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, ZEBRA]),
            ("LINEBELOW", (0, 0), (-1, -2), 0.25, LINHA_CLARA),
            ("BOX", (0, 0), (-1, -1), 0.5, LINHA),
        ]
    )
    if destaque is not None and dados:
        estilo.add("BACKGROUND", (0, destaque), (-1, destaque), VINHO)
        estilo.add("LINEABOVE", (0, destaque), (-1, destaque), 0.6, VINHO_ESCURO)
    tabela.setStyle(estilo)
    return tabela


def _pares_peticao_civel(resumo: dict, parcelas: list[dict]) -> list[tuple[str, str]]:
    """Quadro compacto e completo, pronto para cópia em petição."""
    return [
        ("Principal", brl_memoria(resumo.get("principal")) or "—"),
        ("Correção monetária", brl_memoria(resumo.get("correcao")) or "—"),
        ("Juros", brl_memoria(resumo.get("juros")) or "—"),
        ("Multa", brl_memoria(resumo.get("multa")) or "—"),
        ("Honorários", brl_memoria(resumo.get("honorarios")) or "—"),
        ("Total atualizado", brl_memoria(resumo.get("total")) or "—"),
        ("Pagamentos / abatimentos", _brl_negativo(resumo.get("pagamentos"))),
        ("Saldo final", brl_memoria(resumo.get("saldo")) or "—"),
    ]


def _tabela_resumo_peticao_civel(
    grupos: list[dict],
    resumo: dict,
    parcelas: list[dict],
    estilos: dict[str, ParagraphStyle],
    *,
    largura: float,
) -> Table:
    """Quadro consolidado, estreito e selecionável para o LibreOffice Writer."""
    pares = _pares_peticao_civel(resumo, parcelas)
    return _tabela_peticao_pares(
        pares,
        estilos,
        largura=largura,
        destaque=next(i for i, (rotulo, _) in enumerate(pares) if rotulo == "Saldo final"),
    )

def _texto_peticao_civel(
    memoria: dict,
    estilos: dict[str, ParagraphStyle],
) -> Paragraph:
    """Bloco curto e selecionável para colar na petição (sem teses jurídicas)."""
    ident = memoria.get("identificacao") or {}
    criterios = memoria.get("criterios") or {}
    resumo = memoria.get("resumo") or {}
    codigo = memoria.get("codigo") or ""
    titulo = ident.get("titulo") or "Memória de cálculo"
    desc = f"{titulo} ({codigo})" if codigo else str(titulo)

    cabeca = f"Resumo para petição: {desc}"
    data_base = _data_br(ident.get("data_base") or criterios.get("data_base"))
    if data_base != "—":
        cabeca += f", atualizado até {data_base}"
    frases = [f"{cabeca}."]

    inicio = _data_br(resumo.get("periodo_inicio"))
    fim = _data_br(resumo.get("periodo_fim"))
    if inicio != "—" and fim != "—":
        if inicio == fim:
            frases.append(f"Vencimento em {inicio}.")
        else:
            frases.append(f"Vencimentos de {inicio} a {fim}.")

    valores = [f"principal {brl_memoria(resumo.get('principal')) or '—'}"]
    if _tem_valor(resumo.get("correcao")):
        valores.append(f"correção monetária {brl_memoria(resumo.get('correcao'))}")
    if _tem_valor(resumo.get("juros")):
        valores.append(f"juros {brl_memoria(resumo.get('juros'))}")
    frases.append(f"Valores: {'; '.join(valores)}.")
    frases.append(f"Total apurado: {brl_memoria(resumo.get('total')) or '—'}.")
    if _tem_valor(resumo.get("pagamentos")):
        frases.append(
            f"Pagamentos considerados: {brl_memoria(resumo.get('pagamentos'))}; "
            f"saldo devedor: {brl_memoria(resumo.get('saldo')) or '—'}."
        )
    return _p(" ".join(frases), estilos["corpo"])


def _pares_peticao_alimentos(memoria: dict) -> list[tuple[str, str]]:
    """Pares do resumo para petição de Alimentos, só com o que a memória tem."""
    ident = memoria.get("identificacao") or {}
    criterios = memoria.get("criterios") or {}
    resumo = memoria.get("resumo") or {}
    parcelas = memoria.get("parcelas") or []
    alimentos = criterios.get("alimentos") or {}

    pares: list[tuple[str, str]] = []
    inicio_periodo, fim_periodo = _periodo_regras(alimentos)
    if inicio_periodo and fim_periodo:
        pares.append(
            ("Período do débito", f"{_data_br(inicio_periodo)} a {_data_br(fim_periodo)}")
        )
    elif inicio_periodo:
        pares.append(("Período do débito", f"{_data_br(inicio_periodo)} em diante"))

    pares.append(("Principal", brl_memoria(resumo.get("principal")) or "—"))
    if _tem_valor(resumo.get("correcao")) or any(
        (p.get("correcao") or {}).get("aplicado") for p in parcelas
    ):
        pares.append(("Correção monetária", brl_memoria(resumo.get("correcao")) or "—"))
    if _tem_valor(resumo.get("juros")) or any(
        (p.get("juros") or {}).get("aplicado") for p in parcelas
    ):
        pares.append(("Juros", brl_memoria(resumo.get("juros")) or "—"))
    if _tem_valor(resumo.get("pagamentos")):
        pares.append(
            ("Pagamentos / abatimentos", brl_memoria(resumo.get("pagamentos")))
        )
    pares.append(("Total do débito atualizado", brl_memoria(resumo.get("total")) or "—"))
    pares.append(("Saldo devedor atualizado", brl_memoria(resumo.get("saldo")) or "—"))
    pares.append(
        (
            "Data da atualização",
            _data_br(ident.get("data_base") or criterios.get("data_base")),
        )
    )
    return pares


def _tabela_resumo_peticao_alimentos(
    memoria: dict,
    estilos: dict[str, ParagraphStyle],
    *,
    largura: float,
) -> Table:
    pares = _pares_peticao_alimentos(memoria)
    destaque = next(
        (i for i, (rotulo, _) in enumerate(pares) if rotulo == "Saldo devedor atualizado"),
        None,
    )
    return _tabela_peticao_pares(pares, estilos, largura=largura, destaque=destaque)


def _texto_peticao_alimentos(
    memoria: dict,
    estilos: dict[str, ParagraphStyle],
) -> Paragraph:
    """Resumo do débito em uma frase, para copiar direto do PDF."""
    ident = memoria.get("identificacao") or {}
    criterios = memoria.get("criterios") or {}
    resumo = memoria.get("resumo") or {}
    alimentos = criterios.get("alimentos") or {}

    cabeca = "Resumo do débito alimentar"
    inicio_periodo, fim_periodo = _periodo_regras(alimentos)
    if inicio_periodo and fim_periodo:
        cabeca += (
            f": período de {_data_br(inicio_periodo)} a {_data_br(fim_periodo)}"
        )
    elif inicio_periodo:
        cabeca += f": período a partir de {_data_br(inicio_periodo)}"
    frases = [f"{cabeca}."]

    valores = [f"principal {brl_memoria(resumo.get('principal')) or '—'}"]
    if _tem_valor(resumo.get("correcao")):
        valores.append(f"correção monetária {brl_memoria(resumo.get('correcao'))}")
    if _tem_valor(resumo.get("juros")):
        valores.append(f"juros {brl_memoria(resumo.get('juros'))}")
    if _tem_valor(resumo.get("pagamentos")):
        valores.append(
            f"pagamentos considerados {brl_memoria(resumo.get('pagamentos'))}"
        )
    frases.append(f"Valores: {'; '.join(valores)}.")

    data_base = _data_br(ident.get("data_base") or criterios.get("data_base"))
    if _tem_valor(resumo.get("pagamentos")):
        frases.append(
            f"Total do débito atualizado: {brl_memoria(resumo.get('total')) or '—'}."
        )
    if data_base != "—":
        frases.append(
            f"Saldo devedor atualizado até {data_base}: "
            f"{brl_memoria(resumo.get('saldo')) or '—'}."
        )
    else:
        frases.append(
            f"Saldo devedor atualizado: {brl_memoria(resumo.get('saldo')) or '—'}."
        )
    return _p(" ".join(frases), estilos["corpo"])


def _historia_alimentos(memoria: dict) -> list:
    """A4 paisagem, tipografia reduzida e a mesma identidade visual do app."""
    estilos = _estilos_alimentos()
    ident = memoria.get("identificacao") or {}
    resumo = memoria.get("resumo") or {}
    criterios = memoria.get("criterios") or {}
    bases = memoria.get("bases") or []
    parcelas = memoria.get("parcelas") or []
    avisos = memoria.get("avisos") or []
    codigo = memoria.get("codigo") or ""
    app_version = ident.get("app_version") or ""
    esquema = memoria.get("esquema") or "memoria-calculo"
    alimentos = criterios.get("alimentos") or {}
    largura = PAGINA_ALIMENTOS[0] - 2 * MARGEM

    historia: list = []
    historia.append(_p(CABECALHO_APP.upper(), estilos["marca"]))
    historia.append(_p("MEMÓRIA DE CÁLCULO — ALIMENTOS", estilos["titulo_doc"]))
    historia.append(
        HRFlowable(
            width="100%",
            thickness=1.0,
            color=VINHO,
            spaceBefore=0.4 * mm,
            spaceAfter=1.5 * mm,
        )
    )

    inicio_periodo, fim_periodo = _periodo_regras(alimentos)
    if inicio_periodo and fim_periodo:
        periodo_txt = f"{_data_br(inicio_periodo)} a {_data_br(fim_periodo)}"
    elif inicio_periodo:
        periodo_txt = f"{_data_br(inicio_periodo)} em diante"
    else:
        periodo_txt = "—"
    historia.append(
        _tabela_identificacao_alimentos(
            [
                ("Código", codigo or "—"),
                ("Título", ident.get("titulo") or "—"),
                ("Período", periodo_txt),
                (
                    "Atualizado até",
                    _data_br(ident.get("data_base") or criterios.get("data_base")),
                ),
            ],
            estilos,
            largura=largura,
        )
    )

    resultado = [
        ("Principal", brl_memoria(resumo.get("principal")) or "—"),
        ("Correção monetária", brl_memoria(resumo.get("correcao")) or "—"),
        ("Juros", brl_memoria(resumo.get("juros")) or "—"),
        ("Pagamentos", brl_memoria(resumo.get("pagamentos")) or "—"),
        ("Saldo", brl_memoria(resumo.get("saldo")) or "—"),
    ]
    historia.append(
        KeepTogether(
            _secao("Resultado", estilos)
            + [_tabela_destaque_faixa(resultado, estilos, largura=largura, destaque=4)]
        )
    )

    regras = alimentos.get("regras") or []
    bloco_regra: list = _secao("Regra alimentar", estilos)
    for indice, regra in enumerate(regras, start=1):
        if regra.get("tipo") == "salario_minimo":
            descricao = f"{pct_memoria(regra.get('percentual'))} do salário mínimo"
        else:
            descricao = f"valor fixo de {brl_memoria(regra.get('valor'))}"
        if regra.get("fim"):
            periodo_regra = (
                f"{_data_br(regra.get('inicio'))} a {_data_br(regra.get('fim'))}"
            )
        else:
            periodo_regra = f"{_data_br(regra.get('inicio'))} em diante"
        if len(regras) > 1:
            bloco_regra.append(_p(f"Regra {indice}", estilos["rotulo_grande"]))
        bloco_regra.append(_p(descricao, estilos["valor_forte"]))
        bloco_regra.append(_p(f"Período: {periodo_regra}", estilos["corpo_fraco"]))
        bloco_regra.append(Spacer(1, 1.2 * mm))
    if not regras:
        bloco_regra.append(_p("Nenhuma regra informada.", estilos["corpo_fraco"]))
    if alimentos.get("dia_vencimento"):
        bloco_regra.append(
            _p(
                f"Vencimento: dia {alimentos.get('dia_vencimento')}",
                estilos["corpo_fraco"],
            )
        )

    cfg_correcao = criterios.get("correcao") or {}
    cfg_juros = criterios.get("juros") or {}
    if cfg_correcao.get("aplicar"):
        correcao_txt = _nome_indexador(cfg_correcao.get("indexador"), bases)
    else:
        aplicadas = [
            c for c in ((p.get("correcao") or {}) for p in parcelas) if c.get("aplicado")
        ]
        correcao_txt = (
            " / ".join(
                dict.fromkeys(_nome_indexador(c.get("indexador"), bases) for c in aplicadas)
            )
            or "não aplicada"
        )
    if cfg_juros.get("aplicar"):
        modalidade = cfg_juros.get("modalidade")
        if modalidade == "fixa" and cfg_juros.get("taxa") is not None:
            juros_txt = f"{pct_memoria(cfg_juros.get('taxa'))} ao mês"
        else:
            juros_txt = _modalidade_txt(modalidade)
    else:
        juros_txt = "não aplicados"

    coluna_regra = largura * 0.46
    coluna_rotulo = 30 * mm
    coluna_valor = largura - coluna_regra - coluna_rotulo
    linhas_atualizacao = [
        ("Correção", correcao_txt),
        ("Juros", juros_txt),
        ("Multa", _encargo_txt(criterios.get("multa"))),
        ("Honorários", _encargo_txt(criterios.get("honorarios"))),
    ]
    dados_lado: list[list] = [[bloco_regra, _secao("Atualização", estilos), ""]]
    for chave, valor in linhas_atualizacao:
        dados_lado.append(
            ["", _p(chave, estilos["rotulo"]), _p(valor, estilos["valor"])]
        )
    ultima = len(dados_lado) - 1
    tabela_lado = Table(
        dados_lado,
        colWidths=[coluna_regra, coluna_rotulo, coluna_valor],
        hAlign="LEFT",
    )
    tabela_lado.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 0), (0, ultima)),
                ("SPAN", (1, 0), (2, 0)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (0, ultima), 0),
                ("RIGHTPADDING", (0, 0), (0, ultima), 8 * mm),
                ("LEFTPADDING", (1, 0), (-1, -1), 0),
                ("RIGHTPADDING", (1, 1), (1, ultima), 6),
                ("LEFTPADDING", (2, 1), (2, ultima), 4),
                ("RIGHTPADDING", (2, 0), (2, ultima), 0),
                ("TOPPADDING", (0, 0), (-1, 0), 0),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 1.5),
                ("TOPPADDING", (0, 1), (-1, ultima), 2.5),
                ("BOTTOMPADDING", (0, 1), (-1, ultima), 2.5),
                ("LINEBELOW", (1, 1), (2, ultima), 0.3, LINHA_CLARA),
            ]
        )
    )
    historia.append(KeepTogether(tabela_lado))

    historia.append(Spacer(1, 2 * mm))
    historia.append(
        _tabela_detalhe(
            "Dívida por competência",
            parcelas,
            [
                ("Competência", 24, "cen"),
                ("Vencimento", 26, "cen"),
                ("Salário mín.", 30, "dir"),
                ("%", 16, "cen"),
                ("Devido", 28, "dir"),
                ("Pago", 26, "dir"),
                ("Saldo", 28, "dir"),
            ],
            estilos,
            largura=largura,
            corpo_medio=True,
        )
    )

    detalhamento = _tabela_detalhe(
        "Detalhamento da atualização",
        parcelas,
        [
            ("Competência", 26, "cen"),
            ("Correção", 34, "dir"),
            ("Índice", 32, "dir"),
            ("Juros", 32, "dir"),
            ("Total atualizado", 36, "dir"),
        ],
        estilos,
        largura=largura,
        corpo_medio=True,
    )
    historia.append(
        KeepTogether([Spacer(1, 3 * mm), detalhamento])
        if len(parcelas) <= 15
        else Spacer(1, 3 * mm)
    )
    if len(parcelas) > 15:
        historia.append(detalhamento)

    pagamentos = pagamentos_efetivos(criterios, parcelas)
    if pagamentos:
        historia.append(Spacer(1, 3 * mm))
        historia.append(
            KeepTogether(
                _secao("Pagamentos informados", estilos)
                + [_tabela_pagamentos(pagamentos, estilos, largura)]
            )
        )

    resumo_final = [
        ("TOTAL DO DÉBITO ATUALIZADO", brl_memoria(resumo.get("total")) or "—"),
        ("PAGAMENTOS", brl_memoria(resumo.get("pagamentos")) or "—"),
        ("SALDO", brl_memoria(resumo.get("saldo")) or "—"),
    ]
    historia.append(
        KeepTogether(
            _secao("Resumo final", estilos)
            + [_tabela_destaque_faixa(resumo_final, estilos, largura=largura, destaque=2)]
        )
    )

    historia.append(
        KeepTogether(
            _secao("Resumo para petição", estilos)
            + [
                _tabela_resumo_peticao_alimentos(memoria, estilos, largura=largura),
                Spacer(1, 1.5 * mm),
                _texto_peticao_alimentos(memoria, estilos),
            ]
        )
    )

    if bases:
        historia.append(
            KeepTogether(
                _secao("Bases e versionamento", estilos)
                + [_tabela_bases(bases, estilos, largura=largura)]
            )
        )
    else:
        historia.extend(_secao("Bases e versionamento", estilos))
        historia.append(_p("Nenhuma base indexadora utilizada.", estilos["corpo_fraco"]))

    if avisos:
        historia.extend(_secao("Avisos", estilos))
        for aviso in avisos:
            historia.append(_p(f"• {aviso}", estilos["corpo_fraco"]))

    historia.extend(_metodologia_calculo(memoria, estilos, largura))
    historia.append(Spacer(1, 3 * mm))
    historia.append(
        _p(
            f"Documento gerado a partir da memória de cálculo ({esquema}). "
            f"Sem recálculo de valores."
            + (f" Aplicativo {app_version}." if app_version else ""),
            estilos["nota"],
        )
    )
    return historia


def _historia_civel(memoria: dict) -> list:
    """Monta o fluxo do PDF apenas com dados já presentes na memória."""
    estilos = _estilos()
    ident = memoria.get("identificacao") or {}
    resumo = memoria.get("resumo") or {}
    criterios = memoria.get("criterios") or {}
    bases = memoria.get("bases") or []
    parcelas = memoria.get("parcelas") or []
    verbas = memoria.get("verbas") or []
    avisos = memoria.get("avisos") or []
    codigo = memoria.get("codigo") or ""
    app_version = ident.get("app_version") or ""
    esquema = memoria.get("esquema") or "memoria-calculo"

    historia: list = []

    historia.append(_p(CABECALHO_APP.upper(), estilos["marca"]))
    historia.append(_p("Memória de Cálculo", estilos["titulo_doc"]))
    historia.append(
        HRFlowable(
            width="100%",
            thickness=1.2,
            color=VINHO,
            spaceBefore=0.5 * mm,
            spaceAfter=2 * mm,
        )
    )
    historia.append(
        _p(
            f"Código: {codigo or '—'}"
            f"   •   Data de geração: {_data_br(ident.get('data_geracao'))}"
            f"   •   Atualizado até: {_data_br(ident.get('data_base') or criterios.get('data_base'))}",
            estilos["meta"],
        )
    )

    historia.extend(_secao("Identificação", estilos))
    historia.append(
        KeepTogether(
            _tabela_pares(
                [
                    ("Código", codigo or "—"),
                    ("Título", ident.get("titulo") or "—"),
                    ("Processo", ident.get("processo") or "—"),
                    ("Parte", ident.get("parte") or "—"),
                    (
                        "Aplicativo",
                        f"{ident.get('app_name') or CABECALHO_APP} {app_version}".strip(),
                    ),
                ],
                estilos,
                largura_rotulo=34 * mm,
                largura_total=150 * mm,
            )
        )
    )

    historia.extend(_secao("Resumo do cálculo", estilos))
    historia.append(_tabela_resumo(verbas, parcelas, resumo, estilos))
    historia.extend(_nota_verbas_fora_do_total(verbas, estilos))
    encargos = _encargos_aplicados(parcelas, bases)
    if encargos:
        historia.append(Spacer(1, 1.5 * mm))
        historia.append(
            KeepTogether(
                [
                    _p(
                        "   •   ".join(
                            f"{rotulo}: {valor}" for rotulo, valor in encargos
                        ),
                        estilos["corpo"],
                    )
                ]
            )
        )
    consolidados = memoria.get("encargos_consolidados") or []
    if consolidados:
        historia.extend(_secao("Encargos consolidados", estilos))
        linhas = []
        for encargo in consolidados:
            base = encargo.get("base") or {}
            criterio = pct_memoria(encargo.get("percentual")) or brl_memoria(encargo.get("valor_fixo"))
            linhas.append((
                f"{encargo.get('ordem')} — {encargo.get('tipo')}",
                f"base {brl_memoria(base.get('valor'))}; {criterio}; "
                f"resultado {brl_memoria(encargo.get('valor'))}; "
                f"inclui no total: {'sim' if encargo.get('entra_no_total') else 'não'}.",
            ))
        historia.append(_tabela_pares(linhas, estilos, largura_rotulo=38 * mm, largura_total=150 * mm))

    historia.extend(_secao("Resumo para petição", estilos))
    grupos_peticao = _grupos_de_verbas(verbas, parcelas)
    bloco_peticao: list = [
        _tabela_resumo_peticao_civel(
            grupos_peticao,
            resumo,
            parcelas,
            estilos,
            largura=LARGURA,
        )
    ]
    bloco_peticao.extend(_nota_verbas_fora_do_total(verbas, estilos))
    bloco_peticao.append(Spacer(1, 1.5 * mm))
    bloco_peticao.append(_texto_peticao_civel(memoria, estilos))
    historia.append(KeepTogether(bloco_peticao))

    pagamentos = pagamentos_efetivos(criterios, parcelas)
    if pagamentos or _tem_valor(resumo.get("pagamentos")):
        fechamento: list = []
        if pagamentos:
            fechamento.append(
                _tabela_pagamentos(
                    pagamentos, estilos, LARGURA, como_abatimento=True
                )
            )
            fechamento.append(Spacer(1, 1.5 * mm))
        fechamento.append(
            _tabela_destaque(
                [
                    ("Total apurado", brl_memoria(resumo.get("total")) or "—"),
                    ("Abatimentos", _brl_negativo(resumo.get("pagamentos"))),
                    ("Saldo final", brl_memoria(resumo.get("saldo")) or "—"),
                ],
                estilos,
                largura=LARGURA,
                realcar_ultima=True,
            )
        )
        historia.append(KeepTogether(_secao("Fechamento", estilos) + fechamento))

    if verbas:
        historia.extend(_secao("Configuração das verbas", estilos))
        nomes_por_id = {v.get("id"): v.get("nome") for v in verbas}
        for indice, verba in enumerate(verbas, start=1):
            complemento = dict(verba)
            if verba.get("tipo") == "percentual":
                complemento["base_nomes"] = [
                    {"id": chave, "nome": valor} for chave, valor in nomes_por_id.items()
                ]
            historia.extend(
                _bloco_verba(
                    indice,
                    complemento,
                    _parcelas_da_verba(verba, parcelas),
                    bases,
                    estilos,
                )
            )

    historia.extend(_secao("Memória de cálculo", estilos))
    if verbas:
        for indice, verba in enumerate(verbas, start=1):
            nome = verba.get("nome") or f"Verba {indice}"
            grupo = _parcelas_da_verba(verba, parcelas)
            historia.append(Spacer(1, 2 * mm))
            historia.extend(_tabelas_detalhe_civel(f"{indice}. {nome.upper()}", grupo, estilos))
            historia.append(Spacer(1, 1.5 * mm))
    else:
        historia.extend(_tabelas_detalhe_civel("Parcelas do cálculo", parcelas, estilos))
    if not parcelas:
        historia.append(Spacer(1, 3 * mm))
        historia.append(_p("Nenhuma parcela registrada na memória.", estilos["corpo_fraco"]))

    historia.extend(_secao("Critérios", estilos))
    historia.append(
        KeepTogether(
            _tabela_pares(
                _criterios_pares(criterios, parcelas, bases),
                estilos,
                largura_rotulo=44 * mm,
                largura_total=LARGURA,
            )
        )
    )

    historia.extend(_secao("Bases e versionamento", estilos))
    if bases:
        historia.append(KeepTogether(_tabela_bases(bases, estilos)))
    else:
        historia.append(_p("Nenhuma base indexadora utilizada.", estilos["corpo_fraco"]))

    if avisos:
        historia.extend(_secao("Avisos", estilos))
        for aviso in avisos:
            historia.append(_p(f"• {aviso}", estilos["corpo_fraco"]))

    historia.extend(_metodologia_calculo(memoria, estilos, LARGURA))
    return historia


def montar_historia(memoria: dict) -> list:
    """Estrutura do PDF conforme a modalidade — mesmos estilos e identidade."""
    if str(memoria.get("tipo") or "") == "alimentos":
        return _historia_alimentos(memoria)
    return _historia_civel(memoria)


def _cabecalho_paginas(codigo: str, app_version: str, tamanho_texto: float = 8):
    def on_page(canvas, doc):
        canvas._codigo_memoria = codigo
        canvas._rodape_fonte = tamanho_texto
        if doc.page == 1:
            return
        largura, altura = canvas._pagesize
        canvas.saveState()
        canvas.setFont("Helvetica", tamanho_texto)
        canvas.setFillColor(TINTA_FRACA)
        canvas.drawString(
            MARGEM,
            altura - MARGEM + 2 * mm,
            f"{CABECALHO_APP} — Memória de cálculo",
        )
        sufixo = f"{codigo}" if not app_version else f"{codigo} • {app_version}"
        canvas.drawRightString(largura - MARGEM, altura - MARGEM + 2 * mm, sufixo)
        canvas.setStrokeColor(LINHA)
        canvas.setLineWidth(0.5)
        canvas.line(MARGEM, altura - MARGEM, largura - MARGEM, altura - MARGEM)
        canvas.restoreState()

    return on_page


def gerar_pdf(memoria: dict) -> bytes:
    """Gera o PDF da memória de cálculo sem recalcular nenhum valor."""
    historia = montar_historia(memoria)
    ident = memoria.get("identificacao") or {}
    codigo = memoria.get("codigo") or ""
    app_version = ident.get("app_version") or ""
    eh_alimentos = str(memoria.get("tipo") or "") == "alimentos"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=PAGINA_ALIMENTOS if eh_alimentos else PAGINA_CIVEL,
        leftMargin=MARGEM,
        rightMargin=MARGEM,
        topMargin=MARGEM + 6 * mm,
        bottomMargin=MARGEM + 7 * mm,
        title=f"{CABECALHO_APP} — Memória de cálculo {codigo}".strip(),
        author=CABECALHO_APP,
        subject="Memória de cálculo",
    )
    on_page = _cabecalho_paginas(codigo, app_version, 7.5 if eh_alimentos else 8)
    doc.build(
        historia,
        onFirstPage=on_page,
        onLaterPages=on_page,
        canvasmaker=_CanvasNumerado,
    )
    return buffer.getvalue()
