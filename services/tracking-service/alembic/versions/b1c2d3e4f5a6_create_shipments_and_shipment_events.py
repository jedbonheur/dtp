"""Create shipments and shipment_events tables

Revision ID: b1c2d3e4f5a6
Revises: aec0d6d8bb22
Create Date: 2026-02-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = 'aec0d6d8bb22'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old unused table from prior design
    op.drop_index('ix_tracking_events_status', table_name='tracking_events')
    op.drop_index('ix_tracking_events_order_id', table_name='tracking_events')
    op.drop_table('tracking_events')

    # Create shipments table
    op.create_table(
        'shipments',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('created_by', sa.String(255), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('assigned_driver_id', sa.String(255), nullable=True),
        sa.Column('sender_name', sa.String(255), nullable=False),
        sa.Column('sender_email', sa.String(255), nullable=False),
        sa.Column('sender_phone', sa.String(20), nullable=False),
        sa.Column('sender_address', sa.String(500), nullable=False),
        sa.Column('recipient_name', sa.String(255), nullable=False),
        sa.Column('recipient_email', sa.String(255), nullable=False),
        sa.Column('recipient_phone', sa.String(20), nullable=False),
        sa.Column('recipient_address', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('weight_kg', sa.Float(), nullable=True),
        sa.Column('priority', sa.String(50), nullable=True),
        sa.Column('dimensions_cm', sa.JSON(), nullable=True),
        sa.Column('current_latitude', sa.Float(), nullable=True),
        sa.Column('current_longitude', sa.Float(), nullable=True),
        sa.Column('current_location_updated_at', sa.DateTime(), nullable=True),
        sa.Column('estimated_delivery', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('updated_by', sa.String(255), nullable=True),
    )
    op.create_index('ix_shipments_created_by', 'shipments', ['created_by'])
    op.create_index('ix_shipments_status', 'shipments', ['status'])
    op.create_index('ix_shipments_assigned_driver_id', 'shipments', ['assigned_driver_id'])
    op.create_index('ix_shipments_created_at', 'shipments', ['created_at'])

    # Create shipment_events table
    op.create_table(
        'shipment_events',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('shipment_id', UUID(as_uuid=True), sa.ForeignKey('shipments.id'), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.Column('description', sa.String(500), nullable=False),
        sa.Column('triggered_by_user_id', sa.String(255), nullable=False),
        sa.Column('triggered_by_role', sa.String(50), nullable=False),
        sa.Column('event_metadata', sa.JSON(), nullable=True),
    )
    op.create_index('ix_shipment_events_shipment_id', 'shipment_events', ['shipment_id'])
    op.create_index('ix_shipment_events_event_type', 'shipment_events', ['event_type'])
    op.create_index('ix_shipment_events_timestamp', 'shipment_events', ['timestamp'])


def downgrade() -> None:
    op.drop_index('ix_shipment_events_timestamp', table_name='shipment_events')
    op.drop_index('ix_shipment_events_event_type', table_name='shipment_events')
    op.drop_index('ix_shipment_events_shipment_id', table_name='shipment_events')
    op.drop_table('shipment_events')

    op.drop_index('ix_shipments_created_at', table_name='shipments')
    op.drop_index('ix_shipments_assigned_driver_id', table_name='shipments')
    op.drop_index('ix_shipments_status', table_name='shipments')
    op.drop_index('ix_shipments_created_by', table_name='shipments')
    op.drop_table('shipments')

    op.create_table(
        'tracking_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tracking_events_order_id', 'tracking_events', ['order_id'])
    op.create_index('ix_tracking_events_status', 'tracking_events', ['status'])
