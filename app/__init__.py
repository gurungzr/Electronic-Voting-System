from flask import Flask, request
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail
from pymongo import MongoClient

from app.config import Config, get_config

# Initialize extensions
login_manager = LoginManager()
csrf = CSRFProtect()
mail = Mail()
mongo_client = None
db = None


def get_db():
    """Get database instance."""
    global db
    return db


def create_app(config_class=None):
    """Application factory.

    Args:
        config_class: Configuration class to use. If None, auto-detects based on FLASK_ENV.
    """
    app = Flask(__name__)

    # Use provided config or auto-detect based on environment
    if config_class is None:
        config_class = get_config()
    app.config.from_object(config_class)

    # Initialize MongoDB
    global mongo_client, db
    try:
        mongo_client = MongoClient(app.config['MONGODB_URI'], serverSelectionTimeoutMS=5000)
        # Verify connection works
        mongo_client.admin.command('ping')
        db = mongo_client[app.config['DATABASE_NAME']]
        app.logger.info("Successfully connected to MongoDB")
    except Exception as e:
        app.logger.error(f"Failed to connect to MongoDB: {str(e)}")
        raise RuntimeError(f"Could not connect to MongoDB: {str(e)}")

    # Create indexes for collections
    _create_indexes(db)

    # Initialize extensions
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    csrf.init_app(app)
    mail.init_app(app)

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.voter import voter_bp
    from app.routes.admin import admin_bp
    from app.routes.verify import verify_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(voter_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(verify_bp)

    # User loader for Flask-Login
    from app.models.voter import Voter
    from app.models.admin import Admin

    @login_manager.user_loader
    def load_user(user_id):
        try:
            # Try to load as voter first
            voter = Voter.find_by_id(user_id)
            if voter:
                return voter
            # Try to load as admin
            admin = Admin.find_by_id(user_id)
            return admin
        except Exception as e:
            app.logger.error(f"Failed to load user {user_id}: {str(e)}")
            return None

    @app.after_request
    def add_cache_control_headers(response):
        """Prevent browser from caching pages.

        This fixes issues where pressing 'back' button shows stale pages
        instead of making fresh requests to the server.
        """
        # Apply to HTML responses (not static files like CSS/JS/images)
        if response.content_type and 'text/html' in response.content_type:
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response

    @app.after_request
    def add_security_headers(response):
        """Add Content Security Policy and other security headers."""
        if response.content_type and 'text/html' in response.content_type:
            csp_directives = [
                "default-src 'self'",
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
                "font-src 'self' https://cdn.jsdelivr.net data:",
                "img-src 'self' data: https:",
                "connect-src 'self'",
                "frame-src 'none'",
                "object-src 'none'",
                "base-uri 'self'",
                "form-action 'self'"
            ]
            response.headers['Content-Security-Policy'] = '; '.join(csp_directives)
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    @app.context_processor
    def inject_now():
        """Inject current datetime into all templates."""
        from datetime import datetime
        return {'now': datetime.now}

    return app


def _create_indexes(db):
    """Create necessary database indexes for dual-ballot system."""
    # Citizens collection indexes
    db.citizens.create_index('citizenship_number', unique=True)
    db.citizens.create_index('constituency')

    # Rate limiting collection indexes
    db.rate_limits.create_index('key', unique=True)
    db.rate_limits.create_index('last_attempt', expireAfterSeconds=86400)  # TTL: 24 hours

    # Audit log collection indexes
    db.audit_logs.create_index([('timestamp', -1)])
    db.audit_logs.create_index('user_id')
    db.audit_logs.create_index('event_type')
    db.audit_logs.create_index('category')
    db.audit_logs.create_index('ip_address')
    db.audit_logs.create_index('entry_hash', unique=True, sparse=True)  # Hash chain
    db.audit_logs.create_index('previous_hash', sparse=True)  # For chain traversal

    # Voters collection indexes
    db.voters.create_index('voter_id', unique=True)
    db.voters.create_index('citizenship_number_hash', unique=True)
    db.voters.create_index('constituency')

    # Elections collection indexes
    db.elections.create_index('election_id', unique=True)

    # Admins collection indexes
    db.admins.create_index('username', unique=True)

    # Votes collection indexes (compound indexes for efficient dual-ballot queries)
    db.votes.create_index([('election_id', 1), ('timestamp', -1)])
    db.votes.create_index([('election_id', 1), ('ballot_type', 1)])
    db.votes.create_index([('election_id', 1), ('ballot_type', 1), ('constituency', 1)])
    db.votes.create_index([('election_id', 1), ('party_id', 1)])
    db.votes.create_index('receipt_id')  # Not unique - FPTP and PR votes share same receipt

    # Voting tokens collection indexes
    db.voting_tokens.create_index('token_id', unique=True)
    db.voting_tokens.create_index([('election_id', 1), ('is_fully_used', 1)])
    db.voting_tokens.create_index([('election_id', 1), ('created_at', 1)])
    db.voting_tokens.create_index('constituency')

    # Add index for token issuance tracking on voters
    db.voters.create_index('token_issued_for')

    # Candidates collection indexes (candidate pool)
    db.candidates.create_index('candidate_id', unique=True)
    db.candidates.create_index('constituency')
    db.candidates.create_index('party')
    db.candidates.create_index('is_active')
