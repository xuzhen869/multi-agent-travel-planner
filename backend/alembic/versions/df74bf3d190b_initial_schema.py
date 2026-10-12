"""initial_schema

Revision ID: df74bf3d190b
Revises:
Create Date: 2026-07-26 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = 'df74bf3d190b'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users
    op.create_table(
        'users',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('display_name', sa.String(100)),
        sa.Column('oauth_provider', sa.String(50)),
        sa.Column('oauth_id', sa.String(255)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # user_preferences
    op.create_table(
        'user_preferences',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), unique=True),
        sa.Column('default_departure_city', sa.String(100)),
        sa.Column('preferred_hotel_star', sa.Integer(), default=4),
        sa.Column('preferred_flight_class', sa.String(20), default='economy'),
        sa.Column('pace', sa.String(20), default='moderate'),
        sa.Column('interests', sa.JSON(), default=list),
        sa.Column('dietary', sa.JSON(), default=list),
        sa.Column('budget_default_currency', sa.String(3), default='CNY'),
        sa.Column('default_travelers', sa.JSON(), default=list),
        sa.Column('is_first_time', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # user_profiles
    op.create_table(
        'user_profiles',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), unique=True),
        sa.Column('label', sa.String(50)),
        sa.Column('traits', sa.JSON(), default=list),
        sa.Column('budget_flexibility', sa.String(20)),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # trips
    op.create_table(
        'trips',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), index=True),
        sa.Column('title', sa.String(200)),
        sa.Column('status', sa.String(20), default='draft'),
        sa.Column('mode', sa.String(20), default='recommend'),
        sa.Column('request_params', sa.JSON(), default=dict),
        sa.Column('recommendations', sa.JSON()),
        sa.Column('selected_plan_id', sa.String(20)),
        sa.Column('plan_data', sa.JSON()),
        sa.Column('user_profile', sa.JSON()),
        sa.Column('budget_total', sa.Numeric(12, 2)),
        sa.Column('budget_currency', sa.String(3)),
        sa.Column('started_at', sa.DateTime(timezone=True)),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_trips_user_id', 'trips', ['user_id'])
    op.create_index('idx_trips_status', 'trips', ['status'])

    # agent_logs
    op.create_table(
        'agent_logs',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('trip_id', sa.Uuid(), sa.ForeignKey('trips.id', ondelete='CASCADE'), index=True),
        sa.Column('agent_name', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('input_data', sa.JSON()),
        sa.Column('output_data', sa.JSON()),
        sa.Column('error_message', sa.Text()),
        sa.Column('duration_ms', sa.Integer()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_agent_logs_trip_id', 'agent_logs', ['trip_id'])


def downgrade() -> None:
    op.drop_table('agent_logs')
    op.drop_table('trips')
    op.drop_table('user_profiles')
    op.drop_table('user_preferences')
    op.drop_table('users')
