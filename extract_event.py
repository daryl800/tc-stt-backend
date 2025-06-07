
import json
import os
from tencentcloud.common import credential
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.hunyuan.v20230901 import hunyuan_client, models
from datetime import datetime, timedelta

from classify import classify_text  # assume same directory

TENCENT_SECRET_ID = os.getenv("TENCENT_HUNYUAN_SECRET_ID")
TENCENT_SECRET_KEY = os.getenv("TENCENT_HUNYUAN_SECRET_KEY")

cred = credential.Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)
http_profile = HttpProfile(endpoint="hunyuan.ap-hongkong.tencentcloudapi.com")
client_profile = ClientProfile(httpProfile=http_profile)
client = hunyuan_client.HunyuanClient(cred, "ap-guangzhou", client_profile)


def extract_event_info(text):
    """
    Extract structured event information from Cantonese text input.
    
    Args:
        text (str): The input text in Cantonese containing event details.
    
    Returns:
        dict: A dictionary with structured event information.
    """
    
    # Calculate next Monday and Tuesday
    today = datetime.now()
    days_ahead = 0 - today.weekday() + 7  # next Monday
    next_monday = today + timedelta(days=days_ahead)
    next_monday_str = next_monday.strftime("%Y-%m-%d")
    
    days_ahead_tuesday = days_ahead + 1  # next Tuesday
    next_tuesday = today + timedelta(days=days_ahead_tuesday)
    next_tuesday_str = next_tuesday.strftime("%Y-%m-%d")

    tomorrow = today + timedelta(days=1)
    day_after_tomorrow = today + timedelta(days=2)

    today_str = today.strftime("%Y-%m-%d")
    weekday_str = today.strftime("%A")
    tomorrow_str = tomorrow.strftime("%Y-%m-%d")
    day_after_tomorrow_str = day_after_tomorrow.strftime("%Y-%m-%d")


    prompt_system = f"""
    你是一個智能助理，負責從用戶輸入的廣東話語句中抽取結構化的事件資料。

    📅 今天是：{today_str}（{weekday_str}）。

    請根據這個日期準確解析以下時間表達：
    - 「聽日」或「tomorrow」代表 {tomorrow_str}
    - 「後日」代表 {day_after_tomorrow_str}
    - 「星期一」表示接下來的「星期一」，即 {next_monday_str}
    - 「下星期一」也是 {next_monday_str}
    - ❗ 請避免錯誤地將「星期一」或「下星期一」理解為 {next_tuesday_str}（星期二）

    🧠 你的任務是從輸入中提取以下資訊：
    1. **event**：事件的具體描述（省略提示語如「提醒我」「記住」等，只保留事件內容本身）
    2. **reminderDatetime**：事件的時間，使用 ISO 8601 格式：
        - 若時間明確（例如晏晝3點），請輸出完整格式（例如 "2025-06-09T15:00"）
        - 若只有日期（例如「下星期一」），請輸出日期（例如 "2025-06-09"）
    3. **location**：若語句中提及地點，請以字串列表返回（例如 ["香港", "養和醫院"]），若無則為空列表 []
    4. **isReminder**：若語句中有「記住」「提醒我」「提我一聲」「記落calendar」等提醒語氣，為 true；否則為 false

    📌 注意事項：
    - 僅當語句中明確表示提醒意圖時，才設置 isReminder 為 true。
    - 不要把提示語（如「記得提我」、「提醒我」）包含在 event 裡。
    - 如語句中無明確事件或無法解析時間，請設為：
        - "event": ""
        - "reminderDatetime": ""
        - "location": []
        - "isReminder": false

    🧾 例子：

    輸入：「我話幫我記落calendar，下個禮拜三晏晝3點鐘，我要翻嚟香港去養和醫院覆診。」
    輸出：
    {{
    "event": "翻嚟香港去養和醫院覆診",
    "reminderDatetime": "2025-06-11T15:00",
    "location": ["香港", "養和醫院"],
    "isReminder": true
    }}

    請只回傳純 JSON，不需要多餘說明、文字或 Markdown 格式。
    """


    req = models.ChatCompletionsRequest()
    req.Messages = [
        {"Role": "system", "Content": prompt_system},
        {"Role": "user", "Content": text},
    ]
    req.Model = "hunyuan-standard"
    req.Temperature = 0

    try:
        resp = client.ChatCompletions(req)
        raw_response = resp.Choices[0].Message.Content.strip()
        data = json.loads(raw_response)

        createdAt_iso = datetime.now().isoformat()
        event = data.get("event", "")
        reminderDatetime_iso = data.get("reminderDatetime", "")
        locations = data.get("location", [])
        isReminder = data.get("isReminder", False)

        # Compose final output
        return {
            "createdAt": createdAt_iso,
            "text": text,
            "mainEvent": event,
            "reminderDatetime": reminderDatetime_iso,
            "location": ", ".join(locations) if isinstance(locations, list) else locations,
            "isReminder": isReminder,
            "category": classify_text(text),
            "tags": list(set(event.split() + locations))  # crude keywords from event + location
        }

    except Exception as e:
        print("Error in extracting structured event info:", e)
        print("Raw response might be invalid JSON.")
        return {
            "error": str(e),
            "rawResponse": raw_response if 'raw_response' in locals() else None
        }


# Example usage
if __name__ == "__main__":
    test_text = "我话帮我记落calendar，下个礼拜三晏昼3点钟，我要翻嚟香港去养和医院复诊"
    result = extract_event_info(test_text)
    print(json.dumps(result, ensure_ascii=False, indent=2))
