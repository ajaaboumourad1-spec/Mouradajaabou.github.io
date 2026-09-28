"""Crea uno YouTube Short completo da un solo argomento, a costo zero.

1. Gemini API (fascia gratuita) scrive il testo arabo e 4 descrizioni di immagini
2. Pollinations.ai (gratis, senza chiave) genera le 4 immagini verticali
3. crea_short.py genera la voce araba e monta il video

Uso:
  python automatico.py "le api riconoscono i volti umani"

Serve la variabile d'ambiente GEMINI_API_KEY (chiave gratuita da https://aistudio.google.com/apikey).
"""

import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

import crea_short

MODELLO_GEMINI = "gemini-2.5-flash"
NUMERO_IMMAGINI = 4
TENTATIVI_IMMAGINE = 3
ATTESA_TRA_TENTATIVI = 20       # secondi: Pollinations senza chiave accetta circa 1 richiesta ogni 15 s
CARTELLA_VIDEO = crea_short.CARTELLA / "video"
CARTELLA_VECCHIE = crea_short.CARTELLA / "immagini_vecchie"

PROMPT_GEMINI = """Sei l'autore di un canale YouTube Shorts in lingua araba.
Argomento: {argomento}

Rispondi SOLO con un oggetto JSON con questi campi:
- "testo": il testo parlato in arabo standard, tra 55 e 70 parole, che inizia con una frase che cattura
  l'attenzione e finisce invitando a seguire il canale. Niente emoji, titoli o indicazioni di regia.
- "immagini": una lista di esattamente {n} descrizioni IN INGLESE, una per ogni parte del testo, in ordine.
  Ogni descrizione: scena fotografica realistica, verticale, soggetto al centro, senza testo né scritte.
"""


def chiedi_a_gemini(argomento: str, chiave: str) -> tuple[str, list[str]]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELLO_GEMINI}:generateContent"
    corpo = {
        "contents": [{"parts": [{"text": PROMPT_GEMINI.format(argomento=argomento, n=NUMERO_IMMAGINI)}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    richiesta = urllib.request.Request(
        url,
        data=json.dumps(corpo).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": chiave},
    )
    try:
        with urllib.request.urlopen(richiesta, timeout=60) as risposta:
            dati = json.load(risposta)
    except urllib.error.HTTPError as errore:
        dettaglio = errore.read().decode("utf-8", errors="replace")[:500]
        if errore.code == 429:
            sys.exit("Gemini: limite gratuito raggiunto per oggi o per questo minuto. Riprova più tardi.")
        if errore.code == 404:
            sys.exit(f"Gemini: modello '{MODELLO_GEMINI}' non trovato. Cambia MODELLO_GEMINI in automatico.py.")
        sys.exit(f"Gemini: errore {errore.code}. Controlla la chiave GEMINI_API_KEY.\n{dettaglio}")
    except urllib.error.URLError as errore:
        sys.exit(f"Gemini: impossibile collegarsi ({errore.reason}). Controlla internet.")

    try:
        contenuto = json.loads(dati["candidates"][0]["content"]["parts"][0]["text"])
        testo = contenuto["testo"].strip()
        immagini = [str(d).strip() for d in contenuto["immagini"]][:NUMERO_IMMAGINI]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        sys.exit(f"Gemini ha risposto in un formato inatteso. Riprova.\n{json.dumps(dati)[:500]}")
    if not testo or len(immagini) < NUMERO_IMMAGINI:
        sys.exit("Gemini ha restituito un testo vuoto o meno immagini del previsto. Riprova.")
    return testo, immagini


def scarica_immagine(descrizione: str, destinazione, seme: int) -> None:
    prompt = f"{descrizione}, vertical 9:16, photorealistic, no text"
    url = (
        "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt)
        + "?" + urllib.parse.urlencode({"width": 1080, "height": 1920, "seed": seme, "nologo": "true"})
    )
    richiesta = urllib.request.Request(url, headers={"User-Agent": "crea-short/1.0"})
    for tentativo in range(1, TENTATIVI_IMMAGINE + 1):
        try:
            with urllib.request.urlopen(richiesta, timeout=180) as risposta:
                tipo = risposta.headers.get("Content-Type", "")
                dati = risposta.read()
            if tipo.startswith("image/") and len(dati) > 10_000:
                destinazione.write_bytes(dati)
                return
            motivo = f"risposta non valida ({tipo}, {len(dati)} byte)"
        except (urllib.error.URLError, TimeoutError) as errore:
            motivo = str(getattr(errore, "reason", errore))
        print(f"   tentativo {tentativo}/{TENTATIVI_IMMAGINE} fallito: {motivo}")
        if tentativo < TENTATIVI_IMMAGINE:
            time.sleep(ATTESA_TRA_TENTATIVI)
    sys.exit("Pollinations non risponde. Riprova più tardi, oppure metti le tue immagini in 'immagini/' "
             "e usa: python crea_short.py")


def metti_da_parte_immagini_vecchie() -> None:
    vecchie = [p for p in crea_short.CARTELLA_IMMAGINI.glob("*") if p.suffix.lower() in crea_short.ESTENSIONI]
    if not vecchie:
        return
    archivio = CARTELLA_VECCHIE / datetime.now().strftime("%Y%m%d_%H%M%S")
    archivio.mkdir(parents=True)
    for p in vecchie:
        shutil.move(str(p), str(archivio / p.name))
    print(f"   immagini precedenti spostate in {archivio}")


def nome_file(argomento: str) -> str:
    base = re.sub(r"[^\w-]+", "_", argomento, flags=re.UNICODE).strip("_")[:40] or "short"
    return f"{datetime.now():%Y%m%d_%H%M}_{base}.mp4"


def main() -> None:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        sys.exit('Uso: python automatico.py "argomento del video"')
    argomento = sys.argv[1].strip()

    chiave = os.environ.get("GEMINI_API_KEY", "").strip()
    if not chiave:
        sys.exit("Manca GEMINI_API_KEY. Crea una chiave gratuita su https://aistudio.google.com/apikey\n"
                 'poi esegui: setx GEMINI_API_KEY "la-tua-chiave"  e riapri il terminale.')
    crea_short.controlla_ffmpeg()

    print("1/4 Gemini scrive il testo e le scene...")
    testo, descrizioni = chiedi_a_gemini(argomento, chiave)
    crea_short.FILE_TESTO.write_text(testo, encoding="utf-8")
    print(testo)

    print(f"2/4 Genero {NUMERO_IMMAGINI} immagini (circa 20-30 secondi l'una)...")
    crea_short.CARTELLA_IMMAGINI.mkdir(exist_ok=True)
    metti_da_parte_immagini_vecchie()
    seme = int(time.time()) % 1_000_000
    immagini = []
    for i, descrizione in enumerate(descrizioni, start=1):
        print(f"   immagine {i}: {descrizione}")
        destinazione = crea_short.CARTELLA_IMMAGINI / f"{i}.jpg"
        scarica_immagine(descrizione, destinazione, seme + i)
        immagini.append(destinazione)
        if i < len(descrizioni):
            time.sleep(ATTESA_TRA_TENTATIVI)

    print("3/4 Genero la voce...")
    crea_short.genera_voce(testo, crea_short.FILE_VOCE)

    print("4/4 Monto il video...")
    CARTELLA_VIDEO.mkdir(exist_ok=True)
    file_video = CARTELLA_VIDEO / nome_file(argomento)
    crea_short.monta_video(immagini, crea_short.FILE_VOCE, file_video)
    print(f"Fatto: {file_video}")


if __name__ == "__main__":
    main()
