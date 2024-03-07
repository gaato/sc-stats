import os
from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from sqlalchemy import func, select

from db import Branch, Session, Streamer, SuperChat

session = Session()


st.set_page_config(
    page_title="Superchat Currency Stats for hololive production",
    page_icon=":globe_with_meridians:",
    menu_items={
        "Get Help": "https://x.com/gaato11",
        "Report a bug": "https://github.com/gaato/sc-stats/issues",
        "About": "This app visualizes the relationship "
        "between hololive production talents and fan regions through the superchat currencies. "
        "Developed by [がーと / gaato](https://x.com/gaato11).\n\n"
        "This app is not affiliated with Cover Corp.",
    },
)


@st.cache_resource(ttl=3600)
def fetch_all_branches():
    return session.query(Branch).all()


all_branches = fetch_all_branches()
all_branch_names = [b.name for b in all_branches]


@st.cache_resource(ttl=3600)
def fetch_all_streamers():
    return session.query(Streamer).all()


all_streamers = fetch_all_streamers()
all_streamer_names = [s.english_name for s in all_streamers]


@st.cache_data(ttl=3600)
def fetch_all_currencies():
    return session.scalars(
        select(SuperChat.currency, func.count(SuperChat.currency).label("count"))
        .group_by(SuperChat.currency)
        .order_by(func.count(SuperChat.currency).desc())
    ).all()


all_currencies = fetch_all_currencies()


@st.cache_data(ttl=3600 * 24)
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
                func.count(SuperChat.channel_id.distinct()).label("unique_supporters"),
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
                "Unique Supporters": d.unique_supporters,
            }
            for d in data
        ]
    )
    return df


def fetch_data_by_currency(start_date, end_date, currency):
    rates = fetch_rates(all_currencies)
    with Session() as session:
        data = (
            session.query(
                Streamer.id,
                Streamer.english_name,
                Branch.name.label("branch_name"),
                func.count(SuperChat.id).label("count"),
                func.sum(SuperChat.amount_value).label("total_amount"),
                func.count(SuperChat.channel_id.distinct()).label("unique_supporters"),
            )
            .join(Streamer, SuperChat.streamer_id == Streamer.id)
            .join(Branch, Streamer.branch_id == Branch.id)
            .filter(
                SuperChat.currency == currency,
                SuperChat.timestamp >= start_date,
                SuperChat.timestamp < end_date,
            )
            .group_by(Streamer.id, Streamer.english_name, Branch.name)
            .all()
        )
    df = pd.DataFrame(
        [
            {
                "Streamer ID": d.id,
                "Streamer": d.english_name,
                "Branch": d.branch_name,
                "Count": d.count,
                "Total Amount": float(d.total_amount),
                "Total Amount (USD)": float(d.total_amount) / rates[currency],
                "Unique Supporters": d.unique_supporters,
            }
            for d in data
        ]
    )
    return df


st.title("Superchat Currency Stats for hololive production")

start_date = st.date_input("Start date", datetime.now() - timedelta(days=30))
end_date = st.date_input("End date", datetime.now())
category = st.selectbox("Category", ["Streamer", "Currency"])
if category == "Streamer":
    branch_name = st.selectbox("Branch", all_branch_names)
    branch = next(b for b in all_branches if b.name == branch_name)
    filtered_streamers = [s for s in all_streamers if s.branch_id == branch.id]
    filtered_streamer_names = [s.english_name for s in filtered_streamers]
    target = st.selectbox("Streamer", filtered_streamer_names)
else:
    target = st.selectbox("Currency", all_currencies)

if category == "Streamer":
    df = fetch_data_by_streamer(
        start_date, end_date, all_streamers[all_streamer_names.index(target)]
    )
    if df.empty:
        st.error("No data found.")
        st.stop()
    tabs = st.tabs(["Total Amount (USD)", "Count", "Unique Supporters"])
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
                    values=df["Unique Supporters"],
                    name="Unique Supporters",
                )
            ]
        ),
    ]
else:
    df = fetch_data_by_currency(start_date, end_date, target)
    if df.empty:
        st.error("No data found.")
        st.stop()
    tabs = st.tabs(["Total Amount", "Count", "Unique Supporters"])
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
                    values=df["Unique Supporters"],
                    name="Unique Supporters",
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
    st.dataframe(df.sort_values("Unique Supporters", ascending=False), hide_index=True)
