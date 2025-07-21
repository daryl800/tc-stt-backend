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

# Your MemoryItem model placeholder
from models import MemoryItem, get_hunyuan_client, models  # Modify imports as needed

def calculate_cantonese_date(text: str, base_date: datetime = None) -> Optional[datetime]:
    """
    Calculates a datetime from Cantonese expressions with time handling.
    Returns a datetime object or None.
    """
    base_date = base_date or datetime.now()
    text = text.replace("礼拜", "星期").replace("聽日", "听日")

    # Determine week shift
    if "下下个" in text or "下下個" in text:
        weeks_ahead = 2
        clean_day = text.replace("下下个", "").replace("下下個", "")
    elif "下个" in text or "下個" in text:
        weeks_ahead = 1
        clean_day = text.replace("下个", "").replace("下個", "")
    else:
        weeks_ahead = 0
        clean_day = text

    clean_day = clean_day.replace("下", "").strip()

    # Check weekday
    weekday_match = re.search(r'(星期|禮拜)([一二三四五六七日天])', clean_day)
    if not weekday_match:
        if "听日" in text:
            target_date = base_date + timedelta(days=1)
        elif "後日" in text:
            target_date = base_date + timedelta(days=2)
        elif "大後日" in text:
            target_date = base_date + timedelta(days=3)
        else:
            return None
    else:
        target_weekday = {
            '一': 1, '二': 2, '三': 3, '四': 4,
            '五': 5, '六': 6, '日': 7, '天': 7
        }.get(weekday_match.group(2), 1)

        days_until = (target_weekday - base_date.isoweekday()) % 7
        if days_until == 0 and weeks_ahead == 0:
            days_until = 7  # Move to next week if same day
        total_days = days_until + (7 * weeks_ahead)
        target_date = base_date + timedelta(days=total_days)

    # Time parsing
    hour, minute = 12, 0  # Default noon
    if any(t in text for t in ["中午", "晏昼", "下午"]):
        time_match = re.search(r'(\d+)(点|點)(半)?', text)
        if time_match:
            hour = int(time_match.group(1))
            if hour < 12:
                hour += 12
            if time_match.group(3):
                minute = 30
        else:
            hour = 14
    elif any(t in text for t in ["朝早", "上午"]):
        time_match = re.search(r'(\d+)(点|點)(半)?', text)
        hour = int(time_match.group(1)) if time_match else 9
        if time_match and time_match.group(3):
            minute = 30
    elif any(t in text for t in ["晚上", "夜晚"]):
        time_match = re.search(r'(\d+)(点|點)(半)?', text)
        hour = int(time_match.group(1)) if time_match else 20
        if time_match and time_match.group(3):
            minute = 30
    elif re.search(r'(\d+)(点|點)(半)?', text):
        time_match = re.search(r'(\d+)(点|點)(半)?', text)
        hour = int(time_match.group(1))
        if "下午" in text and hour < 12:
            hour += 12
        if time_match.group(3):
            minute = 30

    return target_date.replace(hour=hour, minute=minute)


def extract_info_withLLM(text: str) -> MemoryItem:
    try:
        # Deterministic datetime
        detected_date = calculate_cantonese_date(text)
        date_str = detected_date.strftime("%Y-%m-%dT%H:%M") if detected_date else ""

        client = get_hunyuan_client()

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
        final_date = date_str if date_str else data.get("reminderDatetime", "")

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


def generate_reflection(text: str) -> str:
    """
    Generate a 20–30 second natural-sounding reflection or follow-up
    based on what the user just said. The tone is friendly, supportive,
    and memory-oriented. It also adds light特色資訊 to enhance usefulness.
    """
    try:
        client = get_hunyuan_client()

        prompt = f"""
        你係一個有記憶力、貼心、識講廣東話的助理。根據使用者啱啱講嘅內容，用大約20–30秒嘅自然語氣回應一段說話，語氣要自然、口語化、親切，可以加入：

        - 重點整理（幫佢重溫重點）
        - 適量反應（如關心、認同、幽默）
        - 有用的生活建議或提醒（如果適用）
        - 不需要加入如：“有冇記錯，你之前話起過”，这类字眼
        - 如果提到地點，請自然地提及當地一個具代表性或最受歡迎的景點或活動，建議只提一個，唔好列舉，要自然地融合入句子，好似朋友咁分享。

        使用者啱啱講咗：
        「{text}」

        請用純廣東話寫一段自然口語說話，唔好加任何解釋或格式，只要一句完整自然說話即可。
        """   

        req = models.ChatCompletionsRequest()
        req.Messages = [{"Role": "user", "Content": prompt}]
        req.Model = "hunyuan-turbos-latest"
        req.Temperature = 1

        resp = client.ChatCompletions(req)
        reflection = resp.Choices[0].Message.Content.strip()

        print(f"[INFO] Reflection: {reflection}")
        return reflection

    except Exception as e:
        print(f"[ERROR] Reflection failed: {e}")
        return "我記低咗你講嘅內容啦，有需要可以再問我！"
