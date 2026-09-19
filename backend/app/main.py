"""The service. One process, one port: the API and the built frontend together.

Stateless by design. No database, no accounts, no session — a request carries
everything, including the plan the user was last shown, and nothing about it
survives the response. That is the security story as much as the architecture:
there is no store of anyone's transactions to breach.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from typing import Literal

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.accounts.product import sample_account
from app.candidates import generate
from app.chat import ChatUnavailable, ChatUpstreamError, chat, status as chat_status
from app.chat.schemas import ChatRequest, ChatResponse, ChatStatus
from app.nessie import NessieUnavailable, NessieUpstreamError
from app.nessie.roundtrip import account_from_nessie
from app.schemas import (
    CandidatesRequest,
    CandidatesResponse,
    NessieAccountResponse,
    SampleAccountRequest,
    SampleAccountResponse,
    SolveRequest,
    SolveResponse,
)
from app.solver.errors import EngineUnavailable
from app.solver.solve import solve


def _default_dist() -> Path:
    """Where the built frontend lives, on a laptop and on the box alike.

    This was `parents[2] / "frontend" / "dist"`, which is right here and wrong in
    production. deploy.sh rsyncs `backend/app/` to `$APP_DIR/app/`, so `backend/`
    is never recreated on the server: `__file__` is
    /opt/overdraft-guard/app/main.py, parents[2] is /opt, and the app looked for
    /opt/frontend/dist while the bundle sat in /opt/overdraft-guard/frontend/dist.

    The mount below is guarded by `is_dir()`, so it failed SILENTLY — the API
    answered, /health returned 200, deploy.sh printed "deployed", and the site
    was a 404. A green deploy you only discover on stage.

    The layout is decided by the directory name, not by whether `dist/` happens
    to exist: `dist/` is gitignored and absent from a fresh checkout, so probing
    for it would make the answer depend on whether anyone had run a build.
    """
    override = os.environ.get("OVERDRAFT_DIST")
    if override:
        return Path(override)
    here = Path(__file__).resolve()
    root = here.parents[1]  # <repo>/backend on a laptop, $APP_DIR on the box

    # In a checkout this directory is named `backend` by the repo's own layout —
    # not a setting, so the test below is safe there.
    #
    # On the box it is $APP_DIR, which IS a setting (deploy.sh:
    # APP_DIR="${APP_DIR:-/opt/overdraft-guard}"), so a box deployed to
    # /opt/backend would match this test and resolve to /opt/frontend/dist — the
    # exact silent 404 this function exists to prevent. The box therefore does not
    # rely on this inference at all: deploy.sh writes OVERDRAFT_DIST into
    # /etc/overdraft-guard.env and the override above wins. This branch is the
    # local-development path.
    if root.name == "backend":
        root = root.parent
    return root / "frontend" / "dist"


DEFAULT_DIST = _default_dist()


def create_app(dist_dir: Path | None = DEFAULT_DIST) -> FastAPI:
    app = FastAPI(title="Overdraft Guard", docs_url="/api/docs", openapi_url="/api/openapi.json")

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

    @app.exception_handler(NessieUnavailable)
    async def _nessie_unavailable(_: Request, exc: NessieUnavailable) -> JSONResponse:
        # No key, or a key the sandbox will not confirm. The client offers the
        # modelled account instead. Never an empty account: a blank screen reads
        # as data, and this is the one failure that must not look like a fact.
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(NessieUpstreamError)
    async def _nessie_upstream(_: Request, exc: NessieUpstreamError) -> JSONResponse:
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

    @app.post("/api/accounts/sample", response_model=SampleAccountResponse)
    def api_sample_account(req: SampleAccountRequest) -> SampleAccountResponse:
        return SampleAccountResponse.model_validate(
            sample_account(
                seed=req.seed,
                as_of=date.fromisoformat(req.as_of) if req.as_of else None,
                horizon_days=req.horizon_days,
            )
        )

    # Seeds a sandbox account from a modelled one and reads it back. Whole
    # dollars, because that is what Nessie stores; `not_round_tripped` names
    # every row the sandbox did not return unchanged.
    @app.post("/api/accounts/nessie", response_model=NessieAccountResponse)
    def api_nessie_account(req: SampleAccountRequest) -> NessieAccountResponse:
        return NessieAccountResponse.model_validate(account_from_nessie(req))

    # Mounted last. A mount at "/" registered first would shadow every route
    # above it, and the API would answer 404 for /health and 405 for the two
    # /api routes. The sample-account route above is inside the same window; a
    # route added below this mount is silently shadowed and answers 405.
    if dist_dir is not None and dist_dir.is_dir():
        app.mount("/", StaticFiles(directory=dist_dir, html=True), name="frontend")

    return app


app = create_app()
