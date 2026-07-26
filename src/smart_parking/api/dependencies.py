"""FastAPI dependency injection helpers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from smart_parking.api.runtime import AppContext, StatusStore
from smart_parking.persistence.repository import EventRepository


def get_app_context(request: Request) -> AppContext:
    """Return the application context attached during app factory setup."""
    context = getattr(request.app.state, "context", None)
    if not isinstance(context, AppContext):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API application context is not configured.",
        )
    return context


def get_status_store(context: Annotated[AppContext, Depends(get_app_context)]) -> StatusStore:
    return context.store


def get_repository(
    context: Annotated[AppContext, Depends(get_app_context)],
) -> EventRepository:
    if context.repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Event persistence is not configured. Enable persistence.enabled "
                "or inject a repository when creating the app."
            ),
        )
    return context.repository


AppContextDep = Annotated[AppContext, Depends(get_app_context)]
StatusStoreDep = Annotated[StatusStore, Depends(get_status_store)]
RepositoryDep = Annotated[EventRepository, Depends(get_repository)]
