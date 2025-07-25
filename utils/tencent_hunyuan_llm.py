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

def calculate_cantonese_date(text: str, base_date: datetime = None) -> Optional[datetime]:
    """
    Correctly calculates dates from Cantonese expressions.
    Handles "下個星期一" as next week's Monday (not current week),
    and "下下個星期一" as the week after next.
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

    # Handle weekdays with or without prefix
    weekday_map = {'一': 1, '二': 2, '三': 3, '四': 4,
                   '五': 5, '六': 6, '日': 7, '天': 7}
    weekday_full_match = re.search(r'(下下個|下下个|下個|下个)?(?:星期|禮拜)([一二三四五六七日天])', text)
    if weekday_full_match:
        prefix = weekday_full_match.group(1) or ''
        weekday_char = weekday_full_match.group(2)
        target_weekday = weekday_map[weekday_char]
        base_weekday = base_date.isoweekday()

        delta = (target_weekday - base_weekday) % 7
        if prefix in ['下下個', '下下个']:
            days_until = delta + 14 if delta != 0 else 14
        elif prefix in ['下個', '下个']:
            days_until = delta + 7 if delta != 0 else 7
        else:
            days_until = delta  # this or upcoming weekday

        target_date = base_date + timedelta(days=days_until)
        print(f"[DEBUG] Calculated weekday: {target_date.date()} from text: {text}")

        # Time handling
        hour, minute = 12, 0  # Default noon
        if "朝早" in text or "上午" in text:
            hour = 9
        elif "晏昼" in text or "下午" in text:
            hour = 14
        elif "夜晚" in text or "晚上" in text:
            hour = 20

        # Handle specific times like "三点半"
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

        # Calculate the date from Cantonese text (your own precise logic)
        detected_date: Optional[datetime] = calculate_cantonese_date(text)
        if detected_date:
            detected_date_str = detected_date.strftime("%Y年%-m月%-d日（%A）")
        else:
            detected_date_str = "未知日期"

        # Current date in natural format
        current_date_str = datetime.now().strftime("%Y年%-m月%-d日（%A）")

        # Build prompt including exact date — instruct LLM NOT to change it!
        prompt = f"""
            [Current Date] {current_date_str}
            [Detected Date] {detected_date_str}

            **日期處理規則**  
            - 嚴格使用[Detected Date]作答，禁止修改或重新計算日期
            - 日期格式：「YYYY年M月D日（星期X）」
            - 例如：「2025年7月28日（星期一）」

            你係一個有記憶力、貼心、識講廣東話嘅助理。
            請根據以下規則回應：

            1. 如果用戶問日期、時間、地點等問題 → 直接用 [Detected Date] 作答，簡潔準確，唔好加反思。
            2. 如果用戶只是分享閒聊 → 用20–30秒親切自然嘅語氣回應，可以加重點整理、關心、幽默同小建議。
            3. 回答時絕對唔可以改變、增加或減少[Detected Date]嘅日期。
            
            用戶剛剛講咗：
            「{text}」

            請用純廣東話寫一句自然流暢嘅說話，唔好加任何解釋或格式。
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
