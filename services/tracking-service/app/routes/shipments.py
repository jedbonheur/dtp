# services/tracking-service/app/routes/shipments.py
# Complete Tracking Service API Routes
# All 8 endpoints in ONE file - Production Ready

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime
from typing import Optional

# Import our building blocks
from app.core.auth import (
    CurrentUser,
    get_current_user,
    verify_resource_access,
)
from app.db.database import get_db
from app.models.shipment import Shipment, ShipmentEvent, ShipmentStatus
from app.schemas.shipment import (
    ShipmentCreate,
    ShipmentUpdate,
    ShipmentResponse,
    ShipmentListResponse,
    ShipmentHistoryResponse,
    ShipmentEventResponse,
)

# Initialize router
router = APIRouter()


# ============================================================================
# ENDPOINT 1: CREATE SHIPMENT
# ============================================================================
# POST /api/v1/tracking/shipments
# Authorization: CLIENT (own), ADMIN (any client)
# Response: 201 Created
# ============================================================================

@router.post(
    "/shipments",
    response_model=ShipmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new shipment",
    tags=["Shipments"],
)
async def create_shipment(
    shipment_data: ShipmentCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShipmentResponse:
    """
    Create a new shipment.
    
    **Authorization:**
    - CLIENT: Can create for themselves only (created_by = their user_id)
    - ADMIN: Can create for any client (can specify client_id)
    - DRIVER: Forbidden (403)
    
    **Request Body:**
    - sender: SenderCreate (name, email, phone, address)
    - recipient: RecipientCreate (name, email, phone, address)
    - package: PackageCreate (description, weight_kg, dimensions_cm)
    - priority: "standard" | "express"
    
    **Response (201):**
    - Complete ShipmentResponse with id, status="pending", events[]
    
    **Errors:**
    - 403: DRIVER tries to create
    - 400: Invalid data (validation error from Pydantic)
    - 500: Database error
    """
    
    # AUTHORIZATION CHECK 1: DRIVER is forbidden
    if current_user.is_driver:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Drivers cannot create shipments. Only clients and admins can.",
        )
    
    # AUTHORIZATION CHECK 2: Determine who created this shipment
    if current_user.is_client:
        # CLIENT: Always create for themselves
        created_by = current_user.user_id
    elif current_user.is_admin:
        # ADMIN: Can create for themselves or a specified client
        created_by = shipment_data.client_id or current_user.user_id
    
    # CREATE SHIPMENT OBJECT
    shipment = Shipment(
        created_by=created_by,
        status=ShipmentStatus.PENDING,
        
        # Sender details
        sender_name=shipment_data.sender.name,
        sender_email=shipment_data.sender.email,
        sender_phone=shipment_data.sender.phone,
        sender_address=shipment_data.sender.address,
        
        # Recipient details
        recipient_name=shipment_data.recipient.name,
        recipient_email=shipment_data.recipient.email,
        recipient_phone=shipment_data.recipient.phone,
        recipient_address=shipment_data.recipient.address,
        
        # Package details
        description=shipment_data.package.description,
        weight_kg=shipment_data.package.weight_kg,
        dimensions_cm=shipment_data.package.dimensions_cm,
        
        # Metadata
        priority=shipment_data.priority,
        created_at=datetime.utcnow(),
    )
    
    # Save shipment to database
    db.add(shipment)
    db.flush()  # Get the generated ID without committing
    
    # CREATE INITIAL EVENT: "shipment_created" (Audit Trail)
    initial_event = ShipmentEvent(
        shipment_id=shipment.id,
        event_type="shipment_created",
        timestamp=datetime.utcnow(),
        description=f"Shipment created by {current_user.role}",
        triggered_by_user_id=current_user.user_id,
        triggered_by_role=current_user.role,
        event_metadata={
            "priority": shipment_data.priority,
            "recipient": shipment_data.recipient.name,
        },
    )
    
    db.add(initial_event)
    db.commit()  # Now commit everything
    db.refresh(shipment)  # Reload shipment with relationships
    
    # Return response (Pydantic will serialize it)
    return ShipmentResponse.from_orm(shipment)


# ============================================================================
# ENDPOINT 2: GET SINGLE SHIPMENT
# ============================================================================
# GET /api/v1/tracking/shipments/{id}
# Authorization: CLIENT (own), ADMIN (all), DRIVER (assigned)
# Response: 200 OK
# ============================================================================

@router.get(
    "/shipments/{shipment_id}",
    response_model=ShipmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a specific shipment",
    tags=["Shipments"],
)
async def get_shipment(
    shipment_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShipmentResponse:
    """
    Get a specific shipment by ID.
    
    **Authorization:**
    - CLIENT: Can view only their own shipments (created_by check)
    - ADMIN: Can view any shipment
    - DRIVER: Can view only assigned shipments (assigned_driver_id check)
    
    **Path Parameters:**
    - shipment_id: UUID of the shipment
    
    **Response (200):**
    - ShipmentResponse with full details + events
    
    **Errors:**
    - 404: Shipment not found
    - 403: User doesn't have permission to view this shipment
    """
    
    # FETCH SHIPMENT FROM DATABASE
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    
    # 404: Shipment doesn't exist
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment {shipment_id} not found",
        )
    
    # AUTHORIZATION CHECK: Use verify_resource_access from auth.py
    verify_resource_access(shipment, current_user)
    
    # Return response
    return ShipmentResponse.from_orm(shipment)


# ============================================================================
# ENDPOINT 3: LIST ALL SHIPMENTS (ADMIN ONLY)
# ============================================================================
# GET /api/v1/tracking/shipments?limit=20&offset=0&status=pending
# Authorization: ADMIN only
# Response: 200 OK with pagination
# ============================================================================

@router.get(
    "/shipments",
    response_model=ShipmentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all shipments (ADMIN only)",
    tags=["Shipments"],
)
async def list_shipments(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    offset: int = Query(0, ge=0, description="Number to skip"),
    status: Optional[str] = Query(None, description="Filter by status"),
) -> ShipmentListResponse:
    """
    List all shipments with pagination and filtering.
    
    **Authorization:**
    - ADMIN: Can list all shipments
    - CLIENT: Forbidden (403) - Use /my-shipments instead
    - DRIVER: Forbidden (403) - Use /assigned-deliveries instead
    
    **Query Parameters:**
    - limit: 1-100 (default: 20)
    - offset: Skip N records (default: 0)
    - status: Filter by status - "pending", "assigned", "in_transit", "delivered"
    
    **Response (200):**
    - total: Total shipments matching filter
    - limit: Results per page
    - offset: Records skipped
    - shipments: List of ShipmentResponse objects
    
    **Errors:**
    - 403: Non-admin user tries to access
    """
    
    # AUTHORIZATION: ADMIN only
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can list all shipments. Use /my-shipments or /assigned-deliveries instead.",
        )
    
    # BUILD QUERY
    query = db.query(Shipment)
    
    # FILTER BY STATUS (optional)
    if status:
        # Validate status is one of allowed values
        valid_statuses = [s.value for s in ShipmentStatus]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
            )
        query = query.filter(Shipment.status == status)
    
    # GET TOTAL COUNT (before pagination)
    total = query.count()
    
    # APPLY PAGINATION
    shipments = query.offset(offset).limit(limit).all()
    
    # Return response with pagination metadata
    return ShipmentListResponse(
        total=total,
        limit=limit,
        offset=offset,
        shipments=[ShipmentResponse.from_orm(s) for s in shipments],
    )


# ============================================================================
# ENDPOINT 4: UPDATE SHIPMENT
# ============================================================================
# PUT /api/v1/tracking/shipments/{id}
# Authorization: ADMIN (full update), DRIVER (status + location only)
# Response: 200 OK
# ============================================================================

@router.put(
    "/shipments/{shipment_id}",
    response_model=ShipmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a shipment",
    tags=["Shipments"],
)
async def update_shipment(
    shipment_id: UUID,
    shipment_data: ShipmentUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShipmentResponse:
    """
    Update a shipment.
    
    **Authorization:**
    - ADMIN: Can update any field (status, driver, priority, etc.)
    - DRIVER: Can only update status and current_location
    - CLIENT: Forbidden (403)
    
    **Path Parameters:**
    - shipment_id: UUID
    
    **Request Body (ADMIN):**
    - status: Optional[str]
    - assigned_driver_id: Optional[str]
    - priority: Optional[str]
    - estimated_delivery: Optional[datetime]
    - current_location: Optional[LocationCreate]
    
    **Request Body (DRIVER - limited):**
    - status: Optional[str]
    - current_location: Optional[LocationCreate]
    
    **Response (200):**
    - Updated ShipmentResponse with new values + new event
    
    **Errors:**
    - 404: Shipment not found
    - 403: Insufficient permissions
    - 400: Invalid data
    """
    
    # FETCH SHIPMENT
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment {shipment_id} not found",
        )
    
    # AUTHORIZATION CHECK
    if current_user.is_client:
        # CLIENT cannot update
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clients cannot update shipments. Contact admin for changes.",
        )
    
    if current_user.is_driver:
        # DRIVER can only update status and location
        # First check: Is this driver assigned to this shipment?
        if shipment.assigned_driver_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update shipments assigned to you.",
            )
        
        # Only allow status and location updates
        if shipment_data.status:
            shipment.status = shipment_data.status
        
        if shipment_data.current_location:
            shipment.current_latitude = shipment_data.current_location.latitude
            shipment.current_longitude = shipment_data.current_location.longitude
            shipment.current_location_updated_at = datetime.utcnow()
    
    elif current_user.is_admin:
        # ADMIN can update any field
        if shipment_data.status:
            shipment.status = shipment_data.status
        
        if shipment_data.assigned_driver_id:
            shipment.assigned_driver_id = shipment_data.assigned_driver_id
        
        if shipment_data.priority:
            shipment.priority = shipment_data.priority
        
        if shipment_data.estimated_delivery:
            shipment.estimated_delivery = shipment_data.estimated_delivery
        
        if shipment_data.current_location:
            shipment.current_latitude = shipment_data.current_location.latitude
            shipment.current_longitude = shipment_data.current_location.longitude
            shipment.current_location_updated_at = datetime.utcnow()
    
    # Update metadata
    shipment.updated_at = datetime.utcnow()
    shipment.updated_by = current_user.user_id
    
    # CREATE EVENT for the update (Audit Trail)
    changes = []
    if shipment_data.status:
        changes.append(f"status → {shipment_data.status}")
    if shipment_data.assigned_driver_id:
        changes.append(f"assigned to {shipment_data.assigned_driver_id}")
    if shipment_data.current_location:
        changes.append("location updated")
    
    update_event = ShipmentEvent(
        shipment_id=shipment.id,
        event_type="shipment_updated",
        timestamp=datetime.utcnow(),
        description=f"Shipment updated by {current_user.role}: {', '.join(changes)}",
        triggered_by_user_id=current_user.user_id,
        triggered_by_role=current_user.role,
        event_metadata={
            "changes": changes,
        },
    )
    
    db.add(update_event)
    db.commit()
    db.refresh(shipment)
    
    return ShipmentResponse.from_orm(shipment)


# ============================================================================
# ENDPOINT 5: DELETE SHIPMENT
# ============================================================================
# DELETE /api/v1/tracking/shipments/{id}
# Authorization: ADMIN only
# Response: 200 OK with confirmation
# ============================================================================

@router.delete(
    "/shipments/{shipment_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a shipment",
    tags=["Shipments"],
)
async def delete_shipment(
    shipment_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Delete a shipment permanently.
    
    **Authorization:**
    - ADMIN: Can delete any shipment
    - CLIENT: Forbidden (403)
    - DRIVER: Forbidden (403)
    
    **Path Parameters:**
    - shipment_id: UUID
    
    **Response (200):**
```json
    {
      "message": "Shipment deleted",
      "shipment_id": "550e8400-e29b-41d4-a716-446655440000",
      "deleted_by": "admin_123",
      "deleted_at": "2026-02-25T12:00:00Z"
    }
```
    
    **Errors:**
    - 404: Shipment not found
    - 403: Non-admin tries to delete
    """
    
    # AUTHORIZATION: ADMIN only
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete shipments.",
        )
    
    # FETCH SHIPMENT
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment {shipment_id} not found",
        )
    
    # DELETE (cascade deletes events automatically via ORM)
    db.delete(shipment)
    db.commit()
    
    # Return confirmation
    return {
        "message": "Shipment deleted",
        "shipment_id": str(shipment_id),
        "deleted_by": current_user.user_id,
        "deleted_at": datetime.utcnow().isoformat(),
    }


# ============================================================================
# ENDPOINT 6: GET SHIPMENT EVENT HISTORY
# ============================================================================
# GET /api/v1/tracking/shipments/{id}/history?limit=50&offset=0
# Authorization: CLIENT (own), ADMIN (all), DRIVER (assigned)
# Response: 200 OK with event timeline
# ============================================================================

@router.get(
    "/shipments/{shipment_id}/history",
    response_model=ShipmentHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get shipment event history",
    tags=["Shipments"],
)
async def get_shipment_history(
    shipment_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200, description="Results per page"),
    offset: int = Query(0, ge=0, description="Number to skip"),
    event_type: Optional[str] = Query(
        None,
        description="Filter by event type",
    ),
) -> ShipmentHistoryResponse:
    """
    Get the event history (timeline) for a shipment.
    
    Shows all actions taken on the shipment in chronological order.
    
    **Authorization:**
    - CLIENT: Can view history of their own shipments
    - ADMIN: Can view history of any shipment
    - DRIVER: Can view history of assigned shipments
    
    **Path Parameters:**
    - shipment_id: UUID
    
    **Query Parameters:**
    - limit: 1-200 events per page (default: 50)
    - offset: Skip N events (default: 0)
    - event_type: Filter by type (optional)
    
    **Response (200):**
    - shipment_id: UUID
    - total_events: Total events for this shipment
    - limit: Events per page
    - offset: Records skipped
    - events: List of ShipmentEventResponse objects
    
    **Errors:**
    - 404: Shipment not found
    - 403: User doesn't have permission to view history
    """
    
    # FETCH SHIPMENT (to verify it exists and check permissions)
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment {shipment_id} not found",
        )
    
    # AUTHORIZATION CHECK: Must have access to shipment
    verify_resource_access(shipment, current_user)
    
    # BUILD QUERY for events
    events_query = db.query(ShipmentEvent).filter(
        ShipmentEvent.shipment_id == shipment_id
    )
    
    # FILTER BY EVENT TYPE (optional)
    if event_type:
        valid_types = [
            "shipment_created",
            "shipment_assigned",
            "shipment_updated",
            "delivery_completed",
            "location_updated",
        ]
        if event_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid event_type. Must be one of: {', '.join(valid_types)}",
            )
        events_query = events_query.filter(ShipmentEvent.event_type == event_type)
    
    # ORDER BY TIMESTAMP (newest first)
    events_query = events_query.order_by(ShipmentEvent.timestamp.desc())
    
    # GET TOTAL COUNT
    total = events_query.count()
    
    # APPLY PAGINATION
    events = events_query.offset(offset).limit(limit).all()
    
    # Return response
    return ShipmentHistoryResponse(
        shipment_id=shipment_id,
        total_events=total,
        limit=limit,
        offset=offset,
        events=[ShipmentEventResponse.from_orm(e) for e in events],
    )


# ============================================================================
# ENDPOINT 7: GET MY SHIPMENTS (CLIENT ONLY)
# ============================================================================
# GET /api/v1/tracking/my-shipments?limit=20&offset=0&status=pending
# Authorization: CLIENT only
# Response: 200 OK (auto-filtered to user's shipments)
# ============================================================================

@router.get(
    "/my-shipments",
    response_model=ShipmentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List my shipments (CLIENT only)",
    tags=["Shipments"],
)
async def get_my_shipments(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
) -> ShipmentListResponse:
    """
    List shipments created by the current CLIENT.
    
    **This is a convenience endpoint - auto-filters to current user.**
    
    **Authorization:**
    - CLIENT: Can see their own shipments
    - ADMIN: Forbidden (403) - Use /shipments instead
    - DRIVER: Forbidden (403) - Use /assigned-deliveries instead
    
    **Query Parameters:**
    - limit: 1-100 (default: 20)
    - offset: Skip (default: 0)
    - status: Filter by status (optional)
    
    **Response (200):**
    - ShipmentListResponse with pagination
    """
    
    # AUTHORIZATION: CLIENT only
    if not current_user.is_client:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is for clients only. Use /shipments or /assigned-deliveries.",
        )
    
    # BUILD QUERY: Auto-filter to current user
    query = db.query(Shipment).filter(Shipment.created_by == current_user.user_id)
    
    # FILTER BY STATUS (optional)
    if status:
        valid_statuses = [s.value for s in ShipmentStatus]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
            )
        query = query.filter(Shipment.status == status)
    
    # GET TOTAL
    total = query.count()
    
    # APPLY PAGINATION
    shipments = query.offset(offset).limit(limit).all()
    
    return ShipmentListResponse(
        total=total,
        limit=limit,
        offset=offset,
        shipments=[ShipmentResponse.from_orm(s) for s in shipments],
    )


# ============================================================================
# ENDPOINT 8: GET ASSIGNED DELIVERIES (DRIVER ONLY)
# ============================================================================
# GET /api/v1/tracking/assigned-deliveries?limit=20&offset=0&status=pending
# Authorization: DRIVER only
# Response: 200 OK (auto-filtered to driver's assignments)
# ============================================================================

@router.get(
    "/assigned-deliveries",
    response_model=ShipmentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List my assigned deliveries (DRIVER only)",
    tags=["Shipments"],
)
async def get_assigned_deliveries(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
) -> ShipmentListResponse:
    """
    List shipments assigned to the current DRIVER.
    
    **This is a convenience endpoint - auto-filters to assigned deliveries.**
    
    **Authorization:**
    - DRIVER: Can see their assigned deliveries
    - CLIENT: Forbidden (403) - Use /my-shipments instead
    - ADMIN: Forbidden (403) - Use /shipments instead
    
    **Query Parameters:**
    - limit: 1-100 (default: 20)
    - offset: Skip (default: 0)
    - status: Filter by status (optional)
    
    **Response (200):**
    - ShipmentListResponse with pagination
    """
    
    # AUTHORIZATION: DRIVER only
    if not current_user.is_driver:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is for drivers only. Use /my-shipments or /shipments.",
        )
    
    # BUILD QUERY: Auto-filter to current driver's assignments
    query = db.query(Shipment).filter(
        Shipment.assigned_driver_id == current_user.user_id
    )
    
    # FILTER BY STATUS (optional)
    if status:
        valid_statuses = [s.value for s in ShipmentStatus]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
            )
        query = query.filter(Shipment.status == status)
    
    # GET TOTAL
    total = query.count()
    
    # APPLY PAGINATION
    shipments = query.offset(offset).limit(limit).all()
    
    return ShipmentListResponse(
        total=total,
        limit=limit,
        offset=offset,
        shipments=[ShipmentResponse.from_orm(s) for s in shipments],
    )
