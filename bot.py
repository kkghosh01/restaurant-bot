import os
import threading
import re
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, BotCommand, ReplyKeyboardMarkup
from telegram.error import TimedOut, NetworkError
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from config import TELEGRAM_TOKEN
from menu import get_menu_text, RESTAURANT_NAME
from keyboards import main_keyboard
from ai import get_ai_reply, reset_session
from orders import (
    init_order,
    get_order,
    get_state,
    set_state,
    add_item,
    set_address,
    set_phone,
    get_order_summary,
    get_full_summary,
    calculate_total,
)
from parser import extract_order
from states import OrderState
from database import (
    init_db,
    save_order,
    save_payment,
    get_pending_order_by_user,  # ✅ নতুন
    get_order_by_id,  # ✅ নতুন
    has_pending_payment,  # ✅ নতুন
    cancel_order,  # ✅ নতুন
    load_menu_cache,
    seed_menu,
)


# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def is_done_signal(text: str) -> bool:
    DONE_SIGNALS = [
        "না",
        "হয়ে গেছে",
        "শেষ",
        "আর না",
        "আর কিছু না",
        "এটুকুই",
        "done",
        "no",
    ]

    text_lower = text.lower().strip()

    # Exact match check
    if text_lower in DONE_SIGNALS:
        return True

    # "ok" only when it's the whole input (allow repetitions like "ok", "okk")
    if re.fullmatch(r"ok+", text_lower):
        return True

    return False


# ─── Health Server ───────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

    def log_message(self, format, *args):
        pass


def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()


# ─── Keyboards ───────────────────────────────────────
def confirm_keyboard():
    buttons = [["✅ Confirm", "❌ Cancel"]]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def done_keyboard():
    buttons = [["🔄 নতুন অর্ডার"]]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


# ─── /start ──────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    reset_session(user_id)
    init_order(user_id)

    # ✅ Pending order check করো
    pending = get_pending_order_by_user(user_id)

    if pending:
        # Session restore করো
        order = get_order(user_id)
        order["order_id"] = pending.id
        order["total"] = pending.total
        set_state(user_id, OrderState.PAYMENT)

        await update.message.reply_text(
            f"🕒 আপনার একটি pending payment আছে!\n\n"
            f"📋 Order ID: ORDER-{pending.id:04d}\n"
            f"💰 Amount: ৳{pending.total}\n\n"
            f"💳 Payment করুন:\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"bKash Personal: 01737-233015\n"
            f"Amount: ৳{pending.total}\n"
            f"Reference: ORDER-{pending.id:04d}\n"
            f"━━━━━━━━━━━━━━━━\n\n"
            f"Transaction ID এবং শেষ ৪ সংখ্যা পাঠান।\n"
            f"উদাহরণ: TRX8HG23K 4831",
            reply_markup=ReplyKeyboardMarkup(
                [["❌ Cancel Order"]], resize_keyboard=True
            ),
        )
        return

    # কোনো pending order নেই → normal start
    await update.message.reply_text(
        f"🎉 {RESTAURANT_NAME}-এ স্বাগতম!\n\n"
        "আমি আপনার AI Food Assistant 🤖\n\n"
        "নিচের বাটন ব্যবহার করে মেনু দেখুন বা অর্ডার করুন 👇",
        reply_markup=main_keyboard(),
    )


# ─── /menu ───────────────────────────────────────────
async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        get_menu_text(),
        reply_markup=main_keyboard(),
    )


# ─── /contact ────────────────────────────────────────
async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📞 যোগাযোগ করুন:\n\n"
        "📱 Phone: 01737-233015\n"
        "📍 Address: Patkelghata, Satkhira, Khulna\n"
        "⏰ Open: 11am – 11pm",
        reply_markup=main_keyboard(),
    )


# ─── /reset ──────────────────────────────────────────
async def reset_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    reset_session(user_id)
    init_order(user_id)
    await update.message.reply_text(
        "✅ Order reset হয়েছে।",
        reply_markup=main_keyboard(),
    )


# ─── Main Handler ────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text.strip()
    state = get_state(user_id)

    try:
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING,
        )
    except (TimedOut, NetworkError) as e:
        logger.warning("Network timeout sending chat action: %s", e)
    except Exception as e:
        logger.exception("Unexpected error sending chat action: %s", e)

    # ── Button shortcuts ────────────────────────────
    if user_text == "🍽️ মেনু দেখুন":
        await show_menu(update, context)
        return
    if user_text == "📞 যোগাযোগ":
        await contact(update, context)
        return
    if user_text == "🔄 নতুন অর্ডার":
        reset_session(user_id)
        init_order(user_id)
        await update.message.reply_text(
            "নতুন অর্ডার শুরু করুন 👇",
            reply_markup=main_keyboard(),
        )
        return

    # ════════════════════════════════════════════════
    # STATE: IDLE
    # ════════════════════════════════════════════════
    if state == OrderState.IDLE:
        if user_text in ["🛒 অর্ডার করুন", "❓ সাহায্য"]:
            # Clear AI memory before entering ORDERING
            reset_session(user_id)
            set_state(user_id, OrderState.ORDERING)
            await update.message.reply_text(
                f"কী অর্ডার করতে চান? Item এবং quantity একসাথে বলুন।\n\n{get_menu_text()}",
                reply_markup=main_keyboard(),
            )
            return
        # ✅ যদি message deterministic order pattern (e.g., "1 pizza")
        #    তাহলে AI কল না করে deterministic flow চালাও
        qty, item_name = extract_order(user_text)
        if item_name:
            # Clear AI memory before entering ORDERING
            reset_session(user_id)
            # Move to ORDERING and add the item deterministically
            set_state(user_id, OrderState.ORDERING)
            item_added = add_item(user_id, item_name, qty)

            if item_added:
                await update.message.reply_text(
                    f"✅ Added!\n\n{get_order_summary(user_id)}\n\n"
                    "আরও কিছু লাগবে? নাকি 'না' বললে ঠিকানায় যাবো।",
                    reply_markup=main_keyboard(),
                )
            else:
                await update.message.reply_text(
                    f"❌ Item টি মেনুতে নেই। আবার চেষ্টা করুন।\n\n{get_menu_text()}",
                    reply_markup=main_keyboard(),
                )
            return

        # ✅ যদি user ORDER-XXXX format-এ message করে
        order_pattern = re.match(r"ORDER-(\d+)", user_text.upper().strip())
        if order_pattern:
            order_id = int(order_pattern.group(1))

            # DB থেকে order খোঁজো
            db_order = get_order_by_id(order_id)

            if (
                db_order
                and db_order.status == "pending"
                and db_order.user_id == user_id
            ):
                # Session restore করো
                order = get_order(user_id)
                order["order_id"] = order_id
                order["total"] = db_order.total
                # Clear AI memory before entering PAYMENT
                reset_session(user_id)
                set_state(user_id, OrderState.PAYMENT)

                await update.message.reply_text(
                    f"✅ Order পাওয়া গেছে!\n\n"
                    f"📋 ORDER-{order_id:04d}\n"
                    f"💰 Amount: ৳{db_order.total}\n\n"
                    f"💳 Payment করুন:\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"bKash: 01737-233015\n"
                    f"Amount: ৳{db_order.total}\n"
                    f"Reference: ORDER-{order_id:04d}\n"
                    f"━━━━━━━━━━━━━━━━\n\n"
                    f"Transaction ID এবং শেষ ৪ সংখ্যা পাঠান।\n"
                    f"উদাহরণ: TRX8HG23K 4831",
                    reply_markup=ReplyKeyboardMarkup(
                        [["❌ Cancel Order"]], resize_keyboard=True
                    ),
                )
                return
            else:
                await update.message.reply_text(
                    "⚠️ Order পাওয়া যায়নি।",
                    reply_markup=main_keyboard(),
                )
                return

        # যেকোনো কথায় AI reply
        reply = get_ai_reply(user_id, user_text)
        await update.message.reply_text(reply, reply_markup=main_keyboard())
        return

    # ════════════════════════════════════════════════
    # STATE: ORDERING
    # ════════════════════════════════════════════════
    if state == OrderState.ORDERING:
        # Order শেষ করার signal
        if is_done_signal(user_text):
            order = get_order(user_id)
            if not order["items"]:
                await update.message.reply_text(
                    "⚠️ কোনো item add হয়নি। কী অর্ডার করতে চান?",
                    reply_markup=main_keyboard(),
                )
                return

            # Clear AI memory before entering ADDRESS (sensitive)
            reset_session(user_id)
            set_state(user_id, OrderState.ADDRESS)
            await update.message.reply_text(
                f"আপনার অর্ডার:\n{get_order_summary(user_id)}\n\n📍 এখন আপনার ঠিকানা লিখুন:",
                reply_markup=main_keyboard(),
            )
            return

        # Item parse করো
        qty, item_name = extract_order(user_text)

        # Validate parser output — avoid None item_name
        if not item_name:
            await update.message.reply_text(
                "⚠️ বুঝতে পারিনি। আবার লিখুন।\n\nউদাহরণ:\n1 pizza\n2 burger",
                reply_markup=main_keyboard(),
            )
            return

        item_added = add_item(user_id, item_name, qty)

        if item_added:
            await update.message.reply_text(
                f"✅ Added!\n\n{get_order_summary(user_id)}\n\n"
                "আরও কিছু লাগবে? নাকি 'না' বললে ঠিকানায় যাবো।",
                reply_markup=main_keyboard(),
            )
        else:
            await update.message.reply_text(
                f"❌ Item টি মেনুতে নেই। আবার চেষ্টা করুন।\n\n{get_menu_text()}",
                reply_markup=main_keyboard(),
            )
        return

    # ════════════════════════════════════════════════
    # STATE: ADDRESS
    # ════════════════════════════════════════════════
    if state == OrderState.ADDRESS:
        set_address(user_id, user_text)
        # Clear AI memory before entering PHONE (sensitive)
        reset_session(user_id)
        set_state(user_id, OrderState.PHONE)
        await update.message.reply_text(
            f"📍 ঠিকানা: {user_text}\n\n📱 এখন আপনার ফোন নম্বর দিন:",
            reply_markup=main_keyboard(),
        )
        return

    # ════════════════════════════════════════════════
    # STATE: PHONE
    # ════════════════════════════════════════════════
    if state == OrderState.PHONE:
        # Phone number validate করো
        digits_only = re.sub(r"\D", "", user_text)
        if len(digits_only) < 10:
            await update.message.reply_text(
                "⚠️ সঠিক ফোন নম্বর দিন। (যেমন: 01700123456)",
                reply_markup=main_keyboard(),
            )
            return

        set_phone(user_id, user_text)
        # Clear AI memory before entering CONFIRM (sensitive)
        reset_session(user_id)
        set_state(user_id, OrderState.CONFIRM)

        await update.message.reply_text(
            f"📋 অর্ডার Summary:\n\n{get_full_summary(user_id)}\n\n✅ Confirm করবেন?",
            reply_markup=confirm_keyboard(),
        )
        return

    # ════════════════════════════════════════════════
    # STATE: CONFIRM
    # ════════════════════════════════════════════════
    if state == OrderState.CONFIRM:
        if user_text == "✅ Confirm":
            order = get_order(user_id)
            total = calculate_total(user_id)
            summary = get_full_summary(user_id)  # ✅ এখানে বানাচ্ছি

            order_id = save_order(
                user_id=user_id,
                items=order["items"],
                address=order["address"],
                phone=order["phone"],
                total=total,
            )

            order["order_id"] = order_id
            order["total"] = total
            # Clear AI memory before entering PAYMENT (sensitive)
            reset_session(user_id)
            set_state(user_id, OrderState.PAYMENT)

            await update.message.reply_text(
                f"✅ অর্ডার নেওয়া হয়েছে!\n\n"
                f"📋 Order ID: ORDER-{order_id:04d}\n\n"
                f"🧾 Summary:\n{summary}\n\n"  # ✅ summary use হচ্ছে
                f"💳 এখন payment করুন:\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"bKash Personal: 01737-233015\n"
                f"Amount: ৳{total}\n"
                f"Reference: ORDER-{order_id:04d}\n"
                f"━━━━━━━━━━━━━━━━\n\n"
                f"⏰ ৩০ মিনিটের মধ্যে payment করুন।\n\n"
                f"Payment করা হলে Transaction ID এবং "
                f"আপনার bKash নম্বরের শেষ ৪ সংখ্যা পাঠান।\n\n"
                f"উদাহরণ: TRX8HG23K 4831",
                reply_markup=ReplyKeyboardMarkup(
                    [["❌ Cancel Order"]], resize_keyboard=True
                ),
            )
            return
    # ════════════════════════════════════════════════
    # STATE: PAYMENT — TRX ID + last 4 digits নাও
    # ════════════════════════════════════════════════
    if state == OrderState.PAYMENT:
        if user_text == "❌ Cancel Order":
            order = get_order(user_id)
            order_id = order.get("order_id", 0)

            # ✅ Fix 1 — DB-তে cancelled করো
            if order_id:
                cancel_order(order_id)

            reset_session(user_id)
            init_order(user_id)
            await update.message.reply_text(
                "❌ অর্ডার cancel হয়েছে।",
                reply_markup=main_keyboard(),
            )
            return

        # Format: "TRX8HG23K 4831"
        parts = user_text.strip().split()

        if len(parts) != 2 or len(parts[1]) != 4 or not parts[1].isdigit():
            await update.message.reply_text(
                "⚠️ সঠিক format-এ দিন:\n\n"
                "Transaction ID + শেষ ৪ সংখ্যা\n"
                "উদাহরণ: TRX8HG23K 4831",
            )
            return

        trx_id = parts[0]
        phone_last4 = parts[1]
        order = get_order(user_id)
        order_id = order.get("order_id", 0)
        total = order.get("total", 0)

        # ✅ Duplicate payment check
        if has_pending_payment(order_id):
            await update.message.reply_text(
                "⚠️ এই order-এ already payment submit করা হয়েছে।\n"
                "Admin verify করছেন। একটু অপেক্ষা করুন।",
                reply_markup=done_keyboard(),
            )
            reset_session(user_id)
            init_order(user_id)
            return

        # Strict TRX ID validation: only accept 8-20 alphanumeric characters
        if not re.fullmatch(r"[A-Za-z0-9]{8,20}", trx_id):
            await update.message.reply_text(
                "⚠️ Transaction ID-এর format ভুল। IDটি 8-20টি আলফানিউমেরিক অক্ষর হতে হবে।\n\nউদাহরণ: TRX8HG23K 4831",
                reply_markup=main_keyboard(),
            )
            return

        # DB-তে payment save করো
        saved = save_payment(
            order_id=order_id,
            trx_id=trx_id,
            phone_last4=phone_last4,
            amount=total,
        )

        if saved:
            await update.message.reply_text(
                f"⏳ Payment যাচাই হচ্ছে...\n\n"
                f"Order ID: ORDER-{order_id:04d}\n"
                f"TRX ID: {trx_id}\n\n"
                f"Admin verify করার পরে আপনাকে জানানো হবে। "
                f"সাধারণত ৫-১০ মিনিট সময় লাগে।",
                reply_markup=done_keyboard(),
            )
            reset_session(user_id)
            init_order(user_id)
        else:
            await update.message.reply_text(
                "⚠️ কোনো সমস্যা হয়েছে। আবার চেষ্টা করুন।",
            )
        return


# ─── Bot Commands ────────────────────────────────────
async def set_commands(app):
    await app.bot.set_my_commands(
        [
            BotCommand("start", "Bot চালু করুন"),
            BotCommand("menu", "মেনু দেখুন"),
            BotCommand("reset", "Order reset করুন"),
            BotCommand("contact", "যোগাযোগ"),
        ]
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.exception("Exception while handling an update:", exc_info=context.error)
    except Exception:
        logger.exception("Failed to log exception in error_handler")

    # Optionally notify the user that something went wrong
    try:
        if update and getattr(update, "effective_message", None):
            await update.effective_message.reply_text(
                "⚠️ একটি সার্ভারের ত্রুটি ঘটেছে। পরে আবার চেষ্টা করুন।"
            )
    except Exception:
        logger.exception("Failed to send error message to user")


# ─── Main ────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 Bot চালু হচ্ছে...")
    # ✅ Database initialize
    init_db()
    seed_menu()
    load_menu_cache()
    # Mark any pending payments that already expired
    try:
        from database import cleanup_expired_payments

        expired_count = cleanup_expired_payments()
        if expired_count:
            logger.info("Marked %d expired payments", expired_count)
    except Exception as e:
        logger.exception("Failed to cleanup expired payments: %s", e)

    threading.Thread(target=run_health_server, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", show_menu))
    app.add_handler(CommandHandler("reset", reset_order))
    app.add_handler(CommandHandler("contact", contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.post_init = set_commands
    app.add_error_handler(error_handler)

    print(f"✅ {RESTAURANT_NAME} Bot ready!")
    app.run_polling()
