"""Fixed PR parties with symbols for all elections."""

# 20 Fixed PR Parties with Bootstrap Icon symbols
PR_PARTIES = [
    {'name': 'Nepal Democratic Party', 'symbol': 'bi-sun-fill'},
    {'name': 'United Peoples Front', 'symbol': 'bi-star-fill'},
    {'name': 'Progressive Alliance', 'symbol': 'bi-lightning-fill'},
    {'name': 'Citizens Movement', 'symbol': 'bi-people-fill'},
    {'name': 'National Unity Party', 'symbol': 'bi-flag-fill'},
    {'name': 'Rastriya Congress', 'symbol': 'bi-tree-fill'},
    {'name': 'Janata Dal', 'symbol': 'bi-flower1'},
    {'name': 'Socialist Front', 'symbol': 'bi-hammer'},
    {'name': 'Green Party Nepal', 'symbol': 'bi-flower2'},
    {'name': 'Workers Alliance', 'symbol': 'bi-gear-fill'},
    {'name': 'Federal Democratic Party', 'symbol': 'bi-building-fill'},
    {'name': 'Peoples Republic Party', 'symbol': 'bi-bell-fill'},
    {'name': 'Democratic Socialist Party', 'symbol': 'bi-book-fill'},
    {'name': 'Unity Front Nepal', 'symbol': 'bi-hand-thumbs-up-fill'},
    {'name': 'Liberal Democratic Party', 'symbol': 'bi-feather'},
    {'name': 'Nationalist Party', 'symbol': 'bi-shield-fill'},
    {'name': 'Reform Party Nepal', 'symbol': 'bi-arrow-clockwise'},
    {'name': 'Independent Alliance', 'symbol': 'bi-gem'},
    {'name': 'Peoples Voice Party', 'symbol': 'bi-megaphone-fill'},
    {'name': 'Mountain Party', 'symbol': 'bi-triangle-fill'},
]


def get_party_by_name(name: str) -> dict:
    """Get party details by name."""
    for party in PR_PARTIES:
        if party['name'] == name:
            return party
    return None


def get_all_party_names() -> list:
    """Get list of all party names."""
    return [party['name'] for party in PR_PARTIES]
