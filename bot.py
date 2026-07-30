import json
import time
from openai import OpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

# ==========================
# CONFIG
# ==========================
import os

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
AIPIPE_TOKEN = os.environ["AIPIPE_TOKEN"]
LOG_URL = os.environ["LOG_URL"]

# ==========================

client = OpenAI(
    base_url="https://aipipe.org/openai/v1",
    api_key=AIPIPE_TOKEN,
)

LOG_FILE = "run.jsonl"

conversation_history = {}


def log_event(event):
    event["timestamp"] = time.time()

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text

    log_event({
        "type": "incoming",
        "chat_id": chat_id,
        "text": user_text
    })

    history = conversation_history.setdefault(chat_id, [])
    history.append({
        "role": "user",
        "content": user_text
    })

    system_prompt = """
You are a careful data analyst.

If the user specifies a JSON format, respond ONLY with that JSON.

Otherwise respond ONLY with a valid JSON object.

Never use markdown.
Never use code fences.
Never explain.
Return valid JSON only.
"""

    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {
                "role": "system",
                "content": system_prompt
            }
        ] + history[-6:]
    )

    reply_text = response.choices[0].message.content.strip()

    print("\n========== AI RESPONSE ==========")
    print(reply_text)
    print("================================\n")

    history.append({
        "role": "assistant",
        "content": reply_text
    })

    try:
        parsed = json.loads(reply_text)

    except Exception:

        start = reply_text.find("{")
        end = reply_text.rfind("}")

        if start != -1 and end != -1:
            try:
                parsed = json.loads(reply_text[start:end + 1])
            except Exception:
                parsed = {
                    "response": reply_text
                }
        else:
            parsed = {
                "response": reply_text
            }

    parsed["log_url"] = LOG_URL

    final_reply = json.dumps(
        parsed,
        ensure_ascii=False
    )

    log_event({
        "type": "outgoing",
        "chat_id": chat_id,
        "text": final_reply
    })

    await update.message.reply_text(final_reply)


app = (
    ApplicationBuilder()
    .token(TELEGRAM_BOT_TOKEN)
    .build()
)

app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message,
    )
)

print("Bot is running...")

app.run_polling()