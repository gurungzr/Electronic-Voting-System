"""Audit logging service for tracking security-relevant events."""
from flask import request, current_app
from app.models.audit_log import AuditLog


class AuditService:
    """Service for logging audit events with request context."""

    @classmethod
    def _is_enabled(cls) -> bool:
        """Check if audit logging is enabled."""
        return current_app.config.get('AUDIT_LOG_ENABLED', True)

    @classmethod
    def _get_request_context(cls) -> dict:
        """Extract request context for audit logging."""
        return {
            'ip_address': cls._get_client_ip(),
            'user_agent': request.headers.get('User-Agent', '')[:500]  # Truncate long user agents
        }

    @classmethod
    def _get_client_ip(cls) -> str:
        """Get the client's IP address, handling proxies."""
        if request.headers.get('X-Forwarded-For'):
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()
        if request.headers.get('X-Real-IP'):
            return request.headers.get('X-Real-IP')
        return request.remote_addr or 'unknown'

    # Authentication events

    @classmethod
    def log_login_success(cls, user_id: str, user_type: str = 'voter'):
        """Log a successful login."""
        if not cls._is_enabled():
            return None

        ctx = cls._get_request_context()
        return AuditLog.log(
            category=AuditLog.CATEGORY_AUTH,
            event_type=AuditLog.EVENT_LOGIN_SUCCESS,
            message=f'{user_type.capitalize()} login successful',
            user_id=user_id,
            user_type=user_type,
            **ctx
        )

    @classmethod
    def log_login_failed(cls, user_id: str, user_type: str = 'voter', reason: str = None):
        """Log a failed login attempt."""
        if not cls._is_enabled():
            return None

        ctx = cls._get_request_context()
        return AuditLog.log(
            category=AuditLog.CATEGORY_AUTH,
            event_type=AuditLog.EVENT_LOGIN_FAILED,
            message=f'{user_type.capitalize()} login failed',
            user_id=user_id,
            user_type=user_type,
            details={'reason': reason} if reason else None,
            **ctx
        )

    @classmethod
    def log_logout(cls, user_id: str, user_type: str = 'voter'):
        """Log a logout."""
        if not cls._is_enabled():
            return None

        ctx = cls._get_request_context()
        return AuditLog.log(
            category=AuditLog.CATEGORY_AUTH,
            event_type=AuditLog.EVENT_LOGOUT,
            message=f'{user_type.capitalize()} logged out',
            user_id=user_id,
            user_type=user_type,
            **ctx
        )

    @classmethod
    def log_registration(cls, user_id: str, success: bool = True, reason: str = None):
        """Log a registration attempt."""
        if not cls._is_enabled():
            return None

        ctx = cls._get_request_context()
        status = 'successful' if success else 'failed'
        return AuditLog.log(
            category=AuditLog.CATEGORY_AUTH,
            event_type=AuditLog.EVENT_REGISTER,
            message=f'Voter registration {status}',
            user_id=user_id,
            user_type='voter',
            details={'success': success, 'reason': reason} if reason else {'success': success},
            **ctx
        )

    # Voting events

    @classmethod
    def log_vote_cast(cls, voter_id: str, election_id: str, ballot_type: str):
        """Log a vote being cast (without revealing the vote choice)."""
        if not cls._is_enabled():
            return None

        ctx = cls._get_request_context()
        return AuditLog.log(
            category=AuditLog.CATEGORY_VOTE,
            event_type=AuditLog.EVENT_VOTE_CAST,
            message=f'{ballot_type.upper()} ballot cast in election',
            user_id=voter_id,
            user_type='voter',
            details={'election_id': election_id, 'ballot_type': ballot_type},
            **ctx
        )

    @classmethod
    def log_token_issued(cls, voter_id: str, election_id: str):
        """Log a voting token being issued."""
        if not cls._is_enabled():
            return None

        ctx = cls._get_request_context()
        return AuditLog.log(
            category=AuditLog.CATEGORY_VOTE,
            event_type=AuditLog.EVENT_TOKEN_ISSUED,
            message='Voting token issued',
            user_id=voter_id,
            user_type='voter',
            details={'election_id': election_id},
            **ctx
        )

    # Election events

    @classmethod
    def log_election_created(cls, admin_id: str, election_id: str, election_name: str):
        """Log election creation."""
        if not cls._is_enabled():
            return None

        ctx = cls._get_request_context()
        return AuditLog.log(
            category=AuditLog.CATEGORY_ELECTION,
            event_type=AuditLog.EVENT_ELECTION_CREATED,
            message=f'Election created: {election_name}',
            user_id=admin_id,
            user_type='admin',
            details={'election_id': election_id, 'election_name': election_name},
            **ctx
        )

    @classmethod
    def log_election_deactivated(cls, admin_id: str, election_id: str):
        """Log election deactivation."""
        if not cls._is_enabled():
            return None

        ctx = cls._get_request_context()
        return AuditLog.log(
            category=AuditLog.CATEGORY_ELECTION,
            event_type=AuditLog.EVENT_ELECTION_DEACTIVATED,
            message='Election deactivated',
            user_id=admin_id,
            user_type='admin',
            details={'election_id': election_id},
            **ctx
        )

    # Security events

    @classmethod
    def log_rate_limit_triggered(cls, identifier: str, action: str):
        """Log when rate limiting is triggered."""
        if not cls._is_enabled():
            return None

        ctx = cls._get_request_context()
        return AuditLog.log(
            category=AuditLog.CATEGORY_SECURITY,
            event_type=AuditLog.EVENT_RATE_LIMIT_TRIGGERED,
            message=f'Rate limit triggered for {action}',
            user_id=identifier,
            details={'action': action},
            **ctx
        )

    @classmethod
    def log_admin_action(cls, admin_id: str, action: str, details: dict = None):
        """Log an administrative action."""
        if not cls._is_enabled():
            return None

        ctx = cls._get_request_context()
        return AuditLog.log(
            category=AuditLog.CATEGORY_ADMIN,
            event_type=AuditLog.EVENT_ADMIN_ACTION,
            message=f'Admin action: {action}',
            user_id=admin_id,
            user_type='admin',
            details=details,
            **ctx
        )

    # Query methods (delegates to AuditLog model)

    @classmethod
    def get_recent_logs(cls, limit: int = 100) -> list:
        """Get recent audit logs."""
        return AuditLog.get_recent(limit)

    @classmethod
    def get_security_events(cls, limit: int = 100) -> list:
        """Get security-related events."""
        return AuditLog.get_security_events(limit)

    @classmethod
    def get_login_stats(cls, hours: int = 24) -> dict:
        """Get login statistics."""
        return AuditLog.get_login_stats(hours)

    @classmethod
    def get_user_activity(cls, user_id: str, limit: int = 100) -> list:
        """Get activity for a specific user."""
        return AuditLog.get_by_user(user_id, limit)

    # Hash chain verification methods

    @classmethod
    def verify_chain_integrity(cls, limit: int = None) -> dict:
        """Verify the integrity of the audit log hash chain.

        Args:
            limit: Maximum number of entries to verify (None = all)

        Returns:
            dict with verification results
        """
        return AuditLog.verify_chain(limit)

    @classmethod
    def get_chain_status(cls) -> dict:
        """Get the current status of the hash chain.

        Returns:
            dict with chain status information
        """
        return AuditLog.get_chain_status()
