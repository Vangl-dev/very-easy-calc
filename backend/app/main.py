from __future__ import annotations

import json
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import CalculoRequest
from app.api.service import executar_calculo
from app.core.config import get_settings
from app.db import get_session, init_db, seed_indexer_versions, session_scope
from app.indexers import CoverageError, IndexerError, listar_metadata, obter
from app.models.entities import Calculo, IndexerVersion


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    with session_scope() as session:
        seed_indexer_versions(session)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(CoverageError)
    async def coverage_handler(_, exc: CoverageError):
        return JSONResponse(
            status_code=422,
            content={
                "erro": "cobertura_insuficiente",
                "mensagem": str(exc),
                "indexador": exc.nome,
                "competencia_solicitada": exc.solicitado.label,
                "cobertura": {
                    "inicio": exc.cobertura.inicio.label,
                    "fim": exc.cobertura.fim.label,
                },
            },
        )

    @app.exception_handler(IndexerError)
    async def indexer_handler(_, exc: IndexerError):
        return JSONResponse(status_code=400, content={"erro": "indexador", "mensagem": str(exc)})

    @app.exception_handler(ValueError)
    async def value_error_handler(_, exc: ValueError):
        return JSONResponse(status_code=422, content={"erro": "validacao", "mensagem": str(exc)})

    @app.get("/api/health")
    def health():
        return {"status": "ok", "app": settings.app_name, "version": settings.app_version}

    @app.get("/api/indexers")
    def indexers(session: Session = Depends(get_session)):
        registros = session.scalars(select(IndexerVersion)).all()
        versionadas = {(r.key, r.version) for r in registros}
        resposta = []
        for meta in listar_metadata():
            item = meta.as_dict()
            item["registrada"] = (meta.key, meta.version) in versionadas
            item["unidade"] = obter(meta.key).unidade()
            resposta.append(item)
        return {"app_version": settings.app_version, "indexers": resposta}

    @app.get("/api/calculos")
    def listar_calculos(session: Session = Depends(get_session)):
        linhas = session.scalars(select(Calculo).order_by(Calculo.id.desc())).all()
        return [
            {
                "codigo": c.codigo,
                "tipo": c.tipo,
                "titulo": c.titulo,
                "processo": c.processo,
                "parte": c.parte,
                "app_version": c.app_version,
                "created_at": c.created_at.isoformat(),
            }
            for c in linhas
        ]

    @app.post("/api/calculos", status_code=201)
    def criar_calculo(payload: CalculoRequest):
        with session_scope() as session:
            return executar_calculo(payload, session)

    @app.get("/api/calculos/{codigo}")
    def obter_calculo(codigo: str, session: Session = Depends(get_session)):
        registro = _carregar_calculo(codigo, session)
        corpo = json.loads(registro.resultado_json)
        corpo["codigo"] = registro.codigo
        corpo["titulo"] = registro.titulo
        corpo["processo"] = registro.processo
        corpo["parte"] = registro.parte
        corpo["created_at"] = registro.created_at.isoformat()
        corpo["memoria"] = json.loads(registro.memoria_json or "{}")
        return corpo

    @app.get("/api/calculos/{codigo}/memoria")
    def obter_memoria(codigo: str, session: Session = Depends(get_session)):
        registro = _carregar_calculo(codigo, session)
        return json.loads(registro.memoria_json or "{}")

    def _carregar_calculo(codigo: str, session: Session) -> Calculo:
        registro = session.scalar(select(Calculo).where(Calculo.codigo == codigo))
        if registro is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "erro": "nao_encontrado",
                    "mensagem": f"cálculo {codigo} não encontrado",
                },
            )
        return registro

    return app


app = create_app()
