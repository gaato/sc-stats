from datetime import datetime
from pprint import pprint

import pytchat


def argb_to_rgb(argb: int) -> int:
    red = (argb >> 16) & 0xFF
    green = (argb >> 8) & 0xFF
    blue = argb & 0xFF

    rgb = (red << 16) | (green << 8) | blue
    return rgb


def collect_superchats(video_id: str, streamer_id: int) -> list[dict]:
    superchats = []
    chat = pytchat.create(video_id=video_id)
    while chat.is_alive():
        items = chat.get().items
        if not items:
            break
        for c in items:
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
    return superchats


if __name__ == "__main__":
    pprint(collect_superchats("5sw1tTY4TYo"))
