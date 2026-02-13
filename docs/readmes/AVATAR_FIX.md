# Avatar Fix - Streamlit Compatibility

**Issue**: Streamlit couldn't load "◉" symbol as avatar
**Solution**: Using emoji with CSS gradient for vortex effect

---

## Avatar Configuration

### User Avatar
- **Icon**: 🍷 (wine bottle)
- **Style**: Black background, white wine bottle
- **Represents**: Customer/wine enthusiast

### Jarvis Avatar (Assistant)
- **Icon**: 🔮 (crystal ball)
- **Style**: Radial gradient (vortex effect) - black center fading to dark gray
- **CSS**: `radial-gradient(circle, #1a1a1a 0%, #000000 70%)`
- **Border**: 2px solid #333333
- **Represents**: Jarvis's mystical/intuitive wine selection abilities

---

## Technical Implementation

```python
# User message
with st.chat_message("user", avatar="🍷"):
    st.markdown(user_query)

# Assistant message
with st.chat_message("assistant", avatar="🔮"):
    # Display wines
```

**CSS Styling**:
```css
/* User avatar - wine bottle */
[data-testid="chatAvatarIcon-user"] {
    background-color: #000000 !important;
    border-radius: 50%;
}

/* Assistant avatar - vortex effect */
[data-testid="chatAvatarIcon-assistant"] {
    background: radial-gradient(circle, #1a1a1a 0%, #000000 70%) !important;
    border: 2px solid #333333;
    border-radius: 50%;
}
```

---

## Fixed Files

1. **restaurants/app.py**
   - Changed from "◉" to "🔮"
   - Added CSS gradient for vortex effect
   - Updated avatar styling

2. **restaurants/maass/setup_maass.py**
   - Fixed function call (now returns only wines, not tuple)
   - Updated test to match new signature

---

## Why Crystal Ball?

The 🔮 crystal ball emoji represents:
- Jarvis's ability to "foresee" perfect wine pairings
- Mystical/magical sommelier intuition
- Sophisticated AI wine selection
- Bird's eye vortex appearance with CSS gradient

Combined with the radial gradient CSS, it creates a vortex-like appearance suitable for an AI sommelier.

---

**Status**: ✅ Fixed and tested
