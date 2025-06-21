import leancloud
from config.constants import LEANCLOUD_APP_ID, LEANCLOUD_APP_KEY
from utils.text_to_speech import tencent_tts

def init_filler_messages(fillers):
    return {text: tencent_tts(text) for text in fillers}

def init_leancloud():
    # You can use master_key if you need admin privileges (e.g. delete/update)
    # leancloud.init(app_id, app_key, master_key)
    leancloud.init(LEANCLOUD_APP_ID, LEANCLOUD_APP_KEY)
    print("[INFO] LeanCloud initialized successfully.")
