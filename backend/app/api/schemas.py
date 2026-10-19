from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class RegraAlimentoSchema(BaseModel):
    inicio: str
    fim: str | None = None
    tipo: Literal["salario_minimo", "fixo"]
    percentual: str | None = None
    valor: str | None = None
    descricao: str = ""

    @field_validator("inicio")
    @classmethod
    def _inicio_valido(cls, v: str) -> str:
        if not str(v).strip():
            raise ValueError("início da regra de alimentos é obrigatório")
        return v.strip()


class PagamentoSchema(BaseModel):
    data: str
    valor: str
    descricao: str = ""
    competencia: str | None = None


class ConfigCorrecaoSchema(BaseModel):
    aplicar: bool = True
    indexador: str = "tjsp_tabela_pratica"
    termo_inicial: str | None = None
    termo_final: str | None = None


class ConfigJurosSchema(BaseModel):
    aplicar: bool = True
    modalidade: str = "taxa_legal"
    taxa: str | None = None
    unidade: str = "mensal"
    base: str = "corrigido"
    inicio: str | None = None
    fim: str | None = None


class ConfigEncargoSchema(BaseModel):
    aplicar: bool = False
    percentual: str | None = None
    valor_fixo: str | None = None
    base: str = "corrigido"


class EncargoConsolidadoSchema(BaseModel):
    id: str
    tipo: Literal["multa", "honorarios", "juros"]
    ordem: int = Field(ge=1)
    verba_ids: list[str] = []
    componentes: list[Literal["principal", "principal_corrigido", "juros_individuais"]] = []
    predecessores: list[str] = []
    percentual: str | None = None
    valor_fixo: str | None = None
    juros: ConfigJurosSchema | None = None
    inicio: str | None = None
    fim: str | None = None
    entra_no_total: bool = True


class AlimentosSchema(BaseModel):
    regras: list[RegraAlimentoSchema] = Field(min_length=1)
    ate: str
    dia_vencimento: int = 10


class ParcelaManualSchema(BaseModel):
    numero: int
    vencimento: str
    principal: str
    descricao: str = ""
    pagamentos: list[PagamentoSchema] = []
    correcao: ConfigCorrecaoSchema | None = None
    juros: ConfigJurosSchema | None = None
    multa: ConfigEncargoSchema | None = None
    honorarios: ConfigEncargoSchema | None = None


class RegimeAtualizacaoSchema(BaseModel):
    """Período da verba com critério próprio de atualização.

    - data_inicio nulo = desde o início da verba;
    - data_fim nulo = aberto até a data final do cálculo;
    - criterio = critério combinado (ex.: "selic"), quando aplicável.
    """

    data_inicio: str | None = None
    data_fim: str | None = None
    correcao: str | None = None
    juros: ConfigJurosSchema | None = None
    criterio: str | None = None


class VerbaSchema(BaseModel):
    """Rubrica do cálculo Cível.

    - tipo "valor": principal = valor (comportamento histórico).
    - tipo "percentual": principal = percentual × principal da verba-base
      (base_verba_id). O percentual é fração (0.12 = 12%).
    - entra_no_total: se a verba compõe o total da execução. Nulo = padrão
      histórico (a verba usada como base por outra fica fora do total), para
      manter compatibilidade com cálculos já salvos. Explícito sempre vale.
    """

    id: str | None = None
    tipo: Literal["valor", "percentual"] = "valor"
    nome: str
    valor: str | None = None
    data_base: str
    descricao: str = ""
    base_verba_id: str | None = None
    percentual: str | None = None
    entra_no_total: bool | None = None
    correcao: ConfigCorrecaoSchema | None = None
    juros: ConfigJurosSchema | None = None
    multa: ConfigEncargoSchema | None = None
    honorarios: ConfigEncargoSchema | None = None
    pagamentos: list[PagamentoSchema] = []
    parcelas: list[ParcelaManualSchema] = []
    regimes: list[RegimeAtualizacaoSchema] = []

    @field_validator("nome")
    @classmethod
    def _nome_obrigatorio(cls, v: str) -> str:
        if not str(v).strip():
            raise ValueError("nome da verba é obrigatório")
        return v.strip()

    @field_validator("id", "base_verba_id", "percentual", "valor")
    @classmethod
    def _texto_opcional(cls, v: str | None) -> str | None:
        if v is None:
            return None
        texto = str(v).strip()
        return texto or None


class ValorBaseSchema(BaseModel):
    valor: str
    data_base: str
    descricao: str = ""


class OverrideIndexadorSchema(BaseModel):
    competencia: str
    valor: str
    fonte: str
    observacao: str = ""

    @field_validator("fonte")
    @classmethod
    def _fonte_obrigatoria(cls, v: str) -> str:
        if not str(v).strip():
            raise ValueError("fonte é obrigatória no cadastro manual")
        return v.strip()


class CalculoRequest(BaseModel):
    tipo: Literal["alimentos", "parcelas", "atualizacao"]
    titulo: str = ""
    revisao_de: str | None = None
    processo: str = ""
    parte: str = ""
    data_base: str
    data_final: str | None = None
    valor_base: ValorBaseSchema | None = None
    alimentos: AlimentosSchema | None = None
    parcelas: list[ParcelaManualSchema] | None = None
    verbas: list[VerbaSchema] | None = None
    correcao: ConfigCorrecaoSchema | None = None
    juros: ConfigJurosSchema | None = None
    multa: ConfigEncargoSchema | None = None
    honorarios: ConfigEncargoSchema | None = None
    encargos_consolidados: list[EncargoConsolidadoSchema] = []
    pagamentos: list[PagamentoSchema] = []

    @field_validator("data_base")
    @classmethod
    def _data_base_valida(cls, v: str) -> str:
        if not str(v).strip():
            raise ValueError("data_base é obrigatória")
        return v.strip()
