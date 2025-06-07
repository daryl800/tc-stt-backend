import json
import os
from datetime import datetime
from tencentcloud.common import credential
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.hunyuan.v20230901 import hunyuan_client, models

# Initialize Hunyuan client (singleton pattern)
def get_hunyuan_client():
    cred = credential.Credential(
        os.getenv("TENCENT_HUNYUAN_SECRET_ID"),
        os.getenv("TENCENT_HUNYUAN_SECRET_KEY")
    )
    http_profile = HttpProfile(endpoint="hunyuan.ap-hongkong.tencentcloudapi.com")
    client_profile = ClientProfile(httpProfile=http_profile)
    return hunyuan_client.HunyuanClient(cred, "ap-guangzhou", client_profile)

# def extract_event_info(text):
#     """
#     Final optimized version with:
#     - Proper client initialization
#     - LLM-native date handling
#     - Robust error handling
#     """
#     try:
#         # Initialize client (thread-safe)
#         client = get_hunyuan_client()
        
#         prompt = f"""
#         [Current Date] {datetime.now().strftime("%Y-%m-%d (%A)")}
        
#         Extract from Cantonese:
#         "{text}"
        
#         Return JSON with:
#         - "event": Action description (remove reminder phrases)
#         - "reminderDatetime": ISO 8601 date/time
#         - "location": List of places
#         - "isReminder": true if contains 提醒/記住/记得
        
#         Time Handling Rules:
#         1. If only date mentioned → Add default time 09:00
#         Example: "星期三開會" → "2025-06-11T09:00"
#         2. Time period defaults:
#         - 朝早/上午 → 09:00
#         - 晏晝/下午 → 14:00
#         - 夜晚 → 20:00
#         3. Exact times keep as-is
#         4. Uncertain times → Return empty string

#         [OUTPUT FORMAT]
#         {{
#             "event": "事件描述",
#             "reminderDatetime": "YYYY-MM-DD或YYYY-MM-DDTHH:MM",
#             "location": ["地點"],
#             "isReminder": true/false
#         }}
#         """

    def extract_event_info(text):
        """
        Final version with explicit weekday handling rules
        """
        try:
            client = get_hunyuan_client()
            today = datetime.now()
            
            prompt = f"""
            [Current Date] {today.strftime("%Y-%m-%d (%A)")}
            [Date Calculation Rules]
            1. Single weekday ("星期三") → Nearest future occurrence
            - Today is {today.strftime("%A")}: 
                "星期三" = {_get_next_weekday(today, 2).strftime("%Y-%m-%d")}
            2. "下星期三" → Same day next week
            - "下星期三" = {(today + timedelta(days=(2 - today.weekday() + 7))).strftime("%Y-%m-%d")}
            3. "下下星期三" → Two weeks ahead
            - Example: {(today + timedelta(days=(2 - today.weekday() + 14))).strftime("%Y-%m-%d")}

            [User Input]
            "{text}"

            [Output Requirements]
            {{
                "event": "cleaned description",
                "reminderDatetime": "ISO8601 format (09:00 default if no time)",
                "location": ["place"],
                "isReminder": boolean
            }}
            """

            # ... rest of your API call code ...

            def _get_next_weekday(from_date, weekday):
                """Helper: Get next specific weekday (0=Monday)"""
                days_ahead = (weekday - from_date.weekday() + 7) % 7
                return from_date + timedelta(days=days_ahead)
            
                req = models.ChatCompletionsRequest()
                req.Messages = [{"Role": "user", "Content": prompt}]
                req.Model = "hunyuan-pro"  # Use the turbo model for better performance
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