# Custom Avatar Images Update

**Date**: 2026-02-11
**Status**: ✅ Complete

---

## Changes Made

### Updated Avatars

**User Avatar**: `bottle_icon.jpeg` (119KB)
- Custom wine bottle icon
- Black background with bottle design
- Located at: `sommelier_agent/bottle_icon.jpeg`

**Jarvis Avatar**: `vortex.jpeg` (295KB)
- Custom vortex/spiral design
- Bird's eye view vortex appearance
- Located at: `sommelier_agent/vortex.jpeg`

---

## Implementation

### File Paths
```python
# Define avatar paths
bottle_icon = str(Path(__file__).parent.parent / "bottle_icon.jpeg")
vortex_icon = str(Path(__file__).parent.parent / "vortex.jpeg")
```

### Usage
```python
# User message
with st.chat_message("user", avatar=bottle_icon):
    st.markdown(user_query)

# Assistant/Jarvis message
with st.chat_message("assistant", avatar=vortex_icon):
    # Display wines
```

---

## CSS Updates

Simplified avatar styling to allow custom images to display naturally:
```css
/* Custom avatars - images will display naturally */
[data-testid="chatAvatarIcon-user"],
[data-testid="chatAvatarIcon-assistant"] {
    border-radius: 50%;
}
```

---

## File Structure

```
sommelier_agent/
├── bottle_icon.jpeg       # User avatar (119KB)
├── vortex.jpeg           # Jarvis avatar (295KB)
└── restaurants/
    └── app.py            # Updated to use custom images
```

---

## Testing

Run the app:
```bash
streamlit run restaurants/app.py
```

**Expected**:
- User messages show bottle icon
- Jarvis messages show vortex icon
- Both display as circular avatars
- Professional, custom branding

---

## Benefits

1. ✅ **Professional Branding**: Custom icons match restaurant theme
2. ✅ **Visual Identity**: Unique, recognizable avatars
3. ✅ **Scalable**: Easy to update images without code changes
4. ✅ **High Quality**: JPEG format for crisp display

---

**Status**: Ready to use!
