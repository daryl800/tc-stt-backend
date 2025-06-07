import leancloud
import os

import leancloud
import os

def init_leancloud():
    app_id = os.getenv("LEAN_APP_ID")
    app_key = os.getenv("LEAN_APP_KEY")
    master_key = os.getenv("LEAN_MASTER_KEY")  # optional

    if not app_id or not app_key:
        raise RuntimeError("Missing LeanCloud environment variables.")

    # You can use master_key if you need admin privileges (e.g. delete/update)
    # leancloud.init(app_id, app_key, master_key)
    leancloud.init(app_id, app_key)
    print("[INFO] LeanCloud initialized successfully.")
