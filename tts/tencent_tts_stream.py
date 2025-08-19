# -*- coding: utf-8 -*-
# 引用 SDK

import asyncio
import sys

import wave
import time
import base64
from concurrent.futures import as_completed
from tts.speech_synthesizer_ws import SpeechSynthesizer, SpeechSynthesisListener
from utils.log import logger
from utils.chk_version import is_python3
from utils.comm_utils import enqueue_audio
from utils.credential import Credential

# Add parent directory of utils
# sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config.constants import TENCENT_APP_ID ,TENCENT_SECRET_ID, TENCENT_SECRET_KEY

VOICETYPE = 101001 # 音色类型
FASTVOICETYPE = ""
CODEC = "pcm" # 音频格式：pcm/mp3
SAMPLE_RATE = 16000 # 音频采样率：8000/16000
ENABLE_SUBTITLE = True

# Capture main asyncio loop once at backend startup
MAIN_LOOP = asyncio.get_event_loop()

class MySpeechSynthesisListener(SpeechSynthesisListener):
    
    def __init__(self, id, codec, sample_rate, fe_websocket):
        super().__init__()
        self.id = id
        self.codec = codec
        self.sample_rate = sample_rate
        self.fe_websocket = fe_websocket
        self.audio_data = b''
        self.audio_file = ""
    
    def set_audio_file(self, filename):
        self.audio_file = filename

    def on_synthesis_start(self, session_id):
        '''
        session_id: 请求session id，类型字符串
        '''
        print(f"[DEBUG] TTS ws session id: {session_id}")
        super().on_synthesis_start(session_id)
        
        # TODO 合成开始，添加业务逻辑
        if not self.audio_file:
            self.audio_file = "speech_synthesis_output_" + str(self.id) + "." + self.codec
        self.audio_data = bytes()

    def on_synthesis_end(self):
        super().on_synthesis_end()
        # Convert to base64
        b64_audio = base64.b64encode(self.audio_data).decode()
        # Send to FE safely using asyncio thread-safe call
        asyncio.run_coroutine_threadsafe(
            enqueue_audio(self.fe_websocket, b64_audio), MAIN_LOOP
        )
        # Optionally log
        print(f"[DEBUG] Sent sentence audio of size {len(self.audio_data)} to FE")

    def on_audio_result(self, audio_bytes):
        super().on_audio_result(audio_bytes)
        self.audio_data += audio_bytes  # accumulate

    def on_synthesis_complete(self, session_id):
        print(f"[INFO] Synthesis complete: {session_id}")

    def on_text_result(self, response):
        '''
        response: 文本结果，类型 dict，如下
        字段名       类型         说明
        code        int         错误码（无需处理，SpeechSynthesizer中已解析，错误消息路由至 on_synthesis_fail）
        message     string      错误信息
        session_id  string      回显客户端传入的 session id
        request_id  string      请求 id，区分不同合成请求，一次 websocket 通信中，该字段相同
        message_id  string      消息 id，区分不同 websocket 消息
        final       bool        合成是否完成（无需处理，SpeechSynthesizer中已解析）
        result      Result      文本结果结构体

        Result 结构体
        字段名       类型                说明
        subtitles   array of Subtitle  时间戳数组
        
        Subtitle 结构体
        字段名       类型     说明
        Text        string  合成文本
        BeginTime   int     开始时间戳
        EndTime     int     结束时间戳
        BeginIndex  int     开始索引
        EndIndex    int     结束索引
        Phoneme     string  音素
        '''
        super().on_text_result(response)

        # TODO 接收到文本数据，添加业务逻辑
        result = response["result"]
        subtitles = []
        if "subtitles" in result and len(result["subtitles"]) > 0:
            subtitles = result["subtitles"]

    def on_synthesis_fail(self, response):
        '''
        response: 文本结果，类型 dict，如下
        字段名 类型
        code        int         错误码
        message     string      错误信息
        '''
        super().on_synthesis_fail(response)

        # TODO 合成失败，添加错误处理逻辑
        err_code = response["code"]
        err_msg = response["message"]

        print(f"[ERROR] err_msg: {err_msg}, err_code: {err_code}")
        

async def process_sentence(text, sentence_id, fe_websocket):
    print(f"[DEBUG] process text thru stream: {text}")
    logger.info("process start: idx={} text={}".format(sentence_id, text))
    listener = MySpeechSynthesisListener(sentence_id, CODEC, SAMPLE_RATE, fe_websocket)
    credential_var = Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)
    synthesizer = SpeechSynthesizer(
        TENCENT_APP_ID, credential_var, listener)
    synthesizer.set_text(text)
    synthesizer.set_voice_type(VOICETYPE)
    synthesizer.set_codec(CODEC)
    synthesizer.set_sample_rate(SAMPLE_RATE)
    synthesizer.set_enable_subtitle(ENABLE_SUBTITLE)
    synthesizer.set_fast_voice_type(FASTVOICETYPE)
    
    synthesizer.start()
    # wait for processing complete
    synthesizer.wait()

    logger.info("process done: idx={} text={}".format(sentence_id, text))


def split_sentences(text: str):
    """
    Split Chinese / English text into sentences based on common punctuation.
    """
    # Define Chinese and English sentence enders
    pattern = r'[。！？.!?\n]+'
    # Split & clean
    sentences = re.split(pattern, text)
    return [s.strip() for s in sentences if s.strip()]


async def process_tts_stream(full_text, fe_websocket):
    sentences = split_sentences(full_text)
    for idx, sentence in enumerate(sentences):
        await process_sentence(sentence, idx, fe_websocket)

def read_tts_text():
    lines_list = []
    with open('tts_text.txt', 'r', encoding='utf-8') as file:
        for line in file:
            lines_list.append(line.strip())
    # print("total read {} lines".format(len(lines_list)))
    return lines_list

if __name__ == "__main__":
    if not is_python3():
        print("only support python3")
        sys.exit(0)

    # 读取示例文本
    lines = read_tts_text()

    #### 示例一：单线程串行调用 ####
    for idx, line in enumerate(lines):
        result = process_tts_stream(idx, line)
        print(f"\nTask {result} completed\n")
    
    #### 示例二：多线程调用 ####
    # thread_concurrency_num = 3 # 最大线程数
    # with ThreadPoolExecutor(max_workers=thread_concurrency_num) as executor:
    #     futures = [executor.submit(process, idx, line) for idx, line in enumerate(lines)]
    #     for future in as_completed(futures):
    #         result = future.result()
    #         print(f"\nTask {result} completed\n")

    #### 示例三：多进程调用（适用于高并发场景） ####
    # process_concurrency_num = 3 # 最大进程数
    # with ProcessPoolExecutor(max_workers=process_concurrency_num) as executor:
    #     futures = [executor.submit(process, idx, line) for idx, line in enumerate(lines)]
    #     for future in as_completed(futures):
    #         result = future.result()
    #         print(f"\nTask {result} completed\n")
