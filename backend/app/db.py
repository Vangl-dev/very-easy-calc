from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import DATABASE_DIR, get_settings
from app.models.entities import Base, IndexerVersion

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def configure(database_url: str | None = None) -> Engine:
    global _engine, _session_factory
    url = database_url or get_settings().database_url
    conect_args: dict = {}
    if url.startswith("sqlite"):
        conect_args = {"check_same_thread": False}
        caminho = url.split("///", 1)[-1]
        if caminho and caminho != ":memory:":
            Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(url, connect_args=conect_args)
    _session_factory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        configure()
    assert _engine is not None
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    if _session_factory is None:
        configure()
    assert _session_factory is not None
    return _session_factory


def init_db() -> None:
    Base.metadata.create_all(get_engine())


def reset() -> None:
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def seed_indexer_versions(session: Session) -> list[IndexerVersion]:
    from app.indexers import chaves, obter
    from app.indexers.base import arquivo_hash

    criadas: list[IndexerVersion] = []
    for key in chaves():
        indexador = obter(key)
        meta = indexador.metadata
        existente = session.scalar(
            select(IndexerVersion).where(
                IndexerVersion.key == meta.key,
                IndexerVersion.version == meta.version,
            )
        )
        if existente is not None:
            continue
        digest = ""
        if indexador.arquivo_dados and indexador.arquivo_dados.exists():
            digest = arquivo_hash(indexador.arquivo_dados)
        registro = IndexerVersion(
            key=meta.key,
            name=meta.name,
            kind=meta.kind,
            source=meta.source,
            source_url=meta.source_url,
            version=meta.version,
            updated_at=meta.updated_at,
            coverage_start=meta.cobertura.inicio.key,
            coverage_end=meta.cobertura.fim.key,
            total_records=meta.total_records,
            content_sha256=digest,
        )
        session.add(registro)
        criadas.append(registro)
    session.flush()
    return criadas
