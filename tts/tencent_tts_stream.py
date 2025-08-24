# -*- coding: utf-8 -*-
import asyncio
import re
import base64
import json
import time
import io
import wave
from concurrent.futures import ThreadPoolExecutor
from tts.speech_synthesizer_ws import SpeechSynthesizer, SpeechSynthesisListener
from utils.log import logger
from utils.credential import Credential
from config.constants import TENCENT_APP_ID, TENCENT_SECRET_ID, TENCENT_SECRET_KEY

VOICETYPE = 101001  # 音色类型
FASTVOICETYPE = ""
CODEC = "pcm"  # 音频格式：pcm/mp3
SAMPLE_RATE = 16000  # 音频采样率：8000/16000
ENABLE_SUBTITLE = True

# Thread pool for handling TTS requests - increased workers
executor = ThreadPoolExecutor(max_workers=10)

def pcm_to_wav(pcm_data, sample_rate=16000, sample_width=2, channels=1):
    """Convert PCM data to WAV format with proper headers"""
    with io.BytesIO() as wav_buffer:
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_data)
        return wav_buffer.getvalue()

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

    def on_synthesis_end(self):
        super().on_synthesis_end()
        processing_time = time.time() - self.start_time
        
        # Convert PCM to WAV format
        wav_data = pcm_to_wav(self.audio_data, self.sample_rate)
        
        # Send complete WAV audio to frontend
        asyncio.run_coroutine_threadsafe(
            self.send_complete_audio(wav_data), 
            self.loop
        )
        
        logger.info(f"Synthesis completed for sentence {self.sentence_id}: "
                   f"{len(self.audio_data)} bytes PCM -> {len(wav_data)} bytes WAV, "
                   f"{self.chunk_count} chunks, time: {processing_time:.2f}s")

    def on_synthesis_fail(self, response):
        super().on_synthesis_fail(response)
        err_code = response.get("code", "N/A")
        err_msg = response.get("message", "")
        logger.error(f"TTS synthesis failed for sentence {self.sentence_id}: {err_code}, {err_msg}")

    async def send_complete_audio(self, wav_data):
        """Send complete WAV audio to frontend"""
        try:
            # Convert to base64
            b64_audio = base64.b64encode(wav_data).decode()
            
            # Send to frontend
            await self.fe_websocket.send_text(json.dumps({
                "type": "audio",
                "sentence_id": self.sentence_id,
                "data": b64_audio,
                "format": "wav",
                "sample_rate": self.sample_rate,
                "size": len(wav_data)
            }))
            
            logger.info(f"Sent complete WAV audio for sentence {self.sentence_id}: {len(wav_data)} bytes")
            
        except Exception as e:
            logger.error(f"Failed to send audio for sentence {self.sentence_id}: {e}")

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