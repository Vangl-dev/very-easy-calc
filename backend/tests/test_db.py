from __future__ import annotations

import pytest
from sqlalchemy import select

from app import db
from app.models.entities import IndexerVersion


@pytest.fixture()
def session():
    db.configure("sqlite:///:memory:")
    db.init_db()
    with db.session_scope() as s:
        yield s
    db.reset()


def test_seed_registra_bases_indexadoras(session) -> None:
    criadas = db.seed_indexer_versions(session)
    assert len(criadas) == 5
    registro = session.scalar(
        select(IndexerVersion).where(IndexerVersion.key == "tjsp_tabela_pratica")
    )
    assert registro is not None
    assert registro.key == "tjsp_tabela_pratica"
    assert registro.version == "2026.09"
    assert registro.coverage_start == "1992-01"
    assert registro.coverage_end == "2026-09"
    assert registro.total_records == 417
    assert registro.kind == "correcao"
    assert len(registro.content_sha256) == 64


def test_seed_e_idempotente(session) -> None:
    assert len(db.seed_indexer_versions(session)) == 5
    assert len(db.seed_indexer_versions(session)) == 0
    registros = session.scalars(select(IndexerVersion)).all()
    assert len(registros) == 5


def test_versoes_distintas_coexistem(session) -> None:
    db.seed_indexer_versions(session)
    session.add(
        IndexerVersion(
            key="tjsp_tabela_pratica",
            name="Tabela Prática TJSP",
            kind="correcao",
            source="AASP",
            source_url="",
            version="2026.10",
            updated_at="2026-11-01",
            coverage_start="1992-01",
            coverage_end="2026-10",
            total_records=418,
            content_sha256="0" * 64,
        )
    )
    session.flush()
    registros = session.scalars(select(IndexerVersion)).all()
    assert len(registros) == 6
    versoes = sorted(r.version for r in registros if r.key == "tjsp_tabela_pratica")
    assert versoes == ["2026.09", "2026.10"]
