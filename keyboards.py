from telegram import ReplyKeyboardMarkup


def main_keyboard():
    buttons = [["🍽️ মেনু দেখুন", "🛒 অর্ডার করুন"], ["📞 যোগাযোগ", "❓ সাহায্য"]]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
