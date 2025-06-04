
import json
from tencentcloud.common import credential
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.hunyuan.v20230901 import hunyuan_client, models
import os

TENCENT_SECRET_ID = os.getenv("TENCENT_HUNYUAN_SECRET_ID")
TENCENT_SECRET_KEY = os.getenv("TENCENT_HUNYUAN_SECRET_KEY")

cred = credential.Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)
http_profile = HttpProfile(endpoint="hunyuan.ap-hongkong.tencentcloudapi.com")
client_profile = ClientProfile(httpProfile=http_profile)
client = hunyuan_client.HunyuanClient(cred, "ap-guangzhou", client_profile)

def extract_datetime_location(text):
    prompt_system = (
        "You are an assistant that extracts structured event information from Cantonese text. "
        "Extract the event description, date and time (ISO 8601 format). "
        "Follow these rules for date inference:\n"
        "1. If '下个' (next) is mentioned, use next week's date.\n"
        "2. If no week is specified, assume **this week** (even if the day has passed today).\n"
        "3. If time is missing, default to 12:00:00.\n"
        "4. Always output time in **Asia/Hong_Kong** timezone (UTC+8).\n"
        "Respond ONLY with a JSON object: {'event': str, 'datetime': 'YYYY-MM-DDTHH:MM:SS+08:00', 'location': str}."    
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

        # Parse JSON from LLM response
        data = json.loads(raw_response)
        return data

    except Exception as e:
        print("Error in extracting date/time/location:", e)
        print("Raw response:", raw_response)
        return None

# Example usage:
test_text = "我话帮我记落calendar，下个礼拜三晏昼3点钟，我要翻嚟香港去养和医院复诊"
result = extract_datetime_location(test_text)
print(result)
