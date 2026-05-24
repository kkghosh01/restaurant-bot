import re
import database
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
    # Use the central MENU_CACHE from the database module so we always
    # read the current cache without shadowing the variable.
    MENU = database.MENU_CACHE

    if not MENU:
        print("⚠️ Menu cache empty!")
        return False

    # Normalize input
    text = item_name.lower().strip()
    user_words = set(re.findall(r"\w+", text, flags=re.UNICODE))

    best_match = None
    best_score = 0

    # Matching priority and scoring:
    # - exact alias or exact name (immediate match)
    # - bangla exact -> high score
    # - alias word match -> medium
    # - exact english word match -> low
    # Minimum score required to accept a match: 5

    for category in MENU.values():
        for item in category:
            score = 0

            name = item.get("name", "").lower()
            aliases = [a.lower() for a in item.get("aliases", [])]
            bangla = [b.lower() for b in item.get("bangla", [])]

            # 1) Full-text exact match (name or alias)
            if text == name or text in aliases:
                best_match = item
                best_score = 999
                break

            # 2) Bangla exact/word match (strong signal)
            for kw in bangla:
                if kw == text:
                    score += 8
                elif kw in user_words:
                    score += 4

            # 3) Alias word matches
            for a in aliases:
                if a == text:
                    score += 10
                elif a in user_words:
                    score += 5

            # 4) English name word matches (require reasonable length)
            for w in name.split():
                if len(w) > 2 and w in user_words:
                    score += 3

            if score > best_score:
                best_score = score
                best_match = item

    # Accept only confident matches to avoid false positives
    if best_match and best_score >= 5:
        # Already আছে কিনা check
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
