"""Shared test fixtures for the Secure Voting System."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch
import mongomock


class TestingConfig:
    """Testing configuration with mocked MongoDB."""
    SECRET_KEY = 'test-secret-key-for-testing-only'
    TESTING = True
    DEBUG = True
    WTF_CSRF_ENABLED = False  # Disable CSRF for testing
    SESSION_COOKIE_SECURE = False
    MONGODB_URI = 'mongodb://localhost:27017/'
    DATABASE_NAME = 'test_secure_voting'

    # Disable rate limiting and audit logging for most tests
    RATE_LIMIT_ENABLED = False
    AUDIT_LOG_ENABLED = False

    # Session config
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600

    # bcrypt - use fewer rounds for faster tests
    BCRYPT_LOG_ROUNDS = 4

    # Email disabled for tests
    MAIL_ENABLED = False
    MAIL_SERVER = 'localhost'
    MAIL_PORT = 25
    MAIL_USE_TLS = False
    MAIL_USE_SSL = False
    MAIL_USERNAME = None
    MAIL_PASSWORD = None
    MAIL_DEFAULT_SENDER = 'test@test.com'


@pytest.fixture
def mock_mongo_client():
    """Create a mock MongoDB client using mongomock."""
    return mongomock.MongoClient()


@pytest.fixture
def app(mock_mongo_client):
    """Create and configure a test application instance."""
    # Patch MongoClient before importing and creating the app
    with patch('app.MongoClient', return_value=mock_mongo_client):
        with patch('pymongo.MongoClient', return_value=mock_mongo_client):
            # Import here to ensure patching works
            from app import create_app

            test_app = create_app(TestingConfig)
            test_app.config['TESTING'] = True
            test_app.config['WTF_CSRF_ENABLED'] = False

            yield test_app


@pytest.fixture
def client(app):
    """Create a test client for the application."""
    return app.test_client()


@pytest.fixture
def app_context(app):
    """Create an application context."""
    with app.app_context():
        yield


@pytest.fixture
def db(app, mock_mongo_client):
    """Get the test database and ensure it's clean."""
    database = mock_mongo_client[TestingConfig.DATABASE_NAME]

    # Clean all collections before each test
    for collection_name in database.list_collection_names():
        database[collection_name].drop()

    # Patch the get_db function to return our test database
    with patch('app.get_db', return_value=database):
        with patch('app.db', database):
            yield database

    # Clean up after test
    for collection_name in database.list_collection_names():
        database[collection_name].drop()


@pytest.fixture
def test_citizen_data():
    """Sample citizen data for testing."""
    return {
        'citizenship_number': 'TEST12345678',
        'full_name': 'Test User',
        'date_of_birth': datetime(1990, 1, 15),
        'address': '123 Test Street, Kathmandu',
        'constituency': 'Kathmandu',
        'is_eligible': True
    }


@pytest.fixture
def test_citizen(db, test_citizen_data):
    """Create a test citizen in the database."""
    db.citizens.insert_one(test_citizen_data)
    return test_citizen_data


@pytest.fixture
def test_voter_credentials():
    """Test voter registration credentials."""
    return {
        'citizenship_number': 'TEST12345678',
        'full_name': 'Test User',
        'date_of_birth': '1990-01-15',
        'password': 'TestPass123!',
        'confirm_password': 'TestPass123!'
    }


@pytest.fixture
def registered_voter(app, db, test_citizen, test_voter_credentials):
    """Create a registered voter for testing."""
    with app.app_context():
        # Patch get_db in the models
        with patch('app.models.voter.get_db', return_value=db):
            with patch('app.models.citizen.get_db', return_value=db):
                from app.services.auth_service import AuthService

                success, message, voter = AuthService.register_voter(
                    citizenship_number=test_voter_credentials['citizenship_number'],
                    full_name=test_voter_credentials['full_name'],
                    date_of_birth=test_voter_credentials['date_of_birth'],
                    password=test_voter_credentials['password'],
                    confirm_password=test_voter_credentials['confirm_password']
                )

                if not success:
                    pytest.fail(f"Failed to create test voter: {message}")

                return {
                    'voter': voter,
                    'voter_id': voter.voter_id,
                    'password': test_voter_credentials['password']
                }


@pytest.fixture
def test_admin_credentials():
    """Test admin credentials."""
    return {
        'username': 'testadmin',
        'password': 'AdminPass123!'
    }


@pytest.fixture
def registered_admin(app, db, test_admin_credentials):
    """Create a registered admin for testing."""
    with app.app_context():
        with patch('app.models.admin.get_db', return_value=db):
            from app.services.auth_service import AuthService

            success, message, admin = AuthService.create_admin(
                username=test_admin_credentials['username'],
                password=test_admin_credentials['password']
            )

            if not success:
                pytest.fail(f"Failed to create test admin: {message}")

            return {
                'admin': admin,
                'username': test_admin_credentials['username'],
                'password': test_admin_credentials['password']
            }


@pytest.fixture
def test_election_data():
    """Sample election data for testing."""
    now = datetime.utcnow()
    return {
        'name': 'Test Election 2024',
        'description': 'A test election for unit testing',
        'start_date': now - timedelta(hours=1),  # Started 1 hour ago
        'end_date': now + timedelta(days=1),  # Ends tomorrow
        'candidates': [
            {'name': 'Candidate A', 'party': 'Party One', 'constituency': 'Kathmandu'},
            {'name': 'Candidate B', 'party': 'Party Two', 'constituency': 'Kathmandu'},
            {'name': 'Candidate C', 'party': 'Party One', 'constituency': 'Lalitpur'},
            {'name': 'Candidate D', 'party': 'Party Two', 'constituency': 'Lalitpur'},
            {'name': 'Candidate E', 'party': 'Party One', 'constituency': 'Bhaktapur'},
            {'name': 'Candidate F', 'party': 'Party Two', 'constituency': 'Bhaktapur'},
        ],
        'parties': [
            {'name': 'Party One', 'symbol': 'sun'},
            {'name': 'Party Two', 'symbol': 'moon'},
            {'name': 'Party Three', 'symbol': 'star'},
        ]
    }


@pytest.fixture
def test_election(app, db, test_election_data):
    """Create a test election in the database."""
    with app.app_context():
        with patch('app.models.election.get_db', return_value=db):
            from app.models.election import Election
            from app.utils.security import generate_election_id, generate_candidate_id, generate_party_id

            # Process candidates with IDs
            candidates = []
            for c in test_election_data['candidates']:
                candidates.append({
                    'candidate_id': generate_candidate_id(),
                    'name': c['name'],
                    'party': c['party'],
                    'constituency': c['constituency']
                })

            # Process parties with IDs
            parties = []
            for p in test_election_data['parties']:
                parties.append({
                    'party_id': generate_party_id(),
                    'name': p['name'],
                    'symbol': p.get('symbol')
                })

            election = Election(
                election_id=generate_election_id(),
                name=test_election_data['name'],
                description=test_election_data['description'],
                candidates=candidates,
                parties=parties,
                start_date=test_election_data['start_date'],
                end_date=test_election_data['end_date'],
                public_key='test_public_key',
                encrypted_key_bundle='test_encrypted_bundle'
            )

            db.elections.insert_one(election.to_dict())

            return election


@pytest.fixture
def future_election(app, db, test_election_data):
    """Create a future election that hasn't started yet."""
    with app.app_context():
        with patch('app.models.election.get_db', return_value=db):
            from app.models.election import Election
            from app.utils.security import generate_election_id, generate_candidate_id, generate_party_id

            now = datetime.utcnow()

            candidates = []
            for c in test_election_data['candidates']:
                candidates.append({
                    'candidate_id': generate_candidate_id(),
                    'name': c['name'],
                    'party': c['party'],
                    'constituency': c['constituency']
                })

            parties = []
            for p in test_election_data['parties']:
                parties.append({
                    'party_id': generate_party_id(),
                    'name': p['name'],
                    'symbol': p.get('symbol')
                })

            election = Election(
                election_id=generate_election_id(),
                name='Future Election',
                description='An election that has not started',
                candidates=candidates,
                parties=parties,
                start_date=now + timedelta(days=1),  # Starts tomorrow
                end_date=now + timedelta(days=2),
                public_key='test_public_key',
                encrypted_key_bundle='test_encrypted_bundle'
            )

            db.elections.insert_one(election.to_dict())

            return election


@pytest.fixture
def ended_election(app, db, test_election_data):
    """Create an election that has already ended."""
    with app.app_context():
        with patch('app.models.election.get_db', return_value=db):
            from app.models.election import Election
            from app.utils.security import generate_election_id, generate_candidate_id, generate_party_id

            now = datetime.utcnow()

            candidates = []
            for c in test_election_data['candidates']:
                candidates.append({
                    'candidate_id': generate_candidate_id(),
                    'name': c['name'],
                    'party': c['party'],
                    'constituency': c['constituency']
                })

            parties = []
            for p in test_election_data['parties']:
                parties.append({
                    'party_id': generate_party_id(),
                    'name': p['name'],
                    'symbol': p.get('symbol')
                })

            election = Election(
                election_id=generate_election_id(),
                name='Ended Election',
                description='An election that has ended',
                candidates=candidates,
                parties=parties,
                start_date=now - timedelta(days=2),  # Started 2 days ago
                end_date=now - timedelta(hours=1),   # Ended 1 hour ago
                public_key='test_public_key',
                encrypted_key_bundle='test_encrypted_bundle'
            )

            db.elections.insert_one(election.to_dict())

            return election
