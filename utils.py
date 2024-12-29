from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from linebot.models import TextSendMessage
import os
import json
import logging
from datetime import datetime

# 設定日誌
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def upload_file_to_google_drive(file_path, file_name, folder_id):
    """將檔案上傳到 Google Drive，並返回下載連結"""
    try:
        credentials_info = json.loads(os.getenv("GOOGLE_DRIVE_CREDENTIALS"))
        creds = service_account.Credentials.from_service_account_info(credentials_info)
        service = build("drive", "v3", credentials=creds)

        # 構建文件元數據
        file_metadata = {"name": file_name, "parents": [folder_id]}
        media = MediaFileUpload(file_path, resumable=True)
        file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
        file_id = file.get("id")

        # 設置檔案為公開可讀
        service.permissions().create(fileId=file_id, body={"type": "anyone", "role": "reader"}).execute()

        # 返回下載連結
        return f"https://drive.google.com/uc?id={file_id}&export=download"
    except Exception as e:
        logger.error(f"Google Drive 上傳失敗：{e}")
        raise Exception(f"Google Drive 上傳失敗：{e}")

def save_file_metadata(user_id, file_name, file_url, upload_time, subject="", grade="", year="", price=""):
    """儲存文件元數據到 Firebase Firestore"""
    try:
        from firebase_admin import firestore
        db = firestore.client()
        db.collection("notes").add({
            "user_id": user_id,
            "file_name": file_name,
            "file_url": file_url,
            "subject": subject,
            "grade": grade,
            "year": year,
            "price": price,
            "upload_time": upload_time,
            "status": "審核中"
        })
        logger.info(f"文件元數據已成功儲存：{file_name}")
    except Exception as e:
        logger.error(f"儲存文件元數據失敗：{e}")
        raise Exception(f"儲存文件元數據失敗：{e}")

def background_upload_and_save(user_id, year, file_name, file_path, subject, grade, price, upload_time, folder_id, line_bot_api):
    """後台處理文件上傳到 Google Drive 並儲存元數據到 Firestore"""
    try:
        logger.info(f"開始處理文件：{file_name}，用戶：{user_id}")

        # 上傳到 Google Drive
        file_url = upload_file_to_google_drive(file_path, file_name, folder_id)

        # 儲存元數據到 Firestore
        save_file_metadata(user_id, file_name, file_url, upload_time, subject, grade, year, price)

        # 通知用戶上傳成功
        line_bot_api.push_message(
            user_id,
            TextSendMessage(
                text="✅ 您的檔案已成功上傳！ 🎉\n"
                     "📬 我們會在有最新進展時通知您，筆記審核通過後將由 Enote 上架！✨\n"
                     "📢 上架成功後我們也會再次通知您！ 📚"
            )
        )
        logger.info(f"文件處理成功：{file_name}，下載連結：{file_url}")

    except Exception as e:
        logger.error(f"文件處理失敗：{e}")
        # 通知用戶處理失敗
        line_bot_api.push_message(
            user_id,
            TextSendMessage(text="❌ 文件處理失敗，請稍後再試。")
        )
    finally:
        # 刪除本地文件
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"已刪除本地文件：{file_path}")
