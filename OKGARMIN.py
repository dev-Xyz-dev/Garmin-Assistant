import sys
import os
import subprocess

# ──────────────── 1️⃣ Installer les dépendances manquantes ────────────────
required_modules = ["keyboard", "playsound", "sounddevice", "vosk", "requests"]
for module in required_modules:
    try:
        __import__(module)
    except ImportError:
        print(f"Module '{module}' manquant, installation...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", module])

# ──────────────── 2️⃣ Imports ────────────────
import keyboard
from playsound import playsound
import time
import json
from pathlib import Path
import sounddevice as sd
import queue
from vosk import Model, KaldiRecognizer
import webbrowser
import requests
import shutil
import zipfile

# ──────────────── Suppression ancien backup ────────────────
bak_path = "OKGARMIN.bak"  
if os.path.exists(bak_path):
    os.remove(bak_path)
    print(f"Ancien backup supprimé : {bak_path}")

# ──────────────── 3️⃣ Configuration du script ────────────────
__version__ = "1.0.6"

# ──────────────── URLs cassées en 3 parties ────────────────
v_part1 = "https://raw."
v_part2 = "githubuser"
v_part3 = "content.com/dev-Xyz-dev/Garmin-Assistant/main/version.txt"
VERSION_URL = v_part1 + v_part2 + v_part3

s_part1 = "https://raw."
s_part2 = "githubuser"
s_part3 = "content.com/dev-Xyz-dev/Garmin-Assistant/main/OKGARMIN.py"
SCRIPT_URL = s_part1 + s_part2 + s_part3

MP3_URLS = {
    "bip.mp3": "https://raw." + "githubuser" + "content.com/dev-Xyz-dev/Garmin-Assistant/main/bip.mp3",
    "bipok.mp3": "https://raw." + "githubuser" + "content.com/dev-Xyz-dev/Garmin-Assistant/main/bipok.mp3"
}

m_part1 = "https://alphacep"
m_part2 = "hei.com/vosk/"
m_part3 = "models/vosk-model-small-fr-0.22.zip"
MODEL_URL = m_part1 + m_part2 + m_part3

CONFIG_FILE = Path("config.json")
TRIGGER_WAKE = "garmin"
TRIGGER_CLIP = "la vidéo"
TRIGGER_SNAP = "pornhub"
AFTER_WAKE_TIMEOUT = 3.5

MP3_PATH = Path("bip.mp3")
BIP_OK_PATH = Path("bipok.mp3")
MODEL_PATH = Path("vosk-model-small-fr-0.22")

# ──────────────── 4️⃣ Gestion des mises à jour ────────────────
def download_file(url, dest):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(dest, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    print(f"Téléchargé : {dest}")

def update_script(new_version):
    try:
        response = requests.get(SCRIPT_URL)
        response.raise_for_status()
        script_path = Path(__file__).resolve()
        backup_path = script_path.with_suffix(".bak")
        shutil.copyfile(script_path, backup_path)
        print(f"Sauvegarde du script existant : {backup_path}")
        with open(script_path, "wb") as f:
            f.write(response.content)
        print(f"Script mis à jour vers {new_version}")

        for name, url in MP3_URLS.items():
            download_file(url, Path(name))

        if not MODEL_PATH.exists():
            zip_path = MODEL_PATH.with_suffix(".zip")
            print(f"Téléchargement du modèle Vosk depuis {MODEL_URL}")
            download_file(MODEL_URL, zip_path)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(MODEL_PATH.parent)
            os.remove(zip_path)
            print("Modèle Vosk prêt à l'emploi.")

        print("Mise à jour terminée ! Relancez le script.")
        sys.exit(0)
    except Exception as e:
        print(f"Erreur lors de la mise à jour : {e}")

def check_for_updates():
    try:
        response = requests.get(VERSION_URL, timeout=5)
        response.raise_for_status()
        remote_version = response.text.strip()
        if remote_version > __version__:
            print(f"\nNouvelle version disponible : {remote_version} (votre version : {__version__})")
            update_script(remote_version)
        else:
            print(f"Vous utilisez la dernière version ({__version__}).\n")
    except requests.RequestException:
        print("Aucune connexion ou impossible de vérifier les mises à jour. Continuation offline...")

# ──────────────── 5️⃣ Configuration du micro ────────────────
if CONFIG_FILE.exists():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
else:
    config = {}

if "mic_index" not in config:
    print("🔍 Micros disponibles :")
    for i, mic_name in enumerate(sd.query_devices()):
        print(f"{i}: {mic_name['name']}")
    mic_index = int(input("Entrez le numéro du micro à utiliser : "))
    config["mic_index"] = mic_index
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print(f"Micro {mic_index} sauvegardé dans {CONFIG_FILE}")
else:
    mic_index = config["mic_index"]

# ──────────────── 6️⃣ Téléchargement modèle Vosk si absent ────────────────
if not MODEL_PATH.exists():
    zip_path = MODEL_PATH.with_suffix(".zip")
    print(f"Téléchargement modèle depuis {MODEL_URL}")
    download_file(MODEL_URL, zip_path)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(MODEL_PATH.parent)
    os.remove(zip_path)
    print("Modèle prêt à l'emploi.")

# ──────────────── 7️⃣ Initialisation Vosk ────────────────
model = Model(str(MODEL_PATH))
recognizer = KaldiRecognizer(model, 16000)
q = queue.Queue()

def callback(indata, frames, time_info, status):
    if status:
        print(status, flush=True)
    q.put(bytes(indata))

def listen_for_phrase(timeout=3):
    start_time = time.time()
    with sd.RawInputStream(samplerate=16000, blocksize=8000, device=mic_index,
                           dtype='int16', channels=1, callback=callback):
        while time.time() - start_time < timeout:
            data = q.get()
            if recognizer.AcceptWaveform(data):
                res = json.loads(recognizer.Result())
                result_text = res.get("text", "").lower()
                if result_text:
                    return result_text
        res = json.loads(recognizer.FinalResult())
        return res.get("text", "").lower()

# ──────────────── 8️⃣ Boucle principale ────────────────
def main():
    print("🎙 Assistant prêt. Dites 'Ok Garmin'.")
    state = "idle"
    wake_time = 0

    while True:
        if state == "idle":
            cmd = listen_for_phrase(timeout=5)
            if cmd and TRIGGER_WAKE in cmd:
                print("Activation détectée")
                playsound(str(MP3_PATH))
                state = "after_wake"
                wake_time = time.time()

        elif state == "after_wake":
            remaining = AFTER_WAKE_TIMEOUT - (time.time() - wake_time)
            if remaining <= 0:
                print("Temps écoulé, retour en veille.")
                state = "idle"
                continue

            cmd = listen_for_phrase(timeout=remaining)
            if cmd:
                if TRIGGER_CLIP in cmd:
                    print("Commande détectée → '='")
                    keyboard.press_and_release('=')
                    playsound(str(BIP_OK_PATH))
                    state = "idle"
                elif TRIGGER_SNAP in cmd:
                    print("Commande détectée → ouverture Ph")
                    webbrowser.open("https://pornhub.com")
                    playsound(str(BIP_OK_PATH))
                    state = "idle"
                else:
                    print(f"Commande inconnue : {cmd}")

# ──────────────── 9️⃣ Démarrage ────────────────
if __name__ == "__main__":
    check_for_updates()
    main()

