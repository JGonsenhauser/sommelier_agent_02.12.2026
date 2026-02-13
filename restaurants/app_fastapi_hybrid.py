"""
Streamlit UI wrapper for FastAPI backend.
Calls FastAPI microservice for wine recommendations with caching.

Deploy to Streamlit Cloud for instant mobile access via QR code.
"""
import streamlit as st
import requests
import os
from pathlib import Path
from typing import Optional, Dict, List
import time

# FastAPI backend URL (change for production)
API_URL = os.getenv("API_URL", "http://localhost:8000")

# Avatar paths
bottle_icon = str(Path(__file__).parent.parent / "bottle_icon.jpeg")
vortex_icon = str(Path(__file__).parent.parent / "vortex.jpeg")

# Restaurant logos
maass_logo = str(Path(__file__).parent / "maass" / "maass_logo.jpg")


@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_wine_recommendations(query: str, restaurant_id: str) -> Optional[Dict]:
    """
    Call FastAPI backend for wine recommendations.
    Cached for 1 hour to avoid duplicate API calls.
    """
    try:
        response = requests.post(
            f"{API_URL}/api/recommend",
            json={"query": query, "restaurant_id": restaurant_id},
            timeout=60
        )

        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API error: {response.status_code}")
            return None

    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to backend API. Make sure FastAPI is running at " + API_URL)
        st.info("Start backend: `python -m uvicorn api.mobile_api:app --port 8000`")
        return None
    except requests.exceptions.Timeout:
        return {"error": "Our wine search is momentarily refreshing — like a good decant! Please try again in a few seconds.", "wines": []}
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None


@st.cache_data(ttl=86400)  # Cache for 24 hours
def get_restaurant_info(restaurant_id: str) -> Optional[Dict]:
    """Get restaurant information from API."""
    try:
        response = requests.get(
            f"{API_URL}/api/restaurants/{restaurant_id}",
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None


def display_wine_streaming(wine: dict, index: int):
    """Display wine in clean, streamed format using new schema."""
    import re
    # Use the 'text' field from schema if available (formatted wine info)
    text = wine.get('text', '')

    # Remove "Major Region: ..." from the text display
    if text:
        text = re.sub(r'\s*\|\s*Major Region:\s*[^|]*', '', text)
        # Clean up any trailing pipe
        text = text.strip().rstrip('|').strip()

    # If no text field, build from components (fallback)
    if not text:
        vintage = wine.get('vintage', '')
        producer = wine.get('producer', 'Unknown')
        wine_name = wine.get('wine_name', '')
        region = wine.get('region', '')

        wine_title_parts = []
        if vintage:
            wine_title_parts.append(str(vintage))
        wine_title_parts.append(producer)
        if wine_name:
            wine_title_parts.append(wine_name)
        elif region:
            wine_title_parts.append(region)

        text = " ".join(wine_title_parts)

    # Display wine name/info from text field
    st.markdown(f"**{text}**")

    # Display price on separate line underneath
    price = wine.get('price', '')
    if price:
        st.markdown(f"**Price:** ${price}")

    st.markdown("")  # Spacing

    # Tasting Note - ALWAYS display (never show "No tasting note provided")
    tasting_note = wine.get('tasting_note', '')
    if tasting_note:
        st.markdown(f"**Tasting Note:**")
        st.markdown(tasting_note)
        st.markdown("")

    # Food Pairing - ONLY display if explicitly set (not None)
    food_pairing = wine.get('food_pairing')
    if food_pairing:
        st.markdown(f"**Food Pairing:**")
        st.markdown(food_pairing)
        st.markdown("")

    st.markdown("---")


def init_session_state():
    """Initialize Streamlit session state."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "restaurant_id" not in st.session_state:
        st.session_state.restaurant_id = None


def main():
    """Main Streamlit app."""
    # Page config MUST be first Streamlit command
    st.set_page_config(
        page_title="Maass Sommelier",
        page_icon=maass_logo,
        layout="centered",
        initial_sidebar_state="collapsed"
    )

    # Get restaurant from URL parameter
    params = st.query_params
    restaurant_id = params.get("restaurant", "maass")

    # Get restaurant info
    restaurant_info = get_restaurant_info(restaurant_id)
    restaurant_name = restaurant_info['name'] if restaurant_info else "Wine Sommelier"

    init_session_state()
    st.session_state.restaurant_id = restaurant_id

    # Sleek black and white styling
    st.markdown("""
        <style>
        /* Clean interface */
        .stApp {
            background-color: #FFFFFF;
        }

        /* Hide sidebar */
        [data-testid="stSidebar"] {
            display: none;
        }

        /* Header styling */
        h1 {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            font-weight: 600;
            color: #000000;
            letter-spacing: -0.02em;
            margin-bottom: 0.5rem;
        }

        /* Text styling */
        .element-container p {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            color: #4A4A4A;
            font-size: 1rem;
            line-height: 1.6;
        }

        /* Chat messages */
        .stChatMessage {
            background-color: #F8F9FA;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1rem;
        }

        /* Custom avatars */
        [data-testid="chatAvatarIcon-user"],
        [data-testid="chatAvatarIcon-assistant"] {
            border-radius: 50%;
        }

        /* Input box */
        .stChatInputContainer {
            border-top: 1px solid #E5E7EB;
            padding-top: 1rem;
        }

        /* Buttons */
        .stButton>button {
            background-color: #000000;
            color: #FFFFFF;
            border: none;
            border-radius: 6px;
            padding: 0.5rem 1rem;
            font-family: 'Inter', sans-serif;
            font-weight: 500;
        }

        /* Dividers */
        hr {
            border-color: #E5E7EB;
            margin: 1.5rem 0;
        }

        /* Hide Streamlit branding completely */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        [data-testid="stToolbar"] {display: none;}
        [data-testid="stDecoration"] {display: none;}
        [data-testid="stStatusWidget"] {display: none;}
        .viewerBadge_container__r5tak {display: none;}
        .stDeployButton {display: none;}

        /* Performance badge */
        .performance-badge {
            position: fixed;
            bottom: 10px;
            right: 10px;
            background: #000000;
            color: #FFFFFF;
            padding: 8px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            z-index: 1000;
        }
        </style>
    """, unsafe_allow_html=True)

    # Header — restaurant logo
    st.image(maass_logo, width=250)

    # Jarvis introduction
    st.markdown("""
    Hi! I'm **Jarvis**, your personal wine assistant

    Whether you are new to wine or a total pro, just type whatever you are thinking — no wrong answers!

    Here are some easy ways to get started:
    - Red wine under 80
    - Something crisp and light for summer
    - What pairs with steak? or type pairing and I will recommend a dish from the menu to pair with the wines
    - Cabernet Sauvignon from Napa, full-bodied, around 100 to 150

    Tell me your mood, budget, food, grape, region, or any vibe you are after — I will recommend wines from your restaurant's list that match perfectly.
    """)

    st.markdown("---")

    # Chat interface
    for message in st.session_state.messages:
        with st.chat_message(message["role"], avatar=bottle_icon if message["role"] == "user" else vortex_icon):
            if message["role"] == "assistant" and "wines" in message:
                # Display wines
                for i, wine in enumerate(message["wines"]):
                    display_wine_streaming(wine, i)

                # Show processing time badge
                if "processing_time" in message:
                    st.caption(f"⚡ {message['processing_time']:.2f}s")
            else:
                st.markdown(message["content"])

    # Chat input
    user_query = st.chat_input("Describe the wine you're looking for...")

    if user_query:
        # Display user message
        st.session_state.messages.append({"role": "user", "content": user_query})
        with st.chat_message("user", avatar=bottle_icon):
            st.markdown(user_query)

        # Get recommendations from FastAPI backend
        with st.spinner("Searching our collection..."):
            start_time = time.time()

            # Call FastAPI (with caching)
            result = get_wine_recommendations(user_query, st.session_state.restaurant_id)

            if result and result.get('error'):
                # Embedding service or other temporary error — friendly message
                error_msg = result['error']
                with st.chat_message("assistant", avatar=vortex_icon):
                    st.markdown(error_msg)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_msg
                })
            elif result and result.get('wines'):
                processing_time = time.time() - start_time

                # Display Jarvis response with wines
                with st.chat_message("assistant", avatar=vortex_icon):
                    for i, wine in enumerate(result['wines']):
                        display_wine_streaming(wine, i)

                    # Show performance badge
                    st.caption(f"⚡ {processing_time:.2f}s (API: {result.get('processing_time', 0):.2f}s)")

                # Store in session
                st.session_state.messages.append({
                    "role": "assistant",
                    "wines": result['wines'],
                    "processing_time": processing_time
                })
            else:
                with st.chat_message("assistant", avatar=vortex_icon):
                    st.markdown("I couldn't find wines matching your criteria. Please try different search terms.")

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "I couldn't find wines matching your criteria. Please try different search terms."
                })


if __name__ == "__main__":
    main()
