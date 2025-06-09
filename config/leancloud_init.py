import leancloud
from config.constants import LEANCLOUD_APP_ID, LEANCLOUD_APP_KEY

def init_leancloud():

    # You can use master_key if you need admin privileges (e.g. delete/update)
    # leancloud.init(app_id, app_key, master_key)
    leancloud.init(LEANCLOUD_APP_ID, LEANCLOUD_APP_KEY)
    print("[INFO] LeanCloud initialized successfully.")
