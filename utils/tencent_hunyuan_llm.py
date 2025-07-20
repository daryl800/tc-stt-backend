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
from datetime import datetime, timedelta
from datetime import datetime, timedelta
from typing import Optional
import re
import json


from datetime import datetime, timedelta
import re
import json
from typing import Optional



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

def calculate_cantonese_date(text: str, base_date: datetime = None) -> Optional[datetime]:
    """
    Correctly calculates dates from Cantonese expressions with precise time handling
    Returns: datetime object with proper date and time
    """
    base_date = base_date or datetime.now()
    
    # Normalize input
    text = text.replace("礼拜", "星期").replace("聽日", "听日")
    
    # Date calculation
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
    
    # Find weekday if present
    weekday_match = re.search(r'(星期|禮拜)([一二三四五六七日天])', clean_day)
    if not weekday_match:
        # Handle relative days without weekday
        if "听日" in text:
            target_date = base_date + timedelta(days=1)
        elif "後日" in text:
            target_date = base_date + timedelta(days=2)
        elif "大後日" in text:
            target_date = base_date + timedelta(days=3)
        else:
            return None
    else:
        target_weekday = weekday_chinese_to_number(weekday_match.group(2))
        days_until = (target_weekday - base_date.isoweekday()) % 7
        if days_until == 0 and weeks_ahead == 0:
            days_until = 7  # Move to next week if same day
        total_days = days_until + (7 * weeks_ahead)
        target_date = base_date + timedelta(days=total_days)
    
    # Time calculation
    if "晏昼" in text or "下午" in text:
        time_match = re.search(r'(\d+)点', text)
        hour = int(time_match.group(1)) + 12 if time_match and int(time_match.group(1)) < 12 else 14
        minute = 0
    elif "朝早" in text or "上午" in text:
        time_match = re.search(r'(\d+)点', text)
        hour = int(time_match.group(1)) if time_match else 9
        minute = 0
    elif "夜晚" in text or "晚上" in text:
        time_match = re.search(r'(\d+)点', text)
        hour = int(time_match.group(1)) if time_match else 20
        minute = 0
    elif any(str(i)+"点" in text for i in range(1,13)):
        time_match = re.search(r'(\d+)点', text)
        hour = int(time_match.group(1))
        if "下午" in text and hour < 12:
            hour += 12
        minute = 0
    else:
        # Default time
        hour, minute = 9, 0
    
    return target_date.replace(hour=hour, minute=minute)

def extract_info_withLLM(text: str) -> MemoryItem:
    try:
        # First get deterministic date
        detected_date = calculate_cantonese_date(text)
        date_str = detected_date.strftime("%Y-%m-%dT%H:%M") if detected_date else ""
        
        client = get_hunyuan_client()
        
        prompt = f"""
        [Current Date] {datetime.now().strftime("%Y-%m-%d (%A)")}
        [Detected Date] {date_str if date_str else "None"}
        
        Extract from Cantonese:
        "{text}"
        
        Rules:
        1. Date/Time Handling:
           - "下个[weekday]" = Next week's weekday
           - Time defaults:
             - 上午/朝早 → 09:00
             - 下午/晏昼 → 14:00
             - 晚上/夜晚 → 20:00
             - Exact times (e.g. 两点) → use as-is
        
        2. Output MUST include:
           - "reminderDatetime": ISO format or ""
           - "category": [General, Family, Health, Shopping, Reminder, Question]
           - "mainEvent": Short summary
           - "location": List of places
           - "isReminder": true if contains 提我/提醒我
           - "isQuery": true if asking something
           - "tags": Relevant keywords
           - "Question": Direct answer if question
        
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

        # Ensure date consistency
        final_date = data.get("reminderDatetime", date_str if date_str else "")
        
        return MemoryItem(
            category=data.get("category", "General"),
            transcription=text,
            mainEvent=data.get("mainEvent", ""),
            reminderDatetime=final_date,
            isReminder=data.get("isReminder", False),
            isQuery=data.get("isQuery", False),
            location=list(set(data.get("location", []))),
            tags=list(set(data.get("tags", []))),
            eventCreatedAt=datetime.now(),
            originalVoice_Url=None,
            sourceLang='yue-HK',
            userId=None
        )

    except Exception as e:
        print(f"[ERROR] LLM extraction failed: {e}")
        return MemoryItem(
            eventCreatedAt=datetime.now(),
            transcription=text,
            category="General",
            tags=[f"Error: {str(e)}"] if not isinstance(e, json.JSONDecodeError) else [],
            mainEvent="",
            reminderDatetime="",
            isReminder=False,
            isQuery=False,
            location=[],
            originalVoice_Url=None,
            sourceLang='yue-HK',
            userId=None
        )

# Test Cases
if __name__ == "__main__":
    # Verification Tests
    test_date = datetime(2025, 7, 21)  # Monday July 21
    test_cases = [
        ("提醒我下个星期五要食药", "2025-08-01T09:00"),
        ("下个星期四晏昼两点钟开会", "2025-07-31T14:00"),
        ("後日上午十点体检", "2025-07-23T10:00"),
        ("听日下午三点见", "2025-07-22T15:00")
    ]
    
    for text, expected in test_cases:
        print(f"\nTesting: {text}")
        result = calculate_cantonese_date(text, test_date)
        formatted = result.strftime("%Y-%m-%dT%H:%M") if result else "None"
        print(f"Calculated: {formatted} | Expected: {expected}")
        if expected != "None":
            assert formatted == expected, f"Test failed for: {text}"
    
    # Full integration test
    test_text = "提醒我下个星期五下午三点要食药"
    print(f"\nFull test for: {test_text}")
    memory_item = extract_info_withLLM(test_text)
    print(f"Result: {memory_item.reminderDatetime} | {memory_item.mainEvent}")
    assert "2025-08-01T15:00" in memory_item.reminderDatetime

# Main Extraction Function
def extract_info_withLLM(text: str) -> MemoryItem:
    try:
        # First try deterministic date extraction
        detected_date = detect_date_from_text(text)
        date_str = detected_date.strftime("%Y-%m-%dT%H:%M") if detected_date else ""
        
        client = get_hunyuan_client()
        
        prompt = f"""
        [Current Date] {datetime.now().strftime("%Y-%m-%d (%A)")}
        [Detected Date] {date_str if date_str else "None"}
        
        Extract from Cantonese:
        "{text}"
        
        Rules:
        1. DATE MUST BE IN ISO FORMAT: YYYY-MM-DDTHH:MM
        2. Use this date if detected: {date_str}
        3. Time defaults:
           - Morning/上午 → 09:00
           - Afternoon/下午 → 14:00
           - Evening/晚上 → 20:00
           - No time specified → 09:00
        
        Calculation Examples (Today: {datetime.now().strftime('%Y-%m-%d')}):
        - "下个星期六" → {calculate_next_weekday("下个星期六").strftime('%Y-%m-%dT%H:%M')}
        - "今个星期三" → {calculate_next_weekday("星期三").strftime('%Y-%m-%dT%H:%M')}
        - "听日" → {(datetime.now() + timedelta(days=1)).replace(hour=9, minute=0).strftime('%Y-%m-%dT%H:%M')}
        
        Output JSON with:
        - "reminderDatetime": ISO format or ""
        - "mainEvent": Short summary
        - "category": [General, Family, Health, Shopping, Reminder, Question]
        - "location": List of places
        - "isReminder": true if contains 提我/提醒我
        - "isQuery": true if asking something
        - "tags": Relevant keywords
        - "Question": Direct answer if question
        
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

        # Ensure date consistency
        final_date = data.get("reminderDatetime", date_str if date_str else "")
        
        return MemoryItem(
            category=data.get("category", "General"),
            transcription=text,
            mainEvent=data.get("mainEvent", ""),
            reminderDatetime=final_date,
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
    # Verification Tests
    test_date = datetime(2025, 7, 21)  # Monday July 21, 2025
    assert calculate_next_weekday("星期六", test_date).strftime("%Y-%m-%d") == "2025-07-26"
    assert calculate_next_weekday("下个星期六", test_date).strftime("%Y-%m-%d") == "2025-08-02"
    assert calculate_next_weekday("下下个星期六", test_date).strftime("%Y-%m-%d") == "2025-08-09"
    print("All date calculation tests passed!")
    
    # Integration Tests
    test_cases = [
        ("提醒我呢个星期六Nora会去中山", "2025-07-26"),
        ("记住提我下个星期六Nora会翻落香港", "2025-08-02"),
        ("下下个星期六开会", "2025-08-09"),
        ("听日下午三点开会", ""),  # Exact time should be preserved
        ("後日早上十点体检", "")
    ]
    
    for text, expected_date in test_cases:
        print(f"\nTesting: {text}")
        result = extract_info_withLLM(text)
        if expected_date:
            assert expected_date in result.reminderDatetime
        print(f"Result: {result.reminderDatetime} | {result.mainEvent}")

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
