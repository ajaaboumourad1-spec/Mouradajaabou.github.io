# Crea Short: YouTube Short in arabo a costo zero

Lo script prende un testo in arabo e alcune immagini e crea un video verticale 1080×1920.
Il video ha la voce araba e uno zoom lento su ogni immagine.

**Costo: 0 €.** Usa solo strumenti gratuiti: Python, FFmpeg ed edge-tts.

## 1. Installazione (una volta sola)

1. **Python 3.10 o più recente**: scaricalo da <https://www.python.org/downloads/>.
   Su Windows spunta **"Add Python to PATH"** durante l'installazione.
2. **FFmpeg**
   - Windows: apri il terminale e scrivi `winget install Gyan.FFmpeg`, poi chiudi e riapri il terminale.
   - Mac: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg`
3. **edge-tts**: nella cartella `crea-short` esegui:
   ```bash
   pip install -r requirements.txt
   ```

Per verificare: `ffmpeg -version` e `python --version` devono stampare una versione.

## 2. Preparare uno Short

1. **Testo**: incolla in `testo.txt` il testo in arabo (circa 70 parole, cioè circa 30 secondi).
   Puoi generarlo gratis nell'app Gemini con questo prompt:
   > Scrivi il testo parlato per uno YouTube Short di 30 secondi su [ARGOMENTO]. Lingua: arabo standard.
   > Massimo 70 parole. Inizia con una frase che cattura l'attenzione. Rispondi SOLO con il testo da
   > leggere, senza titoli, emoji o indicazioni di regia.
2. **Immagini**: metti 3–5 immagini in `immagini/`, chiamate `1.jpg`, `2.jpg`, `3.jpg`...
   - Creale **verticali (9:16)**: le immagini orizzontali vengono tagliate ai lati.
   - Se ne usi più di 9, chiamale `01.jpg`, `02.jpg`, ecc., così l'ordine resta giusto.

## 3. Creare il video

```bash
python crea_short.py
```

Il risultato è `short.mp4`, pronto da caricare su YouTube come Short.

Se hai già un audio (per esempio la tua voce registrata), puoi usarlo al posto di edge-tts:
```bash
python crea_short.py --audio mia_voce.mp3
```

## Versione automatica (Gemini + Pollinations, gratis)

```bash
setx GEMINI_API_KEY "la-tua-chiave"      # una volta sola, poi riapri il terminale
python automatico.py "argomento del video"
```
Il video finisce in `video/`. Chiave gratuita: <https://aistudio.google.com/apikey>.

## Strada ibrida: una clip animata + immagini

1. Crea una clip **verticale 9:16** di 5–8 secondi nell'app Gemini e salvala come `immagini/1.mp4`.
2. Lancia `python automatico.py "argomento"` (genera solo le immagini 2, 3, 4)
   oppure metti tu le immagini `2.jpg`, `3.jpg`, `4.jpg` e lancia `python crea_short.py`.

Le clip vengono usate intere e senza il loro audio. Le clip orizzontali vengono tagliate ai lati.
Dopo il video, **togli la clip** da `immagini/`, altrimenti viene riusata nel video successivo.

## Voci arabe disponibili

Cambia `VOCE` in cima a `crea_short.py`:
- `ar-SA-HamedNeural` (uomo, Arabia Saudita). È la voce predefinita.
- `ar-SA-ZariyahNeural` (donna, Arabia Saudita)
- `ar-EG-SalmaNeural` / `ar-EG-ShakirNeural` (egiziano)
- `ar-MA-JamalNeural` / `ar-MA-MounaNeural` (marocchino)

Per vedere l'elenco completo: `edge-tts --list-voices`

## Problemi comuni

| Errore | Soluzione |
|---|---|
| `'ffmpeg' non trovato` | FFmpeg non è nel PATH: reinstallalo e riapri il terminale |
| `Manca edge-tts` | `pip install -r requirements.txt` |
| `Errore nella generazione della voce` | Serve internet. edge-tts è gratuito ma non ufficiale: se smette di funzionare, aggiorna con `pip install -U edge-tts` |
| `supera i 60 s` | Il testo è troppo lungo: accorcialo |
