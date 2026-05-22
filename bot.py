import os
import threading
import re
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update, BotCommand, ReplyKeyboardMarkup, KeyboardButton
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
    init_order, get_order, get_state, set_state,
    add_item, set_address, set_phone,
    get_order_summary, get_full_summary, calculate_total,
)
from parser import extract_order
from states import OrderState


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
    user_id  = update.effective_user.id
    user_text = update.message.text.strip()
    state    = get_state(user_id)

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING,
    )

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
            set_state(user_id, OrderState.ORDERING)
            await update.message.reply_text(
                "কী অর্ডার করতে চান? Item এবং quantity একসাথে বলুন।\n\n"
                f"{get_menu_text()}",
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
        DONE_SIGNALS = ["না", "হয়ে গেছে", "শেষ", "আর না",
                        "আর কিছু না", "এটুকুই", "ok", "done", "no"]

        if any(sig in user_text.lower() for sig in DONE_SIGNALS):
            order = get_order(user_id)
            if not order["items"]:
                await update.message.reply_text(
                    "⚠️ কোনো item add হয়নি। কী অর্ডার করতে চান?",
                    reply_markup=main_keyboard(),
                )
                return

            set_state(user_id, OrderState.ADDRESS)
            await update.message.reply_text(
                f"আপনার অর্ডার:\n{get_order_summary(user_id)}\n\n"
                "📍 এখন আপনার ঠিকানা লিখুন:",
                reply_markup=main_keyboard(),
            )
            return

        # Item parse করো
        qty, item_name = extract_order(user_text)
        item_added = add_item(user_id, item_name, qty)

        if item_added:
            await update.message.reply_text(
                f"✅ Added!\n\n{get_order_summary(user_id)}\n\n"
                "আরও কিছু লাগবে? নাকি 'না' বললে ঠিকানায় যাবো।",
                reply_markup=main_keyboard(),
            )
        else:
            await update.message.reply_text(
                "❌ Item টি মেনুতে নেই। আবার চেষ্টা করুন।\n\n"
                f"{get_menu_text()}",
                reply_markup=main_keyboard(),
            )
        return

    # ════════════════════════════════════════════════
    # STATE: ADDRESS
    # ════════════════════════════════════════════════
    if state == OrderState.ADDRESS:
        set_address(user_id, user_text)
        set_state(user_id, OrderState.PHONE)
        await update.message.reply_text(
            f"📍 ঠিকানা: {user_text}\n\n"
            "📱 এখন আপনার ফোন নম্বর দিন:",
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
        set_state(user_id, OrderState.CONFIRM)

        await update.message.reply_text(
            f"📋 অর্ডার Summary:\n\n"
            f"{get_full_summary(user_id)}\n\n"
            "✅ Confirm করবেন?",
            reply_markup=confirm_keyboard(),
        )
        return

    # ════════════════════════════════════════════════
    # STATE: CONFIRM
    # ════════════════════════════════════════════════
    if state == OrderState.CONFIRM:
        if user_text == "✅ Confirm":
            total = calculate_total(user_id)
            summary = get_full_summary(user_id)

            await update.message.reply_text(
                f"🎉 অর্ডার Confirmed!\n\n"
                f"{summary}\n\n"
                f"💰 মোট: ৳{total}\n"
                f"🚚 30-40 মিনিটে delivery হবে।\n\n"
                f"ধন্যবাদ! 🙏",
                reply_markup=done_keyboard(),
            )

            # Reset
            reset_session(user_id)
            init_order(user_id)

        elif user_text == "❌ Cancel":
            reset_session(user_id)
            init_order(user_id)
            await update.message.reply_text(
                "❌ অর্ডার cancel হয়েছে।",
                reply_markup=main_keyboard(),
            )
        return


# ─── Bot Commands ────────────────────────────────────
async def set_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start",   "Bot চালু করুন"),
        BotCommand("menu",    "মেনু দেখুন"),
        BotCommand("reset",   "Order reset করুন"),
        BotCommand("contact", "যোগাযোগ"),
    ])


# ─── Main ────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 Bot চালু হচ্ছে...")

    threading.Thread(target=run_health_server, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start",   start))
    app.add_handler(CommandHandler("menu",    show_menu))
    app.add_handler(CommandHandler("reset",   reset_order))
    app.add_handler(CommandHandler("contact", contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.post_init = set_commands

    print(f"✅ {RESTAURANT_NAME} Bot ready!")
    app.run_polling()