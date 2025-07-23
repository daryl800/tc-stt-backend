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

def calculate_cantonese_date(text: str, base_date: datetime = None) -> Optional[datetime]:
    base_date = base_date or datetime.now()
    text = text.replace("礼拜", "星期").replace("聽日", "听日")

    # Week shift calculation
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

    # Date calculation
    if "听日" in clean_day:
        target_date = base_date + timedelta(days=1)
    elif "後日" in clean_day or "后日" in clean_day:
        target_date = base_date + timedelta(days=2)
    elif "大後日" in clean_day:
        target_date = base_date + timedelta(days=3)
    else:
        weekday_match = re.search(r'(星期|禮拜)([一二三四五六七日天])', clean_day)
        if not weekday_match:
            return None

        weekday_map = {'一': 1, '二': 2, '三': 3, '四': 4,
                      '五': 5, '六': 6, '日': 7, '天': 7}
        target_weekday = weekday_map[weekday_match.group(2)]

        # Key Fix: Calculate days to next occurrence
        days_until = (target_weekday - base_date.isoweekday()) % 7
        if days_until == 0:  # Same day
            days_until = 7 if weeks_ahead > 0 else 0
        
        # Add full weeks if needed
        target_date = base_date + timedelta(days=days_until + (7 * weeks_ahead))

    # Time parsing (unchanged)
    hour, minute = 12, 0
    if any(t in text for t in ["中午", "晏昼", "下午"]):
        time_match = re.search(r'(\d+)(点|點)(半)?', text)
        hour = int(time_match.group(1)) if time_match else 14
        if time_match and hour < 12 and "下午" in text:
            hour += 12
        if time_match and time_match.group(3):
            minute = 30
    # ... (other time cases)

    return target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)


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


def generate_reflection(text: str) -> str:
    """
    Generate a 20–30 second natural-sounding reflection or follow-up
    based on what the user just said. The tone is friendly, supportive,
    and memory-oriented. It also adds light特色資訊 to enhance usefulness.
    """
    try:

        detected_date = calculate_cantonese_date(text)
        date_str = detected_date.strftime("%Y-%m-%dT%H:%M") if detected_date else ""

        client = get_hunyuan_client()

        prompt = f"""
            [Current Date] {datetime.now().strftime("%Y-%m-%d (%A)")}
            [Detected Date] {date_str if date_str else "None"}

            你係一個有記憶力、貼心、識講廣東話的助理。請根據以下規則回應：

            1. **日期處理規則**  
            - 若[Detected Date]有值，必須用該日期回答，格式如「2025年7月23日」或「7月23日星期三」。  
            - "听日" = tomorrow
            - "後日" = day after tomorrow
            - "大後日" = three days later
            - "今个[weekday]" = this week's [weekday]
            - "下个[weekday]" = next week's [weekday]
            - "中午" = 12:00, "晏昼" = 14:00, "晚上"/"夜晚" = 20:00, "朝早"/"上午" = 09:00
            - Time like "两点半" = 14:30 if in afternoon context
            - 若用戶問「聽日/下星期X幾號」，必須清楚答出正確日期。  

            2. **如果使用者問問題（例如問日期、時間、地點等）** → 直接回答問題，簡潔準確，唔需要加反思或建議。
            - 例子：  
                - 用戶問：「今日幾號？」→ 答：「今日係2025年7月23日，星期三。」  
                - 用戶問：「聽日天氣點？」→ 答：「聽日預測多雲，有幾陣雨，氣溫26至30度。」  

            3. **如果使用者只係分享或閒聊（冇明確問題）** → 用20–30秒自然語氣回應，語氣親切、口語化，可加入：
            - 重點整理（幫佢重溫內容）
            - 適量反應（關心、認同、幽默）
            - 生活小建議或提醒（如果適用）
            - 若提到地點，自然地提一個代表性景點/活動（唔好列舉多個）
            - 例子：  
                - 用戶講：「今日同朋友去咗飲茶。」→ 答：「同朋友飲茶真係開心！記得你之前都鍾意去陸羽茶室，今次去邊度飲呀？」  



            使用者啱啱講咗：  
            「{text}」  

            請嚴格按上述規則回應，用純廣東話寫一句自然說話，唔好加任何解釋或格式。  
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
