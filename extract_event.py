
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


from datetime import datetime, timedelta

def get_date_references():
    """Generate all date references for the prompt."""
    today = datetime.now()
    weekday = today.weekday()  # Monday=0, Sunday=6
    
    # Core dates
    date_refs = {
        'today': today.strftime("%Y-%m-%d"),
        'tomorrow': (today + timedelta(days=1)).strftime("%Y-%m-%d"),
        'day_after_tomorrow': (today + timedelta(days=2)).strftime("%Y-%m-%d"),
        '3_days_later': (today + timedelta(days=3)).strftime("%Y-%m-%d"),
        '1_week_later': (today + timedelta(weeks=1)).strftime("%Y-%m-%d"),
        '2_weeks_later': (today + timedelta(weeks=2)).strftime("%Y-%m-%d"),
        'next_month': (today.replace(month=today.month % 12 + 1, year=today.year + (today.month // 12))).strftime("%Y-%m-01"),
    }
    
    # Next [Weekday] calculations
    for day_idx, day in enumerate(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]):
        days_until = (day_idx - weekday + 7) % 7 or 7
        date_refs[f'next_{day}'] = (today + timedelta(days=days_until)).strftime("%Y-%m-%d")
    
    return date_refs

def build_system_prompt(date_refs):
    return f"""
    【角色】你是一個精通廣東話的智能助理，專門從用戶輸入中提取結構化事件資料。

    📅 **當前日期參考**（必須嚴格遵守）：
    - 今日：{date_refs['today']}
    - 聽日/明天 → {date_refs['tomorrow']}
    - 後日 → {date_refs['day_after_tomorrow']}
    - 3日後 → {date_refs['3_days_later']}
    - 1個星期後 → {date_refs['1_week_later']}
    - 2個星期後 → {date_refs['2_weeks_later']}
    - 下個月 → {date_refs['next_month']}（預設為1號）
    - 下星期一 → {date_refs['next_monday']}
    - 下星期二 → {date_refs['next_tuesday']}
    - 下星期三 → {date_refs['next_wednesday']}
    - ...（其他星期幾類推）

    🎯 **提取規則**：
    1. `event`：事件核心內容（刪除「提醒我」「記住」等輔助詞）
       - 錯誤示例：「記住book機票」→ "book機票"
    2. `reminderDatetime`：
       - 格式：YYYY-MM-DD（無時間則用日期）或 YYYY-MM-DDTHH:MM（有具體時間）
       - 必須使用上述日期參考，禁止自行推算
    3. `location`：只提取明確提及的地點（如「廣州」「公司」）
    4. `isReminder`：僅當出現「提我」「提醒」「記住」等關鍵詞時為`true`

    🚫 **禁止行為**：
    - 猜測未明確指定的時間（如「晏晝」預設為中午12點）
    - 修改用戶的事件描述（如簡化「預約醫生」→「睇醫生」）

    📝 **範例**：
    | 用戶輸入 | 輸出 |
    |---------|------|
    | 「下個星期三3點PM去中環見客」 | {{
      "event": "去中環見客",
      "reminderDatetime": "{date_refs['next_wednesday']}T15:00",
      "location": ["中環"],
      "isReminder": false
    }} |
    | 「兩個星期後提我交電費」 | {{
      "event": "交電費",
      "reminderDatetime": "{date_refs['2_weeks_later']}",
      "location": [],
      "isReminder": true
    }} |

    ⚠️ 只輸出JSON，不要任何解釋或註釋！
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
