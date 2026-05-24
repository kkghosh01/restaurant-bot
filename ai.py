from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from config import GROQ_API_KEY, MODEL_NAME, MAX_HISTORY
from menu import get_menu_text, RESTAURANT_NAME

# ─── AI Model ───────────────────────────────────────
llm = ChatGroq(api_key=GROQ_API_KEY, model_name=MODEL_NAME)


def build_system_prompt():
    """
    Build the system prompt at runtime. This fetches the latest menu
    from the database (via `get_menu_text`) and therefore MUST be
    called only after the DB is initialized.
    """

    menu_text = get_menu_text()

    return f"""
তুমি {RESTAURANT_NAME} রেস্টুরেন্টের AI assistant — কিন্তু খুব সীমাবদ্ধ ভূমিকা আছে।

তুমি কেবল নিম্নলিখিত কাজগুলো করো:
- গ্রাহকদের স্বাগত জানাও এবং হালকা কথাবার্তা (greetings, small talk)
- রেস্টুরেন্ট সম্পর্কিত প্রশ্নের উত্তর দাও (মেনু আইটেম বিবরণ, উপকরণ, খোলার সময় ইত্যাদি)
- মেনু থেকে সাজেস্ট করো বা রিকমেন্ডেশন দাও

তুমি কখনই নিচের কাজগুলো করবে না — এগুলো কঠোরভাবে নিষিদ্ধ:
- ঠিকানা বা ফোন নম্বর চাও বা সংগ্রহ করো না
- কোনো অর্ডার কনফার্ম করো বা অর্ডার প্রসেস করো না
- পেমেন্ট নিয়ে অনুরোধ, নির্দেশ বা প্রসেস করো না
- মেনুতে নেই এমন কোনো খাবার invent/প্রস্তাব করো না
- কোনো মূল্য (price) তৈরি বা গণনা করো না

যদি ইউজার সরাসরি একটি অর্ডার-স্টাইল মেসেজ পাঠায় (যেমন "1 pizza"), তুমি সেটি নিজে থেকেই হ্যান্ডল করো না — শুধু সংক্ষিপ্ত উত্তর দাও বা বোতাম/নির্দেশনা বলো।

মেনু (সংদর্ভ):
{menu_text}

সংক্ষেপে: শুধুমাত্র informative, conversational এবং recommendation-ভিত্তিক উত্তর দাও; কখনোই অর্ডার-ফ্লো, ঠিকানা/ফোন, কনফার্মেশন বা পেমেন্ট নিয়ে কোনো কার্যসম্পাদন করো বা অনুরোধ করো।
"""


# Safety: blocked keywords that must never appear in AI replies (case-insensitive)
BLOCKED_WORDS = [
    "ঠিকানা",
    "address",
    "ফোন",
    "phone",
    "payment",
    "bkash",
    "nagad",
    "confirm order",
    "transaction",
    "trx",
]

# Safe fallback shown when AI attempts to provide order/payment/contact flows
SAFE_FALLBACK = "অর্ডার করতে নিচের বাটন ব্যবহার করুন 👇"

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

        # Build final message list (build system prompt at call time)
        messages = [SystemMessage(content=build_system_prompt()), *session]

        # AI response
        response = llm.invoke(messages)

        # Safe conversion
        reply = str(getattr(response, "content", "")).strip()

        # Filter dangerous / out-of-scope replies — replace with safe fallback
        reply_lower = reply.lower()
        if any(keyword in reply_lower for keyword in BLOCKED_WORDS):
            # Do NOT store the original LLM response to session (avoid poisoning)
            reply = SAFE_FALLBACK
            session.append(AIMessage(content=reply))
        else:
            # Save original safe AI response
            session.append(response)

        # Trim again
        trim_session(session)

        return reply

    except Exception as e:
        print(f"❌ AI Error: {e}")

        return "⚠️ দুঃখিত, এখন server busy। একটু পরে আবার চেষ্টা করুন।"
