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


from datetime import datetime, timedelta
import re
import json
from typing import Optional

# Assuming these are your imports (replace with actual imports)
from your_models import MemoryItem  # Your memory item model
from your_client import get_hunyuan_client, models  # Your LLM client

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
        target_weekday = {
            '一': 1, '二': 2, '三': 3, '四': 4,
            '五': 5, '六': 6, '日': 7, '天': 7
        }.get(weekday_match.group(2), 1)
        
        days_until = (target_weekday - base_date.isoweekday()) % 7
        if days_until == 0 and weeks_ahead == 0:
            days_until = 7  # Move to next week if same day
        total_days = days_until + (7 * weeks_ahead)
        target_date = base_date + timedelta(days=total_days)
    
    # Time calculation
    if "中午" in text or "晏昼" in text or "下午" in text:
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
        hour, minute = 12, 0  # Default to noon for 中午
    
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
           - "今个[weekday]" = This week's weekday
           - "下个[weekday]" = Next week's weekday
           - "中午" = 12:00
           - "晏昼" = 14:00
           - Exact times (e.g. 两点) → use as-is
        
        2. Required Fields:
           - "reminderDatetime": ISO format or ""
           - "mainEvent": Short summary
           - "category": [General, Family, Health, Shopping, Reminder, Question]
           - "location": List of places
           - "isReminder": true if contains 提我/提醒我
           - "isQuery": true if asking something
           - "tags": Relevant keywords
        
        Example Output:
        {{
            "category": "Health",
            "mainEvent": "中午要食药",
            "reminderDatetime": "2025-07-23T12:00",
            "location": [],
            "isReminder": true,
            "isQuery": false,
            "tags": ["药物"]
        }}
        """

        req = models.ChatCompletionsRequest()
        req.Messages = [{"Role": "user", "Content": prompt}]
        req.Model = "hunyuan-standard"
        req.Temperature = 0.7

        resp = client.ChatCompletions(req)
        data = json.loads(resp.Choices[0].Message.Content.strip())

        # Ensure required fields exist
        if "mainEvent" not in data:
            data["mainEvent"] = text.split('。')[0]  # Fallback to first sentence
        
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
            mainEvent=text.split('。')[0],  # Fallback to first sentence
            reminderDatetime="",
            isReminder=False,
            isQuery=False,
            location=[],
            originalVoice_Url=None,
            sourceLang='yue-HK',
            userId=None
        )

# Test Case for the specific error
if __name__ == "__main__":
    # Test with the problematic input
    test_text = "提醒我呢个星期三中午要食药。"
    print(f"Testing: {test_text}")
    
    # Verify date calculation
    test_date = datetime(2025, 7, 21)  # Monday July 21
    calculated_date = calculate_cantonese_date(test_text, test_date)
    print(f"Calculated date: {calculated_date.strftime('%Y-%m-%d %H:%M') if calculated_date else 'None'}")
    assert calculated_date.strftime("%Y-%m-%d %H:%M") == "2025-07-23 12:00", "Date calculation failed"
    
    # Full integration test
    memory_item = extract_info_withLLM(test_text)
    print(f"Extracted reminderDatetime: {memory_item.reminderDatetime}")
    print(f"Main event: {memory_item.mainEvent}")
    assert "2025-07-23T12:00" in memory_item.reminderDatetime
    assert "食药" in memory_item.mainEvent
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
