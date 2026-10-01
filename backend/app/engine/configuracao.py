from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.engine.correcao import ConfigCorrecao
from app.engine.encargos import ConfigEncargo
from app.engine.juros import ConfigJuros


@dataclass(frozen=True)
class ConfiguracaoCalculo:
    data_base: date
    correcao: ConfigCorrecao = field(default_factory=ConfigCorrecao)
    juros: ConfigJuros = field(default_factory=ConfigJuros)
    multa: ConfigEncargo = field(default_factory=ConfigEncargo)
    honorarios: ConfigEncargo = field(default_factory=ConfigEncargo)

    def __post_init__(self) -> None:
        if isinstance(self.data_base, str):
            object.__setattr__(self, "data_base", date.fromisoformat(self.data_base))
