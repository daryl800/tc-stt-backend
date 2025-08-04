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
            http_profile = HttpProfile(
                endpoint="hunyuan.ap-hongkong.tencentcloudapi.com")
            client_profile = ClientProfile(httpProfile=http_profile)
            _hunyuan_client = hunyuan_client.HunyuanClient(
                cred, "ap-hongkong", client_profile)
        except Exception as e:
            print(f"初始化混元客户端失败: {e}")
            raise  # 或返回 None，根据业务需求处理
    return _hunyuan_client

# You would need to implement these helper functions:


# Date Calculation Helpers

WEEKDAY_MAP = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
WEEK_PATTERNS = {
    r'(下下星期)([一二三四五六日天])': 2,
    r'(下星期)([一二三四五六日天])': 1,
    r'(星期)([一二三四五六日天])': 0,
}


def get_date_of_next_weekday(target_weekday: int, base_date: datetime) -> datetime:
    base_weekday = base_date.weekday()
    days_until_next = (target_weekday - base_weekday + 7) % 7
    days_until_next = days_until_next or 7  # ensure next occurrence, not today
    return base_date + timedelta(days=days_until_next)


def calculate_cantonese_date(text: str, base_date: datetime = None) -> Optional[datetime]:
    base_date = base_date or datetime.now()

    # 🔄 Normalize input
    text = (
        text.replace("礼拜", "星期")
            .replace("禮拜", "星期")
            .replace("个", "")
            .replace("個", "")
            .replace("聽日", "听日")
    )

    # Handle relative expressions
    if "聽日" in text or "明日" in text or "聽晚" in text or "明晚" in text or "聽朝" in text or "明朝" in text:
        return (base_date + timedelta(days=1)).replace(hour=12, minute=0)
    elif "後日" in text or "后日" in text:
        return (base_date + timedelta(days=2)).replace(hour=12, minute=0)
    elif "大後日" in text:
        return (base_date + timedelta(days=3)).replace(hour=12, minute=0)
    elif "今日" in text or "而家" in text:
        return base_date.replace(hour=12, minute=0)

    # Match and parse weekday expressions
    for pattern, week_offset in WEEK_PATTERNS.items():
        match = re.search(pattern, text)
        if match:
            prefix, day_char = match.groups()
            target_weekday = WEEKDAY_MAP.get(day_char)
            if target_weekday is None:
                continue

            # Calculate target date
            start_of_week = base_date - timedelta(days=base_date.weekday())
            target_date = start_of_week + \
                timedelta(days=target_weekday, weeks=week_offset)

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
