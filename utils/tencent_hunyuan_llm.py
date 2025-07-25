import json
from datetime import datetime, timedelta  # Add this at the top of your file
from tencentcloud.common import credential
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.hunyuan.v20230901 import hunyuan_client, models
from models.memory_item import MemoryItem
from config.constants import TENCENT_SECRET_ID, TENCENT_SECRET_KEY

# Initialize Hunyuan client (singleton pattern)
_hunyuan_client = None

# def get_hunyuan_client():
#     global _hunyuan_client
#     if _hunyuan_client is None:
#         cred = credential.Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)
#         http_profile = HttpProfile(endpoint="hunyuan.ap-hongkong.tencentcloudapi.com")
#         client_profile = ClientProfile(httpProfile=http_profile)
#         _hunyuan_client = hunyuan_client.HunyuanClient(cred, "ap-hongkong", client_profile)
#     return _hunyuan_client

def get_hunyuan_client():
    global _hunyuan_client
    if _hunyuan_client is None:
        try:
            cred = credential.Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)
            http_profile = HttpProfile(endpoint="hunyuan.ap-hongkong.tencentcloudapi.com")
            client_profile = ClientProfile(httpProfile=http_profile)
            _hunyuan_client = hunyuan_client.HunyuanClient(cred, "ap-hongkong", client_profile)
        except Exception as e:
            print(f"初始化混元客户端失败: {e}")
            raise  # 或返回 None，根据业务需求处理
    return _hunyuan_client

# You would need to implement these helper functions:


# Date Calculation Helpers
import re
import json
from datetime import datetime, timedelta
from typing import Optional

from datetime import datetime, timedelta
import re
from typing import Optional

from datetime import datetime, timedelta
from typing import Optional
import re

import re
from datetime import datetime, timedelta
from typing import Optional

WEEKDAY_MAP = {'一': 0, '二': 1, '三': 2, '四': 3, '五': 4, '六': 5, '日': 6, '天': 6}

def get_date_of_next_weekday(target_weekday: int, base_date: datetime) -> datetime:
    """
    Returns the date of the target weekday in the *next* week (starting from next Monday).
    target_weekday: 0 (Mon) to 6 (Sun)
    """
    base_weekday = base_date.weekday()
    days_until_next_monday = (7 - base_weekday) % 7 or 7
    next_monday = base_date + timedelta(days=days_until_next_monday)
    return next_monday + timedelta(days=target_weekday)

def calculate_cantonese_date(text: str, base_date: datetime = None) -> Optional[datetime]:
    """
    Calculates dates from Cantonese expressions like:
    - 今日, 聽日, 後日
    - 星期五, 下星期五, 下下星期一
    Handles correct offsets for week prefixes.
    """
    base_date = base_date or datetime.now()
    text = text.replace("礼拜", "星期").replace("聽日", "听日")

    # Handle relative days
    if "听日" in text:
        return (base_date + timedelta(days=1)).replace(hour=12, minute=0)
    elif "後日" in text or "后日" in text:
        return (base_date + timedelta(days=2)).replace(hour=12, minute=0)
    elif "大後日" in text:
        return (base_date + timedelta(days=3)).replace(hour=12, minute=0)
    elif "今日" in text or "而家" in text:
        return base_date.replace(hour=12, minute=0)

    # Match weekday expression
    weekday_match = re.search(r'(下下星期|下星期|星期)([一二三四五六日天])', text)
    if weekday_match:
        prefix, day_char = weekday_match.groups()
        target_weekday = WEEKDAY_MAP[day_char]

        if prefix == '星期':
            # Same week
            delta = (target_weekday - base_date.weekday() + 7) % 7
            if delta == 0:
                delta = 7  # Move to next occurrence if same day
            target_date = base_date + timedelta(days=delta)

        elif prefix == '下星期':
            target_date = get_date_of_next_weekday(target_weekday, base_date)

        elif prefix == '下下星期':
            target_date = get_date_of_next_weekday(target_weekday, base_date) + timedelta(days=7)

        else:
            return None

        print(f"[DEBUG] Calculated weekday: {target_date.date()} from text: {text}")

        # Time parsing
        hour, minute = 12, 0
        if "朝早" in text or "上午" in text:
            hour = 9
        elif "晏昼" in text or "下午" in text:
            hour = 14
        elif "夜晚" in text or "晚上" in text:
            hour = 20

        time_match = re.search(r'(\d+)(?:点|點)(半)?', text)
        if time_match:
            hour = int(time_match.group(1))
            if "下午" in text and hour < 12:
                hour += 12
            if time_match.group(2):  # 半
                minute = 30

        return target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

    return None


def extract_info_withLLM(text: str) -> MemoryItem:
    try:
        client = get_hunyuan_client()

        # Deterministic datetime
        detected_date = calculate_cantonese_date(text)
        print(f"[DEBUG] text: {text}")
        # Format date as ISO string if available
        date_str = detected_date.strftime("%Y-%m-%dT%H:%M") if detected_date else ""
        print(f"[DEBUG] Detected date: {date_str}")

        prompt = f"""
            [Current Date] {datetime.now().strftime("%Y-%m-%d (%A)")}
            [Detected Date] {date_str if date_str else "None"}

            Please analyze the following Cantonese input and extract key information.

            Input:
            "{text}"

            ## Instructions:

            1. Date/Time Handling
            - Use the "[Detected Date]" if provided. Do NOT guess or change the date unless the input text clearly contradicts it.
            - "听日" = tomorrow
            - "後日" = day after tomorrow
            - "大後日" = three days later
            - "今个[weekday]" = this week's [weekday]
            - "下个[weekday]" = next week's [weekday]
            - "中午" = 12:00, "晏昼" = 14:00, "晚上"/"夜晚" = 20:00, "朝早"/"上午" = 09:00
            - Time like "两点半" = 14:30 if in afternoon context

            2. Output Format:
            {{
            "reminderDatetime": "ISO string",
            "mainEvent": "...",
            "category": "Reminder",
            "location": [],
            "isReminder": true,
            "isQuery": false,
            "tags": ["..."]
            }}

            Only output a single valid JSON object.
            """

        req = models.ChatCompletionsRequest()
        req.Messages = [{"Role": "user", "Content": prompt}]
        req.Model = "hunyuan-standard"
        req.Temperature = 0.7

        resp = client.ChatCompletions(req)
        data = json.loads(resp.Choices[0].Message.Content.strip())

        # Force deterministic date if available
        final_date = date_str if data.get("isReminder") else ""


        return MemoryItem(
            category=data.get("category", "General"),
            transcription=text,
            mainEvent=data.get("mainEvent", text.split("。")[0]),
            reminderDatetime=final_date,
            isReminder=data.get("isReminder", False),
            isQuery=data.get("isQuery", False),
            location=list(set(data.get("location", []))),
            tags=list(set(data.get("tags", []))),
            eventCreatedAt=datetime.now(),
            originalVoice_Url=None,
            sourceLang="yue-HK",
            userId=None
        )

    except Exception as e:
        print(f"[ERROR] LLM extraction failed: {e}")
        return MemoryItem(
            category="General",
            transcription=text,
            mainEvent=text.split("。")[0],
            reminderDatetime="",
            isReminder=False,
            isQuery=False,
            location=[],
            tags=[f"Error: {str(e)}"] if not isinstance(e, json.JSONDecodeError) else [],
            eventCreatedAt=datetime.now(),
            originalVoice_Url=None,
            sourceLang="yue-HK",
            userId=None
        )


# Example usage
if __name__ == "__main__":
    test_text = "提醒我，听日我约咗人食晚饭。"
    test_base_date = datetime(2025, 7, 21)  # Monday
    calculated = calculate_cantonese_date(test_text, test_base_date)
    print(f"Calculated date: {calculated.strftime('%Y-%m-%d %H:%M') if calculated else 'None'}")

    result = extract_info_withLLM(test_text)
    print(f"Extracted Date: {result.reminderDatetime}")
    print(f"Main Event: {result.mainEvent}")

from datetime import datetime

from datetime import datetime
from typing import Optional

def generate_reflection(text: str) -> str:
    try:
        client = get_hunyuan_client()

        # Deterministic datetime
        detected_date = calculate_cantonese_date(text)
        print(f"[DEBUG] text: {text}")
        # Format date as ISO string if available
        date_str = detected_date.strftime("%Y-%m-%dT%H:%M") if detected_date else ""
        print(f"[DEBUG] Detected date: {date_str}")


        prompt = f"""
            你係一個有記憶力、貼心、識講廣東話嘅助理。

            [Current Date]: {datetime.now().strftime("%Y-%m-%d (%A)")}
            [Detected Date]: {date_str if date_str else "None"}

            【指引】：
            1. 如果用戶問日期、時間、地點等問題（例如「下星期四係幾號？」）→ 直接用 [Detected Date] 回答，用簡潔廣東話答出日期（例如：「下星期四係8月7號」）。
            2. **嚴禁更改或估算 [Detected Date] 之外的日期或時間**。
            3. 如果用戶係閒聊 → 可以輕鬆地做簡短反思或建議。
            4. 如果 [Detected Date] 係 "None"，你可以自由回答。
            5. **只能用純廣東話回應，用一句自然流暢嘅說話，不要解釋或翻譯。**

            【用戶輸入】：
            {text}
            """

        req = models.ChatCompletionsRequest()
        req.Messages = [{"Role": "user", "Content": prompt}]
        req.Model = "hunyuan-standard"
        req.Temperature = 1

        resp = client.ChatCompletions(req)
        reflection = resp.Choices[0].Message.Content.strip()

        print(f"[INFO] Reflection: {reflection}")
        return reflection

    except Exception as e:
        print(f"[ERROR] Reflection failed: {e}")
        return "我記低咗你講嘅內容啦，有需要可以再問我！"
