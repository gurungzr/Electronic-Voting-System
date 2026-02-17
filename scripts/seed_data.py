"""
Seed script to populate the database with initial data for testing.
Run this script to create:
- Mock citizens with constituencies for eligibility verification
- Default admin account
- Sample dual-ballot election with FPTP candidates and PR parties
"""

import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, get_db
from app.models.citizen import Citizen
from app.models.admin import Admin
from app.models.election import Election
from app.models.candidate import Candidate
from app.constants.parties import PR_PARTIES


# The 3 constituencies
CONSTITUENCIES = ["Kathmandu", "Lalitpur", "Bhaktapur"]

# Candidate pool: 5 candidates per constituency (15 total)
CANDIDATE_POOL = [
    # Kathmandu candidates (5)
    {'name': 'Rajesh Koirala', 'party': 'Nepal Democratic Party', 'constituency': 'Kathmandu'},
    {'name': 'Sunita Rai', 'party': 'United Peoples Front', 'constituency': 'Kathmandu'},
    {'name': 'Deepak Shah', 'party': 'Progressive Alliance', 'constituency': 'Kathmandu'},
    {'name': 'Anita Gurung', 'party': 'Citizens Movement', 'constituency': 'Kathmandu'},
    {'name': 'Bikash Thapa', 'party': 'National Unity Party', 'constituency': 'Kathmandu'},

    # Lalitpur candidates (5)
    {'name': 'Kamala Basnet', 'party': 'Nepal Democratic Party', 'constituency': 'Lalitpur'},
    {'name': 'Binod Maharjan', 'party': 'United Peoples Front', 'constituency': 'Lalitpur'},
    {'name': 'Sarita Manandhar', 'party': 'Progressive Alliance', 'constituency': 'Lalitpur'},
    {'name': 'Ramesh Dangol', 'party': 'Citizens Movement', 'constituency': 'Lalitpur'},
    {'name': 'Sushila Shrestha', 'party': 'National Unity Party', 'constituency': 'Lalitpur'},

    # Bhaktapur candidates (5)
    {'name': 'Prakash Joshi', 'party': 'Nepal Democratic Party', 'constituency': 'Bhaktapur'},
    {'name': 'Mina Tuladhar', 'party': 'United Peoples Front', 'constituency': 'Bhaktapur'},
    {'name': 'Gopal Prajapati', 'party': 'Progressive Alliance', 'constituency': 'Bhaktapur'},
    {'name': 'Sabina Ranjit', 'party': 'Citizens Movement', 'constituency': 'Bhaktapur'},
    {'name': 'Nabin Chitrakar', 'party': 'National Unity Party', 'constituency': 'Bhaktapur'},
]


def seed_citizens():
    """Create mock citizens with constituencies for eligibility verification."""
    db = get_db()

    # Clear existing citizens
    db.citizens.delete_many({})

    citizens_data = [
        # Kathmandu constituency citizens
        {
            'citizenship_number': 'CTZ12345678',
            'full_name': 'Ram Sharma',
            'date_of_birth': datetime(1990, 5, 15),
            'address': '123 Thamel, Kathmandu',
            'constituency': 'Kathmandu',
            'is_eligible': True
        },
        {
            'citizenship_number': 'CTZ23456789',
            'full_name': 'Sita Thapa',
            'date_of_birth': datetime(1985, 8, 22),
            'address': '456 Basantapur, Kathmandu',
            'constituency': 'Kathmandu',
            'is_eligible': True
        },
        {
            'citizenship_number': 'CTZ34567890',
            'full_name': 'Hari Prasad',
            'date_of_birth': datetime(1992, 3, 10),
            'address': '789 Lazimpat, Kathmandu',
            'constituency': 'Kathmandu',
            'is_eligible': True
        },
        {
            'citizenship_number': 'CTZ45678901',
            'full_name': 'Gita Adhikari',
            'date_of_birth': datetime(1988, 11, 30),
            'address': '321 Baluwatar, Kathmandu',
            'constituency': 'Kathmandu',
            'is_eligible': True
        },

        # Lalitpur constituency citizens
        {
            'citizenship_number': 'CTZ56789012',
            'full_name': 'Krishna Maharjan',
            'date_of_birth': datetime(1995, 7, 8),
            'address': '654 Patan Durbar, Lalitpur',
            'constituency': 'Lalitpur',
            'is_eligible': True
        },
        {
            'citizenship_number': 'CTZ67890123',
            'full_name': 'Laxmi Shrestha',
            'date_of_birth': datetime(1991, 1, 25),
            'address': '987 Mangalbazar, Lalitpur',
            'constituency': 'Lalitpur',
            'is_eligible': True
        },
        {
            'citizenship_number': 'CTZ78901234',
            'full_name': 'Bikram Tamang',
            'date_of_birth': datetime(1987, 9, 12),
            'address': '147 Jawalakhel, Lalitpur',
            'constituency': 'Lalitpur',
            'is_eligible': True
        },

        # Bhaktapur constituency citizens
        {
            'citizenship_number': 'CTZ89012345',
            'full_name': 'Maya Karki',
            'date_of_birth': datetime(1993, 4, 18),
            'address': '258 Durbar Square, Bhaktapur',
            'constituency': 'Bhaktapur',
            'is_eligible': True
        },
        {
            'citizenship_number': 'CTZ90123456',
            'full_name': 'Suresh Pradhan',
            'date_of_birth': datetime(1989, 12, 5),
            'address': '369 Taumadhi, Bhaktapur',
            'constituency': 'Bhaktapur',
            'is_eligible': True
        },
        {
            'citizenship_number': 'CTZ01234567',
            'full_name': 'Anita Shakya',
            'date_of_birth': datetime(1994, 6, 28),
            'address': '741 Dattatreya, Bhaktapur',
            'constituency': 'Bhaktapur',
            'is_eligible': True
        },

        # One ineligible citizen for testing
        {
            'citizenship_number': 'CTZ99999999',
            'full_name': 'Test Ineligible',
            'date_of_birth': datetime(1980, 1, 1),
            'address': '000 Test Street, Kathmandu',
            'constituency': 'Kathmandu',
            'is_eligible': False
        }
    ]

    for citizen_data in citizens_data:
        citizen = Citizen(**citizen_data)
        citizen.save()

    print(f"Created {len(citizens_data)} citizens")
    print(f"  Kathmandu: 4 citizens")
    print(f"  Lalitpur: 3 citizens")
    print(f"  Bhaktapur: 3 citizens")


def seed_candidates():
    """Create the candidate pool (5 candidates per constituency)."""
    db = get_db()

    # Clear existing candidates
    db.candidates.delete_many({})

    for candidate_data in CANDIDATE_POOL:
        candidate = Candidate.create(
            name=candidate_data['name'],
            party=candidate_data['party'],
            constituency=candidate_data['constituency']
        )

    # Create indexes
    Candidate.ensure_indexes()

    print(f"Created {len(CANDIDATE_POOL)} candidates in pool:")
    print(f"  Kathmandu: 5 candidates")
    print(f"  Lalitpur: 5 candidates")
    print(f"  Bhaktapur: 5 candidates")


def seed_admin():
    """Create default admin account."""
    db = get_db()

    # Clear existing admins
    db.admins.delete_many({})

    # Create default admin
    # Username: admin
    # Password: Admin@123
    admin = Admin.create(
        username='admin',
        password='Admin@123'
    )

    print(f"Created admin account:")
    print(f"  Username: admin")
    print(f"  Password: Admin@123")


def seed_election():
    """Create a sample dual-ballot election."""
    db = get_db()

    # Clear existing elections
    db.elections.delete_many({})

    # Create sample election (starts now, ends in 7 days)
    start_date = datetime.utcnow()
    end_date = datetime.utcnow() + timedelta(days=7)

    # FPTP Candidates - at least 2 per constituency
    # Some candidates belong to PR parties, some are independent
    candidates = [
        # Kathmandu candidates
        {'name': 'Rajesh Koirala', 'party': 'Nepal Democratic Party', 'constituency': 'Kathmandu'},
        {'name': 'Sunita Rai', 'party': 'United Peoples Front', 'constituency': 'Kathmandu'},
        {'name': 'Deepak Shah', 'party': 'Independent', 'constituency': 'Kathmandu'},

        # Lalitpur candidates
        {'name': 'Kamala Basnet', 'party': 'Progressive Alliance', 'constituency': 'Lalitpur'},
        {'name': 'Binod Gurung', 'party': 'Citizens Movement', 'constituency': 'Lalitpur'},
        {'name': 'Sarita Manandhar', 'party': 'Independent', 'constituency': 'Lalitpur'},

        # Bhaktapur candidates
        {'name': 'Prakash Joshi', 'party': 'National Unity Party', 'constituency': 'Bhaktapur'},
        {'name': 'Mina Tuladhar', 'party': 'Nepal Democratic Party', 'constituency': 'Bhaktapur'},
        {'name': 'Gopal Shrestha', 'party': 'Independent', 'constituency': 'Bhaktapur'},
    ]

    election = Election.create(
        name='National Assembly Election 2024',
        description='Vote for your constituency representative (FPTP) and your preferred political party (PR). '
                    'This dual-ballot election will determine both direct constituency seats and proportional representation seats.',
        start_date=start_date,
        end_date=end_date,
        candidates=candidates,
        parties=PR_PARTIES,
        total_pr_seats=110
    )

    print(f"Created dual-ballot election: {election.name}")
    print(f"  Election ID: {election.election_id}")
    print(f"  Start: {start_date}")
    print(f"  End: {end_date}")
    print(f"  FPTP Candidates: {len(candidates)}")
    print(f"    - Kathmandu: 3 candidates")
    print(f"    - Lalitpur: 3 candidates")
    print(f"    - Bhaktapur: 3 candidates")
    print(f"  PR Parties: {len(PR_PARTIES)}")
    print(f"  PR Seats: 110")

    # Create a future election
    future_start = datetime.utcnow() + timedelta(days=14)
    future_end = datetime.utcnow() + timedelta(days=21)

    future_candidates = [
        # Kathmandu
        {'name': 'Arun Subedi', 'party': 'Nepal Democratic Party', 'constituency': 'Kathmandu'},
        {'name': 'Radha Poudel', 'party': 'Progressive Alliance', 'constituency': 'Kathmandu'},
        # Lalitpur
        {'name': 'Sanjay Malla', 'party': 'United Peoples Front', 'constituency': 'Lalitpur'},
        {'name': 'Urmila Dangol', 'party': 'Citizens Movement', 'constituency': 'Lalitpur'},
        # Bhaktapur
        {'name': 'Nabin Chitrakar', 'party': 'National Unity Party', 'constituency': 'Bhaktapur'},
        {'name': 'Pramila Suwal', 'party': 'Independent', 'constituency': 'Bhaktapur'},
    ]

    future_election = Election.create(
        name='Provincial Assembly Election 2024',
        description='Vote for provincial assembly representatives. Choose your constituency candidate and party.',
        start_date=future_start,
        end_date=future_end,
        candidates=future_candidates,
        parties=PR_PARTIES,
        total_pr_seats=110
    )

    print(f"\nCreated future election: {future_election.name}")
    print(f"  Election ID: {future_election.election_id}")


def clear_votes_and_voters():
    """Clear votes and registered voters for fresh testing."""
    db = get_db()
    db.votes.delete_many({})
    db.voters.delete_many({})
    print("Cleared all votes and registered voters")


def main():
    """Run all seed functions."""
    print("=" * 60)
    print("Seeding Secure Voting System Database (Dual-Ballot System)")
    print("=" * 60)

    # Create Flask app to get database connection
    app = create_app()

    with app.app_context():
        print("\n1. Seeding citizens with constituencies...")
        seed_citizens()

        print("\n2. Creating candidate pool...")
        seed_candidates()

        print("\n3. Creating admin account...")
        seed_admin()

        print("\n4. Creating dual-ballot elections...")
        seed_election()

        print("\n5. Clearing votes and voters (fresh start)...")
        clear_votes_and_voters()

    print("\n" + "=" * 60)
    print("Database seeding complete!")
    print("=" * 60)
    print("\nDual-Ballot Voting System Ready!")
    print("\nConstituencies:")
    print("  - Kathmandu (4 eligible citizens)")
    print("  - Lalitpur (3 eligible citizens)")
    print("  - Bhaktapur (3 eligible citizens)")
    print("\nPR Parties (110 seats):")
    for party in PR_PARTIES:
        print(f"  - {party['name']}")
    print("\nYou can now:")
    print("1. Register as a voter using any citizen's data")
    print("2. Login to admin panel with: admin / Admin@123")
    print("3. Cast dual ballots (FPTP + PR)")
    print("\nSample citizens for registration:")
    print("  Kathmandu:")
    print("    - CTZ12345678 / Ram Sharma / 1990-05-15")
    print("    - CTZ23456789 / Sita Thapa / 1985-08-22")
    print("  Lalitpur:")
    print("    - CTZ56789012 / Krishna Maharjan / 1995-07-08")
    print("    - CTZ67890123 / Laxmi Shrestha / 1991-01-25")
    print("  Bhaktapur:")
    print("    - CTZ89012345 / Maya Karki / 1993-04-18")
    print("    - CTZ90123456 / Suresh Pradhan / 1989-12-05")


if __name__ == '__main__':
    main()
