"""Rate limiting service for protecting against brute force attacks."""
from datetime import datetime, timedelta
from flask import current_app, request
from app import get_db


class RateLimiter:
    """Rate limiter using MongoDB for persistent storage.

    Tracks failed login attempts by IP address and user identifier,
    implementing exponential backoff for repeated failures.
    """

    collection_name = 'rate_limits'

    @classmethod
    def _get_config(cls):
        """Get rate limiting configuration."""
        return {
            'enabled': current_app.config.get('RATE_LIMIT_ENABLED', True),
            'max_attempts': current_app.config.get('RATE_LIMIT_MAX_ATTEMPTS', 5),
            'window_seconds': current_app.config.get('RATE_LIMIT_WINDOW_SECONDS', 300),
            'lockout_seconds': current_app.config.get('RATE_LIMIT_LOCKOUT_SECONDS', 900)
        }

    @classmethod
    def _get_client_ip(cls) -> str:
        """Get the client's IP address, handling proxies."""
        # Check for forwarded IP (behind proxy/load balancer)
        if request.headers.get('X-Forwarded-For'):
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()
        if request.headers.get('X-Real-IP'):
            return request.headers.get('X-Real-IP')
        return request.remote_addr or 'unknown'

    @classmethod
    def _get_key(cls, identifier: str, action: str = 'login') -> str:
        """Generate a unique key for rate limiting.

        Args:
            identifier: User identifier (voter_id, username, etc.)
            action: The action being rate limited (login, register, etc.)
        """
        ip = cls._get_client_ip()
        return f"{action}:{ip}:{identifier}"

    @classmethod
    def is_rate_limited(cls, identifier: str, action: str = 'login') -> tuple[bool, str, int]:
        """Check if an identifier is rate limited.

        Args:
            identifier: User identifier (voter_id, username, etc.)
            action: The action being rate limited

        Returns:
            (is_limited, message, seconds_remaining)
        """
        config = cls._get_config()

        if not config['enabled']:
            return False, '', 0

        db = get_db()
        key = cls._get_key(identifier, action)

        record = db[cls.collection_name].find_one({'key': key})

        if not record:
            return False, '', 0

        now = datetime.utcnow()

        # Check if in lockout period
        if record.get('locked_until'):
            locked_until = record['locked_until']
            # Handle timezone-aware datetimes from MongoDB
            if hasattr(locked_until, 'replace') and locked_until.tzinfo is not None:
                locked_until = locked_until.replace(tzinfo=None)
            if now < locked_until:
                seconds_remaining = int((locked_until - now).total_seconds())
                minutes_remaining = max(1, seconds_remaining // 60)  # At least 1 minute shown
                return True, f'Too many failed attempts. Please try again in {minutes_remaining} minutes.', seconds_remaining

        # Check attempt count within window
        window_start = now - timedelta(seconds=config['window_seconds'])
        attempts = record.get('attempts', [])

        # Count attempts within window (handle timezone-aware datetimes)
        recent_attempts = []
        for a in attempts:
            attempt_time = a
            if hasattr(attempt_time, 'replace') and attempt_time.tzinfo is not None:
                attempt_time = attempt_time.replace(tzinfo=None)
            if attempt_time > window_start:
                recent_attempts.append(a)

        if len(recent_attempts) >= config['max_attempts']:
            # Lock the account
            lockout_until = now + timedelta(seconds=config['lockout_seconds'])
            db[cls.collection_name].update_one(
                {'key': key},
                {'$set': {'locked_until': lockout_until}},
                upsert=True
            )
            seconds_remaining = config['lockout_seconds']
            minutes_remaining = seconds_remaining // 60
            return True, f'Too many failed attempts. Please try again in {minutes_remaining} minutes.', seconds_remaining

        return False, '', 0

    @classmethod
    def record_attempt(cls, identifier: str, action: str = 'login', success: bool = False):
        """Record a login attempt.

        Args:
            identifier: User identifier (voter_id, username, etc.)
            action: The action being rate limited
            success: Whether the attempt was successful
        """
        config = cls._get_config()

        if not config['enabled']:
            return

        db = get_db()
        key = cls._get_key(identifier, action)
        now = datetime.utcnow()

        if success:
            # Clear rate limit record on successful login
            db[cls.collection_name].delete_one({'key': key})
        else:
            # Record failed attempt
            window_start = now - timedelta(seconds=config['window_seconds'])

            # Update or create record
            db[cls.collection_name].update_one(
                {'key': key},
                {
                    '$push': {
                        'attempts': {
                            '$each': [now],
                            '$slice': -config['max_attempts']  # Keep only recent attempts
                        }
                    },
                    '$set': {
                        'last_attempt': now,
                        'ip_address': cls._get_client_ip()
                    },
                    '$setOnInsert': {
                        'created_at': now
                    }
                },
                upsert=True
            )

    @classmethod
    def clear_rate_limit(cls, identifier: str, action: str = 'login'):
        """Manually clear rate limit for an identifier.

        Args:
            identifier: User identifier (voter_id, username, etc.)
            action: The action being rate limited
        """
        db = get_db()
        key = cls._get_key(identifier, action)
        db[cls.collection_name].delete_one({'key': key})

    @classmethod
    def get_attempts_remaining(cls, identifier: str, action: str = 'login') -> int:
        """Get the number of attempts remaining before lockout.

        Args:
            identifier: User identifier (voter_id, username, etc.)
            action: The action being rate limited

        Returns:
            Number of attempts remaining
        """
        config = cls._get_config()

        if not config['enabled']:
            return config['max_attempts']

        db = get_db()
        key = cls._get_key(identifier, action)
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=config['window_seconds'])

        record = db[cls.collection_name].find_one({'key': key})

        if not record:
            return config['max_attempts']

        attempts = record.get('attempts', [])
        recent_attempts = [a for a in attempts if a > window_start]

        return max(0, config['max_attempts'] - len(recent_attempts))


def create_rate_limit_indexes(db):
    """Create indexes for the rate_limits collection."""
    # Index for quick lookups
    db.rate_limits.create_index('key', unique=True)
    # TTL index to auto-delete old records (24 hours)
    db.rate_limits.create_index('last_attempt', expireAfterSeconds=86400)
