"""Authentication tests for the Secure Voting System."""

import pytest
from unittest.mock import patch


class TestVoterRegistration:
    """Tests for voter registration functionality."""

    def test_register_valid_voter(self, app, db, test_citizen):
        """Test that registration with valid data succeeds."""
        with app.app_context():
            with patch('app.models.voter.get_db', return_value=db):
                with patch('app.models.citizen.get_db', return_value=db):
                    from app.services.auth_service import AuthService

                    success, message, voter = AuthService.register_voter(
                        citizenship_number='TEST12345678',
                        full_name='Test User',
                        date_of_birth='1990-01-15',
                        password='ValidPass123!',
                        confirm_password='ValidPass123!'
                    )

                    assert success is True
                    assert voter is not None
                    assert voter.voter_id.startswith('VTR-')
                    assert 'Registration successful' in message

    def test_register_duplicate_citizenship(self, app, db, test_citizen, registered_voter):
        """Test that duplicate citizenship number is rejected."""
        with app.app_context():
            with patch('app.models.voter.get_db', return_value=db):
                with patch('app.models.citizen.get_db', return_value=db):
                    from app.services.auth_service import AuthService

                    success, message, voter = AuthService.register_voter(
                        citizenship_number='TEST12345678',
                        full_name='Test User',
                        date_of_birth='1990-01-15',
                        password='AnotherPass123!',
                        confirm_password='AnotherPass123!'
                    )

                    assert success is False
                    assert voter is None
                    assert 'already registered' in message.lower()

    def test_register_weak_password(self, app, db, test_citizen):
        """Test that weak password is rejected."""
        with app.app_context():
            with patch('app.models.voter.get_db', return_value=db):
                with patch('app.models.citizen.get_db', return_value=db):
                    from app.services.auth_service import AuthService

                    # Test password without uppercase
                    success, message, voter = AuthService.register_voter(
                        citizenship_number='TEST12345678',
                        full_name='Test User',
                        date_of_birth='1990-01-15',
                        password='weakpassword123!',
                        confirm_password='weakpassword123!'
                    )

                    assert success is False
                    assert voter is None
                    assert 'uppercase' in message.lower()

    def test_register_password_mismatch(self, app, db, test_citizen):
        """Test that mismatched passwords are rejected."""
        with app.app_context():
            with patch('app.models.voter.get_db', return_value=db):
                with patch('app.models.citizen.get_db', return_value=db):
                    from app.services.auth_service import AuthService

                    success, message, voter = AuthService.register_voter(
                        citizenship_number='TEST12345678',
                        full_name='Test User',
                        date_of_birth='1990-01-15',
                        password='ValidPass123!',
                        confirm_password='DifferentPass123!'
                    )

                    assert success is False
                    assert voter is None
                    assert 'do not match' in message.lower()

    def test_register_invalid_citizenship_format(self, app, db):
        """Test that invalid citizenship number format is rejected."""
        with app.app_context():
            with patch('app.models.voter.get_db', return_value=db):
                with patch('app.models.citizen.get_db', return_value=db):
                    from app.services.auth_service import AuthService

                    success, message, voter = AuthService.register_voter(
                        citizenship_number='123',  # Too short
                        full_name='Test User',
                        date_of_birth='1990-01-15',
                        password='ValidPass123!',
                        confirm_password='ValidPass123!'
                    )

                    assert success is False
                    assert voter is None

    def test_register_underage_voter(self, app, db, test_citizen_data):
        """Test that underage registration is rejected."""
        # Create a citizen who is under 18
        test_citizen_data['date_of_birth'] = pytest.importorskip('datetime').datetime(2010, 1, 15)
        db.citizens.insert_one(test_citizen_data)

        with app.app_context():
            with patch('app.models.voter.get_db', return_value=db):
                with patch('app.models.citizen.get_db', return_value=db):
                    from app.services.auth_service import AuthService

                    success, message, voter = AuthService.register_voter(
                        citizenship_number='TEST12345678',
                        full_name='Test User',
                        date_of_birth='2010-01-15',
                        password='ValidPass123!',
                        confirm_password='ValidPass123!'
                    )

                    assert success is False
                    assert voter is None
                    assert '18' in message


class TestVoterLogin:
    """Tests for voter login functionality."""

    def test_login_valid_credentials(self, app, db, registered_voter):
        """Test that valid credentials allow login."""
        with app.app_context():
            with patch('app.models.voter.get_db', return_value=db):
                from app.services.auth_service import AuthService

                success, message, voter = AuthService.login_voter(
                    voter_id=registered_voter['voter_id'],
                    password=registered_voter['password']
                )

                assert success is True
                assert voter is not None
                assert voter.voter_id == registered_voter['voter_id']

    def test_login_invalid_password(self, app, db, registered_voter):
        """Test that wrong password is rejected."""
        with app.app_context():
            with patch('app.models.voter.get_db', return_value=db):
                from app.services.auth_service import AuthService

                success, message, voter = AuthService.login_voter(
                    voter_id=registered_voter['voter_id'],
                    password='WrongPassword123!'
                )

                assert success is False
                assert voter is None
                assert 'invalid' in message.lower()

    def test_login_nonexistent_voter(self, app, db):
        """Test that nonexistent voter ID is rejected."""
        with app.app_context():
            with patch('app.models.voter.get_db', return_value=db):
                from app.services.auth_service import AuthService

                success, message, voter = AuthService.login_voter(
                    voter_id='VTR-FFFFFFFF',
                    password='SomePassword123!'
                )

                assert success is False
                assert voter is None
                assert 'invalid' in message.lower()

    def test_login_invalid_voter_id_format(self, app, db):
        """Test that invalid voter ID format is rejected."""
        with app.app_context():
            with patch('app.models.voter.get_db', return_value=db):
                from app.services.auth_service import AuthService

                success, message, voter = AuthService.login_voter(
                    voter_id='INVALID-FORMAT',
                    password='SomePassword123!'
                )

                assert success is False
                assert voter is None

    def test_login_empty_password(self, app, db, registered_voter):
        """Test that empty password is rejected."""
        with app.app_context():
            with patch('app.models.voter.get_db', return_value=db):
                from app.services.auth_service import AuthService

                success, message, voter = AuthService.login_voter(
                    voter_id=registered_voter['voter_id'],
                    password=''
                )

                assert success is False
                assert voter is None
                assert 'required' in message.lower()


class TestAdminLogin:
    """Tests for admin login functionality."""

    def test_admin_login_valid_credentials(self, app, db, registered_admin):
        """Test that valid admin credentials allow login."""
        with app.app_context():
            with patch('app.models.admin.get_db', return_value=db):
                from app.services.auth_service import AuthService

                success, message, admin = AuthService.login_admin(
                    username=registered_admin['username'],
                    password=registered_admin['password']
                )

                assert success is True
                assert admin is not None
                assert admin.username == registered_admin['username']

    def test_admin_login_invalid_password(self, app, db, registered_admin):
        """Test that wrong admin password is rejected."""
        with app.app_context():
            with patch('app.models.admin.get_db', return_value=db):
                from app.services.auth_service import AuthService

                success, message, admin = AuthService.login_admin(
                    username=registered_admin['username'],
                    password='WrongPassword123!'
                )

                assert success is False
                assert admin is None

    def test_admin_login_nonexistent_username(self, app, db):
        """Test that nonexistent admin username is rejected."""
        with app.app_context():
            with patch('app.models.admin.get_db', return_value=db):
                from app.services.auth_service import AuthService

                success, message, admin = AuthService.login_admin(
                    username='nonexistent',
                    password='SomePassword123!'
                )

                assert success is False
                assert admin is None


class TestRateLimiting:
    """Tests for rate limiting functionality."""

    def test_rate_limit_tracks_failed_attempts(self, app, db):
        """Test that failed login attempts are tracked."""
        with app.app_context():
            # Enable rate limiting for this test
            app.config['RATE_LIMIT_ENABLED'] = True

            with patch('app.services.rate_limiter.get_db', return_value=db):
                from app.services.rate_limiter import RateLimiter

                voter_id = 'VTR-TESTTEST'

                # Record 3 failed attempts
                for i in range(3):
                    RateLimiter.record_attempt(voter_id, 'voter_login', success=False)

                remaining = RateLimiter.get_attempts_remaining(voter_id, 'voter_login')
                assert remaining == 2  # 5 max - 3 attempts = 2 remaining

    def test_rate_limit_lockout_after_max_attempts(self, app, db):
        """Test that account is locked after max failed attempts."""
        with app.app_context():
            app.config['RATE_LIMIT_ENABLED'] = True

            with patch('app.services.rate_limiter.get_db', return_value=db):
                from app.services.rate_limiter import RateLimiter

                voter_id = 'VTR-LOCKTEST'

                # Record 5 failed attempts (max)
                for i in range(5):
                    RateLimiter.record_attempt(voter_id, 'voter_login', success=False)

                is_limited, message, _ = RateLimiter.is_rate_limited(voter_id, 'voter_login')
                assert is_limited is True
                assert 'locked' in message.lower() or 'attempt' in message.lower()

    def test_rate_limit_clears_on_success(self, app, db):
        """Test that successful login clears rate limit."""
        with app.app_context():
            app.config['RATE_LIMIT_ENABLED'] = True

            with patch('app.services.rate_limiter.get_db', return_value=db):
                from app.services.rate_limiter import RateLimiter

                voter_id = 'VTR-CLEARTEST'

                # Record 3 failed attempts
                for i in range(3):
                    RateLimiter.record_attempt(voter_id, 'voter_login', success=False)

                # Record successful attempt
                RateLimiter.record_attempt(voter_id, 'voter_login', success=True)

                # Should not be limited anymore
                is_limited, _, _ = RateLimiter.is_rate_limited(voter_id, 'voter_login')
                assert is_limited is False


class TestLogout:
    """Tests for logout functionality."""

    def test_logout_clears_session(self, client, app, db, registered_voter):
        """Test that logout clears the user session."""
        with app.app_context():
            with patch('app.models.voter.get_db', return_value=db):
                # First login
                with client.session_transaction() as sess:
                    sess['_user_id'] = str(registered_voter['voter'].get_id())

                # Then logout
                response = client.get('/logout', follow_redirects=True)

                assert response.status_code == 200
                # Should be redirected to login page
                assert b'login' in response.data.lower() or b'log in' in response.data.lower()
