from telegram import Update, BotCommand
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
    add_item,
    get_order_summary,
    calculate_total,
)

from parser import extract_order


# ─────────────────────────────────────────────────────
# START
# ─────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Reset everything
    reset_session(user_id)
    init_order(user_id)

    await update.message.reply_text(
        f"🎉 {RESTAURANT_NAME}-এ স্বাগতম!\n\n"
        "আমি আপনার AI Food Assistant 🤖\n\n"
        "নিচের বাটন ব্যবহার করে মেনু দেখুন বা অর্ডার করুন 👇",
        reply_markup=main_keyboard(),
    )


# ─────────────────────────────────────────────────────
# MENU
# ─────────────────────────────────────────────────────
async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        get_menu_text(),
        reply_markup=main_keyboard(),
    )


# ─────────────────────────────────────────────────────
# CONTACT
# ─────────────────────────────────────────────────────
async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📞 যোগাযোগ করুন:\n\n"
        "📱 Phone: 01737-233015\n"
        "📍 Address: Patkelghata, Satkhira, Khulna\n"
        "⏰ Open: 11am – 11pm",
        reply_markup=main_keyboard(),
    )


# ─────────────────────────────────────────────────────
# RESET ORDER
# ─────────────────────────────────────────────────────
async def reset_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    reset_session(user_id)
    init_order(user_id)

    await update.message.reply_text(
        "✅ আপনার order reset করা হয়েছে।",
        reply_markup=main_keyboard(),
    )


# ─────────────────────────────────────────────────────
# MAIN MESSAGE HANDLER
# ─────────────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text.strip()

    # ─── Button Handling ─────────────────────────────
    if user_text == "🍽️ মেনু দেখুন":
        await show_menu(update, context)
        return

    if user_text == "📞 যোগাযোগ":
        await contact(update, context)
        return

    if user_text == "🛒 অর্ডার করুন":
        user_text = "আমি অর্ডার করতে চাই"

    if user_text == "❓ সাহায্য":
        user_text = "কীভাবে অর্ডার করবো?"

    # ─── Typing Indicator ────────────────────────────
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING,
    )

    # ─── Only Parse Order Related Messages ──────────
    # ✅ Fix 2 — Bangla food names যোগ করো
    ORDER_KEYWORDS = [
        # English
        "pizza",
        "burger",
        "coke",
        "juice",
        "water",
        "bbq",
        # Bangla food
        "পিজ্জা",
        "বার্গার",
        "কোক",
        "জুস",
        "পানি",
        "বিবিকিউ",
        "মার্গারিটা",
        "মার্গারিতা",
        "ভেজি",
        "বিফ",
        "ক্রিস্পি",
        # Action words
        "অর্ডার",
        "দিন",
        "চাই",
        "নিন",
        "লাগবে",
    ]

    user_lower = user_text.lower()

    is_order_related = any(kw in user_lower for kw in ORDER_KEYWORDS)

    item_added = False

    if is_order_related:
        qty, item_name = extract_order(user_text)

        item_added = add_item(user_id, item_name, qty)

        # Optional AI context
        if item_added:
            user_text += "\n(Item added successfully)"

    # ─── AI Response ─────────────────────────────────
    reply = get_ai_reply(user_id, user_text)

    # ─── Order Completion ────────────────────────────
    # ✅ contains check — safe
    if "ORDER_COMPLETE" in reply:
        summary = get_order_summary(user_id)
        total = calculate_total(user_id)

        reply = (
            f"✅ আপনার অর্ডার confirm হয়েছে!\n\n"
            f"{summary}\n\n"
            f"💰 মোট: ৳{total}\n"
            f"🚚 30-40 মিনিটে delivery হবে।\n\n"
            f"ধন্যবাদ! 🙏"
        )

        # Reset AI session
        reset_session(user_id)

    # ─── Send Reply ──────────────────────────────────
    await update.message.reply_text(
        reply,
        reply_markup=main_keyboard(),
    )


# ─────────────────────────────────────────────────────
# BOT COMMANDS
# ─────────────────────────────────────────────────────
async def set_commands(app):
    commands = [
        BotCommand("start", "Bot চালু করুন"),
        BotCommand("menu", "মেনু দেখুন"),
        BotCommand("reset", "Order reset করুন"),
    ]

    await app.bot.set_my_commands(commands)


# ─────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 Bot চালু হচ্ছে...")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", show_menu))
    app.add_handler(CommandHandler("reset", reset_order))

    # Messages
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    # Register bot commands
    app.post_init = set_commands

    print(f"✅ {RESTAURANT_NAME} Bot ready!")

    app.run_polling()
