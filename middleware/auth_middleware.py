"""
Auth & Department Middleware — SLMG BI Portal
"""

from functools import wraps
from flask import jsonify, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from models import User, ActivityLog
from app import db


def jwt_required_custom(f):
    """Require valid JWT token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception as e:
            return jsonify({'error': 'Authentication required', 'message': str(e)}), 401
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Require Admin role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception as e:
            return jsonify({'error': 'Authentication required'}), 401
        
        identity = get_jwt_identity()
        user = User.query.get(identity)
        if not user or user.role != 'Admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


def analyst_or_admin_required(f):
    """Require Analyst or Admin role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception as e:
            return jsonify({'error': 'Authentication required'}), 401
        
        identity = get_jwt_identity()
        user = User.query.get(identity)
        if not user or user.role not in ('Admin', 'Analyst'):
            return jsonify({'error': 'Analyst or Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


def get_current_user():
    """Helper to get current user from JWT."""
    try:
        verify_jwt_in_request()
        identity = get_jwt_identity()
        return User.query.get(identity)
    except Exception:
        return None


def department_filter(query, user, model):
    """
    CORE SECURITY RULE:
    - Admin sees all dashboards
    - Other roles see ONLY their department's dashboards
    Enforced server-side, never solely on frontend.
    """
    if user.role == 'Admin':
        return query  # Admin sees everything
    return query.filter(model.department == user.department)


def log_activity(user_id, action, entity_type=None, entity_id=None, metadata=None):
    """Log user activity to DB."""
    try:
        import json
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
        print(f'Activity log error: {e}')
