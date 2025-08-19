# # -*- coding: utf-8 -*-
# # 引用 SDK

# import asyncio
# import sys
import re
# import base64
# from concurrent.futures import as_completed
# from tts.speech_synthesizer_ws import SpeechSynthesizer, SpeechSynthesisListener
from utils.log import logger
# from utils.chk_version import is_python3
from utils.comm_utils import enqueue_audio
# from utils.credential import Credential

# Add parent directory of utils
# sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config.constants import TENCENT_APP_ID ,TENCENT_SECRET_ID, TENCENT_SECRET_KEY

VOICETYPE = 101001 # 音色类型
FASTVOICETYPE = ""
CODEC = "pcm" # 音频格式：pcm/mp3
SAMPLE_RATE = 16000 # 音频采样率：8000/16000
ENABLE_SUBTITLE = True

# # Capture main asyncio loop once at backend startup
# MAIN_LOOP = asyncio.get_event_loop()

# async def send_safe(fe_ws, b64_audio):
#     """Safely enqueue audio to FE websocket in async loop."""
#     try:
#         if not fe_ws.client_state.closed:
#             await enqueue_audio(fe_ws, b64_audio)
#     except Exception as e:
#         logger.warning(f"Skipping send, WS closed or error: {e}")

# class MySpeechSynthesisListener(SpeechSynthesisListener):
    
#     def __init__(self, id, codec, sample_rate, fe_websocket):
#         super().__init__()
#         self.id = id
#         self.codec = codec
#         self.sample_rate = sample_rate
#         self.fe_websocket = fe_websocket
#         self.audio_data = b''
#         self.audio_file = ""

#     def set_audio_file(self, filename):
#         self.audio_file = filename

#     def on_synthesis_start(self, session_id):
#         print(f"[DEBUG] TTS ws session id: {session_id}")
#         super().on_synthesis_start(session_id)
#         if not self.audio_file:
#             self.audio_file = f"speech_synthesis_output_{self.id}.{self.codec}"
#         self.audio_data = b''

#     def on_audio_result(self, audio_bytes):
#         super().on_audio_result(audio_bytes)
#         self.audio_data += audio_bytes  # accumulate

#     def on_synthesis_end(self):
#         super().on_synthesis_end()
#         b64_audio = base64.b64encode(self.audio_data).decode()
#         # enqueue audio safely in main event loop
#         #asyncio.run_coroutine_threadsafe(send_safe(self.fe_websocket, b64_audio), MAIN_LOOP)
#         logger.info(f"[DEBUG on_synthesis_end:] Sent sentence audio of size {len(self.audio_data)} to FE")

#     def on_synthesis_fail(self, response):
#         super().on_synthesis_fail(response)
#         err_code = response.get("code", "N/A")
#         err_msg = response.get("message", "")
#         print(f"[ERROR] TTS synthesis failed: code={err_code}, msg={err_msg}")

# async def process_sentence(text, sentence_id, fe_websocket):
#     print(f"[DEBUG] process text thru stream: {text}")
#     logger.info("process start: idx={} text={}".format(sentence_id, text))
#     listener = MySpeechSynthesisListener(sentence_id, CODEC, SAMPLE_RATE, fe_websocket)
#     credential_var = Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)
#     synthesizer = SpeechSynthesizer(
#         TENCENT_APP_ID, credential_var, listener)
#     synthesizer.set_text(text)
#     synthesizer.set_voice_type(VOICETYPE)
#     synthesizer.set_codec(CODEC)
#     synthesizer.set_sample_rate(SAMPLE_RATE)
#     synthesizer.set_enable_subtitle(ENABLE_SUBTITLE)
#     synthesizer.set_fast_voice_type(FASTVOICETYPE)
    
#     synthesizer.start()
#     # wait for processing complete
#     synthesizer.wait()

#     logger.info("process done: idx={} text={}".format(sentence_id, text))


def split_sentences(text: str):
    
    """
    Split Chinese / English text into sentences based on common punctuation.
    """
    # Define Chinese and English sentence enders
    pattern = r'[。！？.!?\n]+'
    # Split & clean
    sentences = re.split(pattern, text)
    logger.info("splitted sentence {}".format(sentences))
    return [s.strip() for s in sentences if s.strip()]


# async def process_tts_stream(full_text, fe_websocket):
#     logger.info("process_tts_stream {}:".format(full_text))
#     sentences = split_sentences(full_text)
#     for idx, sentence in enumerate(sentences):
#         # await process_sentence(sentence, idx, fe_websocket)
#         asyncio.create_task(asyncio.to_thread(
#     process_sentence, sentence, idx, fe_websocket
# ))


# def read_tts_text():
#     lines_list = []
#     with open('tts_text.txt', 'r', encoding='utf-8') as file:
#         for line in file:
#             lines_list.append(line.strip())
#     # print("total read {} lines".format(len(lines_list)))
#     return lines_list

# if __name__ == "__main__":
#     if not is_python3():
#         print("only support python3")
#         sys.exit(0)

#     # 读取示例文本
#     lines = read_tts_text()

#     #### 示例一：单线程串行调用 ####
#     for idx, line in enumerate(lines):
#         result = process_tts_stream(idx, line)
#         print(f"\nTask {result} completed\n")
    
#     #### 示例二：多线程调用 ####
#     # thread_concurrency_num = 3 # 最大线程数
#     # with ThreadPoolExecutor(max_workers=thread_concurrency_num) as executor:
#     #     futures = [executor.submit(process, idx, line) for idx, line in enumerate(lines)]
#     #     for future in as_completed(futures):
#     #         result = future.result()
#     #         print(f"\nTask {result} completed\n")

#     #### 示例三：多进程调用（适用于高并发场景） ####
#     # process_concurrency_num = 3 # 最大进程数
#     # with ProcessPoolExecutor(max_workers=process_concurrency_num) as executor:
#     #     futures = [executor.submit(process, idx, line) for idx, line in enumerate(lines)]
#     #     for future in as_completed(futures):
#     #         result = future.result()
#     #         print(f"\nTask {result} completed\n")


#######################################
import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor
from tencentcloud.tts.v20190823 import models
import tencentcloud.tts.v20190823.tts_client as tts_client

# Initialize ThreadPoolExecutor
executor = ThreadPoolExecutor(max_workers=5)

class AsyncTTSHandler:
    def __init__(self, app_id, secret_id, secret_key):
        self.client = tts_client.TtsClient(
            models.Credential(secret_id=secret_id, secret_key=secret_key),
            region="ap-guangzhou"
        )
        self.app_id = app_id

    async def synthesize(self, text, fe_websocket):
        def _run_tts():
            req = models.TextToVoiceRequest()
            req.AppId = self.app_id
            req.Text = text
            req.VoiceType = VOICETYPE
            req.Codec = CODEC
            req.SampleRate = SAMPLE_RATE
            
            response = self.client.TextToVoice(req)
            return base64.b64encode(response.Audio).decode()

        # Offload TTS to thread pool
        b64_audio = await asyncio.get_event_loop().run_in_executor(
            executor, _run_tts
        )
        
        # Send audio via WebSocket in main event loop
        logger.info("penqueue_audio ...")
        # await self._send_audio(fe_websocket, b64_audio)
        await enqueue_audio(fe_websocket, b64_audio)

    async def _send_audio(self, websocket, audio_data):
        if not websocket.closed:
            await websocket.send_text(audio_data)

async def process_tts_stream(full_text, fe_websocket):
    logger.info("process_tts_stream {}".format(full_text))
    handler = AsyncTTSHandler(TENCENT_APP_ID, TENCENT_SECRET_ID, TENCENT_SECRET_KEY)
    sentences = split_sentences(full_text)
    
    for idx, sentence in enumerate(sentences):
        await handler.synthesize(sentence, fe_websocket)