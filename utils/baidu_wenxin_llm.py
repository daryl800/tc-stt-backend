import requests
import json
from datetime import datetime
from models.memory_item import MemoryItem
from config.constants import BAIDU_ACCESS_TOKEN

baidu_accessToken = BAIDU_ACCESS_TOKEN
MODEL = "ernie-bot-turbo"  # 可改为 "ernie-bot"

def extract_info_withLLM(text):
    prompt = f"""
    [Current Date] {datetime.now().strftime("%Y-%m-%d (%A)")}
    Extract from Cantonese:
    "{text}"
    Please output ONLY a JSON object with the following fields:
    - "category": Classify the memory into one of these: [General, Family, Health, Shopping, Reminder, Question]
    - "mainEvent": Short action/plan summary
    - "reminderDatetime": "YYYY-MM-DDTHH:MM" (ISO 8601) or "" if unclear
    - "location": List of places mentioned
    - "isReminder": true if includes "提我" or "提醒我"
    - "isQuery": true if a question (see below)
    - "tags": List of keywords: location, person/entity, important nouns/time
    - "Question": Answer if question is asked

    [OUTPUT FORMAT]
    {{
      "category": "",
      "mainEvent": "",
      "reminderDatetime": "",
      "location": [],
      "isReminder": false,
      "isQuery": false,
      "tags": [],
      "Question": ""
    }}
    """

    url = f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/{MODEL}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {BAIDU_ACCESS_TOKEN}"
    }
    messages = [{"role": "user", "content": prompt}]
    payload = json.dumps({"messages": messages, "temperature": 0.7})

    try:
        res = requests.post(url, headers=headers, data=payload, timeout=30)
        res.raise_for_status()
        reply = res.json()["result"].strip()
        print(f"[DEBUG] Wenxin raw output: {reply}")
        data = json.loads(reply)

        memoryItem = MemoryItem(
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
        return memoryItem

    except Exception as e:
        print(f"[ERROR] LLM extraction failed: {e}")
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

def generate_reflection(text: str) -> str:
    prompt = f"""
    你係一個有記憶力、貼心、識講廣東話的助理。根據使用者啱啱講嘅內容，用大約20–30秒自然語氣回應一段說話，語氣要自然、口語化、親切，可以加入重點整理、關心、建議等。內容如下：「{text}」
    請用廣東話寫一句自然說話，不要加說明。
    """
    url = f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/{MODEL}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {BAIDU_ACCESS_TOKEN}"
    }
    messages = [{"role": "user", "content": prompt}]
    payload = json.dumps({"messages": messages, "temperature": 1})

    try:
        res = requests.post(url, headers=headers, data=payload, timeout=30)
        res.raise_for_status()
        reply = res.json()["result"].strip()
        return reply
    except Exception as e:
        print(f"[ERROR] Reflection failed: {e}")
        return "我記低咗你講嘅內容啦，有需要可以再問我！"

# Example usage:
if __name__ == "__main__":
    result = extract_info_withLLM("星期三提醒我睇无线电视新闻")
    print(result.json(indent=4))
    print(generate_reflection("星期三提醒我睇无线电视新闻"))
