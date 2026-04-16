import os
import json
import requests
import asyncio
from flask import Flask, request, send_file
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Render provides RENDER_EXTERNAL_URL automatically (e.g., https://my-bot.onrender.com)
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:5000")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEB_APP_URL = f"{RENDER_URL}/pad"

app = Flask(__name__)
tg_app = Application.builder().token(BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [[InlineKeyboardButton("Draw Kanji ✍️", web_app=WebAppInfo(url=WEB_APP_URL))]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Click the button below to draw:", reply_markup=reply_markup)

async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data_str = update.effective_message.web_app_data.data
    try:
        data = json.loads(data_str)
        payload = {
            "app_version": 0.4,
            "api_level": "537.36",
            "device": "5.0 (Windows NT 10.0; Win64; x64)",
            "input_type": 0,
            "options": "enable_pre_space",
            "requests": [{
                "writing_guide": {
                    "writing_area_width": data.get("width", 300), 
                    "writing_area_height": data.get("height", 300)
                },
                "ink": data.get("strokes", []),
                "language": "ja"
            }]
        }
        
        url = "https://inputtools.google.com/request?itc=ja-t-i0-handwrit&app=demopage"
        response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
        res_data = response.json()

        if res_data[0] == "SUCCESS":
            candidates = res_data[1][0][1]
            top_match = candidates[0]
            others = ", ".join(candidates[1:6])
            reply_text = f"🎯 **Top Match:** {top_match}\n\n📝 *Other possibilities:* {others}"
        else:
            reply_text = "Sorry, couldn't recognize that drawing."
            
    except Exception as e:
        reply_text = f"An error occurred: {e}"

    await update.message.reply_text(reply_text, parse_mode='Markdown')

# Register handlers
tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))

# --- FLASK ROUTES ---
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
async def webhook():
    # The Telegram application must be initialized before processing updates
    if not tg_app.bot_data.get("is_initialized"):
        await tg_app.initialize()
        tg_app.bot_data["is_initialized"] = True
        
    # Get the data from Telegram and process it
    update = Update.de_json(request.get_json(force=True), tg_app.bot)
    await tg_app.process_update(update)
    
    return "OK", 200

@app.route('/pad', methods=['GET'])
def serve_pad():
    # Safely get the absolute path to the HTML file
    basedir = os.path.abspath(os.path.dirname(__file__))
    return send_file(os.path.join(basedir, 'kanji-pad.html'))

@app.route('/', methods=['GET'])
def index():
    return "Telegram Kanji Bot is running!", 200