import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Each error's `ctx` can embed a raw exception object (e.g. a validator's ValueError),
        # which plain JSONResponse can't serialize. Drop it — `msg` already has the text — and
        # run the rest through jsonable_encoder for any other non-JSON types (UUID, etc.).
        details = [{k: v for k, v in err.items() if k != "ctx"} for err in exc.errors()]
        return JSONResponse(
            status_code=422, content={"error": "Validation failed", "details": jsonable_encoder(details)}
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"error": "Internal server error"})
