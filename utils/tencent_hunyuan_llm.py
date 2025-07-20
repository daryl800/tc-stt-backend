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
def calculate_next_occurrence(weekday_chinese):
    # Convert Chinese weekday to number and calculate next occurrence
    pass

def calculate_this_week(weekday_chinese):
    # Calculate date for this week's occurrence
    pass
    
def extract_info_withLLM(text):
    """
    Final optimized version with:
    - Proper client initialization
    - LLM-native date handling
    - Robust error handling
    """
    try:
        # Initialize client (thread-safe)
        client = get_hunyuan_client()
        
        prompt = f"""
        [Current Date] {datetime.now().strftime("%Y-%m-%d (%A)")}

        Extract from Cantonese:
        "{text}"

        Please output ONLY a JSON object with the following fields:
        - "category": Classify the memory into one of these categories: [General, Family, Health, Shopping, Reminder, Question]
        - "mainEvent": Short action/plan summary (omit reminder words)
        - "reminderDatetime": in strict ISO 8601 format: "YYYY-MM-DDTHH:MM" (e.g., "2025-06-12T14:00") or empty string ("") if unclear.
        - "location": List of places mentioned (e.g., 香港, 瑞典)
        - "isReminder": true if it includes 提我/提醒我
        - "isQuery": true if the sentence asks about something, even indirectly (see below)
        - "tags": List of keywords including:
            - Locations (e.g., 香港)
            - People/entities (e.g., 我個仔, 屋企人)
            - Important nouns or time expressions (e.g., 出年, 暑假, 去旅行)
        - "Question": Answer the question correctly

        Time Handling Rules (IMPORTANT UPDATES):
        1. Weekday references (星期一/二/三/四/五/六/日):
        - 「今個[weekday]」/「呢個[weekday]」 = This week's [weekday]
        - 「下個[weekday]」/「下[weekday]」 = Next week's [weekday] (7 days after this week's)
        - 「[weekday]」 (no modifier) = The next occurring [weekday] from today
            - If today is Tuesday and text says "星期三" → Tomorrow
            - If today is Friday and text says "星期三" → 5 days from now
        - 「下下個[weekday]」 = [weekday] in two weeks

        2. Calculation Algorithm:
        For any weekday reference:
        1. Find today's weekday number (Monday=1 to Sunday=7)
        2. Find target weekday number from text
        3. Calculate days_to_add:
            - If target > current: days_to_add = target - current
            - If target <= current: days_to_add = 7 - (current - target)
        4. Apply modifiers:
            - "下個" → Add 7 more days
            - "下下個" → Add 14 more days
        5. NEVER return dates in the past

        3. Examples (Today: {datetime.now().strftime('%Y-%m-%d (%A)')}):
        - "星期三" → {calculate_next_occurrence('星期三')}
        - "下個星期五" → {calculate_next_occurrence('星期五') + timedelta(days=7)}
        - "下下個星期一" → {calculate_next_occurrence('星期一') + timedelta(days=14)}
        - "今個星期日" → {calculate_this_week('星期日')}

        4. Special Cases:
        - "聽日" = tomorrow at 09:00
        - "後日" = 2 days from now at 09:00
        - "大後日" = 3 days from now at 09:00
        - "禮拜日" = same as "星期日"
        - "禮拜三" = same as "星期三"
    
        5. Explicit time handling:
        - Exact times (e.g., "下午三點") → Convert to 24-hour format ("15:00")
        - Vague times (e.g., "聽日") → Use default time
        - Very vague (e.g., "遲啲") → Empty string

        [Other rules remain the same...]

        [OUTPUT FORMAT]
        {{
        "category": "General",
        "mainEvent": "事件描述",
        "reminderDatetime": "YYYY-MM-DDTHH:MM or empty",
        "location": ["地點"],
        "isReminder": true/false,
        "isQuery": true/false,
        "tags": ["香港", "我個仔", "出年", "旅行"],
        "Question": ""
        }}
        """

        req = models.ChatCompletionsRequest()
        req.Messages = [{"Role": "user", "Content": prompt}]
        req.Model = "hunyuan-standard"
        req.Temperature = 0.7

        resp = client.ChatCompletions(req)
        data = json.loads(resp.Choices[0].Message.Content.strip())

        print(f"[INFO] data: {data}")

        memoryItem = MemoryItem(
            category=data.get("category", "General"),
            transcription=text,
            mainEvent=data.get("mainEvent", ""),
            reminderDatetime=data.get("reminderDatetime", ""),
            isReminder=data.get("isReminder", False),
            isQuery=data.get("isQuery", False),
            location=list(set(data.get("location", []))),   
            tags=list(set(data.get("tags", []))),  # Ensure tags are unique
            eventCreatedAt=datetime.now()
        )

        print(f"[INFO] memoryItem: {memoryItem}")
        
        return memoryItem

    except Exception as e:
        print(f"[ERROR] Exception during LLM extraction: {e}")
        tags = [] if isinstance(e, json.JSONDecodeError) else [f"Error: {str(e)}"]
        return MemoryItem(
            eventCreatedAt=datetime.now(),
            transcription=text,
            mainEvent="",
            reminderDatetime="",
            location=[],
            isReminder=False,
            isQuery=False,
            category="General",
            tags=tags
        )


# Example test
if __name__ == "__main__":
    result = extract_info_withLLM("星期三提醒我睇无线电视新闻")
    print(result.json(indent=4))
# Example test
if __name__ == "__main__":
    print(extract_info_withLLM("星期三提醒我睇无线电视新闻"))


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
