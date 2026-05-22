from menu import MENU
from states import OrderState

# ─── Storage ─────────────────────────────────────────
# {
#   user_id: {
#     "state": OrderState.IDLE,
#     "items": [],
#     "address": "",
#     "phone": "",
#   }
# }
orders = {}


# ─── Init ────────────────────────────────────────────
def init_order(user_id: int):
    orders[user_id] = {
        "state": OrderState.IDLE,
        "items": [],
        "address": "",
        "phone": "",
    }


# ─── State Helpers ───────────────────────────────────
def get_state(user_id: int) -> OrderState:
    if user_id not in orders:
        init_order(user_id)
    return orders[user_id]["state"]


def set_state(user_id: int, state: OrderState):
    if user_id not in orders:
        init_order(user_id)
    orders[user_id]["state"] = state


# ─── Order Helpers ───────────────────────────────────
def get_order(user_id: int) -> dict:
    if user_id not in orders:
        init_order(user_id)
    return orders[user_id]


def add_item(user_id: int, item_name: str, qty: int = 1) -> bool:
    if user_id not in orders:
        init_order(user_id)

    text = item_name.lower().strip()

    best_match = None
    best_score = 0

    for category in MENU.values():
        for item in category:
            score = 0

            # English word match — প্রতিটা word-এর জন্য score বাড়াও
            english_words = item["name"].lower().split()
            for w in english_words:
                if len(w) > 3 and w in text:
                    score += 2  # exact word match

            # Bangla match
            for kw in item.get("bangla", []):
                if kw in text or text in kw:
                    score += 3  # bangla match বেশি important

            if score > best_score:
                best_score = score
                best_match = item

    # Minimum score না হলে match নেই
    if best_match and best_score >= 2:
        for existing in orders[user_id]["items"]:
            if existing["name"] == best_match["name"]:
                existing["qty"] += qty
                return True

        orders[user_id]["items"].append(
            {
                "name": best_match["name"],
                "price": best_match["price"],
                "qty": qty,
            }
        )
        return True

    return False


def set_address(user_id: int, address: str):
    orders[user_id]["address"] = address


def set_phone(user_id: int, phone: str):
    orders[user_id]["phone"] = phone


def calculate_total(user_id: int) -> int:
    order = orders.get(user_id)
    if not order or not order["items"]:
        return 0
    return sum(i["price"] * i["qty"] for i in order["items"])


def get_order_summary(user_id: int) -> str:
    order = orders.get(user_id)
    if not order or not order["items"]:
        return "কোনো item নেই।"

    lines = []
    for item in order["items"]:
        subtotal = item["price"] * item["qty"]
        lines.append(f"• {item['name']} x{item['qty']} = ৳{subtotal}")

    lines.append(f"\n💰 Total: ৳{calculate_total(user_id)}")
    return "\n".join(lines)


def get_full_summary(user_id: int) -> str:
    order = orders.get(user_id)
    summary = get_order_summary(user_id)
    return f"{summary}\n\n📍 ঠিকানা: {order['address']}\n📱 ফোন: {order['phone']}"
