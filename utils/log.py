import logging
import logging.handlers

FORMAT = '%(asctime)15s %(name)s-%(levelname)s  %(funcName)s:%(lineno)s %(message)s'

# App logger
logger = logging.getLogger('tencent_speech')
logger.setLevel(logging.INFO)  # INFO and above

# Rotating file handler
file_handler = logging.handlers.RotatingFileHandler(
    'tencent_speech.log',
    maxBytes=1024*1024,
    backupCount=5,
    encoding='utf-8'
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(FORMAT))
logger.addHandler(file_handler)

# Optional: also log to console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(FORMAT))
logger.addHandler(console_handler)

# Suppress debug from third-party libraries
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("tencentcloud_sdk_common").setLevel(logging.WARNING)
