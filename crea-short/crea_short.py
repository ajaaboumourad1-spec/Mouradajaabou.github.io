"""Crea uno YouTube Short verticale (1080x1920) a costo zero.

Input:
  testo.txt  -> testo in arabo da leggere (circa 70 parole = circa 30 secondi)
  immagini/  -> immagini (.jpg .jpeg .png) e clip video (.mp4 .mov .webm),
                usate in ordine di numero: 1, 2, 3 ... 10

Le clip vengono usate per intero (senza il loro audio), il tempo che resta
della voce viene diviso tra le immagini, che hanno uno zoom lento.

Output:
  voce.mp3         -> voce generata con edge-tts
  sottotitoli.srt  -> sottotitoli arabi sincronizzati con la voce (scritti anche nel video)
  short.mp4        -> video finale

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
FILE_SOTTOTITOLI = CARTELLA / "sottotitoli.srt"
FILE_VIDEO = CARTELLA / "short.mp4"
ESTENSIONI = {".jpg", ".jpeg", ".png"}
ESTENSIONI_CLIP = {".mp4", ".mov", ".webm"}
FPS = 30
LARGHEZZA, ALTEZZA = 1080, 1920
DURATA_MASSIMA = 60             # limite degli Shorts, in secondi
DURATA_MINIMA_IMMAGINE = 1.5    # secondi: sotto questa soglia l'immagine passa troppo in fretta

SOTTOTITOLI = True              # False = video senza sottotitoli
PAROLE_PER_RIGA = 3             # quante parole mostrare insieme sullo schermo
# stile dei sottotitoli: testo bianco, bordo nero, in basso al centro ma sopra i pulsanti di YouTube
STILE_SOTTOTITOLI = ("FontName=Arial,FontSize=15,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                     "BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=70")


def controlla_ffmpeg() -> None:
    for programma in ("ffmpeg", "ffprobe"):
        if shutil.which(programma) is None:
            sys.exit(f"'{programma}' non trovato. Installa FFmpeg e aggiungilo al PATH (vedi README).")


def ordine_naturale(percorso: Path) -> tuple:
    # "2.jpg" prima di "10.jpg"; a parità di numero l'immagine prima della clip
    numero = int(percorso.stem) if percorso.stem.isdigit() else float("inf")
    return (numero, percorso.stem.lower(), percorso.suffix.lower())


def trova_media(cartella: Path) -> list[Path]:
    return sorted(
        (p for p in cartella.glob("*") if p.suffix.lower() in ESTENSIONI | ESTENSIONI_CLIP),
        key=ordine_naturale,
    )


def e_clip(percorso: Path) -> bool:
    return percorso.suffix.lower() in ESTENSIONI_CLIP


def genera_voce(testo: str, file_audio: Path) -> list[tuple[float, float, str]]:
    """Salva la voce in file_audio e restituisce i tempi di ogni parola: (inizio, fine, parola) in secondi."""
    try:
        import edge_tts
    except ImportError:
        sys.exit("Manca edge-tts. Installa con: pip install edge-tts")

    async def scarica() -> list[tuple[float, float, str]]:
        parole = []
        comunica = edge_tts.Communicate(testo, VOCE, boundary="WordBoundary")
        with open(file_audio, "wb") as audio:
            async for pezzo in comunica.stream():
                if pezzo["type"] == "audio":
                    audio.write(pezzo["data"])
                elif pezzo["type"] == "WordBoundary":
                    inizio = pezzo["offset"] / 10_000_000       # edge-tts misura in unità da 100 ns
                    parole.append((inizio, inizio + pezzo["duration"] / 10_000_000, pezzo["text"]))
        return parole

    try:
        return asyncio.run(scarica())
    except Exception as errore:  # errori di rete o servizio non disponibile
        sys.exit(f"Errore nella generazione della voce: {errore}\n"
                 "Controlla la connessione internet e riprova.")


def tempo_srt(secondi: float) -> str:
    millisecondi = round(secondi * 1000)
    ore, resto = divmod(millisecondi, 3_600_000)
    minuti, resto = divmod(resto, 60_000)
    secondi, millisecondi = divmod(resto, 1000)
    return f"{ore:02}:{minuti:02}:{secondi:02},{millisecondi:03}"


def scrivi_sottotitoli(parole: list[tuple[float, float, str]], file_srt: Path) -> bool:
    """Raggruppa le parole in righe corte e scrive il file .srt. Restituisce False se non ci sono parole."""
    gruppi = [parole[i:i + PAROLE_PER_RIGA] for i in range(0, len(parole), PAROLE_PER_RIGA)]
    if not gruppi:
        return False
    righe = []
    for n, gruppo in enumerate(gruppi):
        inizio, fine = gruppo[0][0], gruppo[-1][1]
        if n + 1 < len(gruppi):
            # la riga resta sullo schermo fino alla successiva, così il testo non "lampeggia"
            fine = max(fine, gruppi[n + 1][0][0])
        testo = " ".join(parola for _, _, parola in gruppo)
        righe.append(f"{n + 1}\n{tempo_srt(inizio)} --> {tempo_srt(fine)}\n{testo}\n")
    file_srt.write_text("\n".join(righe), encoding="utf-8")
    return True


def durata(file_media: Path) -> float:
    uscita = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(file_media)],
        capture_output=True, text=True,
    )
    try:
        return float(uscita.stdout.strip())
    except ValueError:
        sys.exit(f"Non riesco a leggere la durata di '{file_media.name}': il file è danneggiato?")


def monta_video(media: list[Path], file_audio: Path, file_video: Path,
                file_sottotitoli: Path | None = None) -> None:
    durata_voce = durata(file_audio)
    if durata_voce > DURATA_MASSIMA:
        sys.exit(f"La voce dura {durata_voce:.0f} s: supera i {DURATA_MASSIMA} s di uno Short. Accorcia il testo.")

    clip = [p for p in media if e_clip(p)]
    immagini = [p for p in media if not e_clip(p)]
    durata_clip = {p: durata(p) for p in clip}
    totale_clip = sum(durata_clip.values())

    secondi_per_immagine = 0.0
    if immagini:
        tempo_libero = durata_voce - totale_clip
        secondi_per_immagine = tempo_libero / len(immagini)
        if secondi_per_immagine < DURATA_MINIMA_IMMAGINE:
            sys.exit(f"Le clip durano {totale_clip:.1f} s e la voce {durata_voce:.1f} s: restano solo "
                     f"{max(tempo_libero, 0):.1f} s per {len(immagini)} immagini.\n"
                     "Allunga il testo oppure togli qualche immagine.")
    # senza immagini, se le clip finiscono prima della voce l'ultima resta ferma fino alla fine
    allungamento_finale = max(durata_voce - totale_clip, 0) if not immagini else 0.0

    comando = ["ffmpeg", "-y", "-loglevel", "error", "-stats"]
    for p in media:
        comando += ["-i", str(p)]            # niente -loop: zoompan crea i frame da una sola immagine
    comando += ["-i", str(file_audio)]

    filtri = []
    for i, p in enumerate(media):
        # le immagini si ingrandiscono al doppio prima dello zoom, così il movimento non "trema"
        w, h = (LARGHEZZA, ALTEZZA) if e_clip(p) else (LARGHEZZA * 2, ALTEZZA * 2)
        adatta = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
        if e_clip(p):
            filtro = f"[{i}:v]{adatta},fps={FPS},setpts=PTS-STARTPTS"
            if allungamento_finale > 0 and i == len(media) - 1:
                filtro += f",tpad=stop_mode=clone:stop_duration={allungamento_finale:.3f}"
        else:
            frame = int(secondi_per_immagine * FPS) + 1
            filtro = (f"[{i}:v]{adatta},"
                      f"zoompan=z='min(zoom+0.0015,1.3)':d={frame}:"
                      f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={LARGHEZZA}x{ALTEZZA}:fps={FPS}")
        filtri.append(f"{filtro},setsar=1,format=yuv420p[v{i}]")
    ingressi = "".join(f"[v{i}]" for i in range(len(media)))
    if file_sottotitoli:
        filtri.append(f"{ingressi}concat=n={len(media)}:v=1:a=0[montato]")
        # nome del file senza percorso (FFmpeg parte dalla sua cartella): evita i problemi con "C:\\" su Windows
        filtri.append(f"[montato]subtitles={file_sottotitoli.name}:charenc=UTF-8:"
                      f"force_style='{STILE_SOTTOTITOLI}'[video]")
    else:
        filtri.append(f"{ingressi}concat=n={len(media)}:v=1:a=0[video]")

    comando += [
        "-filter_complex", ";".join(filtri),
        "-map", "[video]", "-map", f"{len(media)}:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart",
        str(file_video),
    ]
    cartella_lavoro = file_sottotitoli.parent if file_sottotitoli else None
    subprocess.run(comando, check=True, cwd=cartella_lavoro)


def main() -> None:
    parser = argparse.ArgumentParser(description="Crea uno YouTube Short a costo zero.")
    parser.add_argument("--audio", type=Path, help="usa questo file audio invece di generare la voce")
    args = parser.parse_args()

    controlla_ffmpeg()

    media = trova_media(CARTELLA_IMMAGINI)
    if not media:
        sys.exit(f"Nessuna immagine o clip trovata in '{CARTELLA_IMMAGINI}'. Aggiungi file .jpg, .png o .mp4.")
    print(f"File trovati ({len(media)}): " + ", ".join(p.name for p in media))

    file_srt = None                  # con --audio non conosciamo i tempi delle parole: niente sottotitoli
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
        parole = genera_voce(testo, FILE_VOCE)
        file_audio = FILE_VOCE
        if SOTTOTITOLI and scrivi_sottotitoli(parole, FILE_SOTTOTITOLI):
            file_srt = FILE_SOTTOTITOLI

    print("2/2 Monto il video...")
    monta_video(media, file_audio, FILE_VIDEO, file_srt)
    print(f"Fatto: {FILE_VIDEO}")


if __name__ == "__main__":
    main()
