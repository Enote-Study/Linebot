from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
import os

app = Flask(__name__)

# 初始化 LINE Bot API 和 Webhook Handler
line_bot_api = LineBotApi(os.getenv("ZqtE1jWE78Y5oxIkX9d02/E3OdllwiMz5kt+7YF8CBzQqglRuZRulg8dVqoRHpHxcgDwgQXBm8Ld+3rB6VqBFht9nDYkT3CMsE1QamcEAnR7IqHkZTM5VxtFWLpxHL7UJARRKGvttb9MQKV7QXRNuwdB04t89/1O/w1cDnyilFU="))
handler = WebhookHandler(os.getenv("6362624df36e0b65adbc2a9d2de691eb"))

@app.route("/webhook", methods=['POST'])
def webhook():
    # 獲取 X-Line-Signature
    signature = request.headers['X-Line-Signature']

    # 獲取請求的 JSON 資料
    body = request.get_data(as_text=True)

    # 驗證簽名
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)  # 如果驗證失敗，返回 400 錯誤

    return 'OK'

# 可以添加您的事件處理函數
@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=event.message.text)
    )

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
