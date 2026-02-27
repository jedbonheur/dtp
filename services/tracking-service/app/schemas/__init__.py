"""
Pydantic request/response schemas.

Exports all schemas for use in routes and documentation.
"""

from app.schemas.shipment import (
    # Nested schemas
    SenderCreate,
    SenderResponse,
    RecipientCreate,
    RecipientResponse,
    PackageCreate,
    PackageResponse,
    LocationCreate,
    LocationResponse,
    # Request schemas
    ShipmentCreate,
    ShipmentUpdate,
    # Response schemas
    ShipmentEventResponse,
    ShipmentResponse,
    ShipmentListResponse,
    ShipmentHistoryResponse,
    # Error schemas
    ErrorResponse,
    ValidationErrorResponse,
)

__all__ = [
    # Nested
    "SenderCreate",
    "SenderResponse",
    "RecipientCreate",
    "RecipientResponse",
    "PackageCreate",
    "PackageResponse",
    "LocationCreate",
    "LocationResponse",
    # Requests
    "ShipmentCreate",
    "ShipmentUpdate",
    # Responses
    "ShipmentEventResponse",
    "ShipmentResponse",
    "ShipmentListResponse",
    "ShipmentHistoryResponse",
    # Errors
    "ErrorResponse",
    "ValidationErrorResponse",
]