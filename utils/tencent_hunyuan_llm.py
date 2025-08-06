from typing import Optional
from datetime import datetime, timedelta
import re
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


def get_hunyuan_client():
    global _hunyuan_client
    if _hunyuan_client is None:
        try:
            cred = credential.Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)
            http_profile = HttpProfile(
                endpoint="hunyuan.ap-hongkong.tencentcloudapi.com")
            client_profile = ClientProfile(httpProfile=http_profile)
            _hunyuan_client = hunyuan_client.HunyuanClient(
                cred, "ap-hongkong", client_profile)
        except Exception as e:
            print(f"初始化混元客户端失败: {e}")
            raise  # 或返回 None，根据业务需求处理
    return _hunyuan_client


# Example mappings for normalization
TRAD_TO_SIMP_REPLACEMENTS = {
    "聽日": "听日",
    "明日": "听日",
    "聽朝": "听朝",
    "聽早": "听朝",
    "聽晚": "听晚",
    "明晚": "听晚",
    "聽朝早": "听朝",
    "聽日朝早": "听朝",
    "聽日中午": "听日中午",
    "聽日晚上": "听晚",
    "聽日下午": "听日晏昼",
    "聽日下昼": "听日晏昼",
    "聽日晏昼": "听日晏昼",

    "後日": "后日",
    "後天": "后日",
    "後朝": "后朝",
    "後早": "后朝",
    "後晚": "后晚",
    "後朝早": "后朝",
    "後日朝早": "后朝",
    "後日中午": "后日中午",
    "後日晚上": "后晚",
    "後日下午": "后日晏昼",
    "後日下昼": "后日晏昼",
    "後日晏昼": "后日晏昼",

    "大後日": "大后日",
    "大後天": "大后日",
    "大後日朝": "大后朝",
    "大後朝早": "大后朝",
    "大後日朝早": "大后朝",
    "大後日中午": "大后日中午",
    "大後晚": "大后晚",
    "大後日下午": "大后日晏昼",
    "大後日下昼": "大后日晏昼",
    "大後日晏昼": "大后日晏昼",

    "禮拜": "星期",
    "礼拜": "星期",
    "呢": "今",
    "個": "",
    "个": ""
}

# Simplified keyword sets (after normalization)
TOMORROW_KEYWORDS = {"听日", "听朝", "听晚", "听日中午"}
DAY_AFTER_TMR_KEYWORDS = {"后日",  "后朝", "后晚", "后日中午"}
TWO_DAYS_AFTER_TMR_KEYWORDS = {"大后日", "大后朝", "大后晚", "大后日中午"}
TODAY_KEYWORDS = {"而家", "现在", "今日", "今天", "今朝", "今晚"}

# Assume these are defined elsewhere
WEEK_PATTERNS = {
    (r"(今)?星期([一二三四五六日天])", 0),
    (r"(下)?星期([一二三四五六日天])", 1),
    (r"(上)?星期([一二三四五六日天])", -1)
}

WEEKDAY_MAP = {
    "一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5,
    "日": 6, "天": 6
}


def normalize_text(text: str) -> str:
    for trad, simp in TRAD_TO_SIMP_REPLACEMENTS.items():
        text = text.replace(trad, simp)
    return text

# Extract time if mentioned


def extract_time(text: str):
    hour, minute = 12, 0  # default noon

    if "早" in text or "朝" in text or "上昼" in text:
        hour = 9
    elif "午" in text or "下昼" in text:
        hour = 14
    elif "晚" in text:
        hour = 20

    # Find time like 7點, 8點半, 9:15
    match = re.search(r'(?P<hour>\d{1,2})(點|:)(?P<minute>\d{1,2})?', text)
    if match:
        hour = int(match.group("hour"))
        minute = int(match.group("minute")) if match.group("minute") else 0

    return hour, minute


def contains_date_keywords(text: str) -> bool:
    text = normalize_text(text)

    all_keywords = (
        TOMORROW_KEYWORDS |
        DAY_AFTER_TMR_KEYWORDS |
        TWO_DAYS_AFTER_TMR_KEYWORDS |
        TODAY_KEYWORDS
    )

    contains_date_kw = any(kw in text for kw in all_keywords)
    contains_week_pattern = any(re.search(pattern, text)
                                for pattern in WEEK_PATTERNS)

    result = contains_date_kw or contains_week_pattern
    print(f"[DEBUG] Contain any date keywards?: {result}")
    return result


def calculate_cantonese_date(text: str, base_date: datetime = None) -> datetime:
    if not contains_date_keywords(text):
        # No date keywords found
        return None

    if base_date is None:
        base_date = datetime.now()

    hour, minute = extract_time(text)

    # Group 1: relative dates
    if any(kw in text for kw in TOMORROW_KEYWORDS):
        return (base_date + timedelta(days=1)).replace(hour=hour, minute=minute)
    elif any(kw in text for kw in DAY_AFTER_TMR_KEYWORDS):
        return (base_date + timedelta(days=2)).replace(hour=hour, minute=minute)
    elif any(kw in text for kw in TWO_DAYS_AFTER_TMR_KEYWORDS):
        return (base_date + timedelta(days=3)).replace(hour=hour, minute=minute)
    elif any(kw in text for kw in TODAY_KEYWORDS):
        return base_date.replace(hour=hour, minute=minute)

    for pattern, week_offset in WEEK_PATTERNS:
        match = re.search(pattern, text)
        if match:
            _, day_char = match.groups()
            target_weekday = WEEKDAY_MAP.get(day_char)
            if target_weekday is None:
                continue

            start_of_week = base_date - timedelta(days=base_date.weekday())
            target_date = start_of_week + \
                timedelta(days=target_weekday, weeks=week_offset)
            return target_date.replace(hour=hour, minute=minute)

    return None


def extract_info_withLLM(text: str) -> MemoryItem:
    try:
        client = get_hunyuan_client()

        # Deterministic datetime
        detected_date = calculate_cantonese_date(text)
        print(f"[DEBUG] text pasted in extract_info_withLLM: {text}")
        # Format date as ISO string if available
        date_str = detected_date.strftime(
            "%Y-%m-%dT%H:%M") if detected_date else ""
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
            userId=None,
            reflection=None
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
            tags=[f"Error: {str(e)}"] if not isinstance(
                e, json.JSONDecodeError) else [],
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
    print(
        f"Calculated date: {calculated.strftime('%Y-%m-%d %H:%M') if calculated else 'None'}")

    result = extract_info_withLLM(test_text)
    print(f"Extracted Date: {result.reminderDatetime}")
    print(f"Main Event: {result.mainEvent}")


def generate_reflection(text: str) -> str:
    try:
        client = get_hunyuan_client()

        detected_date = calculate_cantonese_date(text)

        system_prompt = (
            "你是一個有禮貌、友善的粵語AI助理，用戶會以語音說出他想記低嘅嘢，"
            "如果用戶問咗一個關於日期嘅問題，而系統已經幫佢計算咗準確嘅日期，你就要根據呢個日期回覆，（例如：「下星期四係8月7號」）,回复的内容不需要加入其他东西，"
            "唔好再自己計算。"
            "如果用戶係閒聊 → 可以輕鬆地做簡短反思或建議。"
            "你要用親切、溫柔嘅語氣幫佢回覆一句粵語句子，好似係一個人同佢傾偈咁。"
        )

        user_message = f"用戶話：「{text}」"
        if detected_date:
            date_str = detected_date.strftime("%Y年%m月%d號")
            print(f"[DEBUG] Detected date: {date_str}")
            user_message += f"\n系統幫佢計算咗日期，係：{date_str}"

        # Create Message objects and assign attributes
        system_msg = models.Message()
        system_msg.Role = "system"
        system_msg.Content = system_prompt

        user_msg = models.Message()
        user_msg.Role = "user"
        user_msg.Content = user_message

        messages = [system_msg, user_msg]

        req = models.ChatCompletionsRequest()
        req.Model = "hunyuan-standard"
        req.Temperature = 1
        req.Messages = messages

        resp = client.ChatCompletions(req)

        if resp.Choices and resp.Choices[0].Message:
            reflection = resp.Choices[0].Message.Content.strip()
        else:
            raise ValueError("No response from model")

        print(f"[INFO] Reflection: {reflection}")
        return reflection

    except Exception as e:
        print(f"[ERROR] Reflection failed: {e}")
        return "我記低咗你講嘅內容啦，有需要可以再問我！"
