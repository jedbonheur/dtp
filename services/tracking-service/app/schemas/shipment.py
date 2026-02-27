# app/schemas/shipment.py

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID

# ════════════════════════════════════════════════════════
# 1. NESTED SCHEMAS (Reusable components)
# ════════════════════════════════════════════════════════

class SenderCreate(BaseModel):
    """Request: Sender information when creating shipment"""
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    phone: str = Field(..., min_length=5, max_length=20)
    address: str = Field(..., min_length=1, max_length=500)


class SenderResponse(BaseModel):
    """Response: Sender information in responses"""
    name: str
    email: str
    phone: str
    address: str
    
    class Config:
        from_attributes = True  # Allow ORM model -> Pydantic


class RecipientCreate(BaseModel):
    """Request: Recipient information when creating shipment"""
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    phone: str = Field(..., min_length=5, max_length=20)
    address: str = Field(..., min_length=1, max_length=500)


class RecipientResponse(BaseModel):
    """Response: Recipient information in responses"""
    name: str
    email: str
    phone: str
    address: str
    
    class Config:
        from_attributes = True


class PackageCreate(BaseModel):
    """Request: Package information when creating shipment"""
    description: str = Field(..., min_length=1, max_length=500)
    weight_kg: Optional[float] = Field(None, gt=0)  # > 0
    dimensions_cm: Optional[dict] = None
    
    @field_validator('weight_kg')
    @classmethod
    def validate_weight(cls, v):
        if v is not None and v <= 0:
            raise ValueError('weight must be positive')
        if v is not None and v > 1000:
            raise ValueError('weight exceeds max 1000kg')
        return v


class PackageResponse(BaseModel):
    """Response: Package information in responses"""
    description: str
    weight_kg: Optional[float]
    dimensions_cm: Optional[dict]
    
    class Config:
        from_attributes = True


class LocationCreate(BaseModel):
    """Request: Location update (DRIVER only)"""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class LocationResponse(BaseModel):
    """Response: Location in responses"""
    latitude: Optional[float]
    longitude: Optional[float]
    
    class Config:
        from_attributes = True


# ════════════════════════════════════════════════════════
# 2. REQUEST SCHEMAS (What clients send)
# ════════════════════════════════════════════════════════

class ShipmentCreate(BaseModel):
    """POST /shipments request"""
    sender: SenderCreate
    recipient: RecipientCreate
    package: PackageCreate
    priority: str = Field(default="standard")
    client_id: Optional[str] = None  # ADMIN can specify who it's for
    
    @field_validator('priority')
    @classmethod
    def validate_priority(cls, v):
        valid_priorities = ["standard", "express", "overnight"]
        if v not in valid_priorities:
            raise ValueError(f"priority must be one of {valid_priorities}")
        return v


class ShipmentUpdate(BaseModel):
    """PUT /shipments/{id} request"""
    # All fields optional for partial updates
    status: Optional[str] = None
    assigned_driver_id: Optional[str] = None
    priority: Optional[str] = None
    estimated_delivery: Optional[datetime] = None
    
    # DRIVER can ONLY update these:
    current_latitude: Optional[float] = None
    current_longitude: Optional[float] = None
    delivery_status: Optional[str] = None  # DRIVER status update
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        if v is None:
            return v
        valid_statuses = ["pending", "assigned", "in_transit", "delivered", "failed", "cancelled"]
        if v not in valid_statuses:
            raise ValueError(f"status must be one of {valid_statuses}")
        return v


# ════════════════════════════════════════════════════════
# 3. RESPONSE SCHEMAS (What we return)
# ════════════════════════════════════════════════════════

class ShipmentEventResponse(BaseModel):
    """Shipment event (audit trail entry)"""
    id: UUID
    timestamp: datetime
    event_type: str
    triggered_by_user_id: str
    triggered_by_role: str
    description: str
    metadata: Optional[dict] = None
    
    class Config:
        from_attributes = True


class ShipmentResponse(BaseModel):
    """Full shipment response (single shipment)"""
    id: UUID
    status: str
    created_at: datetime
    updated_at: Optional[datetime]
    
    # Nested objects
    sender: SenderResponse
    recipient: RecipientResponse
    package: PackageResponse
    
    # Relationships
    created_by: str
    assigned_driver_id: Optional[str]
    estimated_delivery: Optional[datetime]
    
    # Location
    current_latitude: Optional[float]
    current_longitude: Optional[float]
    
    # Priority
    priority: str
    
    # Events (full timeline)
    events: List[ShipmentEventResponse] = []
    
    class Config:
        from_attributes = True  # Allows ORM Shipment object -> response


class ShipmentListResponse(BaseModel):
    """List of shipments with pagination"""
    total: int
    limit: int
    offset: int
    shipments: List[ShipmentResponse]


class ShipmentHistoryResponse(BaseModel):
    """List of events for a shipment"""
    shipment_id: UUID
    total_events: int
    limit: int
    offset: int
    events: List[ShipmentEventResponse]


# ════════════════════════════════════════════════════════
# 4. ERROR SCHEMAS (Consistent error responses)
# ════════════════════════════════════════════════════════

class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str  # e.g., "UNAUTHORIZED", "FORBIDDEN", "NOT_FOUND"
    error_code: str  # e.g., "MISSING_AUTH", "INSUFFICIENT_PERMISSIONS"
    detail: str  # Human-readable message
    timestamp: datetime
    request_id: Optional[str] = None


class ValidationErrorResponse(BaseModel):
    """Validation error response"""
    error: str = "VALIDATION_ERROR"
    error_code: str = "INVALID_INPUT"
    detail: str
    field: Optional[str] = None  # Which field failed
    timestamp: datetime