# services/tracking-service/app/core/auth.py
# ============================================================
# AUTHENTICATION & AUTHORIZATION
# ============================================================
# This file answers two questions:
#   1. WHO are you?       → get_current_user() reads headers set by the Gateway
#   2. CAN you do this?   → verify_resource_access() checks business rules
#
# How the flow works:
#   Gateway validates JWT → strips it → adds headers (X-User-ID, X-User-Role)
#   This file reads those headers → builds a CurrentUser object
#   Routes use CurrentUser to enforce permissions
# ============================================================

from fastapi import HTTPException, Header, Depends
from typing import Optional


# ─────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────

VALID_ROLES = {"CLIENT", "ADMIN", "DRIVER"}


# ─────────────────────────────────────────────────────────────
# CURRENT USER CLASS
# Who is making this request?
# ─────────────────────────────────────────────────────────────

class CurrentUser:
    """
    Represents the authenticated user extracted from request headers.

    The API Gateway validates the JWT token and injects these headers:
        X-User-ID    → unique identifier of the user
        X-User-Role  → their role: CLIENT, ADMIN, or DRIVER
        X-Token-Exp  → token expiry (Unix timestamp)

    We never handle raw JWT tokens here — the Gateway already did that job.
    We simply trust the headers it sends us (because only the Gateway can set them).
    """

    def __init__(
        self,
        user_id: str,
        role: str,
        token_exp: Optional[int] = None,
    ):
        self.user_id = user_id
        self.role = role.upper()       # Always uppercase — safe comparison
        self.token_exp = token_exp

    # ----------------------------------------------------------
    # Convenience properties — so routes read like plain English
    # ----------------------------------------------------------

    @property
    def is_admin(self) -> bool:
        """ADMIN can do everything: view all, update, delete."""
        return self.role == "ADMIN"

    @property
    def is_client(self) -> bool:
        """CLIENT can only touch their own shipments."""
        return self.role == "CLIENT"

    @property
    def is_driver(self) -> bool:
        """DRIVER can only touch shipments assigned to them."""
        return self.role == "DRIVER"

    def __repr__(self) -> str:
        return f"<CurrentUser id={self.user_id} role={self.role}>"


# ─────────────────────────────────────────────────────────────
# STEP 1 — EXTRACT USER FROM REQUEST HEADERS
# FastAPI dependency: injected automatically into every route
# ─────────────────────────────────────────────────────────────

async def get_current_user(
    x_user_id: Optional[str] = Header(default=None, alias="X-User-ID"),
    x_user_role: Optional[str] = Header(default=None, alias="X-User-Role"),
    x_token_exp: Optional[int] = Header(default=None, alias="X-Token-Exp"),
) -> CurrentUser:
    """
    FastAPI dependency that reads and validates identity headers.

    Used in routes like:
        current_user: CurrentUser = Depends(get_current_user)

    If headers are missing or invalid → raises 401 and the route never runs.
    If everything is valid → returns a CurrentUser object.

    401 = "I don't know who you are" (missing/bad identity)
    403 = "I know who you are, but you can't do this" (no permission)
    """

    # ── Guard 1: X-User-ID must be present ──────────────────
    if not x_user_id:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "UNAUTHORIZED",
                "error_code": "MISSING_USER_ID",
                "detail": (
                    "Missing X-User-ID header. "
                    "All requests must pass through the API Gateway."
                ),
            },
        )

    # ── Guard 2: X-User-Role must be present ────────────────
    if not x_user_role:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "UNAUTHORIZED",
                "error_code": "MISSING_USER_ROLE",
                "detail": "Missing X-User-Role header.",
            },
        )

    # ── Guard 3: Role must be one we recognise ───────────────
    if x_user_role.upper() not in VALID_ROLES:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "UNAUTHORIZED",
                "error_code": "INVALID_ROLE",
                "detail": (
                    f"Role '{x_user_role}' is not recognized. "
                    f"Must be one of: {sorted(VALID_ROLES)}"
                ),
            },
        )

    # ── All good — build and return the user object ──────────
    return CurrentUser(
        user_id=x_user_id,
        role=x_user_role,
        token_exp=x_token_exp,
    )


# ─────────────────────────────────────────────────────────────
# STEP 2 — ROLE SHORTCUT DEPENDENCIES
# Use these when an endpoint belongs to ONE specific role only
# ─────────────────────────────────────────────────────────────

async def require_admin(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """
    Dependency: only ADMIN users may proceed.

    Usage:
        current_user: CurrentUser = Depends(require_admin)

    Anyone who is not ADMIN receives 403 Forbidden immediately.
    Example endpoint: DELETE /shipments/{id}, GET /shipments (list all)
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "FORBIDDEN",
                "error_code": "ADMIN_REQUIRED",
                "detail": "This action requires ADMIN privileges.",
            },
        )
    return current_user


async def require_client(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """
    Dependency: only CLIENT users may proceed.

    Usage:
        current_user: CurrentUser = Depends(require_client)

    Example endpoint: GET /my-shipments
    """
    if not current_user.is_client:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "FORBIDDEN",
                "error_code": "CLIENT_REQUIRED",
                "detail": "This action is for CLIENT users only.",
            },
        )
    return current_user


async def require_driver(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """
    Dependency: only DRIVER users may proceed.

    Usage:
        current_user: CurrentUser = Depends(require_driver)

    Example endpoint: GET /assigned-deliveries
    """
    if not current_user.is_driver:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "FORBIDDEN",
                "error_code": "DRIVER_REQUIRED",
                "detail": "This action is for DRIVER users only.",
            },
        )
    return current_user


# ─────────────────────────────────────────────────────────────
# STEP 3 — RESOURCE-LEVEL ACCESS CHECK
# Not just "what role are you?" but "can you touch THIS object?"
# ─────────────────────────────────────────────────────────────

def verify_resource_access(shipment, current_user: CurrentUser) -> None:
    """
    Business-rule authorization check for a specific shipment.

    Call this AFTER confirming the shipment exists (do the 404 check first).
    This function only decides: does this user have permission to see/touch it?

    Rules (from PHASE_1A design):
        ADMIN  → always allowed (can see and touch everything)
        CLIENT → allowed only if shipment.created_by == their user_id
        DRIVER → allowed only if shipment.assigned_driver_id == their user_id

    Raises:
        HTTPException 403 if access is denied
    Returns:
        None if access is granted (caller continues normally)

    Example usage in a route:
        shipment = db.query(Shipment).filter(Shipment.id == id).first()
        if not shipment:
            raise HTTPException(404, ...)          # ← 404 first
        verify_resource_access(shipment, current_user)  # ← then 403 check
        return shipment                             # ← then return data
    """

    # ── ADMIN: no restrictions ───────────────────────────────
    if current_user.is_admin:
        return  # ✅ granted

    # ── CLIENT: must be the one who created this shipment ────
    if current_user.is_client:
        if shipment.created_by != current_user.user_id:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "FORBIDDEN",
                    "error_code": "NOT_YOUR_SHIPMENT",
                    "detail": "You can only access your own shipments.",
                },
            )
        return  # ✅ granted

    # ── DRIVER: must be assigned to this shipment ────────────
    if current_user.is_driver:
        if shipment.assigned_driver_id != current_user.user_id:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "FORBIDDEN",
                    "error_code": "NOT_YOUR_DELIVERY",
                    "detail": "You can only access shipments assigned to you.",
                },
            )
        return  # ✅ granted

    # ── Should never reach here (get_current_user guards roles) ─
    raise HTTPException(
        status_code=403,
        detail={
            "error": "FORBIDDEN",
            "error_code": "UNKNOWN_ROLE",
            "detail": "Access denied.",
        },
    )