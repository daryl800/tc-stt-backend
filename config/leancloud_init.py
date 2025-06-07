import leancloud
import os

def init_leancloud():
    # Toggle based on environment variable or manual flag
    development = os.getenv("ENV", "development") == "development"

    if development:
        # Replace with your actual dev keys
        leancloud.init("LEANCLOUD_APP_ID", "LEANCLOUD_APP_KEY")
    else:
        # Replace with your actual prod keys
        leancloud.init("LEANCLOUD_APP_ID", "LDANCLOUD_APP_KEY")
