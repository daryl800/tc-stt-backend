# filler.py
import random
from utils.tencent_tts_short import tencent_tts

# FILLER_LIST = ["嗯", "好吖", "等陣", "噉我睇吓", "畀啲時間我"]
FILLER_LIST = [
    "請稍等，我正分析您的語音內容。",
    "正在分析您的語音內容，請稍候……",
    "請稍等片刻，系統正在分析您的語音內容。",
    "我正分析您的語音內容，請耐心等候。",
    "我已经开始左分析您的語音內容，請稍候。",
    "系統正在努力處理您的訊息，請稍等。"
]

FILLER_CACHE = {}

def init_filler_messages():
    global FILLER_CACHE
    FILLER_CACHE = {text: tencent_tts(text) for text in FILLER_LIST}

def pick_random_filler():
    chosen_text = random.choice(FILLER_LIST)
    print(f"Chosen filler text: {chosen_text}")
    return FILLER_CACHE[chosen_text]
