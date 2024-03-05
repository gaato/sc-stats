import argparse
import os
from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd
import requests
from sqlalchemy import func, select

from db import Session, Streamer, SuperChat

parser = argparse.ArgumentParser(
    description="Visualize SuperChats for a specified time period."
)
parser.add_argument("period", type=str, help="Time period (YYYY or YYYY-M)")

args = parser.parse_args()


def parse_period(period):
    global yearly
    if "-" in period:
        yearly = False
        start_date = datetime.strptime(period + "-01", "%Y-%m-%d")
        if start_date.month == 12:
            end_date = datetime(start_date.year + 1, 1, 1)
        else:
            end_date = datetime(start_date.year, start_date.month + 1, 1)
    else:
        yearly = True
        start_date = datetime.strptime(period, "%Y")
        end_date = datetime(start_date.year + 1, 1, 1)
    return start_date, end_date


start_date, end_date = parse_period(args.period)

session = Session()

base_output_dir = f"output/{start_date.strftime('%Y')}" if yearly else f"output/{start_date.strftime('%Y-%m')}"
streamers_output_dir = os.path.join(base_output_dir, "streamers")
currencies_output_dir = os.path.join(base_output_dir, "currencies")

os.makedirs(streamers_output_dir, exist_ok=True)
os.makedirs(currencies_output_dir, exist_ok=True)

streamers = session.query(Streamer).all()
all_currencies = session.scalars(select(SuperChat.currency).distinct()).all()


API_URL = "https://api.currencybeacon.com/v1/historical"
params = {
    "base": "USD",
    "date": start_date.strftime("%Y-%m-%d"),
    "symbols": ",".join(all_currencies),
    "api_key": os.environ["CURRENCYBEACON_API_KEY"],
}
response = requests.get(API_URL, params=params)
response.raise_for_status()
rates = response.json()["rates"]


for streamer in streamers:
    data = (
        session.query(
            SuperChat.currency,
            func.count(SuperChat.id).label("count"),
            func.sum(SuperChat.amount_value).label("total_amount"),
            func.count(SuperChat.channel_id.distinct()).label("unique_fans"),
        )
        .filter(
            SuperChat.streamer_id == streamer.id,
            SuperChat.timestamp >= start_date,
            SuperChat.timestamp < end_date,
        )
        .group_by(SuperChat.currency)
        .all()
    )

    if not data:
        continue

    df = pd.DataFrame(
        [
            {
                "Currency": d.currency,
                "Count": d.count,
                "Total Amount": float(d.total_amount),
                "Total Amount (USD)": float(d.total_amount) / rates[d.currency],
                "Unique Fans": d.unique_fans,
            }
            for d in data
        ]
    ).sort_values("Total Amount (USD)", ascending=False)

    df.to_csv(
        os.path.join(
            streamers_output_dir, f"{streamer.english_name.replace(' ', '_')}.csv"
        ),
        index=False,
    )

    fig, axs = plt.subplots(1, 3, figsize=(21, 7))
    fig.suptitle(f"Total SuperChats: N={df["Count"].sum()}", fontsize=12, y=0.05)
    axs[0].pie(
        df["Count"],
        labels=df["Currency"],
        autopct="%1.1f%%",
        startangle=90,
        counterclock=False,
    )
    axs[0].set_title(f"SuperChat Counts for {streamer.english_name}")
    axs[1].pie(
        df["Total Amount (USD)"],
        labels=df["Currency"],
        autopct="%1.1f%%",
        startangle=90,
        counterclock=False,
    )
    axs[1].set_title(f"SuperChat Amounts in USD for {streamer.english_name}")
    axs[2].pie(
        df["Unique Fans"],
        labels=df["Currency"],
        autopct="%1.1f%%",
        startangle=90,
        counterclock=False,
    )
    axs[2].set_title(f"Unique Fans for {streamer.english_name}")
    plt.tight_layout()
    plt.savefig(
        os.path.join(
            streamers_output_dir, f"{streamer.english_name.replace(' ', '_')}.png"
        ),
        bbox_inches="tight",
        pad_inches=0.5,
    )
    plt.close()

for currency in all_currencies:
    data = (
        session.query(
            Streamer.id,
            Streamer.english_name,
            func.count(SuperChat.id).label("count"),
            func.sum(SuperChat.amount_value).label("total_amount"),
            func.count(SuperChat.channel_id.distinct()).label("unique_fans"),
        )
        .join(Streamer, SuperChat.streamer_id == Streamer.id)
        .filter(
            SuperChat.currency == currency,
            SuperChat.timestamp >= start_date,
            SuperChat.timestamp < end_date,
        )
        .group_by(Streamer.id, Streamer.english_name)
        .group_by(Streamer.id)
        .all()
    )

    if not data:
        continue

    df = pd.DataFrame(
        [
            {
                "Streamer ID": d.id,
                "Streamer": d.english_name,
                "Count": d.count,
                "Total Amount": float(d.total_amount),
                "Total Amount (USD)": float(d.total_amount) / rates[currency],
                "Unique Fans": d.unique_fans,
            }
            for d in data
        ]
    ).sort_values("Streamer ID")

    df.to_csv(os.path.join(currencies_output_dir, f"{currency}.csv"))

    fig, axs = plt.subplots(1, 3, figsize=(21, 7))
    fig.suptitle(f"Total SuperChats: N={df["Count"].sum()}", fontsize=12, y=0.05)
    axs[0].pie(
        df["Count"],
        labels=df["Streamer"],
        autopct="%1.1f%%",
        startangle=90,
        counterclock=False,
    )
    axs[0].set_title(f"SuperChat Counts using {currency}")
    axs[1].pie(
        df["Total Amount (USD)"],
        labels=df["Streamer"],
        autopct="%1.1f%%",
        startangle=90,
        counterclock=False,
    )
    axs[1].set_title(f"SuperChat Amounts using {currency}")
    axs[2].pie(
        df["Unique Fans"],
        labels=df["Streamer"],
        autopct="%1.1f%%",
        startangle=90,
        counterclock=False,
    )
    axs[2].set_title(f"Unique Fans using {currency}")
    plt.tight_layout()
    plt.savefig(
        os.path.join(currencies_output_dir, f"{currency}.png"),
        bbox_inches="tight",
        pad_inches=0.5,
    )
    plt.close()

session.close()
