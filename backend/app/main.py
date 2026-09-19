"""The service. One process, one port: the API and the built frontend together.

Stateless by design. No database, no accounts, no session — a request carries
everything, including the plan the user was last shown, and nothing about it
survives the response. That is the security story as much as the architecture:
there is no store of anyone's transactions to breach.
"""

from __future__ import annotations

from pathlib import Path

from typing import Literal

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.candidates import generate
from app.chat import ChatUnavailable, ChatUpstreamError, chat, status as chat_status
from app.chat.schemas import ChatRequest, ChatResponse, ChatStatus
from app.schemas import (
    CandidatesRequest,
    CandidatesResponse,
    SolveRequest,
    SolveResponse,
)
from app.solver.errors import EngineUnavailable
from app.solver.solve import solve

DEFAULT_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def create_app(dist_dir: Path | None = DEFAULT_DIST) -> FastAPI:
    app = FastAPI(title="Safe to Spend", docs_url="/api/docs", openapi_url="/api/openapi.json")

    # Vite's dev server proxies /api here; in production the two are same-origin
    # because this process serves the built files below.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(EngineUnavailable)
    async def _engine_unavailable(_: Request, exc: EngineUnavailable) -> JSONResponse:
        # 503, not 500: the request was well formed and the service is simply
        # unable to answer it exactly right now. Never a heuristic answer.
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(ChatUnavailable)
    async def _chat_unavailable(_: Request, exc: ChatUnavailable) -> JSONResponse:
        # No key on the server. The UI shows the explainer as off; the solver
        # is unaffected.
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(ChatUpstreamError)
    async def _chat_upstream(_: Request, exc: ChatUpstreamError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/solve", response_model=SolveResponse)
    def api_solve(req: SolveRequest) -> SolveResponse:
        return solve(req)

    @app.post("/api/candidates", response_model=CandidatesResponse)
    def api_candidates(req: CandidatesRequest) -> CandidatesResponse:
        return generate(req)

    # The explainer. Gemini puts words to a solve the client already has; the
    # numbers in the reply can only come from the request body. `source` says
    # whether the client's numbers came from this server or its local fallback,
    # so the answer can be honest about provenance.
    @app.get("/api/chat/status", response_model=ChatStatus)
    def api_chat_status() -> ChatStatus:
        return chat_status()

    @app.post("/api/chat", response_model=ChatResponse)
    def api_chat(
        req: ChatRequest, source: Literal["server", "local"] = Query(default="server")
    ) -> ChatResponse:
        return chat(req, source=source)

    # Mounted last. A mount at "/" registered first would shadow every route
    # above it, and the API would answer 404 for /health and 405 for the two
    # /api routes.
    if dist_dir is not None and dist_dir.is_dir():
        app.mount("/", StaticFiles(directory=dist_dir, html=True), name="frontend")

    return app


app = create_app()
