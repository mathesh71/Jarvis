# -----------------------------
# app.py — Jarvis + RAG (Professor Mode)
# -----------------------------

import platform
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import psutil
import speech_recognition as sr
import os
import time
from dotenv import load_dotenv
import webbrowser
import subprocess
import pyautogui
import cv2
import pyttsx3
from datetime import datetime
import socket
import pyjokes
import random
import urllib.parse
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import google.generativeai as genai
# Added missing TTS imports
from gtts import gTTS
from playsound import playsound
import tempfile

# RAG module you already have
import rag


# -----------------------------
# ENV + CONFIG
# -----------------------------
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
genai.configure(api_key=GEMINI_API_KEY)

WAKE_JARVIS = "jarvis"
WAKE_PROFESSOR = "professor"

ACTIVE_MODE = None  # None, "jarvis", "professor"


# -----------------------------
# FLASK SETUP
# -----------------------------
app = Flask(__name__, template_folder="../frontend", static_folder="../frontend")
app.config["SECRET_KEY"] = "secret"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")


# -----------------------------
# LOAD GEMINI MODEL
# -----------------------------
try:
    model = genai.GenerativeModel("models/gemini-2.5-flash")
    print("✅ Gemini loaded")
except Exception as e:
    model = None
    print("❌ Gemini failed:", e)


# -----------------------------
# LOAD FAISS INDEX
# -----------------------------
try:
    rag.load_faiss()
    print("✅ RAG index loaded")
except:
    print("⚠️ RAG: Starting new index")

# -----------------------------
# PYTTSX3 SPEAK SYSTEM (Thread-safe)
# -----------------------------
engine = pyttsx3.init()

voices = engine.getProperty("voices")
if len(voices) > 1:
    engine.setProperty("voice", voices[1].id)
else:
    engine.setProperty("voice", voices[0].id)

import queue
import threading

tts_queue = queue.Queue()

def speak(text):
    """Convert text to speech without opening Windows Media Player."""
    if not text:
        return
    try:
        tts = gTTS(text=text, lang='en')
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            temp_path = tmp.name
            tts.save(temp_path)

        playsound(temp_path)
        os.remove(temp_path)

    except Exception as e:
        print(f"❌ TTS Error: {e}")


def tts_worker():
    print("TTS Worker started...")
    while True:
        text = tts_queue.get()
        print("TTS Received:", text)
        try:
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            print("TTS ERROR:", e)
        tts_queue.task_done()


tts_thread = threading.Thread(target=tts_worker, daemon=True)
tts_thread.start()




# -----------------------------
# COMPUTER CONTROL FUNCTIONS
# -----------------------------
def control_computer(cmd):
    cmd = cmd.lower()
    try:
    # Browser
       if "open browser" in cmd:
            speak("Opening browser")
            webbrowser.open("https://google.com")
            return True

       elif "open youtube" in cmd:
            speak("Opening YouTube")
            webbrowser.open("https://youtube.com")
            return True

       elif "open gmail" in cmd:
        speak("Opening Gmail")
        webbrowser.open("https://mail.google.com")
        return True

    # Notepad
       elif "open notepad" in cmd:
        speak("Opening Notepad")
        subprocess.Popen(["notepad.exe"])
        return True

    # VS Code
       elif "open vscode" in cmd or "open visual studio code" in cmd:
        speak("Opening Visual Studio Code")
        possible = [
            rf"C:\Users\{os.getlogin()}\AppData\Local\Programs\Microsoft VS Code\Code.exe",
            r"C:\Program Files\Microsoft VS Code\Code.exe",
        ]
        for p in possible:
            if os.path.exists(p):
                subprocess.Popen([p])
                return True
        try:
            subprocess.Popen(["code"])
        except:
            speak("Could not open VS Code")
        return True
    
     # Shutdown + misc
       elif "shutdown" in cmd:
            speak("Are you sure? Please say yes or no.")
            r = sr.Recognizer()
            with sr.Microphone() as source:
                audio = r.listen(source)
            try:
                response = r.recognize_google(audio).lower()
                if "yes" in response:
                    speak("Shutting down your computer now.")
                    os.system("shutdown /s /t 0")
                else:
                    speak("Shutdown cancelled.")
            except:
                speak("Cancelling shutdown.")
                return True

    # WhatsApp
       elif "open whatsapp" in cmd:
        speak("Opening WhatsApp")
        p = rf"C:\Users\{os.getlogin()}\AppData\Local\WhatsApp\WhatsApp.exe"
        if os.path.exists(p):
            subprocess.Popen([p])
        else:
            webbrowser.open("https://web.whatsapp.com")
        return True
    
       elif "open instagram" in cmd:
            speak("Opening Instagram.")
            webbrowser.open("https://www.instagram.com")


    # Spotify
       elif "open spotify" in cmd:
        speak("Opening Spotify")
        webbrowser.open("https://open.spotify.com")
        return True
    
       elif "system info" in cmd:
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory().percent
            os_name = platform.system()
            version = platform.release()
            speak(f"You are using {os_name} {version}. CPU {cpu}% and RAM {ram}% used.")

       elif "check battery" in cmd:
        battery = psutil.sensors_battery()
        if battery:
            percent = battery.percent
            speak(f"Battery is at {percent} percent.")
            if battery.power_plugged:
                speak("Charging.")
            else:
                speak("Not charging.")
        else:
            speak("Battery info not available.")
        

            


       elif "open calculator" in cmd:
            speak("Opening calculator.")
            subprocess.Popen(["calc.exe"])

       elif "lock screen" in cmd:
            speak("Locking screen.")
            os.system("rundll32.exe user32.dll,LockWorkStation")

    # Time
       elif "time" in cmd:
        speak("The time is " + time.strftime("%I:%M %p"))
        return True
    
       elif "take note" in cmd:
            speak("What should I write?")
            r = sr.Recognizer()
            with sr.Microphone() as source:
                audio = r.listen(source)
                note_text = r.recognize_google(audio)
            notes_path = os.path.join(os.path.expanduser("~"), "Documents", "voice_notes.txt")
            with open(notes_path, "a") as f:
                f.write(f"\n{time.strftime('%Y-%m-%d %H:%M:%S')} - {note_text}")
            speak("Note saved successfully.")
            
       elif "show ip" in cmd or "ip address" in cmd:
            hostname = socket.gethostname()
            ip_address = socket.gethostbyname(hostname)
            speak(f"Your IP address is {ip_address}")

       elif "remember" in cmd:
            note = cmd.replace("remember", "").strip()
            with open("memory.txt", "a") as f:
                f.write(note + "\n")
            speak("I will remember that.")

       elif "what do you remember" in cmd:
            if os.path.exists("memory.txt"):
                with open("memory.txt", "r") as f:
                    memories = f.read()
                    speak(f"I remember you told me: {memories}")
            else:
                speak("I don't have any memories yet.")

       elif "who created you" in cmd or "who made you" in cmd or "who developed you" in cmd:
            speak("I was created by the two developers Manojkrishna and Mathesh. My mission: assist, learn, and evolve.")

       elif "roast me" in cmd:
           roasts = ["You're not stupid… you just have bad luck thinking.","Your brain has a loading screen.","If laziness was a job, you'd be CEO."]
           chosen_roast = random.choice(roasts)
           speak(chosen_roast)
           socketio.emit('ai_response', {'text': chosen_roast})

       elif "weather" in cmd:
          if "weather in" in cmd:
            city = cmd.replace("weather in", "").strip()
          else:
           city = cmd.replace("weather", "").strip()

          if city == "":
           city = "your location"

          speak(f"Here is the weather report for {city}.")
          webbrowser.open(f"https://www.google.com/search?q=weather+{city.replace(' ', '+')}")


    # Screenshot
       elif "screenshot" in cmd:
        path = os.path.join(os.path.expanduser("~"), "Pictures", "screenshot.png")
        pyautogui.screenshot(path)
        speak("Screenshot saved")
        return True

    # Camera
       elif "open camera" in cmd:
        cam = cv2.VideoCapture(0)
        ret, frame = cam.read()
        if ret:
            out = os.path.join(os.path.expanduser("~"), "Pictures", "photo.png")
            cv2.imwrite(out, frame)
            speak("Photo captured")
        else:
            speak("Camera error")
        cam.release()
        return True

    # Google search
       elif "search" in cmd:
        q = cmd.replace("search", "").strip()
        speak("Searching for " + q)
        webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote_plus(q))
        return True

    # Joke
       elif "joke" in cmd:
        joke = pyjokes.get_joke()
        speak(joke)
        

       else:
            return False
       return True
    except Exception as e:
        speak("There was an issue executing your command.")
        return False



# -----------------------------
# LLM RESPONSE
# -----------------------------
def ask_llm(prompt, max_words=30):
    """
    Ask Gemini model to generate content.
    Limits to max_words to prevent long answers.
    """
    try:
        # Force short response
        prompt = f"{prompt}\n\nAnswer briefly in 1 sentence or less:"
        r = model.generate_content(prompt)
        text = r.text.strip()
        # Truncate if too long
        words = text.split()
        if len(words) > max_words:
            text = " ".join(words[:max_words]) + "..."
        return text
    except Exception as e:
        print("LLM Error:", e)
        return "Model error."



# -----------------------------
# PROCESS COMMANDS
# -----------------------------
def process_professor_mode(cmd):
    """Strict RAG"""
    ctx = rag.retrieve_context(cmd, top_k=5)

    if not ctx:
        return "I don't know. No information in the documents."

    prompt = f"Use only this context to answer:\n\n{ctx}\n\nQuestion: {cmd}\nAnswer shortly:"
    return ask_llm(prompt)


def process_jarvis_mode(cmd):
    """Jarvis: LLM + Computer control only, no RAG"""
    # Check computer control first
    if control_computer(cmd):
        return None

    # LLM response directly from Gemini
    return ask_llm(cmd)



# -----------------------------
# MIC LISTEN EVENT
# -----------------------------
@socketio.on('listen_for_command')
def listen_for_command():
    # ACTIVE_MODE is defined at module level; declare global to modify it here
    global ACTIVE_MODE
    r = sr.Recognizer()
    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source, duration=0.5)
        socketio.emit('ai_update', {'state': 'listening'})
        print("Listening...")
        try:
            # wait up to 5s for phrase to start, and limit phrase length to 10s
            audio = r.listen(source, timeout=5, phrase_time_limit=10)
            socketio.emit('ai_update', {'state': 'processing'})
            voice_data = r.recognize_google(audio)
            socketio.emit('user_command', {'text': voice_data})
            print("Heard:", voice_data)

            text = voice_data.lower().strip()
            
            if text.startswith(WAKE_JARVIS):
              ACTIVE_MODE = "jarvis"
              speak("Jarvis online.")
              socketio.emit("ai_response", {"text": "Jarvis activated."})
              return

            elif text.startswith(WAKE_PROFESSOR):
             ACTIVE_MODE = "professor"
             speak("Professor mode activated.")
             socketio.emit("ai_response", {"text": "Professor mode online."})
             return

            if "stop listening" in text:
                ACTIVE_MODE = None
                speak("Standing by.")
                socketio.emit("ai_response", {"text": "Stopped listening."})
                return

            # No wake
            if ACTIVE_MODE is None:
                socketio.emit("ai_response", {"text": "Say a wake word."})
                return

            # Handle mode
            if ACTIVE_MODE == "jarvis":
                reply = process_jarvis_mode(text)
                if reply:
                    speak(reply)
                    socketio.emit("ai_response", {"text": reply})
                return

            if ACTIVE_MODE == "professor":
                reply = process_professor_mode(text)
                speak(reply)
                socketio.emit("ai_response", {"text": reply})
                return

        except sr.WaitTimeoutError:
            print("Error: listening timed out while waiting for phrase to start")
            socketio.emit("ai_response", {"text": "Listening timed out — please try again."})
        except sr.UnknownValueError:
            print("Error: could not understand audio")
            socketio.emit("ai_response", {"text": "Sorry, I didn't catch that."})
        except sr.RequestError as e:
            print("Error: speech recognition request failed:", e)
            socketio.emit("ai_response", {"text": "Speech recognition service error."})
        except Exception as e:
            print("Error:", e)
            socketio.emit("ai_response", {"text": "I didn't catch that."})


# -----------------------------
# ROUTES
# -----------------------------
@app.route("/")
def index():
    return render_template("index.html")


# -----------------------------
# START SERVER
# -----------------------------
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
