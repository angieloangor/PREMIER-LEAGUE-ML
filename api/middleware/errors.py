from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.schemas.errors import ErrorResponse
from api.services.feature_service import FeatureValidationError


logger = logging.getLogger("match_predictor_api")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(FeatureValidationError)
    async def handle_feature_validation_error(request: Request, exc: FeatureValidationError):
        detail = exc.args[1] if len(exc.args) > 1 else None
        payload = ErrorResponse(
            error="feature_validation_error",
            message=str(exc.args[0]),
            details=detail,
            request_id=getattr(request.state, "request_id", None),
        )
        return JSONResponse(status_code=422, content=payload.model_dump())

    @app.exception_handler(KeyError)
    async def handle_key_error(request: Request, exc: KeyError):
        payload = ErrorResponse(
            error="model_not_found",
            message=str(exc),
            details=None,
            request_id=getattr(request.state, "request_id", None),
        )
        return JSONResponse(status_code=404, content=payload.model_dump())

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(request: Request, exc: RequestValidationError):
        payload = ErrorResponse(
            error="request_validation_error",
            message="Request body, query params or uploaded file are invalid.",
            details=exc.errors(),
            request_id=getattr(request.state, "request_id", None),
        )
        return JSONResponse(status_code=422, content=payload.model_dump())

    @app.exception_handler(Exception)
    async def handle_generic_error(request: Request, exc: Exception):
        logger.exception("Unhandled error while serving request.")
        payload = ErrorResponse(
            error="internal_server_error",
            message="Unexpected server error.",
            details=None,
            request_id=getattr(request.state, "request_id", None),
        )
        return JSONResponse(status_code=500, content=payload.model_dump())
