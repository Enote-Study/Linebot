from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import firebase_admin
from firebase_admin import credentials, firestore
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# 使用 Google Drive API 的服務憑證初始化
creds = service_account.Credentials.from_service_account_file("googledrive_credentials.json")
service = build('drive', 'v3', credentials=creds)


# 使用 Firebase 控制台下載的服務憑證 JSON 檔案
cred = credentials.Certificate("path/to/your/serviceAccountKey.json")
firebase_admin.initialize_app(cred)

# 建立 Firestore 客戶端
db = firestore.client()


app = Flask(__name__)
# LINE BOT info
line_bot_api = LineBotApi(os.getenv('CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('CHANNEL_SECRET'))

# 上傳檔案到 Google Drive 並返回下載連結
def upload_file_to_google_drive(file_path, file_name):
    file_metadata = {'name': file_name}
    media = MediaFileUpload(file_path, resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    file_id = file.get('id')
    service.permissions().create(fileId=file_id, body={'type': 'anyone', 'role': 'reader'}).execute()
    file_url = f"https://drive.google.com/uc?id={file_id}&export=download"
    return file_url

# 儲存檔案元數據到 Firestore
def save_file_metadata(user_id, file_name, file_url):
    db.collection("notes").add({
        "user_id": user_id,
        "file_name": file_name,
        "file_url": file_url
    })

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

# Message event: 處理文字訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    user_id = event.source.user_id
    reply_token = event.reply_token
    message_text = event.message.text.strip()

    if message_text == "我要上傳筆記":
        line_bot_api.reply_message(reply_token, TextSendMessage(text="請上傳您的筆記檔案。"))
    elif message_text == "我要取得筆記":
        # 從 Firestore 中查詢使用者的筆記
        notes = db.collection("notes").where("user_id", "==", user_id).stream()
        notes_text = "\n".join([f"{note.to_dict()['file_name']}: {note.to_dict()['file_url']}" for note in notes])
        
        if notes_text:
            line_bot_api.reply_message(reply_token, TextSendMessage(text=f"這是您的筆記連結：\n{notes_text}"))
        else:
            line_bot_api.reply_message(reply_token, TextSendMessage(text="目前沒有找到您的筆記。"))
    else:
        line_bot_api.reply_message(reply_token, TextSendMessage(text="我有收到您的訊息，但不確定您的需求。請輸入「我要上傳筆記」或「我要取得筆記」。"))

# FileMessage event: 處理檔案上傳
@handler.add(MessageEvent, message=FileMessage)
def handle_file_message(event):
    user_id = event.source.user_id
    reply_token = event.reply_token
    message_id = event.message.id
    file_name = event.message.file_name

    # 下載檔案內容
    message_content = line_bot_api.get_message_content(message_id)
    file_path = f"/tmp/{file_name}"

    # 儲存檔案到本地 /tmp 資料夾
    with open(file_path, 'wb') as f:
        for chunk in message_content.iter_content():
            f.write(chunk)

    # 上傳檔案到 Google Drive 並取得下載連結
    file_url = upload_file_to_google_drive(file_path, file_name)

    # 儲存檔案元數據到 Firestore
    save_file_metadata(user_id, file_name, file_url)

    # 回覆使用者成功訊息
    line_bot_api.reply_message(reply_token, TextSendMessage(text=f"檔案已成功上傳！下載連結：{file_url}"))

    # 刪除本地檔案以節省空間
    os.remove(file_path)

# 啟動 Flask 伺服器
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
