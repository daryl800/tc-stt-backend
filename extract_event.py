
import json
import os
from tencentcloud.common import credential
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.hunyuan.v20230901 import hunyuan_client, models
from datetime import datetime

from classify import classify_text  # assume same directory

TENCENT_SECRET_ID = os.getenv("TENCENT_HUNYUAN_SECRET_ID")
TENCENT_SECRET_KEY = os.getenv("TENCENT_HUNYUAN_SECRET_KEY")

cred = credential.Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)
http_profile = HttpProfile(endpoint="hunyuan.ap-hongkong.tencentcloudapi.com")
client_profile = ClientProfile(httpProfile=http_profile)
client = hunyuan_client.HunyuanClient(cred, "ap-guangzhou", client_profile)


def extract_event_info(text):
    today_str = datetime.now().strftime("%Y-%m-%d")
    weekday_str = datetime.now().strftime("%A")  # e.g., Friday

    prompt_system = f"""
    你是一個智能助理，從廣東話語句中抽取結構化的事件資料。
    今天是：{today_str}（{weekday_str}），請根據這個日期準確计算「聽日」「tomorrow」「next Wednesday」「下星期三」等相對日期。

    請專注於語句中提到的實際事件內容，並判斷這是否屬於用戶的提醒要求。
    請注意，**不要**將語句中的提示詞（如『提醒我』、『記住』、『記落calendar』等）視為事件的一部分。
    只有在語句中**明確提及提醒意圖**時，例如『記住』『提醒我』『提我一聲』『記落calendar』等，才將 isReminder 標記為 true。

    請從輸入中提取以下資訊：
    1. event：事件的描述（省略如『提醒我』等提示語，聚焦事件本身）
    2. reminderDatetime：事件的時間（ISO 8601 格式，精確至分鐘，例如 2025-06-06T08:30），若無明確時間，请提供日期并省略时间，即如 2025-06-06。
    3. location：如有提及，提取所有地點，格式為字串列表，例如 ["佛山", "中山"]。
    4. isReminder：布林值（true/false），如句中有『提醒我』『記住』『記落calendar』等才為 true。

    只回傳純 JSON，不要有多餘文字或 Markdown 格式。
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
