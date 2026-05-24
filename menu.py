RESTAURANT_NAME = "🍕 Spice Garden"


# ✅ DB থেকে load করো
def get_menu() -> dict:
    from database import get_menu_from_db

    return get_menu_from_db()


def get_menu_text() -> str:
    menu = get_menu()

    CATEGORY_ICONS = {
        "pizza": "🍕 Pizza",
        "burger": "🍔 Burger",
        "drinks": "🥤 Drinks",
    }

    text = f"🍽️ {RESTAURANT_NAME} মেনু\n\n"

    for category, icon in CATEGORY_ICONS.items():
        items = menu.get(category, [])
        if items:
            text += f"{icon}\n"
            for item in items:
                text += f"  • {item['name']} — ৳{item['price']}\n"
            text += "\n"

    return text
