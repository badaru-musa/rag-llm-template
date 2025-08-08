from typing import Callable
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.exceptions import BaseRAGException, create_http_exception
from app.logger import logger


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware for handling exceptions and errors"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response
            
        except BaseRAGException as exc:
            # Handle custom RAG exceptions
            logger.error(
                f"RAG Exception occurred",
                extra={
                    "request_id": getattr(request.state, "request_id", None),
                    "exception_type": type(exc).__name__,
                    "message": exc.message,
                    "details": exc.details,
                    "status_code": exc.status_code,
                }
            )
            
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "message": exc.message,
                    "details": exc.details,
                    "request_id": getattr(request.state, "request_id", None),
                }
            )
            
        except HTTPException as exc:
            # Handle FastAPI HTTP exceptions
            logger.warning(
                f"HTTP Exception occurred",
                extra={
                    "request_id": getattr(request.state, "request_id", None),
                    "status_code": exc.status_code,
                    "detail": exc.detail,
                }
            )
            
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "message": exc.detail,
                    "request_id": getattr(request.state, "request_id", None),
                }
            )
            
        except Exception as exc:
            # Handle unexpected exceptions
            import traceback
            logger.error(
                f"Unexpected exception occurred: {str(exc)}",
                extra={
                    "request_id": getattr(request.state, "request_id", None),
                    "exception_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                },
                exc_info=True
            )
            
            return JSONResponse(
                status_code=500,
                content={
                    "message": "Internal server error",
                    "request_id": getattr(request.state, "request_id", None),
                }
            )
