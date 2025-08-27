# # TODO:  This code is for tencent tts short sentence handling, after stream works smoothly, this file should be removed

# import sys
# import os
# import base64
# import shutil
# import re

# from tencentcloud.tts.v20190823 import tts_client, models as tts_models
# from tencentcloud.common import credential


# # Add parent directory of utils
# sys.path.append(os.path.dirname(os.path.dirname(__file__)))
# from config.constants import TENCENT_SECRET_ID, TENCENT_SECRET_KEY

# # Setup credentials
# cred = credential.Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)

# if shutil.which("ffmpeg") is None:
#     raise EnvironmentError("ffmpeg is not installed or not in PATH")

# # Setup credentials
# cred = credential.Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)

# # Initialize Hunyuan client (singleton pattern)
# def get_tts_client():
#     return tts_client.TtsClient(cred, "ap-hongkong") 

# def tencent_tts(text):
#     # Request setup (CORRECT: Using TextToVoiceRequest)
#     params = {
#         "Text": text,
#         "SessionId": "test-123",
#         "ModelType": 1,
#         "VoiceType": 101019,  # Cantonese Female 
#         "Codec": "wav",
#         "Volume": 5,
#         "Speed": 0,
#         "ProjectId": 0,
#         "SampleRate": 16000
#     }

#     client = get_tts_client()
#     # Request and save
#     req = tts_models.TextToVoiceRequest()  # ✅ This is the correct class for TTS generation
#     req.from_json_string(str(params).replace("'", '"'))  # Convert dict to JSON string

#     try:
#         resp = client.TextToVoice(req)
#         audio_bytes = base64.b64decode(resp.Audio)
        
#         print(f"[INFO] Size of data being sent to TC TTS: {len(audio_bytes)/1024:.2f} KB")
#         return audio_bytes

#     except Exception as e:
#         print(f"❌ Error: {str(e)}")
#         if "PkgExhausted" in str(e):
#             print("Solution: Purchase ")




# def clean_text(text):
#     # Remove control characters except \n
#     return re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F]", "", text)

# def group_segments_by_limit(segments, max_chars=200):
#     chunks = []
#     current_chunk = ""

#     for seg in segments:
#         seg = clean_text(seg)
#         if len(current_chunk) + len(seg) <= max_chars:
#             current_chunk += seg
#         else:
#             if current_chunk:
#                 chunks.append(current_chunk)
#             if len(seg) > max_chars:
#                 # Force-split long segments
#                 for i in range(0, len(seg), max_chars):
#                     chunks.append(seg[i:i+max_chars])
#                 current_chunk = ""
#             else:
#                 current_chunk = seg

#     if current_chunk:
#         chunks.append(current_chunk)

#     return chunks