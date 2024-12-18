import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from firebase_admin import firestore
from flexmessage import create_upload_success_flex

def upload_file_to_google_drive(file_path, file_name, folder_id):
    """將檔案上傳到 Google Drive，並返回下載連結"""
    service = build("drive", "v3")
    file_metadata = {"name": file_name, "parents": [folder_id]}
    media = MediaFileUpload(file_path, resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    file_id = file.get("id")
    service.permissions().create(fileId=file_id, body={"type": "anyone", "role": "reader"}).execute()
    return f"https://drive.google.com/uc?id={file_id}&export=download"

def save_file_metadata(user_id, file_name, file_url, subject, grade):
    """將檔案的元數據儲存到 Firebase"""
    db = firestore.client()
    db.collection("notes").add({
        "user_id": user_id,
        "file_name": file_name,
        "file_url": file_url,
        "subject": subject,
        "grade": grade,
        "status": "審核中"
    })

def background_upload_and_save(user_id, file_name, file_path, subject, grade, folder_id, line_bot_api):
    """後台執行上傳和儲存任務"""
    try:
        # 上傳檔案到 Google Drive
        file_url = upload_file_to_google_drive(file_path, file_name, folder_id)
        # 儲存到 Firebase
        save_file_metadata(user_id, file_name, file_url, subject, grade)
        # 刪除本地檔案
        os.remove(file_path)
        # 發送上傳成功的 Flex Message
        flex_message = create_upload_success_flex(file_name, subject, grade)
        line_bot_api.push_message(user_id, flex_message)
        print(f"檔案已上傳並通知用戶 {user_id}")
    except Exception as e:
        print(f"背景處理失敗：{e}")
