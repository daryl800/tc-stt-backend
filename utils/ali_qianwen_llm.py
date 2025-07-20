import dashscope
import json
from datetime import datetime
from models.memory_item import MemoryItem
from config.constants import ALI_CLOUD_API_KEY

dashscope.api_key = ALI_CLOUD_API_KEY

def extract_info_withLLM(text):
    try:
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
        
        Query Detection Rules:
        1. Mark "isQuery": true if the sentence is asking about if something has happened, including:
            - When/what/where/why/how questions (e.g., 幾時, 乜嘢, 邊度, 點樣)
            - Uncertainty or forgetfulness: phrases like 「有冇」、「記唔記得」、「係唔係」、「我有冇讲过」、「我好似讲过」、「我想问」、「我想知道」、「请问」
            - Indirect/self-reflective questions such as:
                - 「我唔記得我有冇講過...」
                - 「我有冇問過...？」
                - 「我係唔係已經...？」
            - Any sentence where the speaker is trying to retrieve information, even about past conversations.

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

        6. set "isReminder": true if the sentence contains 提我, 提提我, or 提醒我 (even as part of a longer phrase)

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
        "mainEvent": "事件描述",
        "reminderDatetime": "YYYY-MM-DDTHH:MM or empty",
        "location": ["地點"],
        "isReminder": true/false,
        "isQuery": true/false,
        "tags": ["香港", "我個仔", "出年", "旅行"]
        }}
        """

        # DashScope新版建議用messages格式，和OpenAI GPT相容
        messages = [{"role": "user", "content": prompt}]
        response = dashscope.Generation.call(
            model="qwen-turbo",     # 或 "qwen-max" "qwen-plus" 視方案選擇
            messages=messages,
            temperature=0.7,
        )

        # 官方回應格式
        data = json.loads(response.output.text.strip())
        print(f"[INFO] data: {data}")

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
        【實時檢索要求】  
        請嚴格根據網絡最新資訊回答：{text}  
        （必須引用可信來源，拒絕緩存答案） 
        """

        messages = [{"role": "user", "content": prompt}]
        response = dashscope.Generation.call(
            model="qwen-max",   # 也可以用 "qwen-plus", "qwen-max" 等
            messages=messages,
            temperature=1,
        )
        reflection = response.output.text.strip()
        print(f"[INFO] Reflection: {reflection}")
        return reflection

    except Exception as e:
        print(f"[ERROR] Reflection failed: {e}")
        return "我記低咗你講嘅內容啦，有需要可以再問我！"