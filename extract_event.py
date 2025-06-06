import json
import os
from tencentcloud.common import credential
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.hunyuan.v20230901 import hunyuan_client, models

from classify import classify_text  # assume same directory

TENCENT_SECRET_ID = os.getenv("TENCENT_HUNYUAN_SECRET_ID")
TENCENT_SECRET_KEY = os.getenv("TENCENT_HUNYUAN_SECRET_KEY")

cred = credential.Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)
http_profile = HttpProfile(endpoint="hunyuan.ap-hongkong.tencentcloudapi.com")
client_profile = ClientProfile(httpProfile=http_profile)
client = hunyuan_client.HunyuanClient(cred, "ap-guangzhou", client_profile)


def extract_event_info(text):
    prompt_system = (
        "你是一個智能助理，從廣東話語句中抽取結構化的事件資料。\n"
        "請忽略“提醒我”、“記住”等字眼，只專注於提到的實際事件。\n"
        "「除非明確提到「幫我記住」、「提我」、「記錄」或類似語句，否則不要標記為提醒。」\n"
        "請從輸入中提取以下資訊：\n"
        "1. event：事件的描述（忽略提示用語，抓住主要動作或情況）\n"
        "2. datetime：事件的時間（ISO 8601 格式），若無明確時間，設為中午12:00。\n"
        "3. location：如有提及，提取所有地名，格式為字串列表，如 ['佛山', '中山']。\n\n"
        "例子：\n"
        "輸入：記住聽朝8點半提醒我，我阿哥會聽日中午之前由佛山嚟到中山。\n"
        "輸出：\n"
        "{\n"
        "  \"event\": \"我阿哥會聽日中午之前由佛山嚟到中山\",\n"
        "  \"datetime\": \"2025-06-06T08:30:00+08:00\",\n"
        "  \"location\": [\"佛山\", \"中山\"]\n"
        "}\n\n"
        "只回傳純 JSON，不要有多餘文字或 Markdown 格式。"
    )

    req = models.ChatCompletionsRequest()
    req.Messages = [
        {"Role": "system", "Content": prompt_system},
        {"Role": "user", "Content": text},
    ]
    req.Model = "hunyuan-standard"
    req.Temperature = 0

    try:
        resp = client.ChatCompletions(req)
        raw_response = resp.Choices[0].Message.Content.strip()
        data = json.loads(raw_response)

        event = data.get("event", "")
        datetime_iso = data.get("datetime", "")
        locations = data.get("location", [])

        # Compose final output
        return {
            "text": text,
            "mainEvent": event,
            "dateTime": datetime_iso,
            "location": ", ".join(locations) if isinstance(locations, list) else locations,
            "isReminder": True,
            "category": classify_text(event),
            "tags": list(set(event.split() + locations))  # crude keywords from event + location
        }

    except Exception as e:
        print("Error in extracting structured event info:", e)
        print("Raw response might be invalid JSON.")
        return {
            "error": str(e),
            "rawResponse": raw_response if 'raw_response' in locals() else None
        }


# Example usage
if __name__ == "__main__":
    test_text = "我话帮我记落calendar，下个礼拜三晏昼3点钟，我要翻嚟香港去养和医院复诊"
    result = extract_event_info(test_text)
    print(json.dumps(result, ensure_ascii=False, indent=2))
