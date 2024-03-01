import os
import traceback

import requests

from db import Branch, Session, Streamer

session = Session()


def initialize_branches():
    branches_info = [
        {"name": "hololive", "category": "hololive", "language": "ja"},
        {"name": "HOLOSTARS", "category": "HOLOSTARS", "language": "ja"},
        {"name": "hololive Indonesia", "category": "hololive", "language": "id"},
        {"name": "hololive English", "category": "hololive", "language": "en"},
        {"name": "HOLOSTARS English", "category": "HOLOSTARS", "language": "en"},
        {"name": "hololive DEV_IS", "category": "hololive", "language": "ja"},
    ]

    existing_branches = session.query(Branch).all()
    existing_branch_names = [branch.name for branch in existing_branches]

    for branch_info in branches_info:
        if branch_info["name"] not in existing_branch_names:
            new_branch = Branch(
                name=branch_info["name"],
                category=branch_info["category"],
                language=branch_info["language"],
            )
            session.add(new_branch)

    try:
        session.commit()
        print("Branches initialized.")
    except Exception:
        session.rollback()
        print("Failed to initialize branches.")
        traceback.print_exc()
    finally:
        session.close()


def initialize_streamers(offset: int = 0):
    URL = "https://holodex.net/api/v2/channels"
    params = {
        "type": "vtuber",
        "offset": offset,
        "limit": 50,
        "org": "Hololive",
        "sort": "published_at",
        "order": "asc",
    }
    response = requests.get(
        URL,
        params=params,
        headers={"X-APIKEY": os.environ["HOLODEX_API_KEY"]},
    )
    response.raise_for_status()
    channels = response.json()

    branches = session.query(Branch).all()
    print("Available branches:")
    for branch in branches:
        print(f"{branch.id}: {branch.name} ({branch.category}, {branch.language})")

    for channel in channels:
        print()
        for branch in branches:
            print(f"{branch.id}: {branch.name} ({branch.category}, {branch.language})")
        print()
        branch_input = input(f"{channel['name']}: ")
        if branch_input:
            add_channel_to_db(channel, branch_input)

    if len(channels) == 50:
        initialize_streamers(offset + 50)


def add_channel_to_db(channel: dict, branch_input: str):
    branch = session.query(Branch).filter_by(id=int(branch_input)).first()
    if not branch:
        print("Branch not found. Skipping this channel.")
        return

    new_streamer = Streamer(
        name=channel["name"],
        english_name=channel["english_name"],
        photo=channel["photo"],
        channel_id=channel["id"],
        twitter=channel["twitter"],
        inactive=channel["inactive"],
        branch_id=branch.id,
    )
    session.add(new_streamer)
    try:
        session.commit()
        print("Channel added to the database.")
    except Exception as e:
        session.rollback()
        print(f"Failed to add channel to the database: {e}")


initialize_branches()
initialize_streamers()

session.close()
