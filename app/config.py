import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    MONGODB_URI = os.environ.get('MONGODB_URI') or 'mongodb://localhost:27017/'
    DATABASE_NAME = os.environ.get('DATABASE_NAME') or 'secure_voting_fresh'

    # Environment detection
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    DEBUG = FLASK_ENV == 'development'

    # Session configuration - secure by default based on environment
    SESSION_COOKIE_SECURE = FLASK_ENV == 'production'  # Auto-enable for production
    SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access to session cookie
    SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF protection
    PERMANENT_SESSION_LIFETIME = 3600  # Session expires after 1 hour

    # bcrypt configuration
    BCRYPT_LOG_ROUNDS = 12

    # Rate limiting configuration
    RATE_LIMIT_ENABLED = True
    RATE_LIMIT_MAX_ATTEMPTS = 5  # Max login attempts
    RATE_LIMIT_WINDOW_SECONDS = 300  # 5 minute window
    RATE_LIMIT_LOCKOUT_SECONDS = 900  # 15 minute lockout after max attempts

    # Audit logging configuration
    AUDIT_LOG_ENABLED = True

    # Email configuration (SMTP)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@onlinevotingnepal.com')
    MAIL_ENABLED = bool(os.environ.get('MAIL_USERNAME'))


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    SESSION_COOKIE_SECURE = False  # Allow HTTP in development


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    SESSION_COOKIE_SECURE = True  # Require HTTPS
    SESSION_COOKIE_SAMESITE = 'Strict'  # Stricter CSRF protection


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    RATE_LIMIT_ENABLED = False  # Disable rate limiting in tests
    AUDIT_LOG_ENABLED = False  # Disable audit logging in tests


def get_config():
    """Get configuration based on FLASK_ENV environment variable."""
    env = os.environ.get('FLASK_ENV', 'development')
    config_map = {
        'development': DevelopmentConfig,
        'production': ProductionConfig,
        'testing': TestingConfig
    }
    return config_map.get(env, DevelopmentConfig)
