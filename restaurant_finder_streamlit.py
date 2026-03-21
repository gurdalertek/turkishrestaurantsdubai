import html
import math
import re
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
import pydeck as pdk
import streamlit as st
import streamlit.components.v1 as components

APP_TITLE = "Turkish Restaurants Dubai"
DEFAULT_FILENAMES = [
    "TurkishRestaurantsDubai.xlsx",
    "Turkish Restaurants Dubai - v06g.xlsx",
]

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .block-container {
        max-width: 1150px;
        padding-top: 0.9rem;
        padding-bottom: 5rem;
    }
    h1, h2, h3 { line-height: 1.15; }
    .stButton > button,
    .stDownloadButton > button {
        width: 100%;
        min-height: 44px;
        border-radius: 14px;
        font-weight: 600;
    }
    .metric-chip {
        padding: 0.8rem 0.95rem;
        border: 1px solid rgba(49, 51, 63, 0.18);
        border-radius: 16px;
        background: rgba(255,255,255,0.72);
        margin-bottom: 0.6rem;
    }
    .restaurant-card {
        border: 1px solid rgba(49, 51, 63, 0.14);
        border-radius: 18px;
        padding: 0.95rem 1rem;
        background: #ffffff;
        box-shadow: 0 1px 10px rgba(0,0,0,0.03);
        margin-bottom: 0.9rem;
        min-height: 170px;
    }
    .small-muted {
        color: rgba(49, 51, 63, 0.72);
        font-size: 0.93rem;
    }
    .card-meta {
        display: flex;
        gap: 0.9rem;
        flex-wrap: wrap;
        margin-bottom: 0.35rem;
    }
    iframe { border-radius: 18px; }

    /* Make Streamlit columns stack nicely on small screens */
    @media (max-width: 768px) {
        .block-container {
            padding-left: 0.8rem;
            padding-right: 0.8rem;
            padding-bottom: 6rem;
        }
        div[data-testid="stHorizontalBlock"] {
            flex-wrap: wrap;
            gap: 0.75rem;
        }
        div[data-testid="column"] {
            min-width: 100% !important;
            flex: 1 1 100% !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def find_default_file() -> Path | None:
    base = Path(__file__).resolve().parent
    for name in DEFAULT_FILENAMES:
        path = base / name
        if path.exists():
            return path
    return None



def normalize_phone(value):
    if pd.isna(value):
        return ""
    try:
        as_int = int(float(value))
        return f"+{as_int}"
    except Exception:
        return str(value).strip()



def extract_precise_coords(url: str):
    if pd.isna(url):
        return None, None, "missing"

    text = str(url)
    precise_matches = re.findall(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", text)
    if precise_matches:
        lat, lng = precise_matches[-1]
        return float(lat), float(lng), "place_coords"

    return None, None, "no_precise_coords"



def card_html(row) -> str:
    name = html.escape(str(row["Restaurant Name"]))
    area = html.escape(str(row["Neighbourhood"] or "Unknown"))
    rating = f"⭐ {row['Google Rating']:.1f}" if pd.notna(row["Google Rating"]) else "⭐ N/A"
    reviews = f"💬 {int(row['Number of Comments'])}" if pd.notna(row["Number of Comments"]) else "💬 N/A"
    phone = html.escape(str(row["Phone"] or "No phone"))
    coords_note = ""
    if pd.isna(row.get("Latitude")) or pd.isna(row.get("Longitude")):
        coords_note = " · map pin hidden"
    map_link_html = ""
    if pd.notna(row.get("Google Maps Link")):
        safe_link = html.escape(str(row["Google Maps Link"]), quote=True)
        map_link_html = f"<a href='{safe_link}' target='_blank'>Open map</a>"

    return f"""
    <div class='restaurant-card'>
        <div style='font-size:1.05rem;font-weight:700;margin-bottom:0.2rem'>{name}</div>
        <div class='small-muted' style='margin-bottom:0.45rem'>{area}</div>
        <div class='card-meta'>
            <span>{rating}</span>
            <span>{reviews}</span>
            <span>📞 {phone}</span>
        </div>
        <div class='small-muted'>{map_link_html}{coords_note}</div>
    </div>
    """


@st.cache_data(show_spinner=False)
def load_data():
    try:
        file_path = find_default_file()
        if file_path is None:
            return None, None
        df = pd.read_excel(file_path, sheet_name="Turkish Restaurants")
    except ImportError:
        st.error("Excel support needs openpyxl. Install it with: pip install openpyxl")
        st.stop()
    except Exception as exc:
        st.error(f"Could not read the Excel file: {exc}")
        st.stop()

    df = df.copy()
    df = df.loc[:, ~df.columns.astype(str).str.contains(r"^Unnamed", na=False)]
    df.columns = [str(c).strip() for c in df.columns]

    expected = [
        "Restaurant Name",
        "Neighbourhood",
        "Number of Comments",
        "Google Rating",
        "TelephoneNumber",
        "Google Maps Link",
    ]
    keep_cols = [c for c in expected if c in df.columns]
    df = df[keep_cols].copy()

    df["Restaurant Name"] = df.get("Restaurant Name", "").fillna("").astype(str).str.strip()
    df["Neighbourhood"] = df.get("Neighbourhood", "").fillna("Unknown").astype(str).str.strip()
    df["Number of Comments"] = pd.to_numeric(df.get("Number of Comments"), errors="coerce")
    df["Google Rating"] = pd.to_numeric(df.get("Google Rating"), errors="coerce")
    df["Phone"] = df.get("TelephoneNumber", "").apply(normalize_phone)

    coords = df.get("Google Maps Link", pd.Series([None] * len(df))).apply(lambda x: pd.Series(extract_precise_coords(x)))
    coords.columns = ["Latitude", "Longitude", "Coord Source"]
    df = pd.concat([df, coords], axis=1)

    df["search_blob"] = (
        df["Restaurant Name"].fillna("")
        + " "
        + df["Neighbourhood"].fillna("")
        + " "
        + df["Phone"].fillna("")
    ).str.lower()

    df = df[df["Restaurant Name"].ne("")].reset_index(drop=True)
    return df, file_path


st.title("🍽️ Turkish Restaurants Dubai")
st.caption("Search restaurants, filter the list, and view them on a mobile-friendly map.")

st.markdown("**Terms of Use:**)
st.caption("This is a vibe coded app, please use at your own risk with no liability for the developer.")
st.caption("The developer is not affiliated, is not endorsing in any way any restaurant, and is not obliged to reply to any messages.")

st.markdown("**Advertisement:**)
st.markdown(
    """
    Learn Prompts for Data Analytics with AI  
    [https://www.researchgate.net/publication/383481066_Data_Analytics_with_Large_Language_Models_LLM_A_Novel_Prompting_Framework](https://www.researchgate.net/publication/383481066_Data_Analytics_with_Large_Language_Models_LLM_A_Novel_Prompting_Framework)
    """
)

df, file_path = load_data()
if df is None:
    expected_names = " or ".join(DEFAULT_FILENAMES)
    st.warning(f"Put {expected_names} in the same folder as this script.")
    st.stop()

st.caption(f"Loaded file: {file_path.name}")

query = st.text_input(
    "Search by restaurant, neighbourhood, or phone",
    placeholder="Try: hallab, dubai mall, deira...",
)

c1, c2, c3 = st.columns([1, 1, 1])
with c1:
    neighbourhoods = ["All"] + sorted([x for x in df["Neighbourhood"].dropna().unique().tolist() if str(x).strip()])
    chosen_neighbourhood = st.selectbox("Neighbourhood", neighbourhoods)
with c2:
    min_rating = st.slider("Minimum Google rating", 3.0, 5.0, 4.0, 0.1)
with c3:
    min_reviews = st.number_input("Minimum comments", min_value=0, value=30, step=10)

filtered = df.copy()
if query:
    filtered = filtered[filtered["search_blob"].str.contains(query.lower(), na=False)]
if chosen_neighbourhood != "All":
    filtered = filtered[filtered["Neighbourhood"] == chosen_neighbourhood]
filtered = filtered[filtered["Google Rating"].fillna(0) >= min_rating]
filtered = filtered[filtered["Number of Comments"].fillna(0) >= min_reviews]
filtered = filtered.sort_values(["Google Rating", "Number of Comments"], ascending=[False, False]).reset_index(drop=True)

m1, m2, m3 = st.columns(3)
avg_rating = filtered["Google Rating"].mean() if len(filtered) else 0
m1.markdown(
    f"<div class='metric-chip'><div class='small-muted'>Matches</div><div style='font-size:1.5rem;font-weight:700'>{len(filtered)}</div></div>",
    unsafe_allow_html=True,
)
m2.markdown(
    f"<div class='metric-chip'><div class='small-muted'>Average rating</div><div style='font-size:1.5rem;font-weight:700'>{avg_rating:.1f}</div></div>",
    unsafe_allow_html=True,
)
m3.markdown(
    f"<div class='metric-chip'><div class='small-muted'>Mappable exactly</div><div style='font-size:1.5rem;font-weight:700'>{int(filtered['Latitude'].notna().sum())}</div></div>",
    unsafe_allow_html=True,
)

list_tab, map_tab = st.tabs(["Restaurant list", "Map view"])

with list_tab:
    if filtered.empty:
        st.info("No restaurants match the current filters.")
    else:
        option_labels = ["Choose a restaurant to show details and map"]
        for _, row in filtered.iterrows():
            rating_text = f"{float(row['Google Rating']):.1f}" if pd.notna(row['Google Rating']) else "N/A"
            option_labels.append(f"{row['Restaurant Name']} · {row['Neighbourhood']} · ⭐ {rating_text}")

        chosen_label = st.selectbox("Selected restaurant", option_labels, index=0)

        if chosen_label != option_labels[0]:
            chosen_idx = option_labels.index(chosen_label) - 1
            selected_row = filtered.iloc[chosen_idx]

            st.subheader(selected_row["Restaurant Name"])
            info_cols = st.columns([1, 1])
            with info_cols[0]:
                st.write(f"**Neighbourhood:** {selected_row['Neighbourhood'] or 'Unknown'}")
                st.write(f"**Google rating:** {selected_row['Google Rating'] if pd.notna(selected_row['Google Rating']) else 'N/A'}")
                st.write(f"**Comments:** {int(selected_row['Number of Comments']) if pd.notna(selected_row['Number of Comments']) else 'N/A'}")
            with info_cols[1]:
                st.write(f"**Phone:** {selected_row['Phone'] or 'N/A'}")
                if pd.notna(selected_row.get("Google Maps Link")):
                    st.link_button("Open in Google Maps", selected_row["Google Maps Link"])

            if pd.notna(selected_row.get("Latitude")) and pd.notna(selected_row.get("Longitude")):
                embed_url = f"https://www.google.com/maps?q={selected_row['Latitude']},{selected_row['Longitude']}&z=15&output=embed"
            elif pd.notna(selected_row.get("Google Maps Link")):
                q = quote_plus(selected_row["Restaurant Name"] + " " + str(selected_row["Neighbourhood"]))
                embed_url = f"https://www.google.com/maps?q={q}&z=15&output=embed"
            else:
                embed_url = None

            if embed_url:
                components.html(
                    f'<iframe src="{embed_url}" width="100%" height="360" style="border:0;" loading="lazy"></iframe>',
                    height=380,
                )

        st.markdown("### Results")
        records = filtered.to_dict("records")
        for start in range(0, len(records), 3):
            row_records = records[start:start + 3]
            cols = st.columns(3)
            for col, row in zip(cols, row_records):
                with col:
                    st.markdown(card_html(row), unsafe_allow_html=True)

with map_tab:
    map_df = filtered.dropna(subset=["Latitude", "Longitude"]).copy()
    if map_df.empty:
        st.info("No exact coordinates are available for the current filters.")
    else:
        st.caption(
            "Only restaurants with exact place coordinates are shown here. "
            "This avoids the incorrect sea locations that came from map viewport centers in some Google links."
        )
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=map_df,
            id="restaurants",
            get_position='[Longitude, Latitude]',
            get_radius=180,
            get_fill_color=[220, 38, 38, 180],
            get_line_color=[255, 255, 255, 220],
            line_width_min_pixels=1,
            stroked=True,
            pickable=True,
            auto_highlight=True,
        )
        view_state = pdk.ViewState(
            latitude=float(map_df["Latitude"].mean()),
            longitude=float(map_df["Longitude"].mean()),
            zoom=10.8,
            pitch=0,
        )
        tooltip = {
            "html": "<b>{Restaurant Name}</b><br/>{Neighbourhood}<br/>Rating: {Google Rating}<br/>Comments: {Number of Comments}",
            "style": {"backgroundColor": "white", "color": "black"},
        }
        st.pydeck_chart(
            pdk.Deck(
                map_provider="carto",
                map_style=None,
                initial_view_state=view_state,
                layers=[layer],
                tooltip=tooltip,
            ),
            use_container_width=True,
            height=520,
        )

        st.dataframe(
            map_df[["Restaurant Name", "Neighbourhood", "Google Rating", "Number of Comments"]],
            use_container_width=True,
            hide_index=True,
        )

csv_bytes = filtered[[
    "Restaurant Name",
    "Neighbourhood",
    "Google Rating",
    "Number of Comments",
    "Phone",
    "Google Maps Link",
    "Latitude",
    "Longitude",
    "Coord Source",
]].to_csv(index=False).encode("utf-8")

st.download_button(
    "Download filtered results as CSV",
    csv_bytes,
    file_name="turkish_restaurants_filtered.csv",
    mime="text/csv",
)
