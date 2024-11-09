from flask import Flask, request, abort
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import *

app = Flask(__name__)
# LINE BOT info
line_bot_api = LineBotApi('ZqtE1jWE78Y5oxIkX9d02/E3OdllwiMz5kt+7YF8CBzQqglRuZRulg8dVqoRHpHxcgDwgQXBm8Ld+3rB6VqBFht9nDYkT3CMsE1QamcEAnR7IqHkZTM5VxtFWLpxHL7UJARRKGvttb9MQKV7QXRNuwdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('6362624df36e0b65adbc2a9d2de691eb')

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    print(body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# Message event
@handler.add(MessageEvent)
def handle_message(event):
    message_type = event.message.type
    user_id = event.source.user_id
    reply_token = event.reply_token
    message = event.message.text
    line_bot_api.reply_message(reply_token, TextSendMessage(text = "我超愛你"))

import os
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
