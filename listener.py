import json
import queue
import os
import time
import logging
import sounddevice as sd
import pyautogui
import winsound
from vosk import Model, KaldiRecognizer

# auto-find model folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = next(
    (os.path.join(BASE_DIR, f) for f in os.listdir(BASE_DIR)
     if f.startswith("vosk-model") and os.path.isdir(os.path.join(BASE_DIR, f))),
    None
)
if MODEL_PATH is None:
    raise FileNotFoundError("No vosk-model folder found next to the script.")

SAMPLE_RATE = 16000
MUTE_WORD = "mute"
EXIT_WORD = "exit"
DISCORD_HOTKEY = ("ctrl", "alt")  # change if needed
COOLDOWN_SEC = 1.5

LOG_FILE = os.path.join(BASE_DIR, "log.txt")
LOG_MAX_SIZE = 50 * 1024 * 1024  # 50MB


class CappedFileHandler(logging.Handler):
    def __init__(self, filepath, max_bytes):
        super().__init__()
        self.filepath = filepath
        self.max_bytes = max_bytes

    def emit(self, record):
        msg = self.format(record) + "\n"
        if os.path.exists(self.filepath):
            with open(self.filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()
        else:
            lines = []

        while lines and (sum(len(l.encode("utf-8")) for l in lines) + len(msg.encode("utf-8")) > self.max_bytes):
            lines.pop(0)

        lines.append(msg)

        with open(self.filepath, "w", encoding="utf-8") as f:
            f.writelines(lines)


# logger setup
logger = logging.getLogger("listener")
logger.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

file_handler = CappedFileHandler(LOG_FILE, LOG_MAX_SIZE)
file_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

audio_queue = queue.Queue()
last_trigger = 0


def audio_callback(indata, frames, time_info, status):
    audio_queue.put(bytes(indata))


def main():
    global last_trigger
    last_trigger = 0

    logger.info("Loading model...")
    model = Model(MODEL_PATH)
    rec = KaldiRecognizer(model, SAMPLE_RATE)

    logger.info(f'Listening for "{MUTE_WORD}" or "{EXIT_WORD}"...\n')

    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=4000,
                           dtype="int16", channels=1, callback=audio_callback):

        while True:
            data = audio_queue.get()

            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                text = result.get("text", "").lower()

                if text:
                    logger.info(f"Heard: {text}")

                # EXIT
                if EXIT_WORD in text:
                    logger.info(">>> Exiting... bye")
                    winsound.Beep(600, 300)
                    break

                # MUTE
                if MUTE_WORD in text:
                    now = time.time()
                    if now - last_trigger > COOLDOWN_SEC:
                        logger.info(">>> Toggling Discord mute")
                        pyautogui.hotkey(*DISCORD_HOTKEY)
                        last_trigger = now


if __name__ == "__main__":
    main()