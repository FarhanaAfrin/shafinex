import logging

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import create_token, require_auth, verify_password
from ..schemas import LoginRequest, LoginResponse

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    if not verify_password(payload.password):
        log.warning("failed login attempt")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect password")
    token, expires_at = create_token()
    log.info("login ok")
    return LoginResponse(token=token, expires_at=expires_at)


@router.get("/me")
def me(_: str = Depends(require_auth)):
    return {"authenticated": True}
