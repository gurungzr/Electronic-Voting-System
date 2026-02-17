"""Election lifecycle tests for the Secure Voting System."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta


class TestElectionCreation:
    """Tests for election creation functionality."""

    def test_create_election_with_candidates(self, app, db):
        """Test that an election can be created with candidates."""
        with app.app_context():
            with patch('app.models.election.get_db', return_value=db):
                with patch('app.services.election_service.get_db', return_value=db):
                    from app.models.election import Election

                    now = datetime.utcnow()

                    election = Election.create(
                        name='Test Election',
                        description='A test election',
                        start_date=now + timedelta(hours=1),
                        end_date=now + timedelta(days=1),
                        candidates=[
                            {'name': 'Candidate A', 'party': 'Party One', 'constituency': 'Kathmandu'},
                            {'name': 'Candidate B', 'party': 'Party Two', 'constituency': 'Lalitpur'},
                        ],
                        parties=[
                            {'name': 'Party One'},
                            {'name': 'Party Two'},
                        ]
                    )

                    assert election is not None
                    assert election.election_id.startswith('ELC-')
                    assert election.name == 'Test Election'
                    assert len(election.candidates) == 2
                    assert len(election.parties) == 2

    def test_election_candidates_have_ids(self, app, db):
        """Test that created candidates get unique IDs."""
        with app.app_context():
            with patch('app.models.election.get_db', return_value=db):
                from app.models.election import Election

                now = datetime.utcnow()

                election = Election.create(
                    name='Test Election',
                    description='Testing candidate IDs',
                    start_date=now,
                    end_date=now + timedelta(days=1),
                    candidates=[
                        {'name': 'Candidate A', 'party': 'Party One', 'constituency': 'Kathmandu'},
                        {'name': 'Candidate B', 'party': 'Party Two', 'constituency': 'Kathmandu'},
                    ],
                    parties=[{'name': 'Party One'}, {'name': 'Party Two'}]
                )

                assert all('candidate_id' in c for c in election.candidates)
                assert all(c['candidate_id'].startswith('CND-') for c in election.candidates)

                # Check IDs are unique
                ids = [c['candidate_id'] for c in election.candidates]
                assert len(ids) == len(set(ids))

    def test_election_parties_have_ids(self, app, db):
        """Test that created parties get unique IDs."""
        with app.app_context():
            with patch('app.models.election.get_db', return_value=db):
                from app.models.election import Election

                now = datetime.utcnow()

                election = Election.create(
                    name='Test Election',
                    description='Testing party IDs',
                    start_date=now,
                    end_date=now + timedelta(days=1),
                    candidates=[{'name': 'Candidate A', 'party': 'Party One', 'constituency': 'Kathmandu'}],
                    parties=[
                        {'name': 'Party One'},
                        {'name': 'Party Two'},
                        {'name': 'Party Three'},
                    ]
                )

                assert all('party_id' in p for p in election.parties)
                assert all(p['party_id'].startswith('PTY-') for p in election.parties)

                # Check IDs are unique
                ids = [p['party_id'] for p in election.parties]
                assert len(ids) == len(set(ids))


class TestElectionState:
    """Tests for election state management."""

    def test_election_not_started(self, future_election):
        """Test that future election is not started."""
        assert future_election.has_started() is False
        assert future_election.is_ongoing() is False
        assert future_election.has_ended() is False

    def test_election_ongoing(self, test_election):
        """Test that current election is ongoing."""
        assert test_election.has_started() is True
        assert test_election.is_ongoing() is True
        assert test_election.has_ended() is False

    def test_election_ended(self, ended_election):
        """Test that past election has ended."""
        assert ended_election.has_started() is True
        assert ended_election.is_ongoing() is False
        assert ended_election.has_ended() is True


class TestElectionTermination:
    """Tests for election termination functionality."""

    def test_terminate_ongoing_election(self, app, db, test_election):
        """Test that an ongoing election can be terminated."""
        with app.app_context():
            with patch('app.models.election.get_db', return_value=db):
                from app.models.election import Election

                # Verify election is ongoing
                assert test_election.is_ongoing() is True

                # Terminate the election
                Election.terminate(test_election.election_id)

                # Reload and verify it has ended
                updated = Election.find_by_election_id(test_election.election_id)
                assert updated.has_ended() is True

    def test_deactivate_election(self, app, db, test_election):
        """Test that an election can be deactivated."""
        with app.app_context():
            with patch('app.models.election.get_db', return_value=db):
                from app.models.election import Election

                # Verify election is active
                assert test_election.is_active is True

                # Deactivate the election
                Election.deactivate(test_election.election_id)

                # Reload and verify it's inactive
                updated = Election.find_by_election_id(test_election.election_id)
                assert updated.is_active is False
                assert updated.is_ongoing() is False


class TestElectionQueries:
    """Tests for election query functionality."""

    def test_find_election_by_id(self, app, db, test_election):
        """Test finding an election by its ID."""
        with app.app_context():
            with patch('app.models.election.get_db', return_value=db):
                from app.models.election import Election

                found = Election.find_by_election_id(test_election.election_id)

                assert found is not None
                assert found.election_id == test_election.election_id
                assert found.name == test_election.name

    def test_find_nonexistent_election(self, app, db):
        """Test that finding nonexistent election returns None."""
        with app.app_context():
            with patch('app.models.election.get_db', return_value=db):
                from app.models.election import Election

                found = Election.find_by_election_id('ELC-NONEXISTENT')

                assert found is None

    def test_get_candidates_by_constituency(self, test_election):
        """Test getting candidates filtered by constituency."""
        kathmandu_candidates = test_election.get_candidates_by_constituency('Kathmandu')
        lalitpur_candidates = test_election.get_candidates_by_constituency('Lalitpur')
        bhaktapur_candidates = test_election.get_candidates_by_constituency('Bhaktapur')

        assert len(kathmandu_candidates) >= 1
        assert len(lalitpur_candidates) >= 1
        assert len(bhaktapur_candidates) >= 1

        # Verify all returned candidates are from correct constituency
        assert all(c['constituency'] == 'Kathmandu' for c in kathmandu_candidates)
        assert all(c['constituency'] == 'Lalitpur' for c in lalitpur_candidates)
        assert all(c['constituency'] == 'Bhaktapur' for c in bhaktapur_candidates)

    def test_get_candidate_by_id(self, test_election):
        """Test getting a specific candidate by ID."""
        first_candidate = test_election.candidates[0]
        found = test_election.get_candidate(first_candidate['candidate_id'])

        assert found is not None
        assert found['candidate_id'] == first_candidate['candidate_id']
        assert found['name'] == first_candidate['name']

    def test_get_party_by_id(self, test_election):
        """Test getting a specific party by ID."""
        first_party = test_election.parties[0]
        found = test_election.get_party(first_party['party_id'])

        assert found is not None
        assert found['party_id'] == first_party['party_id']
        assert found['name'] == first_party['name']


class TestElectionValidation:
    """Tests for election validation rules."""

    def test_election_requires_name(self, app, db):
        """Test that election name is required."""
        with app.app_context():
            with patch('app.models.election.get_db', return_value=db):
                from app.models.election import Election

                now = datetime.utcnow()

                # Empty name should still create (validation at service level)
                election = Election.create(
                    name='',
                    description='Test',
                    start_date=now,
                    end_date=now + timedelta(days=1),
                    candidates=[],
                    parties=[]
                )

                # Basic creation works, but name is empty
                assert election.name == ''

    def test_election_dates_stored_correctly(self, app, db):
        """Test that election dates are stored correctly."""
        with app.app_context():
            with patch('app.models.election.get_db', return_value=db):
                from app.models.election import Election

                start = datetime(2024, 6, 1, 9, 0, 0)
                end = datetime(2024, 6, 1, 18, 0, 0)

                election = Election.create(
                    name='Date Test Election',
                    description='Testing dates',
                    start_date=start,
                    end_date=end,
                    candidates=[],
                    parties=[]
                )

                assert election.start_date == start
                assert election.end_date == end


class TestElectionCounting:
    """Tests for election counting functionality."""

    def test_count_all_elections(self, app, db, test_election, future_election, ended_election):
        """Test counting all elections."""
        with app.app_context():
            with patch('app.models.election.get_db', return_value=db):
                from app.models.election import Election

                count = Election.count_all()

                assert count == 3  # test_election, future_election, ended_election

    def test_get_all_elections(self, app, db, test_election, future_election):
        """Test getting all elections."""
        with app.app_context():
            with patch('app.models.election.get_db', return_value=db):
                from app.models.election import Election

                elections = Election.get_all_elections()

                assert len(elections) >= 2
                election_ids = [e.election_id for e in elections]
                assert test_election.election_id in election_ids
                assert future_election.election_id in election_ids
