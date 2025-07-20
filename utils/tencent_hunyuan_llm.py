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
from datetime import datetime, timedelta
import json
from typing import Optional

# Date Calculation Helpers
from datetime import datetime, timedelta

# Date Calculation Helpers (single definition)
def weekday_chinese_to_number(day: str) -> int:
    """Convert Chinese weekday to number (Monday=1)"""
    mapping = {
        '一': 1, '二': 2, '三': 3, '四': 4,
        '五': 5, '六': 6, '日': 7, '天': 7,
        '礼拜一': 1, '礼拜二': 2, '礼拜三': 3, '礼拜四': 4,
        '礼拜五': 5, '礼拜六': 6, '礼拜日': 7, '礼拜天': 7
    }
    for key, val in mapping.items():
        if key in day:
            return val
    return 1  # Default to Monday if not found

from datetime import datetime, timedelta

def calculate_next_weekday(day_chinese: str, base_date: Optional[datetime] = None) -> datetime:
    """
    Correctly calculates Chinese weekday references
    - "星期六" = Next Saturday (could be this week)
    - "下个星期六" = Saturday next week
    - "下下个星期六" = Saturday in two weeks
    """
    base_date = base_date or datetime.now()
    
    # Extract week modifiers
    if "下下个" in day_chinese or "下下個" in day_chinese:
        weeks_ahead = 2
        clean_day = day_chinese.replace("下下个", "").replace("下下個", "")
    elif "下个" in day_chinese or "下個" in day_chinese:
        weeks_ahead = 1
        clean_day = day_chinese.replace("下个", "").replace("下個", "")
    else:
        weeks_ahead = 0
        clean_day = day_chinese
    
    clean_day = clean_day.replace("下", "").strip()
    
    # Calculate target weekday (1=Monday, 7=Sunday)
    target_weekday = {
        '一': 1, '二': 2, '三': 3, '四': 4,
        '五': 5, '六': 6, '日': 7, '天': 7
    }.get(clean_day[-1], 6)  # Default to Saturday if unknown
    
    # Calculate days until target
    days_until = (target_weekday - base_date.isoweekday()) % 7
    if days_until == 0 and weeks_ahead == 0:
        days_until = 7  # Move to next week if same day
    
    total_days = days_until + (7 * weeks_ahead)
    return (base_date + timedelta(days=total_days)).replace(hour=9, minute=0)

# Test Cases
def test_calculations():
    test_date = datetime(2025, 7, 21)  # Monday July 21
    assert calculate_next_weekday("星期六", test_date).strftime("%Y-%m-%d") == "2025-07-26"
    assert calculate_next_weekday("下个星期六", test_date).strftime("%Y-%m-%d") == "2025-08-02"
    assert calculate_next_weekday("下下个星期六", test_date).strftime("%Y-%m-%d") == "2025-08-09"
    print("All tests passed!")

test_calculations()

def generate_time_examples() -> str:
    """Generate accurate calculation examples for the prompt"""
    now = datetime.now()
    examples = [
        f'"星期三" → {calculate_next_weekday("星期三").strftime("%Y-%m-%dT%H:%M")}',
        f'"下個星期四" → {calculate_next_weekday("下個星期四").strftime("%Y-%m-%dT%H:%M")}',
        f'"聽日" → {(now + timedelta(days=1)).replace(hour=9, minute=0).strftime("%Y-%m-%dT%H:%M")}'
    ]
    return "\n   - ".join(examples)

# Main Extraction Function
def extract_info_withLLM(text: str) -> MemoryItem:
    try:
        client = get_hunyuan_client()
        
        prompt = f"""
        [Current Date] {datetime.now().strftime("%Y-%m-%d (%A)")}
        [Example Calculations]:
           - {generate_time_examples()}

        Extract from Cantonese:
        "{text}"

        Rules:
        - "下個[weekday]" = next week's weekday
        - "下下個[weekday]" = weekday in two weeks
        - "[weekday]" = next occurrence

        Output JSON with:
        - "reminderDatetime": ISO format or ""
        - "mainEvent": Short summary
        - "category": [General, Family, Health, Shopping, Reminder, Question]
        - "mainEvent": Short summary
        - "reminderDatetime": ISO 8601 or ""
        - "location": List of places
        - "isReminder": true if contains 提我/提醒我
        - "isQuery": true if asking something
        - "tags": Relevant keywords
        - "Question": Direct answer if question

        Time Handling Rules:
        1. Weekday references:
           - 「今個[weekday]」/「呢個[weekday]」 = This week
           - 「下個[weekday]」 = Next week (+7 days)
           - 「[weekday]」 = Next occurrence
        2. Special cases:
           - 聽日/後日 = tomorrow/day after at 09:00
           - 禮拜X = same as X

        [OUTPUT FORMAT]
        {{
            "category": "General",
            "mainEvent": "事件描述",
            "reminderDatetime": "YYYY-MM-DDTHH:MM" or "",
            "location": ["地點"],
            "isReminder": true/false,
            "isQuery": true/false,
            "tags": ["關鍵詞"],
            "Question": ""
        }}
        """

        req = models.ChatCompletionsRequest()
        req.Messages = [{"Role": "user", "Content": prompt}]
        req.Model = "hunyuan-standard"
        req.Temperature = 0.7

        resp = client.ChatCompletions(req)
        data = json.loads(resp.Choices[0].Message.Content.strip())

        return MemoryItem(
            category=data.get("category", "General"),
            transcription=text,
            mainEvent=data.get("mainEvent", ""),
            reminderDatetime=data.get("reminderDatetime", ""),
            isReminder=data.get("isReminder", False),
            isQuery=data.get("isQuery", False),
            location=list(set(data.get("location", []))),
            tags=list(set(data.get("tags", []))),
            eventCreatedAt=datetime.now()
        )

    except Exception as e:
        print(f"[ERROR] LLM extraction failed: {e}")
        return MemoryItem(
            eventCreatedAt=datetime.now(),
            transcription=text,
            category="General",
            tags=[f"Error: {str(e)}"] if not isinstance(e, json.JSONDecodeError) else []
        )

# Test Cases
if __name__ == "__main__":
    test_cases = [
        "提醒我下個星期二去醫院覆診",
        "今個星期四約牙醫洗牙",
        "記住聽日交電費",
        "我係唔係已經約咗下個月驗身？"
    ]
    
    for text in test_cases:
        print(f"\nInput: {text}")
        result = extract_info_withLLM(text)
        print(f"Result: {result}")

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
