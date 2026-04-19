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

async def draw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    dynamic_url = f"{WEB_APP_URL}?user_id={user_id}&v=4"
    
    keyboard = [[KeyboardButton("Draw Kanji", web_app=WebAppInfo(url=dynamic_url))]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text("Click the 'Draw Kanji' button on your keyboard below to open the pad:", reply_markup=reply_markup)



tg_app.add_handler(CommandHandler("draw", draw))


@app.before_serving
async def init_bot():
    await tg_app.initialize()
    await tg_app.start()

@app.after_serving
async def stop_bot():
    await tg_app.stop()
    await tg_app.shutdown()

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
async def webhook():
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

@app.route('/recognize', methods=['POST'])
async def recognize_api():
    data = await request.get_json(force=True)
    user_id = data.get("user_id")

    if not user_id:
        return "Missing User ID", 400

    try:
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
            reply_text = f"<b>Top Match:</b> {top_match}\n\n <i>Other possibilities:</i> {others}"
        else:
            reply_text = "Sorry, couldn't recognize that drawing."
            
    except Exception as e:
        reply_text = f"An error occurred: {e}"

    await tg_app.bot.send_message(chat_id=user_id, text=reply_text, parse_mode='HTML')

    return "OK", 200