from __future__ import annotations

import io
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.export.comum import (
    bases_txt,
    brl_memoria,
    criterios_txt,
    pct_memoria,
    regra_parcela_txt,
)

CABECALHO_APP = "Very Easy Calc"
MARGEM = 12 * mm


def _estilos() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle(
            "titulo",
            parent=base["Heading1"],
            alignment=TA_CENTER,
            fontSize=14,
            spaceAfter=4 * mm,
        ),
        "sub": ParagraphStyle(
            "sub",
            parent=base["Normal"],
            alignment=TA_CENTER,
            fontSize=9,
            textColor=colors.HexColor("#333333"),
        ),
        "secao": ParagraphStyle(
            "secao",
            parent=base["Heading2"],
            fontSize=11,
            spaceBefore=4 * mm,
            spaceAfter=2 * mm,
        ),
        "celula": ParagraphStyle(
            "celula",
            parent=base["Normal"],
            fontSize=7.5,
            leading=9,
            alignment=TA_LEFT,
        ),
        "celula_centro": ParagraphStyle(
            "celula_centro",
            parent=base["Normal"],
            fontSize=7.5,
            leading=9,
            alignment=TA_CENTER,
        ),
        "rodape": ParagraphStyle(
            "rodape",
            parent=base["Normal"],
            fontSize=7,
            textColor=colors.HexColor("#555555"),
        ),
    }


def _p(texto: object, estilo: ParagraphStyle) -> Paragraph:
    valor = "" if texto is None else str(texto)
    valor = valor.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(valor, estilo)


def _cabecalho_rodape(codigo: str, app_version: str, esquema: str):
    def on_page(canvas, doc):
        largura, altura = canvas._pagesize
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#222222"))
        canvas.drawString(
            MARGEM,
            altura - MARGEM + 2 * mm,
            f"{CABECALHO_APP} — memória de cálculo",
        )
        canvas.drawRightString(
            largura - MARGEM,
            altura - MARGEM + 2 * mm,
            f"{codigo} | app {app_version} | {esquema}",
        )
        canvas.setStrokeColor(colors.HexColor("#999999"))
        canvas.line(MARGEM, altura - MARGEM, largura - MARGEM, altura - MARGEM)
        canvas.line(MARGEM, MARGEM, largura - MARGEM, MARGEM)
        canvas.drawString(
            MARGEM,
            MARGEM - 2 * mm,
            f"Documento gerado a partir da memória de cálculo ({esquema}). "
            "Sem recálculo de valores.",
        )
        canvas.drawRightString(largura - MARGEM, MARGEM - 2 * mm, f"Página {doc.page}")
        canvas.restoreState()

    return on_page


def _tabela_pares(chaves_valores: Iterable[tuple[str, str]], estilo) -> Table:
    dados = [[_p(k, estilo), _p(v, estilo)] for k, v in chaves_valores]
    tabela = Table(dados, colWidths=[45 * mm, 130 * mm])
    tabela.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF2F7")),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#BBBBBB")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return tabela


def _colunas_parcelas(memoria: dict) -> list[tuple[str, int]]:
    tipo = memoria.get("tipo")
    alimentos = tipo == "alimentos"
    colunas: list[tuple[str, int]] = [
        ("Nº", 8),
        ("Competência", 16),
        ("Vencimento", 16),
        ("Regra / detalhe" if alimentos else "Verba / detalhe", 34),
        ("Principal", 18),
        ("Pagto.", 14),
        ("Diferença", 14),
        ("Saldo", 14),
        ("Início corr.", 14),
        ("Correção", 14),
        ("Índice", 14),
        ("Início juros", 14),
        ("Juros", 14),
        ("Multa", 12),
        ("Hon.", 12),
        ("Total", 18),
    ]
    if alimentos:
        colunas.insert(4, ("Salário mín.", 16))
        colunas.insert(5, ("% / regra", 20))
    return colunas


def _linha_parcela(parcela: dict, tem_alimentos: bool, estilo) -> list:
    correcao = parcela.get("correcao") or {}
    juros = parcela.get("juros") or {}
    multa = parcela.get("multa") or {}
    honorarios = parcela.get("honorarios") or {}
    pagamento = parcela.get("total_pago") or "0.00"
    verba = parcela.get("verba") or {}
    regra = (
        regra_parcela_txt(parcela)
        or verba.get("nome")
        or parcela.get("descricao")
        or ""
    )
    indice = correcao.get("fator_exibicao") or correcao.get("razao")

    linha_centro = [
        _p(parcela.get("numero"), estilo["celula_centro"]),
        _p(parcela.get("competencia_rotulo") or parcela.get("competencia"), estilo["celula_centro"]),
        _p(parcela.get("vencimento"), estilo["celula_centro"]),
    ]
    linha_centro.append(_p(regra, estilo["celula"]))
    if tem_alimentos:
        linha_centro.append(_p(brl_memoria(parcela.get("salario_minimo")), estilo["celula_centro"]))
        pct = parcela.get("percentual")
        detalhe = parcela.get("detalhe") or ""
        rotulo = pct_memoria(pct) if pct is not None else (detalhe or "—")
        linha_centro.append(_p(rotulo, estilo["celula_centro"]))

    linha_centro.extend(
        [
            _p(brl_memoria(parcela.get("principal")), estilo["celula_centro"]),
            _p(brl_memoria(pagamento), estilo["celula_centro"]),
            _p(brl_memoria(parcela.get("diferenca")) or "—", estilo["celula_centro"]),
            _p(brl_memoria(parcela.get("saldo")), estilo["celula_centro"]),
            _p(parcela.get("inicio_correcao") or "—", estilo["celula_centro"]),
            _p(brl_memoria(correcao.get("correcao")), estilo["celula_centro"]),
            _p(str(indice) if indice is not None else "—", estilo["celula_centro"]),
            _p(parcela.get("inicio_juros") or "—", estilo["celula_centro"]),
            _p(brl_memoria(juros.get("juros")), estilo["celula_centro"]),
            _p(brl_memoria(multa.get("valor")), estilo["celula_centro"]),
            _p(brl_memoria(honorarios.get("valor")), estilo["celula_centro"]),
            _p(brl_memoria(parcela.get("total")), estilo["celula_centro"]),
        ]
    )
    return linha_centro


def gerar_pdf(memoria: dict) -> bytes:
    """Gera PDF ReportLab exclusivamente a partir da memória de cálculo."""
    estilos = _estilos()
    ident = memoria.get("identificacao") or {}
    resumo = memoria.get("resumo") or {}
    criterios = memoria.get("criterios") or {}
    bases = memoria.get("bases") or []
    parcelas = memoria.get("parcelas") or []
    codigo = memoria.get("codigo") or ""
    app_version = ident.get("app_version") or ""
    esquema = memoria.get("esquema") or "memoria-calculo"

    buffer = io.BytesIO()
    paginas = landscape(A4)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=paginas,
        leftMargin=MARGEM,
        rightMargin=MARGEM,
        topMargin=MARGEM + 6 * mm,
        bottomMargin=MARGEM + 4 * mm,
        title=f"{CABECALHO_APP} — {codigo}",
        author=CABECALHO_APP,
    )

    historia: list = []
    historia.append(_p(CABECALHO_APP, estilos["titulo"]))
    historia.append(
        _p(
            f"Cálculo {codigo} — {memoria.get('tipo') or ''}",
            estilos["sub"],
        )
    )
    historia.append(Spacer(1, 3 * mm))

    historia.append(_p("Identificação", estilos["secao"]))
    historia.append(
        _tabela_pares(
            [
                ("Código", codigo),
                ("Título", ident.get("titulo") or "—"),
                ("Processo", ident.get("processo") or "—"),
                ("Parte", ident.get("parte") or "—"),
                ("Aplicativo", f"{ident.get('app_name') or CABECALHO_APP} {app_version}".strip()),
                ("Data de geração", ident.get("data_geracao") or "—"),
                ("Data-base", ident.get("data_base") or "—"),
                ("Esquema da memória", esquema),
            ],
            estilos["celula"],
        )
    )

    historia.append(_p("Critérios / configurações", estilos["secao"]))
    historia.append(_tabela_pares(criterios_txt(criterios), estilos["celula"]))

    verbas = criterios.get("verbas") or []
    if verbas:
        historia.append(_p("Verbas do cálculo", estilos["secao"]))
        linhas_verbas = []
        for v in verbas:
            correcao_txt = (
                f"correção desde {v.get('inicio_correcao')}"
                if v.get("inicio_correcao")
                else "correção não aplicada"
            )
            juros_txt = (
                f"juros desde {v.get('inicio_juros')}"
                if v.get("inicio_juros")
                else "juros não aplicados"
            )
            linhas_verbas.append(
                (
                    str(v.get("nome") or "—"),
                    f"{brl_memoria(v.get('valor'))} · base {v.get('data_base') or '—'} · "
                    f"{correcao_txt} · {juros_txt}",
                )
            )
        historia.append(_tabela_pares(linhas_verbas, estilos["celula"]))

    historia.append(_p("Bases e versionamento", estilos["secao"]))
    if bases:
        historia.append(_tabela_pares(bases_txt(bases), estilos["celula"]))
    else:
        historia.append(_p("Nenhuma base indexadora utilizada.", estilos["celula"]))

    historia.append(_p("Resumo dos valores", estilos["secao"]))
    historia.append(
        _tabela_pares(
            [
                ("Parcelas", str(resumo.get("qtd_parcelas", ""))),
                ("Período", f"{resumo.get('periodo_inicio') or '—'} a {resumo.get('periodo_fim') or '—'}"),
                ("Principal", brl_memoria(resumo.get("principal"))),
                ("Correção", brl_memoria(resumo.get("correcao"))),
                ("Juros", brl_memoria(resumo.get("juros"))),
                ("Multa", brl_memoria(resumo.get("multa"))),
                ("Honorários", brl_memoria(resumo.get("honorarios"))),
                ("Total", brl_memoria(resumo.get("total"))),
                ("Pagamentos", brl_memoria(resumo.get("pagamentos"))),
                ("Saldo", brl_memoria(resumo.get("saldo"))),
                ("Adicional", brl_memoria(resumo.get("adicional"))),
            ],
            estilos["celula"],
        )
    )

    avisos = memoria.get("avisos") or []
    if avisos:
        historia.append(_p("Avisos", estilos["secao"]))
        for aviso in avisos:
            historia.append(_p(f"• {aviso}", estilos["celula"]))

    historia.append(PageBreak())
    historia.append(_p("Detalhamento das parcelas", estilos["secao"]))

    tem_alimentos = bool(criterios.get("alimentos")) or any(
        p.get("regra") or p.get("tipo_regra") for p in parcelas
    )
    colunas = _colunas_parcelas({"tipo": memoria.get("tipo"), "alimentos": criterios.get("alimentos")})
    cabecalho = [_p(nome, estilos["celula_centro"]) for nome, _ in colunas]
    dados_tabela: list[list] = [cabecalho]
    for parcela in parcelas:
        dados_tabela.append(_linha_parcela(parcela, tem_alimentos, estilos))

    larguras = [larg * mm for _, larg in colunas]
    total_largura = sum(larguras)
    max_largura = paginas[0] - 2 * MARGEM
    if total_largura > max_largura:
        fator = max_largura / total_largura
        larguras = [w * fator for w in larguras]

    tabela_parcelas = Table(
        dados_tabela,
        colWidths=larguras,
        repeatRows=1,
        splitByRow=1,
    )
    estilo_tabela = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#AAAAAA")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9FC")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    tabela_parcelas.setStyle(TableStyle(estilo_tabela))
    historia.append(tabela_parcelas)

    if not parcelas:
        historia.append(Spacer(1, 4 * mm))
        historia.append(_p("Nenhuma parcela registrada na memória.", estilos["celula"]))

    doc.build(
        historia,
        onFirstPage=_cabecalho_rodape(codigo, app_version, esquema),
        onLaterPages=_cabecalho_rodape(codigo, app_version, esquema),
    )
    return buffer.getvalue()
