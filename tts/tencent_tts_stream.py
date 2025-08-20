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
#from utils.credential import Credential

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
# -*- coding: utf-8 -*-
import asyncio
import re
import base64
import json
import time
from concurrent.futures import ThreadPoolExecutor
from tts.speech_synthesizer_ws import SpeechSynthesizer, SpeechSynthesisListener
from utils.log import logger
from utils.credential import Credential
from config.constants import TENCENT_APP_ID, TENCENT_SECRET_ID, TENCENT_SECRET_KEY

VOICETYPE = 101019  # 音色类型
FASTVOICETYPE = ""
CODEC = "pcm"  # 音频格式：pcm/mp3
SAMPLE_RATE = 16000  # 音频采样率：8000/16000
ENABLE_SUBTITLE = True

# Thread pool for handling TTS requests - increased workers
executor = ThreadPoolExecutor(max_workers=10)

class MySpeechSynthesisListener(SpeechSynthesisListener):
    def __init__(self, sentence_id, codec, sample_rate, fe_websocket):
        super().__init__()
        self.sentence_id = sentence_id
        self.codec = codec
        self.sample_rate = sample_rate
        self.fe_websocket = fe_websocket
        self.audio_data = b''
        self.start_time = time.time()
        self.chunk_count = 0
        self.loop = asyncio.get_event_loop()

    def on_synthesis_start(self, session_id):
        logger.info(f"Synthesis started for sentence {self.sentence_id}, session: {session_id}")
        self.audio_data = b''

    def on_audio_result(self, audio_bytes):
        super().on_audio_result(audio_bytes)
        self.audio_data += audio_bytes
        self.chunk_count += 1
        
        # Send audio chunk immediately without waiting for full synthesis
        asyncio.run_coroutine_threadsafe(
            self.send_audio_chunk(audio_bytes), 
            self.loop
        )

    def on_synthesis_end(self):
        super().on_synthesis_end()
        processing_time = time.time() - self.start_time
        logger.info(f"Synthesis completed for sentence {self.sentence_id}: "
                   f"{len(self.audio_data)} bytes, {self.chunk_count} chunks, "
                   f"time: {processing_time:.2f}s")

    def on_synthesis_fail(self, response):
        super().on_synthesis_fail(response)
        err_code = response.get("code", "N/A")
        err_msg = response.get("message", "")
        logger.error(f"TTS synthesis failed for sentence {self.sentence_id}: {err_code}, {err_msg}")

    async def send_audio_chunk(self, audio_bytes):
        """Send individual audio chunks as they become available"""
        try:
            # Skip empty or very small audio chunks
            if len(audio_bytes) < 100:
                return
                
            # Convert to base64
            b64_audio = base64.b64encode(audio_bytes).decode()
            
            # Send to frontend immediately
            await self.fe_websocket.send_text(json.dumps({
                "type": "audio",
                "sentence_id": self.sentence_id,
                "payload": b64_audio,
                "format": CODEC,
                "sample_rate": SAMPLE_RATE,
                "chunk_size": len(audio_bytes)
            }))
            
            logger.debug(f"Sent audio chunk for sentence {self.sentence_id}: {len(audio_bytes)} bytes")
            
        except Exception as e:
            logger.warning(f"Failed to send audio chunk for sentence {self.sentence_id}: {e}")

def run_synthesizer(synthesizer):
    """Run the synthesizer in a thread"""
    synthesizer.start()
    synthesizer.wait()

async def process_sentence(text, sentence_id, fe_websocket):
    """Process a single sentence asynchronously"""
    logger.info(f"Starting TTS for sentence {sentence_id}: {text[:50]}...")
    
    listener = MySpeechSynthesisListener(sentence_id, CODEC, SAMPLE_RATE, fe_websocket)
    credential_var = Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)
    
    synthesizer = SpeechSynthesizer(
        TENCENT_APP_ID, credential_var, listener
    )
    synthesizer.set_text(text)
    synthesizer.set_voice_type(VOICETYPE)
    synthesizer.set_codec(CODEC)
    synthesizer.set_sample_rate(SAMPLE_RATE)
    synthesizer.set_enable_subtitle(ENABLE_SUBTITLE)
    synthesizer.set_fast_voice_type(FASTVOICETYPE)
    
    # Run synthesizer in thread pool to avoid blocking
    await asyncio.get_event_loop().run_in_executor(
        executor, run_synthesizer, synthesizer
    )
    
    logger.info(f"Completed TTS for sentence {sentence_id}")

def split_sentences(text: str):
    """Split Chinese/English text into sentences"""
    pattern = r'[。！？.!?\n]+'
    sentences = re.split(pattern, text)
    logger.info(f"Split text into {len(sentences)} sentences")
    return [s.strip() for s in sentences if s.strip()]

async def process_tts_stream(full_text, fe_websocket):
    """Process full text through TTS with parallel execution"""
    logger.info(f"Starting TTS stream processing: {full_text[:100]}...")
    start_time = time.time()
    
    sentences = split_sentences(full_text)
    
    # Create all TTS tasks to run in parallel
    tasks = []
    for idx, sentence in enumerate(sentences):
        task = asyncio.create_task(
            process_sentence(sentence, idx, fe_websocket)
        )
        tasks.append(task)
    
    # Wait for all tasks to complete with timeout
    try:
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=300)  # 5-minute timeout
    except asyncio.TimeoutError:
        logger.error("TTS processing timed out after 5 minutes")
        # Cancel all remaining tasks
        for task in tasks:
            if not task.done():
                task.cancel()
    
    processing_time = time.time() - start_time
    logger.info(f"Completed TTS stream processing in {processing_time:.2f} seconds")
    
    # Send completion message
    try:
        await fe_websocket.send_text(json.dumps({
            "type": "tts_complete",
            "total_sentences": len(sentences),
            "processing_time": processing_time
        }))
    except Exception as e:
        logger.warning(f"Failed to send completion message: {e}")