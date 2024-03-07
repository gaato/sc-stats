import os
from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from sqlalchemy import func, select

from db import Session, Streamer, SuperChat

session = Session()


all_streamers = session.query(Streamer).all()
all_streamer_names = [s.english_name for s in all_streamers]
all_currencies = session.scalars(
    select(SuperChat.currency, func.count(SuperChat.currency).label("count"))
    .group_by(SuperChat.currency)
    .order_by(func.count(SuperChat.currency).desc())
).all()


@st.cache_data(ttl=60 * 60 * 24)
def fetch_rates(all_currencies: list[str]) -> dict[str, float]:
    API_URL = "https://api.currencybeacon.com/v1/latest"
    params = {
        "base": "USD",
        "symbols": ",".join(all_currencies),
        "api_key": os.environ["CURRENCYBEACON_API_KEY"],
    }
    response = requests.get(API_URL, params=params)
    response.raise_for_status()
    return response.json()["rates"]


def fetch_data_by_streamer(start_date, end_date, streamer):
    rates = fetch_rates(all_currencies)
    with Session() as session:
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
    return df


def fetch_data_by_currency(start_date, end_date, currency):
    rates = fetch_rates(all_currencies)
    with Session() as session:
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
    return df


st.title("sc-stats")

start_date = st.date_input("Start date", datetime.now() - timedelta(days=30))
end_date = st.date_input("End date", datetime.now())
category = st.selectbox("Category", ["Streamer", "Currency"])
if category == "Streamer":
    target = st.selectbox("Streamer", all_streamer_names)
else:
    target = st.selectbox("Currency", all_currencies)

if category == "Streamer":
    df = fetch_data_by_streamer(
        start_date, end_date, all_streamers[all_streamer_names.index(target)]
    )
    tabs = st.tabs(["Total Amount (USD)", "Count", "Unique Fans"])
    figs = [
        go.Figure(
            data=[
                go.Pie(
                    labels=df["Currency"],
                    values=df["Total Amount (USD)"],
                    name="Total Amount (USD)",
                )
            ]
        ),
        go.Figure(
            data=[
                go.Pie(
                    labels=df["Currency"],
                    values=df["Count"],
                    name="Count",
                )
            ]
        ),
        go.Figure(
            data=[
                go.Pie(
                    labels=df["Currency"],
                    values=df["Unique Fans"],
                    name="Unique Fans",
                )
            ]
        ),
    ]
else:
    df = fetch_data_by_currency(start_date, end_date, target)
    tabs = st.tabs(["Total Amount", "Count", "Unique Fans"])
    figs = [
        go.Figure(
            data=[
                go.Pie(
                    labels=df["Streamer"],
                    values=df["Total Amount"],
                    name="Total Amount",
                )
            ]
        ),
        go.Figure(
            data=[
                go.Pie(
                    labels=df["Streamer"],
                    values=df["Count"],
                    name="Count",
                )
            ]
        ),
        go.Figure(
            data=[
                go.Pie(
                    labels=df["Streamer"],
                    values=df["Unique Fans"],
                    name="Unique Fans",
                )
            ]
        ),
    ]

with tabs[0]:
    st.plotly_chart(figs[0], use_container_width=True)
    st.dataframe(df.sort_values("Total Amount (USD)", ascending=False), hide_index=True)
with tabs[1]:
    st.plotly_chart(figs[1], use_container_width=True)
    st.dataframe(df.sort_values("Count", ascending=False), hide_index=True)
with tabs[2]:
    st.plotly_chart(figs[2], use_container_width=True)
    st.dataframe(df.sort_values("Unique Fans", ascending=False), hide_index=True)
