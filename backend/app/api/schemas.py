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


class ConfigEncargoSchema(BaseModel):
    aplicar: bool = False
    percentual: str | None = None
    valor_fixo: str | None = None
    base: str = "corrigido"


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


class CalculoRequest(BaseModel):
    tipo: Literal["alimentos", "parcelas"]
    titulo: str = ""
    processo: str = ""
    parte: str = ""
    data_base: str
    alimentos: AlimentosSchema | None = None
    parcelas: list[ParcelaManualSchema] | None = None
    correcao: ConfigCorrecaoSchema | None = None
    juros: ConfigJurosSchema | None = None
    multa: ConfigEncargoSchema | None = None
    honorarios: ConfigEncargoSchema | None = None
    pagamentos: list[PagamentoSchema] = []

    @field_validator("data_base")
    @classmethod
    def _data_base_valida(cls, v: str) -> str:
        if not str(v).strip():
            raise ValueError("data_base é obrigatória")
        return v.strip()
