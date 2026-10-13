from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config.settings import Settings
from app.infrastructure.database.connector import lifespan
from app.interface.http.routes.auth import router as auth_router
from app.interface.http.routes.data import router as data_router
from app.interface.http.routes.health import router as health_router


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings if settings is not None else Settings()
    application = FastAPI(title=config.name, version=config.version, lifespan=lifespan)
    application.state.settings = config

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # ไม่ส่ง input ของ password กลับไปใน validation errors
        errors = [
            {key: error[key] for key in ("type", "loc", "msg") if key in error}
            for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": errors})

    application.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["Content-Type", "Authorization"],
    )
    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(auth_router, prefix="/api/v1/users", include_in_schema=False)
    application.include_router(data_router)
    application.include_router(data_router, prefix="/api/v1", include_in_schema=False)
    return application


app = create_app()
