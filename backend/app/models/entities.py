from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class IndexerVersion(Base):
    __tablename__ = "indexer_versions"
    __table_args__ = (UniqueConstraint("key", "version", name="uq_indexer_key_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    source_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    coverage_start: Mapped[str] = mapped_column(String(7), nullable=False)
    coverage_end: Mapped[str] = mapped_column(String(7), nullable=False)
    total_records: Mapped[int] = mapped_column(Integer, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class Calculo(Base):
    __tablename__ = "calculos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    tipo: Mapped[str] = mapped_column(String(32), nullable=False, default="civel")
    titulo: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    processo: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    parte: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    app_version: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    resultado_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    bases_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
