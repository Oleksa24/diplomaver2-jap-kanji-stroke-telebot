import json
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8469752876:AAHg9mN7D6DSMpOVQ4DZhY92-0pJOMeX5qM"
WEB_APP_URL = "https://diplomaver2-jap-kanji-stroke-telebo.vercel.app/" # Your hosted HTML file

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("Draw Kanji ✍️", web_app=WebAppInfo(url=WEB_APP_URL))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Click the button below to draw:", reply_markup=reply_markup)

async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # 1. Get the JSON string sent from JavaScript
    data_str = update.effective_message.web_app_data.data
    
    try:
        # 2. Parse the JSON
        data = json.loads(data_str)
        strokes = data.get("strokes", [])
        width = data.get("width", 300)
        height = data.get("height", 300)

        # 3. Format the payload exactly how Google Input Tools expects it
        payload = {
            "app_version": 0.4,
            "api_level": "537.36",
            "device": "5.0 (Windows NT 10.0; Win64; x64)",
            "input_type": 0,
            "options": "enable_pre_space",
            "requests": [
                {
                    "writing_guide": {
                        "writing_area_width": width,
                        "writing_area_height": height
                    },
                    "ink": strokes,
                    "language": "ja" # 'ja' for Japanese (Kanji/Kana)
                }
            ]
        }

        # 4. Send the request to Google
        url = "https://inputtools.google.com/request?itc=ja-t-i0-handwrit&app=demopage"
        headers = {'Content-Type': 'application/json'}
        
        response = requests.post(url, json=payload, headers=headers)
        res_data = response.json()

        # 5. Parse the results
        if res_data[0] == "SUCCESS":
            # Google returns a deeply nested list. The candidates are here:
            candidates = res_data[1][0][1]
            
            # Format the candidates into a nice string
            top_result = candidates[0]
            other_options = ", ".join(candidates[1:6]) # Show the next 5 options
            
            reply_text = f"🎯 **Top Match:** {top_result}\n\n📝 *Other possibilities:* {other_options}"
        else:
            reply_text = "Sorry, Google's API couldn't recognize that drawing."

    except Exception as e:
        reply_text = f"An error occurred: {e}"

    # 6. Send the result back to the user in Telegram
    await update.message.reply_text(reply_text, parse_mode='Markdown')

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))
    application.run_polling()

if __name__ == "__main__":
    main()