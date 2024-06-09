import os
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
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


all_branches = session.query(Branch).all()
all_branch_names = [b.name for b in all_branches]


all_streamers = session.query(Streamer).all()
all_streamer_names = [s.english_name for s in all_streamers]


all_currencies = session.scalars(
    select(SuperChat.currency, func.count(SuperChat.currency).label("count"))
    .group_by(SuperChat.currency)
    .order_by(func.count(SuperChat.currency).desc())
).all()


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


def fetch_data_by_streamer(
    start_date: datetime, end_date: datetime, branch: Branch | None, streamer: Streamer | None
) -> pd.DataFrame:
    rates = fetch_rates(all_currencies)
    with Session() as session:
        query = (
            session.query(
                SuperChat.currency,
                func.count(SuperChat.id).label("count"),
                func.sum(SuperChat.amount_value).label("total_amount"),
                func.count(SuperChat.channel_id.distinct()).label("unique_supporters"),
            )
            .filter(
                SuperChat.timestamp >= start_date,
                SuperChat.timestamp < end_date + timedelta(days=1),
            )
        )
        if streamer is not None:
            query.filter(SuperChat.streamer_id == streamer.id)
        elif branch is not None:
            query.filter(Streamer.branch_id == branch.id)
            query.join(SuperChat.streamer)
        data = query.group_by(SuperChat.currency).all()

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


def fetch_data_by_currency(
    start_date: datetime, end_date: datetime, currency: str, branch_name: str
) -> pd.DataFrame:
    rates = fetch_rates(all_currencies)
    with Session() as session:
        query = (
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
                SuperChat.timestamp < end_date + timedelta(days=1),
            )
        )
        if branch_name != "All":
            query = query.filter(Branch.name == branch_name)
        data = query.group_by(Streamer.id, Streamer.english_name, Branch.name).all()

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

start_date = st.date_input(
    "Start date (UTC)",
    datetime.now() - timedelta(days=30),
    min_value=datetime(2024, 1, 1),
    max_value=datetime.now(),
)
end_date = st.date_input(
    "End date (UTC)", datetime.now(), min_value=start_date, max_value=datetime.now()
)
selected_type = st.selectbox("Type", ["Streamer", "Currency"])
match selected_type:
    case "Streamer":
        branch_name = st.selectbox("Branch", ["All"] + all_branch_names)
        if branch_name == "All":
            branch = None
        else:
            branch = next(b for b in all_branches if b.name == branch_name)
        filtered_streamers = [s for s in all_streamers if branch is None or s.branch_id == branch.id]
        filtered_streamer_names = [s.english_name for s in filtered_streamers]
        target = st.selectbox("Streamer", ["All"] + filtered_streamer_names)
        df = fetch_data_by_streamer(
            start_date, end_date, branch, all_streamers[all_streamer_names.index(target)] if target != "All" else None
        )
        if df.empty:
            st.error("No data found.")
            st.stop()
        tabs = st.tabs(["Total Amount (USD)", "Count", "Unique Supporters"])
        figs = []
        for value_name in ("Total Amount (USD)", "Count", "Unique Supporters"):
            fig = px.pie(
                df,
                names="Currency",
                values=value_name,
                title=f"{value_name} by Currency for {target}",
            )
            fig.update_traces(textposition="inside", textinfo="percent+label")
            fig.add_annotation(
                text=f"{start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}  (Total: {df[value_name].sum()})",
                xref="paper",
                yref="paper",
                x=0.5,
                y=-0.1,
                showarrow=False,
                font_size=10,
            )
            figs.append(fig)
    case "Currency":
        target = st.selectbox("Currency", all_currencies)
        branch_name = st.selectbox("Branch", ["All"] + all_branch_names)
        df = fetch_data_by_currency(start_date, end_date, target, branch_name)
        if df.empty:
            st.error("No data found.")
            st.stop()
        tabs = st.tabs(["Total Amount", "Count", "Unique Supporters"])
        figs = []
        for value_name in ("Total Amount", "Count", "Unique Supporters"):
            fig = px.pie(
                df,
                names="Streamer",
                values=value_name,
                title=f"{value_name} by Streamer for {target}",
            )
            fig.update_traces(textposition="inside", textinfo="percent+label")
            fig.add_annotation(
                text=f"{start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}  (Total: {df[value_name].sum()})",
                xref="paper",
                yref="paper",
                x=0.5,
                y=-0.1,
                showarrow=False,
                font_size=10,
            )
            figs.append(fig)
    case _:
        st.error("Invalid type selected.")
        st.stop()


with tabs[0]:
    st.plotly_chart(figs[0], use_container_width=True)
    st.dataframe(df.sort_values("Total Amount (USD)", ascending=False), hide_index=True)
with tabs[1]:
    st.plotly_chart(figs[1], use_container_width=True)
    st.dataframe(df.sort_values("Count", ascending=False), hide_index=True)
with tabs[2]:
    st.plotly_chart(figs[2], use_container_width=True)
    st.dataframe(df.sort_values("Unique Supporters", ascending=False), hide_index=True)
