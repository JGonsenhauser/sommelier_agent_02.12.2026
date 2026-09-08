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

# Header / favicon logo
brand_logo = str(Path(__file__).parent.parent / "logo" / "03-spine-ring.png")


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
            timeout=120
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

    food_pairing = wine.get("food_pairing")
    if food_pairing:
        st.markdown("**Food pairing:**")
        st.markdown(food_pairing)
        st.markdown("")

    if index == 0:
        st.markdown("---")


def init_session_state():
    """Initialize Streamlit session state."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "restaurant_id" not in st.session_state:
        st.session_state.restaurant_id = None
    if "guide" not in st.session_state:
        st.session_state.guide = {
            "color": None,
            "body": None,
            "profile": None,
            "price": None,
            "food": None,
        }
    if "results" not in st.session_state:
        st.session_state.results = None


def _toggle_guide(group: str, value: str):
    current = st.session_state.guide.get(group)
    st.session_state.guide[group] = None if current == value else value


def compose_guided_query(text: str, guide: Dict) -> str:
    bits = []
    color = guide.get("color")
    if color == "Champagne":
        bits.append("champagne, sparkling")
    elif color:
        bits.append(f"{color.lower()} wine")
    body = guide.get("body")
    if body:
        bits.append(f"{body.lower()}-bodied")
    profile = guide.get("profile")
    if profile == "Dry & crisp":
        bits.append("dry and crisp")
    elif profile == "Off-dry":
        bits.append("off-dry")
    elif profile == "Fruity":
        bits.append("fruity profile")
    elif profile == "Earthy":
        bits.append("earthy profile")
    elif profile:
        bits.append(profile.lower())
    price = guide.get("price")
    if price and price != "Any price":
        bits.append(price.lower())
    food = guide.get("food")
    if food:
        bits.append(f"to drink with {food.lower()}")
    extra = ", ".join(bits)
    text = (text or "").strip()
    if text and extra:
        return f"{text}. Preferences: {extra}."
    return text or extra


def render_guide_row(number: str, label: str, group: str, options: List[str]):
    st.caption(f"{number}  {label}")
    cols = st.columns(len(options))
    for col, option in zip(cols, options):
        with col:
            on = st.session_state.guide.get(group) == option
            if st.button(option, key=f"guide_{group}_{option}", type="primary" if on else "secondary"):
                _toggle_guide(group, option)
                st.rerun()


def inject_css(results_mode: bool = False):
    extra = ""
    if results_mode:
        extra = """
        [data-testid="stChatInput"],
        [data-testid="stChatInputContainer"],
        .stChatInput,
        footer,
        [data-testid="stBottomBlockContainer"] {
            display: none !important;
        }
        """
    st.markdown(f"""
        <style>
        .stApp {{
            background-color: #FFFFFF;
        }}
        [data-testid="stSidebar"] {{
            display: none;
        }}
        h1 {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            font-weight: 600;
            color: #000000;
            letter-spacing: -0.02em;
            margin-bottom: 0.5rem;
        }}
        .element-container p {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            color: #4A4A4A;
            font-size: 1rem;
            line-height: 1.6;
        }}
        .stChatMessage {{
            background-color: #F8F9FA;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1rem;
        }}
        [data-testid="chatAvatarIcon-user"],
        [data-testid="chatAvatarIcon-assistant"] {{
            border-radius: 50%;
        }}
        .stChatInputContainer {{
            border-top: 1px solid #E5E7EB;
            padding-top: 1rem;
        }}
        .stButton>button {{
            background-color: #000000;
            color: #FFFFFF;
            border: none;
            border-radius: 6px;
            padding: 0.5rem 1rem;
            font-family: 'Inter', sans-serif;
            font-weight: 500;
        }}
        hr {{
            border-color: #E5E7EB;
            margin: 1.5rem 0;
        }}
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        header {{visibility: hidden;}}
        [data-testid="stToolbar"] {{display: none;}}
        [data-testid="stDecoration"] {{display: none;}}
        [data-testid="stStatusWidget"] {{display: none;}}
        .viewerBadge_container__r5tak {{display: none;}}
        .stDeployButton {{display: none;}}
        {extra}
        </style>
    """, unsafe_allow_html=True)


def main():
    """Main Streamlit app."""
    # Page config MUST be first Streamlit command
    st.set_page_config(
        page_title="Jarvis Sommelier",
        page_icon=brand_logo,
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

    if st.session_state.results:
        inject_css(results_mode=True)
        top_l, top_r = st.columns([1, 1])
        with top_l:
            st.image(brand_logo, width=88)
        with top_r:
            st.write("")
            if st.button("New search", type="primary"):
                st.session_state.results = None
                st.session_state.messages = []
                st.session_state.guide = {
                    "color": None,
                    "body": None,
                    "profile": None,
                    "price": None,
                    "food": None,
                }
                st.rerun()
        for i, wine in enumerate(st.session_state.results):
            display_wine_streaming(wine, i)
        return

    inject_css(results_mode=False)

    # Header — brand logo + guest QR
    qr_path = Path(__file__).parent / "maass" / "static" / "maass_qr.png"
    header_l, header_r = st.columns([1, 1])
    with header_l:
        st.image(brand_logo, width=140)
    with header_r:
        if qr_path.exists():
            st.image(str(qr_path), width=180)
            st.caption("Staff kiosk — guests should scan the PWA QR on :8000")

    st.markdown("""
Hi! I'm **Jarvis**, your personal wine assistant.

Not sure what to order? You don't need the right wine words.

Tap the options below to steer me — color, body, price, food — then add a thought if you like. Skip them and just type. Either way, I'll bring back two bottles, each with a tasting note and a dish that belongs with it.
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

    render_guide_row("1", "Color", "color", ["White", "Red", "Rosé", "Champagne"])
    render_guide_row("2", "Body", "body", ["Light", "Medium", "Full"])
    render_guide_row("3", "Profile", "profile", ["Fruity", "Earthy", "Dry & crisp", "Off-dry"])
    render_guide_row("4", "Price", "price", ["Under $75", "$75–$150", "$150–$250", "Cellar", "Any price"])
    render_guide_row("5", "Tonight", "food", ["Oysters", "Steak", "Chicken", "Branzino", "Cream sauce", "Tomato sauce", "Hard cheese", "Soft cheese"])

    if st.button("Search with these guides"):
        if compose_guided_query("", st.session_state.guide):
            st.session_state["_pending_query"] = True
            st.rerun()

    typed = st.chat_input("Describe the wine you're looking for...")
    if st.session_state.pop("_pending_query", None):
        user_query = compose_guided_query("", st.session_state.guide)
    elif typed:
        user_query = compose_guided_query(typed, st.session_state.guide)
    else:
        user_query = None

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
                st.session_state.results = result['wines']
                st.rerun()
            else:
                with st.chat_message("assistant", avatar=vortex_icon):
                    st.markdown("I couldn't find wines matching your criteria. Please try different search terms.")

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "I couldn't find wines matching your criteria. Please try different search terms."
                })


if __name__ == "__main__":
    main()
