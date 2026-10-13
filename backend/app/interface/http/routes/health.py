from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request) -> dict[str, str]:
    """Liveness only: this does not check database connectivity."""
    settings = request.app.state.settings
    return {"status": "ok", "name": settings.name, "version": settings.version}
