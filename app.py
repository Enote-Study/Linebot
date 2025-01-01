from flask import Flask, request, abort, jsonify
import json
import openai
from chat_history import save_chat_history, load_chat_history

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, QuickReply, QuickReplyButton,
    URIAction, ImageSendMessage, MessageAction, ImageMessage
)
from Upload_Handler import UploadHandler
from utils import check_environment_variables
import os
import firebase_admin
from firebase_admin import credentials, firestore
from threading import Thread
from review_monitor import monitor_review_status  # 假設監聽邏輯放在 review_monitor.py
from firebase_utils import db  # 引入 Firestore 客戶端

# 初始化環境變數檢查
check_environment_variables()

NOTES_PRICING = {
    "A01": 150,
    "A02": 150,
    "A03": 150,
    "A04": 30,
    "A05": 150,
    "A06": 150,
    "A07": 150,
    "A08": 150,
    "A09": 150,
    "A10": 100,
    "A11": 150
}


# 初始化 Flask 和 LINE API
app = Flask(__name__)
line_bot_api = LineBotApi(os.getenv('CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('CHANNEL_SECRET'))

# 從環境變數中獲取 OpenAI API 金鑰
openai.api_key = os.getenv("OPENAI_API_KEY")
# 用戶狀態管理
def get_user_state(user_id):
    try:
        doc = db.collection("user_states").document(user_id).get()
        if doc.exists:
            return doc.to_dict().get("state", "default")
    except Exception as e:
        print(f"Error getting user state: {e}")
    return "default"

def set_user_state(user_id, state):
    try:
        db.collection("user_states").document(user_id).set({
            "state": state,
            "last_updated": firestore.SERVER_TIMESTAMP
        }, merge=True)
    except Exception as e:
        print(f"Error setting user state: {e}")

# 更新生成學霸小E回應的函數
def generate_E_response(user_id, user_message):
    try:
        # 加載用戶對話歷史
        conversations = load_chat_history(user_id)

        # 始終確保系統角色在對話開頭
        system_message = {
            "role": "system",
            "content": (
                """你是喜歡吐槽別人的學霸小E，是幽默風趣勸學專家，針對不讀書的人，請嚴厲的指責、吐槽、批評。
                你的興趣是跟別人聊天、唱歌、講奇怪的冷笑話、偶爾幽默的引用流行歌歌詞在對話裡，
                並且要適時唱出來，或引用經典歌詞來表達你的吐槽內容！
                你必須給出具體、實用的建議，這些建議應包括可操作的步驟或真實可行的範例，幫助用戶真正解決問題。
                最近期末將至，你專治那些臨時抱佛腳、偷懶或不想讀書的學生。如果用戶考完試，你可以提供具體的放鬆方法或生活建議。
                歐趴的意思是考試ALL PASS，如果對方問你期末如何歐趴，務必給出實際的學習建議，同時保持幽默。
                可偶爾加入可愛的表情符號，每次回應在100-150字之間。

                ---
                
                【Enote 平台介紹】
                在這裡，您可以：
                📘 獲取筆記：協助您媒合及找尋需要的科目/老師的筆記
                💡 上傳筆記：分享您的筆記，成交後賺取分潤，並幫助更多學習者
                🤖 跟小E聊天：在學習之餘，陪您閒聊紓壓

                小E，做為Enote的吉祥物，你在聊天過程中適時向用戶推薦這些功能，但不要太多刻意，自然一點，幫助他們發揮 Enote 平台的最大價值！
                """
            )


        }
        if not conversations or conversations[0]["role"] != "system":
            conversations.insert(0, system_message)

        # 添加用戶的最新訊息
        conversations.append({"role": "user", "content": user_message})

        # 呼叫 GPT API 生成回應
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=conversations,
            max_tokens=180,
            temperature=0.85,
            top_p=0.9
        )

        # GPT 回應
        assistant_message = response.choices[0].message['content'].strip()

        # 儲存新的對話
        save_chat_history(user_id, "user", user_message)
        save_chat_history(user_id, "assistant", assistant_message)

        return assistant_message
    except Exception as e:
        print(f"Error generating response: {e}")
        return "抱歉，小E現在有點忙，稍後再試吧！"

# 註冊 UploadHandler
FOLDER_ID = "1h7DL1gRlB96Dpxmad0-gMvSDdVjm57vn"
upload_handler = UploadHandler(upload_folder="uploads", line_bot_api=line_bot_api, folder_id=FOLDER_ID)
app.register_blueprint(upload_handler.blueprint)

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', None)
    body = request.get_data(as_text=True)

    app.logger.info(f"Request body: {body}")
    if not signature:
        app.logger.error("缺少 X-Line-Signature")
        abort(400)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.error("簽名驗證失敗")
        abort(400)
    return 'OK'

# 快速回覆選項生成
def get_quick_reply(user_state):
    default_quick_reply = [
        QuickReplyButton(action=MessageAction(label="找學霸小E談談心！", text="跟小E對話")),
        QuickReplyButton(action=MessageAction(label="上傳筆記", text="我要上傳筆記")),
        QuickReplyButton(action=MessageAction(label="找筆記", text="找筆記")),
        QuickReplyButton(action=MessageAction(label="許願池", text="筆記許願池")),
        QuickReplyButton(action=MessageAction(label="了解Enote", text="介紹Enote"))
    ]
    chat_quick_reply = [
        QuickReplyButton(action=MessageAction(label="吐槽我為甚麼還沒開始讀書", text="吐槽我為甚麼還沒開始讀書")),
        QuickReplyButton(action=MessageAction(label="告訴我期末如何歐趴", text="告訴我期末如何歐趴")),
        QuickReplyButton(action=MessageAction(label="許願池", text="筆記許願池")),
        QuickReplyButton(action=MessageAction(label="退出小E談話模式", text="退出小E模式"))
        
        

    ]
    return QuickReply(items=chat_quick_reply if user_state == "chat_with_xiaoE" else default_quick_reply)

# 處理用戶訊息邏輯
@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    user_id = getattr(event.source, 'user_id', None)
    if not user_id:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="無法獲取用戶 ID，請確保您已添加好友。")
        )
        return

    message_text = event.message.text.strip()
    user_state = get_user_state(user_id)

    if user_state == "default":
        if message_text == "跟小E對話":
            set_user_state(user_id, "chat_with_xiaoE")
            reply_message = TextSendMessage(
                text="你好，我是學霸小E，歡迎跟我聊天！",
                quick_reply=get_quick_reply("chat_with_xiaoE")
            )

        elif message_text == "我要上傳筆記":
            quick_reply = QuickReply(items=[
                QuickReplyButton(action=URIAction(label="點擊上傳檔案", uri=f"https://{request.host}/upload?user_id={user_id}")),
                QuickReplyButton(action=MessageAction(label="找筆記", text="找筆記"))

            ])
            reply_message = TextSendMessage(
                text="請點擊下方按鈕上傳檔案：", quick_reply=quick_reply
            )
        elif message_text.startswith("購買筆記"):
            import re
            match = re.match(r"購買筆記\s*(A\d{2})", message_text)
            if match:
                note_code = match.group(1)
                if note_code in NOTES_PRICING:
                    price = NOTES_PRICING[note_code]
                    quick_reply = QuickReply(items=[
                        QuickReplyButton(action=MessageAction(label="LINE Pay", text="選擇 LINE Pay")),
                        QuickReplyButton(action=MessageAction(label="郵局匯款", text="選擇 郵局匯款"))
                    ])
                    reply_message = TextSendMessage(
                        text=f"您選擇購買筆記 {note_code}，價格為 {price} 元。請選擇您的付款方式：",
                        quick_reply=quick_reply
                    )
                else:
                    reply_message = TextSendMessage(
                        text="🌟 未找到該筆記編號，請確認後重新輸入。"
                    )
            else:
                reply_message = TextSendMessage(
                    text="🌟 請提供有效的筆記編號，例如：購買筆記 A01。"
                )
        elif message_text == "選擇 LINE Pay":
            linepay_image_url = f"https://{request.host}/static/images/linepay_qrcode.jpg"
            text_message = TextSendMessage(
                text=("✨ 感謝您的支持！\n\n"
                      "📷 請掃描以下的 QR Code 完成付款：\n\n"
                      "📤 完成付款後，請回傳付款截圖，我們將在確認款項後提供限時有效的下載連結給您！\n\n"
                      "🌟 感謝您的支持與信任，期待您的購買！ 🛍️"),
                quick_reply=get_quick_reply(user_state)
            )
            image_message = ImageSendMessage(
                original_content_url=linepay_image_url,
                preview_image_url=linepay_image_url
            )
            line_bot_api.reply_message(event.reply_token, [text_message, image_message])
            return
        elif message_text == "選擇 郵局匯款":
            reply_message = TextSendMessage(
                text=("✨ 感謝您的支持！\n\n"
                      "🏦郵局匯款\n\n"
                      "銀行代碼：700\n"
                      "帳號：0000023980362050\n\n"
                      "📤 完成匯款後，請回傳付款截圖，我們將在確認款項後提供限時有效的下載連結給您！\n\n"
                      "🌟 感謝您的支持，祝期末HIGH PASS！ 🎉"),
                quick_reply=get_quick_reply(user_state)
            )
        else:
            reply_message = TextSendMessage(
                text=" ",
                quick_reply=get_quick_reply("default")
            )
        line_bot_api.reply_message(event.reply_token, reply_message)

    

    elif user_state == "chat_with_xiaoE":
        if message_text == "退出小E模式":
            set_user_state(user_id, "default")
            reply_message = TextSendMessage(
                text="已退出學霸小E模式，趕快去讀書啦！",
                quick_reply=get_quick_reply("default")
            )

        elif message_text == "找筆記":
            set_user_state(user_id, "default")
            quick_reply=get_quick_reply("default")

        elif message_text == "筆記許願池":
            set_user_state(user_id, "default")
            quick_reply=get_quick_reply("default")

 
        elif "購買筆記" in message_text:
            set_user_state(user_id, "default")
            quick_reply=get_quick_reply("default")

        elif "上傳筆記" in message_text:
            set_user_state(user_id, "default")
            quick_reply=get_quick_reply("default")

        else:
            reply_content = generate_E_response(user_id, message_text)
            reply_message = TextSendMessage(
                text=reply_content, quick_reply=get_quick_reply("chat_with_xiaoE")
            )
        line_bot_api.reply_message(event.reply_token, reply_message)

@handler.add(MessageEvent, message=ImageMessage) 
def handle_image_message(event):
    reply_token = event.reply_token
    confirmation_message = TextSendMessage(
        text="✅ 已收到您的付款證明。我們將在確認款項後提供下載連結！"
    )
    line_bot_api.reply_message(reply_token, confirmation_message)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))

    # 啟動 Firebase 監聽器
    Thread(target=monitor_review_status, args=(line_bot_api,)).start()

    # 啟動 Flask 應用
    app.run(host='0.0.0.0', port=port)
