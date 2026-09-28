"""Crea uno YouTube Short verticale (1080x1920) a costo zero.

Input:
  testo.txt  -> testo in arabo da leggere (circa 70 parole = circa 30 secondi)
  immagini/  -> immagini .jpg/.jpeg/.png, usate in ordine alfabetico

Output:
  voce.mp3   -> voce generata con edge-tts
  short.mp4  -> video finale con zoom lento su ogni immagine

Uso:
  python crea_short.py
  python crea_short.py --audio mia_voce.mp3   (usa un audio già pronto, salta edge-tts)
"""

import argparse
import asyncio
import shutil
import subprocess
import sys
from pathlib import Path

VOCE = "ar-SA-HamedNeural"      # alternativa femminile: "ar-SA-ZariyahNeural"
CARTELLA = Path(__file__).resolve().parent
FILE_TESTO = CARTELLA / "testo.txt"
CARTELLA_IMMAGINI = CARTELLA / "immagini"
FILE_VOCE = CARTELLA / "voce.mp3"
FILE_VIDEO = CARTELLA / "short.mp4"
ESTENSIONI = {".jpg", ".jpeg", ".png"}
FPS = 30
LARGHEZZA, ALTEZZA = 1080, 1920
DURATA_MASSIMA = 60             # limite degli Shorts, in secondi


def controlla_ffmpeg() -> None:
    for programma in ("ffmpeg", "ffprobe"):
        if shutil.which(programma) is None:
            sys.exit(f"'{programma}' non trovato. Installa FFmpeg e aggiungilo al PATH (vedi README).")


def genera_voce(testo: str, file_audio: Path) -> None:
    try:
        import edge_tts
    except ImportError:
        sys.exit("Manca edge-tts. Installa con: pip install edge-tts")
    try:
        asyncio.run(edge_tts.Communicate(testo, VOCE).save(str(file_audio)))
    except Exception as errore:  # errori di rete o servizio non disponibile
        sys.exit(f"Errore nella generazione della voce: {errore}\n"
                 "Controlla la connessione internet e riprova.")


def durata_audio(file_audio: Path) -> float:
    uscita = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(file_audio)],
        capture_output=True, text=True, check=True,
    )
    return float(uscita.stdout.strip())


def monta_video(immagini: list[Path], file_audio: Path, file_video: Path) -> None:
    durata = durata_audio(file_audio)
    if durata > DURATA_MASSIMA:
        sys.exit(f"La voce dura {durata:.0f} s: supera i {DURATA_MASSIMA} s di uno Short. Accorcia il testo.")
    frame_per_immagine = int(durata / len(immagini) * FPS) + 1

    comando = ["ffmpeg", "-y", "-loglevel", "error", "-stats"]
    for img in immagini:
        comando += ["-i", str(img)]          # niente -loop: zoompan crea i frame da una sola immagine
    comando += ["-i", str(file_audio)]

    filtri = []
    for i in range(len(immagini)):
        filtri.append(
            f"[{i}:v]scale={LARGHEZZA*2}:{ALTEZZA*2}:force_original_aspect_ratio=increase,"
            f"crop={LARGHEZZA*2}:{ALTEZZA*2},"
            f"zoompan=z='min(zoom+0.0015,1.3)':d={frame_per_immagine}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={LARGHEZZA}x{ALTEZZA}:fps={FPS},"
            f"setsar=1[v{i}]"
        )
    ingressi = "".join(f"[v{i}]" for i in range(len(immagini)))
    filtri.append(f"{ingressi}concat=n={len(immagini)}:v=1:a=0[video]")

    comando += [
        "-filter_complex", ";".join(filtri),
        "-map", "[video]", "-map", f"{len(immagini)}:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart",
        str(file_video),
    ]
    subprocess.run(comando, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Crea uno YouTube Short a costo zero.")
    parser.add_argument("--audio", type=Path, help="usa questo file audio invece di generare la voce")
    args = parser.parse_args()

    controlla_ffmpeg()

    immagini = sorted(p for p in CARTELLA_IMMAGINI.glob("*") if p.suffix.lower() in ESTENSIONI)
    if not immagini:
        sys.exit(f"Nessuna immagine trovata in '{CARTELLA_IMMAGINI}'. Aggiungi file .jpg o .png.")
    print(f"Immagini trovate ({len(immagini)}): " + ", ".join(p.name for p in immagini))

    if args.audio:
        if not args.audio.exists():
            sys.exit(f"File audio non trovato: {args.audio}")
        file_audio = args.audio
    else:
        if not FILE_TESTO.exists():
            sys.exit(f"Manca il file '{FILE_TESTO.name}'. Crealo e incolla il testo in arabo.")
        testo = FILE_TESTO.read_text(encoding="utf-8").strip()
        if not testo:
            sys.exit(f"Il file '{FILE_TESTO.name}' è vuoto.")
        print("1/2 Genero la voce...")
        genera_voce(testo, FILE_VOCE)
        file_audio = FILE_VOCE

    print("2/2 Monto il video...")
    monta_video(immagini, file_audio, FILE_VIDEO)
    print(f"Fatto: {FILE_VIDEO}")


if __name__ == "__main__":
    main()
