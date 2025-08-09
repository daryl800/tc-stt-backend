from groq import Groq
from typing import Optional
from datetime import datetime, timedelta
import re
import json
from models.memory_item import MemoryItem
from config.constants import GROQ_API_KEY, SERPER_API_KEY
import requests

GROQ_CLIENT = Groq(api_key=GROQ_API_KEY)
GROQ_LLM_MODEL = "llama-3.1-8b-instant"
SERPER_URL = "https://google.serper.dev/news"  # Serper News 搜索接口

# Simplified keyword sets (after normalization)
TOMORROW_KEYWORDS = {"聽日", "聽朝", "聽晚", "聽日中午"}
DAY_AFTER_TMR_KEYWORDS = {"後日",  "後朝", "後晚", "後日中午"}
TWO_DAYS_AFTER_TMR_KEYWORDS = {"大後日", "大後朝", "大後晚", "大後日中午"}
TODAY_KEYWORDS = {"而家", "依家", "現在", "今日", "今天", "今朝", "今晚"}

# Assume these are defined elsewhere
WEEK_PATTERNS = {
    r"(今)?星期([一二三四五六日天])": 0,
    r"(下)?星期([一二三四五六日天])": 1,
    r"(上)?星期([一二三四五六日天])": -1
}

WEEKDAY_MAP = {
    "一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5,
    "日": 6, "天": 6
}


# Extract time if mentioned


def extract_time(text: str):
    hour, minute = 12, 0  # default noon

    if "早" in text or "朝" in text or "上昼" in text:
        hour = 9
    elif "下午" in text or "下昼" in text or "晏昼" in text:
        hour = 14
    elif "晚" in text:
        hour = 20

    # Find time like 7點, 8點半, 9:15
    match = re.search(r'(?P<hour>\d{1,2})(點|:)(?P<minute>\d{1,2})?', text)
    if match:
        hour = int(match.group("hour"))
        minute = int(match.group("minute")) if match.group("minute") else 0

    return hour, minute


def is_date_related(text: str) -> bool:

    all_keywords = (
        TOMORROW_KEYWORDS |
        DAY_AFTER_TMR_KEYWORDS |
        TWO_DAYS_AFTER_TMR_KEYWORDS |
        TODAY_KEYWORDS
    )

    contains_date_kw = any(kw in text for kw in all_keywords)
    contains_week_pattern = any(re.search(pattern, text)
                                for pattern in WEEK_PATTERNS)

    result = contains_date_kw or contains_week_pattern
    print(f"[DEBUG] Contain any date keywords?: {result}")
    return result


def calculate_cantonese_date(text: str, base_date: datetime = None) -> datetime:

    if base_date is None:
        base_date = datetime.now()

    hour, minute = extract_time(text)

    # Group 1: relative dates
    if any(kw in text for kw in TOMORROW_KEYWORDS):
        return (base_date + timedelta(days=1)).replace(hour=hour, minute=minute)
    elif any(kw in text for kw in DAY_AFTER_TMR_KEYWORDS):
        return (base_date + timedelta(days=2)).replace(hour=hour, minute=minute)
    elif any(kw in text for kw in TWO_DAYS_AFTER_TMR_KEYWORDS):
        return (base_date + timedelta(days=3)).replace(hour=hour, minute=minute)
    elif any(kw in text for kw in TODAY_KEYWORDS):
        return base_date.replace(hour=hour, minute=minute)

    # Group 2: weekday (e.g., 星期三)
    for pattern, week_offset in WEEK_PATTERNS.items():
        match = re.search(pattern, text)
        if match:
            _, day_char = match.groups()
            target_weekday = WEEKDAY_MAP.get(day_char)
            if target_weekday is None:
                continue

            # Find date of that weekday in target week
            start_of_week = base_date - timedelta(days=base_date.weekday())
            target_date = start_of_week + \
                timedelta(days=target_weekday, weeks=week_offset)

        return target_date.replace(hour=hour, minute=minute)

    return None

def web_search(query):

    payload = json.dumps({
        "q": query,
        "gl": "Hong Kong"
    })

    headers = {
        'X-API-KEY': SERPER_API_KEY,
        'Content-Type': 'application/json'
    }

    response = requests.post(SERPER_URL, headers=headers, data=payload)
    response.raise_for_status()

    data = response.json()

    news_items = data.get("news", [])
    snippets = []
    for i, item in enumerate(news_items[:10]):
        title = item.get("title", "無標題")
        snippet = item.get("snippet", "")
        source_raw = item.get("source", "未知來源")

        # 判斷 source 欄位型別
        if isinstance(source_raw, dict):
            source = source_raw.get("domain", "未知來源")
        elif isinstance(source_raw, str):
            source = source_raw
        else:
            source = "未知來源"

        snippets.append(f"{i+1}. {title}（來源：{source}）：{snippet}")

    search_summary = "\n".join(snippets)

    print(f"=== 網路搜索摘要 ===\n{search_summary}\n")
    return search_summary


def is_web_search_needed(user_query: str, knowledge_cutoff_date: str = "2025-01") -> bool:
    """
    根據用戶輸入判斷是否需要啟動網絡搜索。
    
    判斷要點：
    - 是否包含時間敏感關鍵詞 (如 '今天', '最新', '天氣' 等)
    - 是否包含地區關鍵詞 (如 '中山', '北京' 等)
    - 是否同時含有時間敏感詞與地區詞
    - 是否包含明確要求最新資訊的字眼 (如 '最新', '查詢')
    - 是否涉及超過知識庫截止日期的年份
    """
    # 時間敏感詞（可視需求擴充）
    time_sensitive_keywords = ['今天', '今日', '依家', '而家', '宜家', '目前', '現在', '現時', '現任', '最新', '最近', '價格', '新聞', '天氣', '股價', '匯率', '當前', '實時']
    # 地區詞（可視需求擴充）
    location_keywords = ['香港', '國內', '中山', '廣東', '北京', '上海', '地點', '深圳', '杭州']

    # 判斷是否包含時間敏感詞
    contains_time_sensitive = any(keyword in user_query for keyword in time_sensitive_keywords)
    # 判斷是否包含地區詞
    contains_location = any(keyword in user_query for keyword in location_keywords)

    # 若既含時間敏感詞又含地區詞，建議啟動網絡搜索
    if contains_time_sensitive and contains_location:
        return True

    # 只含時間敏感詞，也建議啟動網絡搜索
    if contains_time_sensitive:
        return True

    # 明確要求最新或查詢
    if '最新' in user_query or '查詢' in user_query:
        return True

    # 假設用戶問題中含年份，判斷是否超過知識庫截止日期
    years_in_query = re.findall(r'\b(19|20)\d{2}\b', user_query)
    if years_in_query:
        # 取第一個年份判斷即可
        query_year = int(years_in_query[0] + user_query[user_query.find(years_in_query[0]) + 2:user_query.find(years_in_query[0]) + 4])
        cutoff_year = int(knowledge_cutoff_date.split('-')[0])
        if query_year > cutoff_year:
            return True

    # 若以上條件皆不符合，則不啟動網絡搜索
    return False

def extract_info_withLLM(text: str) -> MemoryItem:
    try:
        detected_date = calculate_cantonese_date(text) if is_date_related(text) else None
        print(f"[DEBUG] text pasted in extract_info_withLLM: {text}")
        
        date_str = ""
        if detected_date:
            date_str = detected_date.strftime("%Y-%m-%dT%H:%M")
            print(f"[DEBUG] Detected date: {date_str}")

        user_prompt = f"""
        [Current Date] {datetime.now().strftime("%Y-%m-%d (%A)")}
        [Detected Date] {date_str if date_str else "None"}

        Please analyze the following Cantonese input and extract key information.

        Input:
        "{text}"

        ## Instructions:

        1. Date/Time Handling
        - Use the "[Detected Date]" if provided. Do NOT guess or change the date unless the input text clearly contradicts it.

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

        messages = [
            {"role": "user", "content": user_prompt}
        ]

        response = GROQ_CLIENT.chat.completions.create(
            model=GROQ_LLM_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=300
        )

        raw_content = json.loads(response.choices[0].message.content.strip())
        print(f"[DEBUG] LLM output: {raw_content}")
        try:
            result_dict = json.loads(raw_content)
        except Exception as e:
            print(f"[ERROR] JSON parse failed: {e}")
            result_dict = {}

        final_date = date_str if result_dict.get("isReminder") else ""

        return MemoryItem(
            category = result_dict.get("category", "General"),
            transcription = text,
            mainEvent = result_dict.get("mainEvent", text.split("。")[0] if "。" in text else text),
            reminderDatetime = final_date,
            isReminder = result_dict.get("isReminder", False),
            isQuery = result_dict.get("isQuery", False),
            location = result_dict.get("location", []) if isinstance(result_dict.get("location", []), list) else [],
            tags = result_dict.get("tags", []) if isinstance(result_dict.get("tags", []), list) else [],
            eventCreatedAt = datetime.now(),
            originalVoice_Url = None,
            sourceLang = "yue-HK",
            userId = None,
            reflection = None
        )

    except Exception as e:
        print(f"[ERROR] LLM extraction failed: {e}")
        return MemoryItem(
            category = "General",
            transcription = text,
            mainEvent = text.split("。")[0] if "。" in text else text,
            reminderDatetime = "",
            isReminder = False,
            isQuery = False,
            location = [],
            tags = [f"Error: {str(e)}"],
            eventCreatedAt = datetime.now(),
            originalVoice_Url = None,
            sourceLang = "yue-HK",
            userId = None
        )


# Example usage
if __name__ == "__main__":
    test_text = "提醒我，聽日我约咗人食晚飯。"
    test_base_date = datetime(2025, 7, 21)  # Monday
    calculated = calculate_cantonese_date(test_text, test_base_date)
    print(
        f"Calculated date: {calculated.strftime('%Y-%m-%d %H:%M') if calculated else 'None'}")

    result = extract_info_withLLM(test_text)
    print(f"Extracted Date: {result.reminderDatetime}")
    print(f"Main Event: {result.mainEvent}")


def generate_reflection(query: str) -> str:
    try:
        detected_date = calculate_cantonese_date(query) if is_date_related(query) else None

        date_str = detected_date.strftime("%Y年%m月%d號") if detected_date else ""
        if detected_date:
            print(f"[DEBUG] Detected date: {date_str}")

        system_prompt = (
            "你係一個有實時網絡搜索能力嘅助理。"
            "如果有網路搜索結果，請嚴格根據其結果回答，不要使用內部知識庫或者過時資料。"
            "回答要用親切、溫柔嘅粵語語氣，簡短直接，最多200字。"
        )

        if is_web_search_needed(query):
            print(f"[DEBUG] 現在開始網絡搜索...")
            search_result = web_search(query)
            user_prompt = (
                f"請根據以下相關網絡搜索結果回答：\n{search_result}\n"
            )
        else:
            print("不需要網絡搜索。")

        if date_str:
            user_prompt += f"如果係跟日期有關嘅：請適當地加入系統計算嘅日期，係：{date_str}\n"

        user_prompt += f"回答用戶問題：{query}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = GROQ_CLIENT.chat.completions.create(
            model=GROQ_LLM_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=300
        )

        result = response.choices[0].message.content.strip()
        print(f"[INFO] Reflection: {result}")
        return result

    except Exception as e:
        print(f"[ERROR] Reflection failed: {e}")
        return "我記低咗你講嘅內容啦，有需要可以再問我！"
