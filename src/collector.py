import logging
import os
import time
from datetime import datetime, timezone

import pytchat
import requests
from sqlalchemy import select

from db import Collection, DoneVideo, Session, Streamer, SuperChat

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

handler = logging.StreamHandler()
handler.setFormatter(
    logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
)

logger.addHandler(handler)


def argb_to_rgb(argb: int) -> int:
    red = (argb >> 16) & 0xFF
    green = (argb >> 8) & 0xFF
    blue = argb & 0xFF

    rgb = (red << 16) | (green << 8) | blue
    return rgb


def collect_superchats(video_id: str, streamer_id: int) -> tuple[list[dict], bool]:
    superchats = []
    chat = pytchat.create(video_id=video_id)
    found_chat = False
    while chat.is_alive():
        items = chat.get().items
        if not items:
            break
        for c in items:
            found_chat = True
            if c.type == "superChat":
                superchats.append(
                    {
                        "timestamp": datetime.fromtimestamp(c.timestamp / 1000),
                        "currency": c.currency.strip(),
                        "amount_value": c.amountValue,
                        "bg_color": argb_to_rgb(c.bgColor),
                        "channel_id": c.author.channelId,
                        "streamer_id": streamer_id,
                    }
                )
    return superchats, found_chat


def get_from_channel(
    streamer: Streamer,
    offset: int = 0,
    done_before=datetime(2024, 1, 1, tzinfo=timezone.utc),
    done_videos=[],
) -> None:
    URL = "https://holodex.net/api/v2/videos"
    videos = []
    params = {
        "channel_id": streamer.channel_id,
        "status": "past",
        "type": "stream",
        "include": "live_info",
        "sort": "published_at",
        "order": "desc",
        "limit": 50,
        "offset": offset,
    }
    response = requests.get(
        URL,
        params=params,
        headers={"X-APIKEY": os.environ["HOLODEX_API_KEY"]},
    )
    response.raise_for_status()
    data = response.json()

    for video in data:
        end_actual = video.get("end_actual")
        if not end_actual:
            logger.debug(f"Video {video['title']} is not a stream. Skipping.")
            continue
        video_date = datetime.fromisoformat(end_actual)
        if video_date < done_before:
            return
        if video["id"] in done_videos:
            logger.debug(f"Video {video['title']} already collected. Skipping.")
            continue
        logger.info(f"Collecting superchats for video {video['title']} ({video['id']})")
        videos.append(video)
        try:
            superchats, found_chat = collect_superchats(video["id"], streamer.id)
        except Exception as e:
            logger.error(
                f"Failed to collect superchats for video {video['title']} ({video['id']}) - {e}"
            )
            continue
        if not found_chat:
            logger.info(f"No chat found for video {video['title']} ({video['id']})")
            continue
        logger.info(f"{len(superchats)} superchats collected.")
        session.bulk_insert_mappings(SuperChat, superchats)
        session.add(DoneVideo(id=video["id"]))
        session.commit()
        logger.info(f"Superchats collected for video {video['title']} ({video['id']})")

    if len(videos) == 50:
        get_from_channel(
            streamer=streamer,
            offset=offset + 50,
            done_before=done_before,
            done_videos=done_videos,
        )


def main():
    started_at = datetime.now()
    streamers = session.query(Streamer).filter_by(inactive=False).all()
    done_before = (
        session.query(Collection.timestamp)
        .order_by(Collection.timestamp.desc())
        .scalar()
    )
    if done_before:
        done_before = done_before.replace(tzinfo=timezone.utc)
    else:
        done_before = datetime(2024, 1, 1, tzinfo=timezone.utc)
    done_videos = session.scalars(select(DoneVideo.id)).all()
    for streamer in streamers:
        logger.info(f"Collecting superchats for {streamer.name}")
        get_from_channel(
            streamer,
            done_before=done_before,
            done_videos=done_videos,
        )
        logger.info(f"Superchats collected for {streamer.name}")
    session.add(Collection(timestamp=started_at))
    logger.info("All superchats collected.")


if __name__ == "__main__":
    while True:
        session = Session()
        main()
        session.close()
        logger.info("Sleeping for 1 hour.")
        time.sleep(3600)
