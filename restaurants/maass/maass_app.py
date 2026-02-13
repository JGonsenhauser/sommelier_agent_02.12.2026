"""
MAASS Restaurant Sommelier App.
Users scan QR code to access this personalized wine recommendation interface.
"""
import streamlit as st
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from restaurants.restaurant_config import MAASS_CONFIG
from restaurants.wine_recommender import WineRecommender


def init_session_state():
    """Initialize Streamlit session state."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "recommender" not in st.session_state:
        st.session_state.recommender = WineRecommender(MAASS_CONFIG)


def display_welcome():
    """Display welcome message and instructions."""
    st.title(f"🍷 {MAASS_CONFIG.name}")

    if MAASS_CONFIG.location:
        st.caption(f"📍 {MAASS_CONFIG.location}")

    st.markdown("""
    ### Welcome to Your Personal Sommelier!

    I'm here to help you find the perfect wine from our collection.
    Tell me what you're looking for, and I'll recommend **2 wines** that match your taste.

    **Try asking me:**
    - "I want a bold red wine for steak"
    - "Something light and refreshing"
    - "White wine under $50"
    - "Wine for a special celebration"
    """)

    st.divider()


def display_wine_card(wine: dict, index: int):
    """Display a wine recommendation card."""
    with st.container():
        st.markdown(f"### 🍾 Option {index + 1}")

        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown(f"**{wine['producer']}**")
            st.caption(f"📍 {wine['region']}")

        with col2:
            st.markdown(f"**{wine['price_range']}**")

        # Wine details
        st.markdown(f"**Type:** {wine['wine_type'].title()}")

        if wine['grapes']:
            st.markdown(f"**Grapes:** {wine['grapes']}")

        if wine['tasting_keywords']:
            st.markdown(f"**Tasting Notes:** {wine['tasting_keywords']}")

        # Similarity score (hidden from user, for debugging)
        # st.caption(f"Match Score: {wine['score']:.1%}")

        st.divider()


def display_chat_message(role: str, content: str):
    """Display a chat message."""
    with st.chat_message(role):
        st.markdown(content)


def main():
    """Main application."""
    # Page config
    st.set_page_config(
        page_title=f"{MAASS_CONFIG.name} - Wine Sommelier",
        page_icon="🍷",
        layout="centered",
        initial_sidebar_state="collapsed"
    )

    # Custom CSS
    st.markdown(f"""
        <style>
        .stApp {{
            background-color: #f8f9fa;
        }}
        .stButton>button {{
            background-color: {MAASS_CONFIG.primary_color};
            color: white;
            border-radius: 8px;
            padding: 0.5rem 1rem;
            border: none;
        }}
        .stButton>button:hover {{
            background-color: {MAASS_CONFIG.accent_color};
        }}
        </style>
    """, unsafe_allow_html=True)

    # Initialize
    init_session_state()

    # Welcome section
    display_welcome()

    # Chat interface
    st.subheader("💬 Ask Your Sommelier")

    # Display chat history
    for message in st.session_state.messages:
        display_chat_message(message["role"], message["content"])

    # Chat input
    user_query = st.chat_input("Tell me what wine you're looking for...")

    if user_query:
        # Display user message
        st.session_state.messages.append({"role": "user", "content": user_query})
        display_chat_message("user", user_query)

        # Get recommendations
        with st.spinner("Finding the perfect wines for you..."):
            try:
                recommendation_text, wines = st.session_state.recommender.get_full_recommendation(
                    user_query
                )

                # Display sommelier response
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": recommendation_text
                })
                display_chat_message("assistant", recommendation_text)

                # Display wine cards
                if wines:
                    st.markdown("### 🎯 My Recommendations")
                    for i, wine in enumerate(wines):
                        display_wine_card(wine, i)

                    # Store wines in session state for reference
                    st.session_state.last_recommendations = wines

            except Exception as e:
                error_msg = f"I apologize, but I'm having trouble accessing our wine list. Please try again in a moment."
                st.error(error_msg)
                st.exception(e)  # Show for debugging

    # Sidebar with info
    with st.sidebar:
        st.markdown("### About")
        st.markdown(f"""
        You're viewing the wine list for **{MAASS_CONFIG.name}**.

        I'll help you find wines that match your taste preferences.
        """)

        if MAASS_CONFIG.phone:
            st.markdown(f"📞 {MAASS_CONFIG.phone}")

        if MAASS_CONFIG.website:
            st.markdown(f"🌐 [{MAASS_CONFIG.website}]({MAASS_CONFIG.website})")

        if MAASS_CONFIG.hours:
            st.markdown(f"🕒 {MAASS_CONFIG.hours}")

        st.divider()

        # Quick actions
        st.markdown("### Quick Searches")
        quick_searches = [
            "🔴 Bold red wines",
            "⚪ Light white wines",
            "🥂 Sparkling wines",
            "💰 Budget-friendly options",
            "⭐ Premium selections"
        ]

        for search in quick_searches:
            if st.button(search, key=f"quick_{search}"):
                st.session_state.quick_search = search.split(" ", 1)[1]

        # Reset button
        if st.button("🔄 Start New Search"):
            st.session_state.messages = []
            st.session_state.last_recommendations = None
            st.rerun()


if __name__ == "__main__":
    main()
