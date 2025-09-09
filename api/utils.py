from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

class APIStatus:
    # Set the constant.
    NOT_FOUND = "NOT_FOUND"
    OK = "OK"
    ERROR = "ERROR"
    INVALID = "INVALID"

async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": exc.detail.get("status", APIStatus.ERROR),
            "data": exc.detail.get("data", []),
            "message": exc.detail.get("message", "An error occurred.")
        }
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    error_messages = [
        f"{error['loc'][-1]}: {error['msg']}" for error in errors
    ]
    message = "Invalid input: " + "; ".join(error_messages)

    return JSONResponse(
        status_code=400,
        content={
            "status": APIStatus.INVALID,
            "data": [],
            "message": message
        }
    )
