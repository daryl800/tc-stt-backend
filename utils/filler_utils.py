# filler.py
import random
from utils.text_to_speech import tencent_tts

# FILLER_LIST = ["嗯", "好吖", "等陣", "噉我睇吓", "畀啲時間我"]
FILLER_LIST = [
    "收到……唔～",
    "Okay……er～",
    "听到……唔～"
]

FILLER_CACHE = {}

def init_filler_messages():
    global FILLER_CACHE
    FILLER_CACHE = {text: tencent_tts(text) for text in FILLER_LIST}

def pick_random_filler():
    chosen_text = random.choice(FILLER_LIST)
    print(f"Chosen filler text: {chosen_text}")
    return FILLER_CACHE[chosen_text]
