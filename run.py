"""
Entry point for the Secure Voting System application.

Usage:
    python run.py

The application will start on http://localhost:5000
"""

from app import create_app

app = create_app()

if __name__ == '__main__':
    print("=" * 50)
    print("Secure Voting System")
    print("=" * 50)
    print("\nStarting server...")
    print("Application URL: http://localhost:5000")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 50)

    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )
