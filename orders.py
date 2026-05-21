from menu import MENU

orders = {}


def init_order(user_id):
    orders[user_id] = {"items": [], "address": "", "phone": "", "status": ""}


def get_order(user_id):
    return orders.get(user_id)


def add_item(user_id, item_name, qty=1):
    if user_id not in orders:
        init_order(user_id)

    text = item_name.lower().strip()

    for category in MENU.values():
        for item in category:
            # ✅ English match
            english_words = item["name"].lower().split()
            english_match = any(w in text for w in english_words if len(w) > 3)

            # ✅ Bangla match — menu.py তে bangla key থাকতে হবে
            bangla_match = any(
                kw in text or text in kw for kw in item.get("bangla", [])
            )

            if english_match or bangla_match:
                orders[user_id]["items"].append(
                    {
                        "name": item["name"],
                        "price": item["price"],
                        "qty": qty,
                    }
                )
                return True

    return False


def calculate_total(user_id):
    order = orders.get(user_id)

    if not order or not order["items"]:
        return 0

    total = 0

    for item in order["items"]:
        total += item["price"] * item["qty"]

    return total


def get_order_summary(user_id):
    order = orders.get(user_id)

    if not order or not order["items"]:
        return "কোনো item নেই।"

    lines = []

    for item in order["items"]:
        subtotal = item["price"] * item["qty"]

        lines.append(f"• {item['name']} x{item['qty']} = ৳{subtotal}")

    total = calculate_total(user_id)

    lines.append(f"\n💰 Total: ৳{total}")

    return "\n".join(lines)
