import json
import os
import re
from datetime import datetime, timedelta
from tencentcloud.common import credential
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.hunyuan.v20230901 import hunyuan_client, models

TENCENT_SECRET_ID = os.getenv("TENCENT_HUNYUAN_SECRET_ID")
TENCENT_SECRET_KEY = os.getenv("TENCENT_HUNYUAN_SECRET_KEY")

cred = credential.Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)
http_profile = HttpProfile(endpoint="hunyuan.ap-hongkong.tencentcloudapi.com")
client_profile = ClientProfile(httpProfile=http_profile)
client = hunyuan_client.HunyuanClient(cred, "ap-guangzhou", client_profile)

def extract_event_info(text):
    """
    Extract structured event information from Cantonese text input.
    Optimized for HunYuan LLM with dynamic date handling.
    
    Args:
        text (str): Input text in Cantonese (e.g., "下個星期三book機票去桂林")
    
    Returns:
        dict: Structured event data in format:
            {
                "createdAt": str,
                "text": str,
                "mainEvent": str,
                "reminderDatetime": str,
                "location": str,
                "isReminder": bool,
                "category": str,
                "tags": list
            }
    """
    # ===== 1. Generate Dynamic Date References =====
    today = datetime.now()
    date_refs = {
        # Core dates
        'today': today.strftime("%Y-%m-%d"),
        'tomorrow': (today + timedelta(days=1)).strftime("%Y-%m-%d"),
        'day_after_tomorrow': (today + timedelta(days=2)).strftime("%Y-%m-%d"),
        '1_week_later': (today + timedelta(weeks=1)).strftime("%Y-%m-%d"),
        '2_weeks_later': (today + timedelta(weeks=2)).strftime("%Y-%m-%d"),
        'next_month': (today.replace(
            month=today.month % 12 + 1,
            year=today.year + (today.month // 12)
        )).strftime("%Y-%m-01")
    }
    # Next [Weekday] calculations (Monday=0 to Sunday=6)
    for day_idx, day in enumerate(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]):
        days_until = (day_idx - today.weekday() + 7) % 7 or 7
        date_refs[f'next_{day}'] = (today + timedelta(days=days_until)).strftime("%Y-%m-%d")

    # ===== 2. Build Optimized Prompt =====
    prompt_system = f"""
    [SYSTEM PROMPT]
    Role: 你是一個廣東話事件提取助手，嚴格按以下規則輸出JSON:
    
    📅 日期映射 (必須使用):
    - 今日: {date_refs['today']}
    - 聽日/明天: {date_refs['tomorrow']}
    - 後日: {date_refs['day_after_tomorrow']}
    - 下星期三: {date_refs['next_wednesday']}
    - 2個星期後: {date_refs['2_weeks_later']}
    - 下個月: {date_refs['next_month']}
    (其他星期幾類推)

    🎯 提取要求:
    1. "event": 事件內容 (刪除「提醒我」等詞)
    2. "reminderDatetime": 嚴格使用上方日期 + 時間 (如 "15:00")
    3. "location": 只提取明確地點 (如 ["桂林"])
    4. "isReminder": 僅當有「提我」「記住」時為true

    🚫 禁止:
    - 自行計算日期
    - 猜測模糊時間 (如「晏晝」默認14:00)

    [OUTPUT FORMAT]
    {{
        "event": "事件描述",
        "reminderDatetime": "YYYY-MM-DD或YYYY-MM-DDTHH:MM",
        "location": ["地點"],
        "isReminder": true/false
    }}
    """

    # ===== 3. Call HunYuan LLM =====
    req = models.ChatCompletionsRequest()
    req.Messages = [
        {"Role": "system", "Content": prompt_system},
        {"Role": "user", "Content": text}
    ]
    req.Model = "hunyuan-standard"
    req.Temperature = 0

    try:
        resp = client.ChatCompletions(req)
        raw_response = resp.Choices[0].Message.Content.strip()
        data = json.loads(raw_response)

        # Handle "下個月X號" pattern
        if "下個月" in text and "號" in text:
            if match := re.search(r"下個月(\d{1,2})號", text):
                day = match.group(1).zfill(2)
                data["reminderDatetime"] = f"{date_refs['next_month'][:-3]}{day}"

        # Compose final output
        return {
            "createdAt": datetime.now().isoformat(),
            "text": text,
            "mainEvent": data.get("event", ""),
            "reminderDatetime": data.get("reminderDatetime", ""),
            "location": ", ".join(data.get("location", [])),
            "isReminder": data.get("isReminder", False),
            "category": classify_text(text) if 'classify_text' in globals() else "Reminder",
            "tags": list(set(data.get("event", "").split() + data.get("location", [])))
        }

    except json.JSONDecodeError:
        return {
            "createdAt": datetime.now().isoformat(),
            "text": text,
            "error": "Invalid JSON response from LLM",
            "rawResponse": raw_response
        }
    except Exception as e:
        return {
            "createdAt": datetime.now().isoformat(),
            "text": text,
            "error": str(e)
        }

# Example usage
if __name__ == "__main__":
    test_text = "下個星期三，記住提我book機票去桂林"
    result = extract_event_info(test_text)
    print(json.dumps(result, ensure_ascii=False, indent=2))