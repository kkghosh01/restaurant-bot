RESTAURANT_NAME = "🍕 Spice Garden"

MENU = {
    "pizza": [
        {
            "name": "Margherita Pizza",
            "bangla": ["মার্গারিটা", "মার্গারিতা", "মারগারিটা", "margherita"],
            "price": 350,
        },
        {
            "name": "Chicken BBQ Pizza",  # ✅ Fix 1 — সঠিক item
            "bangla": ["চিকেন বিবিকিউ", "বিবিকিউ", "bbq", "chicken bbq", "বারবেকু"],
            "price": 450,
        },
        {
            "name": "Veggie Delight",
            "bangla": ["ভেজি", "veggie", "সবজি"],
            "price": 320,
        },
    ],
    "burger": [
        {
            "name": "Classic Beef Burger",
            "bangla": ["বিফ বার্গার", "বিফ", "beef burger", "beef"],
            "price": 220,
        },
        {
            "name": "Chicken Crispy Burger",
            "bangla": ["চিকেন ক্রিস্পি", "ক্রিস্পি", "crispy", "chicken crispy"],
            "price": 180,
        },
    ],
    "drinks": [
        {"name": "Coke", "bangla": ["কোক", "কোলা", "coke"], "price": 60},
        {"name": "Fresh Juice", "bangla": ["রস", "জুস", "juice"], "price": 80},
        {"name": "Water", "bangla": ["পানি", "water"], "price": 20},
    ],
}


def get_menu_text():
    text = f"🍽️ {RESTAURANT_NAME} মেনু\n\n"  # ✅ Fix 3 — * সরিয়ে দিলাম

    text += "🍕 Pizza\n"
    for item in MENU["pizza"]:
        text += f"  • {item['name']} — ৳{item['price']}\n"

    text += "\n🍔 Burger\n"
    for item in MENU["burger"]:
        text += f"  • {item['name']} — ৳{item['price']}\n"

    text += "\n🥤 Drinks\n"
    for item in MENU["drinks"]:
        text += f"  • {item['name']} — ৳{item['price']}\n"

    return text
