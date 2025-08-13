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
import json as js
from vosk import Model, KaldiRecognizer
import os
import webbrowser
import requests
import shutil
# ────────────────Supp old ver────────────────
bak_path = "OKGARMIN.py.bak"
if os.path.exists(bak_path):
    os.remove(bak_path)
    print(f"Ancien backup supprimé : {bak_path}")

# ──────────────── 3️⃣ Configuration du script ────────────────
__version__ = "1.0.4"
VERSION_URL = "https://raw.githubusercontent.com/dev-Xyz-dev/Garmin-Assistant/main/version.txt"
SCRIPT_URL = "https://raw.githubusercontent.com/dev-Xyz-dev/Garmin-Assistant/main/OKGARMIN.py"

CONFIG_FILE = Path("config.json")
TRIGGER_WAKE = "garmin"
TRIGGER_CLIP = "la vidéo"
TRIGGER_SNAP = "pornhub"
AFTER_WAKE_TIMEOUT = 3.5
MP3_PATH = str(Path(__file__).parent / "bip.mp3")

# ──────────────── 4️⃣ Gestion des mises à jour ────────────────
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

def update_script(new_version):
    try:
        response = requests.get(SCRIPT_URL)
        response.raise_for_status()
        script_path = os.path.realpath(__file__)
        backup_path = script_path + ".bak"

        # Création de la sauvegarde
        shutil.copyfile(script_path, backup_path)
        print(f"Sauvegarde du script existant : {backup_path}")

        # Écriture du nouveau script
        with open(script_path, "wb") as f:
            f.write(response.content)

        print(f"Mise à jour vers la version {new_version} terminée !")

        # Suppression automatique de l'ancien backup
        if os.path.exists(backup_path):
            os.remove(backup_path)
            print(f"Ancien backup {backup_path} supprimé.")

        print("Relancez le script pour appliquer les changements.")
        sys.exit(0)
    except requests.RequestException as e:
        print(f"Erreur lors de la mise à jour : {e}")
    except Exception as e:
        print(f"Erreur inattendue : {e}")

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

# ──────────────── 6️⃣ Téléchargement et extraction du modèle Vosk ────────────────
MODEL_PATH = Path(__file__).parent / "vosk-model-small-fr-0.22"
MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip"

if not MODEL_PATH.exists():
    zip_path = MODEL_PATH.with_suffix(".zip")
    print(f"Modèle introuvable, téléchargement depuis {MODEL_URL}...")
    
    with requests.get(MODEL_URL, stream=True) as r:
        r.raise_for_status()
        with open(zip_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    print(f"Téléchargement terminé : {zip_path}")

    print("Décompression du modèle...")
    import zipfile
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(MODEL_PATH.parent)

    os.remove(zip_path)
    print("ZIP supprimé, modèle prêt à l'emploi.")

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
                res = js.loads(recognizer.Result())
                result_text = res.get("text", "").lower()
                if result_text:
                    return result_text
        res = js.loads(recognizer.FinalResult())
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
                playsound(MP3_PATH)
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
                    state = "idle"
                elif TRIGGER_SNAP in cmd:
                    print("Commande détectée → ouverture Ph")
                    webbrowser.open("https://pornhub.com")
                    state = "idle"
                else:
                    print(f"Commande inconnue : {cmd}")

# ──────────────── 9️⃣ Démarrage ────────────────
if __name__ == "__main__":
    check_for_updates()
    main()




