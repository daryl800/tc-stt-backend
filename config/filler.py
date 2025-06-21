# filler.py
import random
from utils.text_to_speech import tencent_tts

# FILLER_LIST = ["嗯", "好吖", "等陣", "噉我睇吓", "畀啲時間我"]
FILLER_LIST = ["Okay，收到～", "好呀，聽到你讲～", "收到，明白～"]
FILLER_CACHE = {}

def init_filler_messages():
    global FILLER_CACHE
    FILLER_CACHE = {text: tencent_tts(text) for text in FILLER_LIST}

def pick_random_filler():
    return FILLER_CACHE[random.choice(FILLER_LIST)]
