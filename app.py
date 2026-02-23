"""
SLMG Beverages — Enterprise BI Portal
Flask Application Factory (Fixed + Enhanced)
"""

from flask import Flask, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from config import Config
import os
import pathlib

db = SQLAlchemy()
jwt = JWTManager()
bcrypt = Bcrypt()


def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(Config)

    pathlib.Path(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')).mkdir(exist_ok=True)

    db.init_app(app)
    jwt.init_app(app)
    bcrypt.init_app(app)
    CORS(app,
         resources={r"/api/*": {"origins": "*"}},
         supports_credentials=True,
         allow_headers=["Content-Type", "Authorization"],
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

    @jwt.unauthorized_loader
    def unauthorized_callback(reason):
        return jsonify({'error': 'Authentication required', 'reason': reason}), 401

    @jwt.expired_token_loader
    def expired_callback(jwt_header, jwt_data):
        return jsonify({'error': 'Session expired. Please log in again.'}), 401

    @jwt.invalid_token_loader
    def invalid_callback(reason):
        return jsonify({'error': 'Invalid token', 'reason': reason}), 401

    # Global error handlers — prevent raw 500s
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Resource not found'}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({'error': 'Method not allowed'}), 405

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return jsonify({'error': 'Internal server error', 'detail': str(e)}), 500

    from routes.auth import auth_bp
    from routes.dashboards import dash_bp
    from routes.users import users_bp
    from routes.analytics import analytics_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(dash_bp, url_prefix='/api/dashboards')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(analytics_bp, url_prefix='/api/analytics')

    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        if path and os.path.exists(os.path.join(static_dir, path)):
            return send_from_directory(static_dir, path)
        return send_from_directory(template_dir, 'index.html')

    with app.app_context():
        db.create_all()
        _seed_data()

    return app


def _seed_data():
    from models import User, Dashboard

    if User.query.filter_by(email='admin@slmg.com').first():
        return

    admin = User(
        name='SLMG Admin',
        email='admin@slmg.com',
        password=bcrypt.generate_password_hash('Admin@1234').decode('utf-8'),
        role='Admin',
        department='Operations'
    )
    db.session.add(admin)

    dept_users = [
        ('Finance Manager', 'finance@slmg.com', 'Finance@1234', 'Analyst', 'Finance'),
        ('Sales Head', 'sales@slmg.com', 'Sales@1234', 'Analyst', 'Sales'),
        ('HR Manager', 'hr@slmg.com', 'HR@1234', 'Viewer', 'HR'),
        ('Ops Manager', 'ops@slmg.com', 'Ops@1234', 'Analyst', 'Operations'),
    ]
    for name, email, pwd, role, dept in dept_users:
        db.session.add(User(
            name=name, email=email,
            password=bcrypt.generate_password_hash(pwd).decode('utf-8'),
            role=role, department=dept
        ))

    dashboards = [
        Dashboard(
            title='Finance Overview Q1 2025',
            embed_url='https://app.powerbi.com/view?r=demo_finance',
            department='Finance', category='Financial',
            tags_raw='["revenue","EBITDA","Q1","finance"]',
            kpis_raw='[{"name":"Revenue","value":4800000,"target":5000000,"previousValue":4500000},{"name":"EBITDA Margin","value":18.5,"target":20,"previousValue":17.2},{"name":"Cost of Goods","value":2100000,"target":2000000,"previousValue":2300000},{"name":"Net Profit","value":820000,"target":900000,"previousValue":750000}]',
            commentary='Q1 shows improving revenue trend. EBITDA slightly below target. Cost reduction initiative underway.',
            ai_context='Finance department Q1 2025 report covering revenue, EBITDA, cost management, and net profit. Key focus: cost of goods exceeds target.',
            created_by='admin@slmg.com'
        ),
        Dashboard(
            title='Sales Performance Dashboard',
            embed_url='https://app.powerbi.com/view?r=demo_sales',
            department='Sales', category='Sales',
            tags_raw='["sales","pipeline","conversion","growth"]',
            kpis_raw='[{"name":"Total Sales","value":12500,"target":13000,"previousValue":11800},{"name":"Conversion Rate","value":24.3,"target":25,"previousValue":22.1},{"name":"Avg Deal Size","value":18500,"target":20000,"previousValue":17800},{"name":"Customer Retention","value":87,"target":90,"previousValue":89}]',
            commentary='Sales team showing strong conversion improvement. Deal size needs focus.',
            ai_context='Sales dashboard tracking units sold, conversion rates, deal sizes, and customer retention across all channels.',
            created_by='admin@slmg.com'
        ),
        Dashboard(
            title='HR Analytics & Workforce',
            embed_url='https://app.powerbi.com/view?r=demo_hr',
            department='HR', category='People',
            tags_raw='["headcount","attrition","hiring","productivity"]',
            kpis_raw='[{"name":"Employee Satisfaction","value":78,"target":80,"previousValue":74},{"name":"Attrition Rate","value":9.2,"target":8,"previousValue":11.5},{"name":"Time to Hire","value":32,"target":30,"previousValue":38},{"name":"Training Completion","value":91,"target":90,"previousValue":85}]',
            commentary='Attrition improving. Satisfaction scores rising. Training on target.',
            ai_context='HR workforce analytics: employee satisfaction, attrition rate, hiring timelines, and training completion rates.',
            created_by='admin@slmg.com'
        ),
        Dashboard(
            title='Operations & Supply Chain',
            embed_url='https://app.powerbi.com/view?r=demo_ops',
            department='Operations', category='Operations',
            tags_raw='["supply","logistics","OEE","efficiency"]',
            kpis_raw='[{"name":"OEE Score","value":76,"target":85,"previousValue":72},{"name":"On-Time Delivery","value":93,"target":95,"previousValue":90},{"name":"Inventory Turnover","value":8.2,"target":9,"previousValue":7.8},{"name":"Downtime Hours","value":48,"target":30,"previousValue":65}]',
            commentary='OEE below target but improving. Delivery performance strong.',
            ai_context='Operations and supply chain dashboard: OEE, delivery performance, inventory management, and machine downtime.',
            created_by='admin@slmg.com'
        ),
    ]
    for d in dashboards:
        db.session.add(d)

    db.session.commit()
    print('✅ Database seeded successfully.')


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
