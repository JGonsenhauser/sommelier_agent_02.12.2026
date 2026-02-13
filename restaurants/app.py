"""
Universal Restaurant Sommelier App - Jarvis AI Sommelier
Sleek, minimal interface with intelligent wine recommendations.
"""
import streamlit as st
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from restaurants.restaurant_config import get_restaurant_config
from restaurants.wine_recommender import WineRecommender


def init_session_state():
    """Initialize Streamlit session state."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "recommender" not in st.session_state:
        st.session_state.recommender = None
    if "config" not in st.session_state:
        st.session_state.config = None


def display_wine_streaming(wine: dict, index: int):
    """Display wine in clean, streamed format."""
    # Format: 2020 Ricasoli Chianti Classico Italy $125
    vintage = wine.get('vintage', '')
    producer = wine.get('producer', 'Unknown')
    wine_name = wine.get('wine_name', '')
    region = wine.get('region', '')
    country = wine.get('country', '')
    price = wine.get('price', '')

    # Build wine title - use wine_name as the region/designation
    wine_title_parts = []
    if vintage:
        wine_title_parts.append(str(vintage))
    wine_title_parts.append(producer)
    if wine_name:
        wine_title_parts.append(wine_name)
    elif region:
        wine_title_parts.append(region)
    if country and not wine_name:  # Only add country if wine_name not present
        wine_title_parts.append(country)
    if price:
        wine_title_parts.append(f"${price}")

    wine_title = " ".join(wine_title_parts)

    # Display in clean format
    st.markdown(f"**{wine_title}**")
    st.markdown("")

    # Tasting Note
    if wine.get('tasting_note'):
        st.markdown(f"**Tasting Note:**")
        st.markdown(wine['tasting_note'])
        st.markdown("")

    # Food Pairing
    if wine.get('food_pairing'):
        st.markdown(f"**Food Pairing:**")
        st.markdown(wine['food_pairing'])

    st.markdown("---")


def main():
    """Main application."""
    # Get restaurant from URL parameter first
    params = st.query_params
    restaurant_id = params.get("restaurant", "maass")
    config = get_restaurant_config(restaurant_id)

    if not config:
        config_name = "Wine Sommelier"
    else:
        config_name = config.name

    # Page config with restaurant name only
    st.set_page_config(
        page_title=config_name,
        page_icon=None,  # No icon
        layout="centered",
        initial_sidebar_state="collapsed"
    )

    init_session_state()

    # Define avatar paths
    bottle_icon = str(Path(__file__).parent.parent / "bottle_icon.jpeg")
    vortex_icon = str(Path(__file__).parent.parent / "vortex.jpeg")

    if not config:
        st.error(f"Restaurant not found: {restaurant_id}")
        st.stop()

    # Initialize recommender if needed
    if st.session_state.config != config:
        st.session_state.config = config
        st.session_state.recommender = WineRecommender(config)
        st.session_state.messages = []

    # Sleek black and white with custom icons
    st.markdown("""
        <style>
        /* Clean interface */
        .stApp {
            background-color: #FFFFFF;
        }

        /* Hide sidebar completely */
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

        /* User message styling */
        [data-testid="stChatMessageContent"] {
            font-family: 'Inter', sans-serif;
            color: #1F2937;
        }

        /* Custom avatars - images will display naturally */
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
            transition: background-color 0.2s;
        }

        .stButton>button:hover {
            background-color: #1F2937;
        }

        /* Dividers */
        hr {
            border-color: #E5E7EB;
            margin: 1.5rem 0;
        }

        /* Remove default padding */
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }

        /* Hide Streamlit branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        </style>
    """, unsafe_allow_html=True)

    # Header - Restaurant name only
    st.title(config.name)

    # Jarvis introduction
    st.markdown("""
    Welcome to your personal sommelier! My name is **Jarvis**.

    Tell me about the wine you're looking for. Share your preferred price point, grape varietal,
    region, and body preference. Or, if you'd like a food pairing, simply tell me what you're eating,
    and I'll recommend the perfect wines for your meal.
    """)

    st.markdown("---")

    # Chat interface
    for message in st.session_state.messages:
        with st.chat_message(message["role"], avatar=bottle_icon if message["role"] == "user" else vortex_icon):
            if message["role"] == "assistant" and "wines" in message:
                # Display wines only, no intro text
                for i, wine in enumerate(message["wines"]):
                    display_wine_streaming(wine, i)
            else:
                st.markdown(message["content"])

    # Chat input
    user_query = st.chat_input("Describe the wine you're looking for...")

    if user_query:
        # Display user message
        st.session_state.messages.append({"role": "user", "content": user_query})
        with st.chat_message("user", avatar=bottle_icon):
            st.markdown(user_query)

        # Get recommendations
        with st.spinner("Searching our collection..."):
            try:
                wines = st.session_state.recommender.get_full_recommendation(user_query)

                # Display Jarvis response with wines (NO intro text)
                with st.chat_message("assistant", avatar=vortex_icon):
                    if wines:
                        for i, wine in enumerate(wines):
                            display_wine_streaming(wine, i)
                    else:
                        st.markdown("I couldn't find wines matching your criteria. Please try different search terms.")

                # Store in session
                st.session_state.messages.append({
                    "role": "assistant",
                    "wines": wines if wines else []
                })

            except Exception as e:
                error_msg = "I apologize, I'm having difficulty accessing the wine list. Please try again."
                st.error(error_msg)
                st.exception(e)


if __name__ == "__main__":
    main()
