"""Crea uno YouTube Short completo da un solo argomento, a costo zero.

1. Gemini API (fascia gratuita) scrive il testo arabo e 4 descrizioni di immagini
2. Pollinations.ai (gratis, senza chiave) genera le 4 immagini verticali
3. crea_short.py genera la voce araba e monta il video

Strada ibrida: se in immagini/ c'è già una clip fatta a mano (es. 1.mp4 creata con
l'app Gemini), la clip prende il posto della prima scena e le immagini generate
sono solo quelle che mancano.

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

MODELLO_GEMINI = ""             # vuoto = sceglie da solo il modello Flash migliore disponibile
MAX_MODELLI_DA_PROVARE = 6
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


API_GEMINI = "https://generativelanguage.googleapis.com/v1beta"
PAROLE_ESCLUSE = ("image", "tts", "audio", "live", "embedding", "vision", "learnlm", "robotics", "computer-use")


def modelli_disponibili(chiave: str) -> list[str]:
    """Chiede a Google quali modelli Flash di testo può usare questa chiave, dal più nuovo al più vecchio."""
    richiesta = urllib.request.Request(f"{API_GEMINI}/models?pageSize=1000", headers={"x-goog-api-key": chiave})
    try:
        with urllib.request.urlopen(richiesta, timeout=30) as risposta:
            elenco = json.load(risposta).get("models", [])
    except urllib.error.HTTPError as errore:
        if errore.code in (400, 401, 403):
            sys.exit("Gemini: la chiave GEMINI_API_KEY non è valida. Creane una nuova su "
                     "https://aistudio.google.com/apikey")
        sys.exit(f"Gemini: errore {errore.code} nel leggere l'elenco dei modelli.")
    except urllib.error.URLError as errore:
        sys.exit(f"Gemini: impossibile collegarsi ({errore.reason}). Controlla internet.")

    nomi = []
    for modello in elenco:
        nome = modello.get("name", "").removeprefix("models/")
        if ("generateContent" in modello.get("supportedGenerationMethods", [])
                and "flash" in nome and not any(parola in nome for parola in PAROLE_ESCLUSE)):
            nomi.append(nome)

    def priorita(nome: str) -> tuple:
        versione = re.search(r"gemini-(\d+(?:\.\d+)?)", nome)
        sperimentale = any(parola in nome for parola in ("preview", "exp", "latest"))
        # prima i modelli stabili, poi i più nuovi, poi Flash normale prima di Flash-Lite
        return (sperimentale, -float(versione.group(1)) if versione else 0.0, "lite" in nome, nome)

    return sorted(nomi, key=priorita)


def chiama_gemini(modello: str, corpo: dict, chiave: str) -> dict:
    richiesta = urllib.request.Request(
        f"{API_GEMINI}/models/{modello}:generateContent",
        data=json.dumps(corpo).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": chiave},
    )
    with urllib.request.urlopen(richiesta, timeout=90) as risposta:
        return json.load(risposta)


def chiedi_a_gemini(argomento: str, chiave: str) -> tuple[str, list[str]]:
    corpo = {
        "contents": [{"parts": [{"text": PROMPT_GEMINI.format(argomento=argomento, n=NUMERO_IMMAGINI)}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    candidati = [MODELLO_GEMINI] if MODELLO_GEMINI else []
    candidati += [m for m in modelli_disponibili(chiave) if m not in candidati]
    if not candidati:
        sys.exit("Gemini: nessun modello Flash disponibile per questa chiave.")

    dati = None
    limite_raggiunto = False
    for modello in candidati[:MAX_MODELLI_DA_PROVARE]:
        try:
            dati = chiama_gemini(modello, corpo, chiave)
            print(f"   modello usato: {modello}")
            break
        except urllib.error.HTTPError as errore:
            dettaglio = errore.read().decode("utf-8", errors="replace")[:300]
            if errore.code in (404, 429):
                # 404: modello ritirato; 429: limite gratuito finito o modello non incluso nel piano gratuito
                limite_raggiunto |= errore.code == 429
                print(f"   {modello} non disponibile (errore {errore.code}), provo il prossimo...")
                continue
            if errore.code in (400, 401, 403) and "API key" in dettaglio:
                sys.exit("Gemini: la chiave GEMINI_API_KEY non è valida.")
            sys.exit(f"Gemini: errore {errore.code} con il modello {modello}.\n{dettaglio}")
        except urllib.error.URLError as errore:
            sys.exit(f"Gemini: impossibile collegarsi ({errore.reason}). Controlla internet.")
    if dati is None:
        if limite_raggiunto:
            sys.exit("Gemini: limite gratuito raggiunto su tutti i modelli provati. Riprova tra qualche minuto "
                     "o domani.")
        sys.exit("Gemini: nessuno dei modelli provati ha funzionato.")

    try:
        contenuto = json.loads(dati["candidates"][0]["content"]["parts"][0]["text"])
        testo = contenuto["testo"].strip()
        immagini = [str(d).strip() for d in contenuto["immagini"]][:NUMERO_IMMAGINI]
    except (KeyError, IndexError, TypeError, AttributeError, json.JSONDecodeError):
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

    crea_short.CARTELLA_IMMAGINI.mkdir(exist_ok=True)
    metti_da_parte_immagini_vecchie()
    clip = [p for p in crea_short.trova_media(crea_short.CARTELLA_IMMAGINI) if crea_short.e_clip(p)]
    if clip:
        # le clip fatte a mano prendono il posto delle prime scene
        print(f"   uso le tue clip: {', '.join(p.name for p in clip)}")
    da_generare = list(enumerate(descrizioni, start=1))[len(clip):]

    print(f"2/4 Genero {len(da_generare)} immagini (circa 20-30 secondi l'una)...")
    seme = int(time.time()) % 1_000_000
    for posizione, (i, descrizione) in enumerate(da_generare, start=1):
        print(f"   immagine {i}: {descrizione}")
        scarica_immagine(descrizione, crea_short.CARTELLA_IMMAGINI / f"{i}.jpg", seme + i)
        if posizione < len(da_generare):
            time.sleep(ATTESA_TRA_TENTATIVI)

    print("3/4 Genero la voce...")
    crea_short.genera_voce(testo, crea_short.FILE_VOCE)

    print("4/4 Monto il video...")
    CARTELLA_VIDEO.mkdir(exist_ok=True)
    file_video = CARTELLA_VIDEO / nome_file(argomento)
    media = crea_short.trova_media(crea_short.CARTELLA_IMMAGINI)
    crea_short.monta_video(media, crea_short.FILE_VOCE, file_video)
    print(f"Fatto: {file_video}")


if __name__ == "__main__":
    main()
