"""
Auth & Department Access Middleware — SLMG BI Portal
"""

from functools import wraps
from flask import jsonify, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from models import User, ActivityLog
from app import db
import json


def jwt_required_custom(f):
    """Require valid JWT Bearer token in Authorization header."""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            verify_jwt_in_request(locations=['headers'])
        except Exception as e:
            return jsonify({'error': 'Authentication required', 'detail': str(e)}), 401
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Require Admin role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            verify_jwt_in_request(locations=['headers'])
        except Exception as e:
            return jsonify({'error': 'Authentication required', 'detail': str(e)}), 401

        identity = get_jwt_identity()
        user = User.query.get(int(identity))
        if not user or user.role != 'Admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


def analyst_or_admin_required(f):
    """Require Analyst or Admin role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            verify_jwt_in_request(locations=['headers'])
        except Exception as e:
            return jsonify({'error': 'Authentication required', 'detail': str(e)}), 401

        identity = get_jwt_identity()
        user = User.query.get(int(identity))
        if not user or user.role not in ('Admin', 'Analyst'):
            return jsonify({'error': 'Analyst or Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


def get_current_user():
    """Get current authenticated user from JWT identity."""
    try:
        verify_jwt_in_request(locations=['headers'])
        identity = get_jwt_identity()
        # identity is stored as string, must cast to int for DB lookup
        return User.query.get(int(identity))
    except Exception:
        return None


def department_filter(query, user, model):
    """
    CORE SECURITY — Enforced server-side, never only on frontend.
    Admin sees ALL dashboards.
    All other roles see ONLY their own department's dashboards.
    """
    if user.role == 'Admin':
        return query
    return query.filter(model.department == user.department)


def log_activity(user_id, action, entity_type=None, entity_id=None, metadata=None):
    """Write an activity log entry."""
    try:
        log = ActivityLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_raw=json.dumps(metadata or {}),
            ip_address=request.remote_addr if request else None
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f'Activity log error: {e}')
