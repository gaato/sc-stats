import logging
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from sqlalchemy import select

from collector import collect_superchats
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


def get_from_channel(
    streamer: Streamer,
    offset: int = 0,
    done_before=datetime(2024, 3, 1, tzinfo=ZoneInfo("Asia/Tokyo")),
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
        video_date = datetime.fromisoformat(end_actual).replace(tzinfo=ZoneInfo("UTC"))
        video_date_jst = video_date.astimezone(ZoneInfo("Asia/Tokyo"))
        if video_date_jst < done_before:
            return
        if video["id"] in done_videos:
            logger.debug(f"Video {video['title']} already collected. Skipping.")
            continue
        logger.info(f"Collecting superchats for video {video['title']} ({video['id']})")
        videos.append(video)
        try:
            superchats = collect_superchats(video["id"], streamer.id)
        except Exception as e:
            logger.error(
                f"Failed to collect superchats for video {video['title']} ({video['id']}) - {e}"
            )
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
    started_at = datetime.now(tz=ZoneInfo("Asia/Tokyo"))
    streamers = session.query(Streamer).filter_by(inactive=False).all()
    done_before = (
        session.query(Collection.timestamp)
        .order_by(Collection.timestamp.desc())
        .scalar()
    )
    if not done_before:
        done_before = datetime(2024, 1, 1, tzinfo=ZoneInfo("Asia/Tokyo"))
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
