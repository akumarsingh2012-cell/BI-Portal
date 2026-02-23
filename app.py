"""
SLMG Beverages — Enterprise BI Portal
Flask Backend Application
"""

from flask import Flask, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from config import Config
import os

db = SQLAlchemy()
jwt = JWTManager()
bcrypt = Bcrypt()


def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(Config)

    # Extensions
    db.init_app(app)
    jwt.init_app(app)
    bcrypt.init_app(app)
    CORS(app, supports_credentials=True, origins=app.config.get('CORS_ORIGINS', '*'))

    # Register blueprints
    from routes.auth import auth_bp
    from routes.dashboards import dash_bp
    from routes.users import users_bp
    from routes.analytics import analytics_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(dash_bp, url_prefix='/api/dashboards')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(analytics_bp, url_prefix='/api/analytics')

    # Serve frontend SPA
    @app.route('/')
    @app.route('/<path:path>')
    def serve_frontend(path=''):
        if path and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        return send_from_directory(app.template_folder, 'index.html')

    # Create DB tables + seed admin
    with app.app_context():
        db.create_all()
        _seed_data()

    return app


def _seed_data():
    """Seed default admin user and sample dashboards if empty."""
    from models import User, Dashboard
    
    if not User.query.filter_by(email='admin@slmg.com').first():
        from app import bcrypt as bc
        admin = User(
            name='Admin User',
            email='admin@slmg.com',
            password=bc.generate_password_hash('Admin@1234').decode('utf-8'),
            role='Admin',
            department='Operations'
        )
        db.session.add(admin)

        # Seed sample users
        users = [
            User(name='Finance Manager', email='finance@slmg.com',
                 password=bc.generate_password_hash('Finance@1234').decode('utf-8'),
                 role='Analyst', department='Finance'),
            User(name='Sales Analyst', email='sales@slmg.com',
                 password=bc.generate_password_hash('Sales@1234').decode('utf-8'),
                 role='Analyst', department='Sales'),
            User(name='HR Viewer', email='hr@slmg.com',
                 password=bc.generate_password_hash('HR@1234').decode('utf-8'),
                 role='Viewer', department='HR'),
        ]
        for u in users:
            db.session.add(u)

        # Seed sample dashboards
        import json
        dashboards = [
            Dashboard(
                title='Finance Overview Q1 2025',
                embed_url='https://app.powerbi.com/view?r=demo_finance',
                department='Finance',
                category='Financial',
                tags=json.dumps(['revenue', 'EBITDA', 'Q1', 'finance']),
                kpis=json.dumps([
                    {"name": "Revenue", "value": 4800000, "target": 5000000, "previousValue": 4500000},
                    {"name": "EBITDA Margin", "value": 18.5, "target": 20, "previousValue": 17.2},
                    {"name": "Cost of Goods", "value": 2100000, "target": 2000000, "previousValue": 2300000},
                    {"name": "Net Profit", "value": 820000, "target": 900000, "previousValue": 750000},
                ]),
                commentary='Q1 shows improving revenue trend. EBITDA slightly below target. Cost reduction initiative underway.',
                created_by='admin@slmg.com'
            ),
            Dashboard(
                title='Sales Performance Dashboard',
                embed_url='https://app.powerbi.com/view?r=demo_sales',
                department='Sales',
                category='Sales',
                tags=json.dumps(['sales', 'pipeline', 'conversion', 'growth']),
                kpis=json.dumps([
                    {"name": "Total Sales", "value": 12500, "target": 13000, "previousValue": 11800},
                    {"name": "Conversion Rate", "value": 24.3, "target": 25, "previousValue": 22.1},
                    {"name": "Avg Deal Size", "value": 18500, "target": 20000, "previousValue": 17800},
                    {"name": "Customer Retention", "value": 87, "target": 90, "previousValue": 89},
                ]),
                commentary='Sales team showing strong conversion improvement. Deal size needs attention.',
                created_by='admin@slmg.com'
            ),
            Dashboard(
                title='HR Analytics & Workforce',
                embed_url='https://app.powerbi.com/view?r=demo_hr',
                department='HR',
                category='People',
                tags=json.dumps(['headcount', 'attrition', 'hiring', 'productivity']),
                kpis=json.dumps([
                    {"name": "Employee Satisfaction", "value": 78, "target": 80, "previousValue": 74},
                    {"name": "Attrition Rate", "value": 9.2, "target": 8, "previousValue": 11.5},
                    {"name": "Time to Hire", "value": 32, "target": 30, "previousValue": 38},
                    {"name": "Training Completion", "value": 91, "target": 90, "previousValue": 85},
                ]),
                commentary='Attrition improving significantly. Satisfaction scores rising. Training on target.',
                created_by='admin@slmg.com'
            ),
            Dashboard(
                title='Operations & Supply Chain',
                embed_url='https://app.powerbi.com/view?r=demo_ops',
                department='Operations',
                category='Operations',
                tags=json.dumps(['supply', 'logistics', 'OEE', 'efficiency']),
                kpis=json.dumps([
                    {"name": "OEE Score", "value": 76, "target": 85, "previousValue": 72},
                    {"name": "On-Time Delivery", "value": 93, "target": 95, "previousValue": 90},
                    {"name": "Inventory Turnover", "value": 8.2, "target": 9, "previousValue": 7.8},
                    {"name": "Downtime Hours", "value": 48, "target": 30, "previousValue": 65},
                ]),
                commentary='OEE below target but improving. Delivery performance strong. Downtime reducing.',
                created_by='admin@slmg.com'
            ),
        ]
        for d in dashboards:
            db.session.add(d)

        db.session.commit()
        print('✅ Database seeded with admin, users, and dashboards.')


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
