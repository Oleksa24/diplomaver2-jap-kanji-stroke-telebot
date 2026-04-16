import os
import json
import requests
from quart import Quart, request, send_file
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:5000")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEB_APP_URL = f"{RENDER_URL}/pad"

app = Quart(__name__)
tg_app = Application.builder().token(BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [[KeyboardButton("Draw Kanji ✍️", web_app=WebAppInfo(url=WEB_APP_URL))]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Click the 'Draw Kanji' button on your keyboard below to open the pad:", reply_markup=reply_markup)

async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data_str = update.effective_message.web_app_data.data
    try:
        data = json.loads(data_str)
        payload = {
            "app_version": 0.4,
            "api_level": "537.36",
            "device": "5.0",
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

tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))

# --- QUART SERVER LIFECYCLE & ROUTES ---

@app.before_serving
async def init_bot():
    """Start the bot when the web server boots up."""
    await tg_app.initialize()
    await tg_app.start()

@app.after_serving
async def stop_bot():
    """Gracefully shut down the bot when the server stops."""
    await tg_app.stop()
    await tg_app.shutdown()

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
async def webhook():
    # Quart requires awaiting the json body payload
    req_json = await request.get_json(force=True)
    update = Update.de_json(req_json, tg_app.bot)
    await tg_app.process_update(update)
    return "OK", 200

@app.route('/pad', methods=['GET'])
async def serve_pad():
    basedir = os.path.abspath(os.path.dirname(__file__))
    return await send_file(os.path.join(basedir, 'kanji-pad.html'))

@app.route('/', methods=['GET'])
async def index():
    return "Telegram Kanji Bot is running!", 200