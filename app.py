import os
import json
import requests
from quart import Quart, request, send_file
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

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


async def kanji_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    kanji_char = query.data.split('_')[1]

    try:
        api_url = f"https://kanjiapi.dev/v1/kanji/{kanji_char}"
        resp = requests.get(api_url)

        if resp.status_code == 200:
            data = resp.json()
            meanings = ", ".join(data.get("meanings", []))
            kun = ", ".join(data.get("kun_readings", []))
            on = ", ".join(data.get("on_readings", []))

            excerpt = f"<b>{kanji_char}</b>\n\n"
            excerpt += f"<b>Meaning:</b> {meanings}\n"
            if kun: excerpt += f"<b>Kun:</b> {kun}\n"
            if on: excerpt += f"<b>On:</b> {on}\n"
        else:
            excerpt = f"<b>{kanji_char}</b>\n\nNo standard dictionary entry found for this character."

    except Exception as e:
        excerpt = "Sorry, couldn't reach the dictionary right now."

    jisho_url = f"https://jisho.org/search/{kanji_char}%20%23kanji"
    dict_keyboard = [[InlineKeyboardButton("View full page on Jisho.org", url=jisho_url)]]
    reply_markup = InlineKeyboardMarkup(dict_keyboard)

    await query.message.reply_text(excerpt, parse_mode='HTML', reply_markup=reply_markup)

tg_app.add_handler(CommandHandler("draw", draw))
tg_app.add_handler(CallbackQueryHandler(kanji_button_click, pattern="^k_"))

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
            candidates = res_data[1][0][1][:6]
            
            buttons = []
            for kanji in candidates:
                buttons.append(InlineKeyboardButton(kanji, callback_data=f"k_{kanji}"))
            
            keyboard = [buttons[i:i+3] for i in range(0, len(buttons), 3)]
            reply_markup = InlineKeyboardMarkup(keyboard)

            reply_text = "<b>Drawing Recognized!</b>\nSelect a Kanji below to see its definition:"
            
            await tg_app.bot.send_message(
                chat_id=user_id, 
                text=reply_text, 
                parse_mode='HTML', 
                reply_markup=reply_markup
            )
            return "OK", 200

        else:
            await tg_app.bot.send_message(chat_id=user_id, text="Sorry, couldn't recognize that drawing.")
            return "OK", 200
            
    except Exception as e:
        reply_text = f"An error occurred: {e}"

    return "OK", 200