from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from config import GROQ_API_KEY, MODEL_NAME, MAX_HISTORY
from menu import get_menu_text, RESTAURANT_NAME

# ─── AI Model ───────────────────────────────────────
llm = ChatGroq(api_key=GROQ_API_KEY, model_name=MODEL_NAME)

# ─── System Prompt ──────────────────────────────────
menu_text = get_menu_text()

SYSTEM_PROMPT = f"""
তুমি {RESTAURANT_NAME} রেস্টুরেন্টের AI assistant।

তোমার কাজ:
- Customer-দের মেনু দেখানো
- অর্ডার নেওয়া
- বাংলায় friendly ভাবে কথা বলা

মেনু:
{menu_text}

অর্ডার নেওয়ার নিয়ম:
- item ও quantity একসাথে confirm করো, আলাদা message-এ জিজ্ঞেস করো না
- সব item নেওয়া শেষ হলে একবারেই address ও phone নাও এভাবে:
  "আপনার ঠিকানা এবং ফোন নম্বর একসাথে দিন।"
- address ও phone পেলে ORDER_COMPLETE লেখো

গুরুত্বপূর্ণ নিয়ম:
- মেনুর বাইরে কোনো খাবার invent করবে না
- নিজে কখনো total calculate করবে না
- অবশ্যই address এবং phone দুটোই পাওয়ার পরেই ORDER_COMPLETE লেখো
"""

# ─── Session Storage ────────────────────────────────
# Example:
# {
#   12345: [HumanMessage(), AIMessage(), ...]
# }

user_sessions = {}

# Human + AI দুটোই store হয়
MAX_MESSAGES = MAX_HISTORY * 2


# ─── Session Helpers ────────────────────────────────
def get_session(user_id: int):
    """
    Get or create user session
    """
    return user_sessions.setdefault(user_id, [])


def reset_session(user_id: int):
    """
    Clear conversation history
    """
    user_sessions[user_id] = []


def trim_session(messages: list):
    """
    Keep only recent messages
    """
    if len(messages) > MAX_MESSAGES:
        del messages[:-MAX_MESSAGES]


# ─── Main AI Function ───────────────────────────────
def get_ai_reply(user_id: int, user_text: str) -> str:
    try:
        # Get session
        session = get_session(user_id)

        # Add user message
        session.append(HumanMessage(content=user_text))

        # Trim old messages
        trim_session(session)

        # Build final message list
        messages = [SystemMessage(content=SYSTEM_PROMPT), *session]

        # AI response
        response = llm.invoke(messages)

        # Safe conversion
        reply = str(response.content).strip()

        # Save AI response
        session.append(response)

        # Trim again
        trim_session(session)

        return reply

    except Exception as e:
        print(f"❌ AI Error: {e}")

        return "⚠️ দুঃখিত, এখন server busy। একটু পরে আবার চেষ্টা করুন।"
