import json
import os
from datetime import datetime
from tencentcloud.common import credential
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.hunyuan.v20230901 import hunyuan_client, models
from config.constants import TENCENT_SECRET_ID, TENCENT_SECRET_KEY

# Initialize Hunyuan client (singleton pattern)
def get_hunyuan_client():
    cred = credential.Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)
    http_profile = HttpProfile(endpoint="hunyuan.ap-hongkong.tencentcloudapi.com")
    client_profile = ClientProfile(httpProfile=http_profile)
    return hunyuan_client.HunyuanClient(cred, "ap-guangzhou", client_profile)

def extract_event_info(text):
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
        
        Return JSON with:
        - "event": Short action/plan summary (omit reminder words)
        - "reminderDatetime": ISO 8601 format or empty string if unclear
        - "location": List of places mentioned (e.g., 香港, 瑞典)
        - "isReminder": true if it includes 提我/提醒我
        - "tags": List of keywords including:
        - Locations (e.g., 香港)
        - People/entities (e.g., 我個仔, 屋企人)
        - Important nouns or time expressions (e.g., 出年, 暑假, 去旅行)
        
        Time Handling Rules:
        1. Cantonese weekdays:
        - 「星期三」 means this week's Wednesday.
        - 「下星期三」 means next week's Wednesday (7 days after this week's Wednesday).
        - 「出年」、「下個月」、「下星期」 all refer to the **next full period**, not the day after.

        2. If only date mentioned → Add default time 09:00
        Example: "星期三開會" → "2025-06-11T09:00"

        3. Time period defaults:
        - 朝早 / 上午 → 09:00
        - 晏晝 / 下午 → 14:00
        - 夜晚 / 晚上 → 20:00

        4. Exact times (e.g., “下午三點”) should be preserved as-is.

        5. If time is vague or uncertain → Use empty string for "reminderDatetime"

        6. If the sentence includes “提醒我” or “提我”:
        → Interpret the date as the next upcoming matching date from today.
        Example:
        - If today is Monday, and text says “提醒我星期三”，then return this week's Wednesday.
        - If today is Friday and text says “提醒我星期三”，then return next week's Wednesday (as this week’s Wednesday is already past).

        → Always calculate the next valid date from today to avoid reminders set in the past.

        Tagging rules:
        1. Tags should be useful for searching and grouping memories.
        2. Tags should be short (1–5 words) and meaningful.
        3. Avoid stopwords like "我", "咁", "啦", "喇", "啊", "的".

        [OUTPUT FORMAT]
        {{
        "event": "事件描述",
        "reminderDatetime": "YYYY-MM-DDTHH:MM or empty",
        "location": ["地點"],
        "isReminder": true/false,
        "tags": ["香港", "我個仔", "出年", "旅行"]
        }}
        """
    
        req = models.ChatCompletionsRequest()
        req.Messages = [{"Role": "user", "Content": prompt}]
        req.Model = "hunyuan-standard"  # Use the turbo model for better performance
        req.Temperature = 0

        resp = client.ChatCompletions(req)
        data = json.loads(resp.Choices[0].Message.Content.strip())

        return {
            "createdAt": datetime.now().isoformat(),
            "text": text,
            "mainEvent": data.get("event", ""),
            "reminderDatetime": data.get("reminderDatetime", ""),
            "location": ", ".join(data.get("location", [])),
            "isReminder": data.get("isReminder", False),
            "category": "Reminder",
            "tags": list(set(data.get("location", [])))
        }

    except json.JSONDecodeError:
        return {
            "error": "LLM returned invalid JSON",
            "text": text,
            "rawResponse": resp.Choices[0].Message.Content if 'resp' in locals() else None
        }
    except Exception as e:
        return {
            "error": str(e),
            "text": text
        }

# Example test
if __name__ == "__main__":
    print(extract_event_info("星期三提醒我睇无线电视新闻"))