import os
import csv
import argparse
import logging
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from mutagen.mp4 import MP4, MP4FreeForm
from mutagen.id3 import ID3, TXXX, ID3NoHeaderError


DEFAULT_CSV = "replaygain.csv"
M4A_TAG_KEY = "----:com.apple.iTunes:REPLAYGAIN_ALBUM_GAIN"
MP3_TAG_KEY = "REPLAYGAIN_ALBUM_GAIN"
VALID_EXTENSIONS = [".mp3", ".m4a"]


def init_logging():
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"replaygain_write_{now}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        handlers=[
            logging.FileHandler(log_filename, encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    return log_filename


def get_loudest_track_gain(csv_path):
    max_loudness = -999
    target_gain = None
    try:
        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                if row["Filename"].lower() == "album":
                    continue
                try:
                    loudness = float(row["Loudness (LUFS)"])
                    gain = float(row["Gain (dB)"])
                except ValueError:
                    continue
                if loudness > max_loudness:
                    max_loudness = loudness
                    target_gain = gain
        return target_gain
    except Exception as e:
        logging.error(f"❌ Unable to read CSV file: {csv_path} | {e}")
        return None


def get_album_max_gain(csv_path):
    try:
        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                if row["Filename"].lower() == "album":
                    try:
                        return float(row["Gain (dB)"])
                    except ValueError:
                        return None
    except Exception as e:
        logging.error(f"❌ Unable to read CSV file: {csv_path} | {e}")
    return None


def write_gain(file_path, gain_db, dry_run):
    ext = file_path.suffix.lower()
    gain_str = f"{gain_db:.2f} dB"
    if dry_run:
        return

    try:
        if ext == ".m4a":
            audio = MP4(file_path)
            audio[M4A_TAG_KEY] = [MP4FreeForm(gain_str.encode("utf-8"))]
            audio.save()
        elif ext == ".mp3":
            try:
                audio = ID3(file_path)
            except ID3NoHeaderError:
                audio = ID3()
            audio.add(TXXX(encoding=3, desc=MP3_TAG_KEY, text=gain_str))
            audio.save(file_path)
    except Exception as e:
        logging.error(f"❌ Write failed: {file_path} | {e}")


def process_album(folder_path, dry_run=False):
    csv_path = os.path.join(folder_path, DEFAULT_CSV)
    album_name = f"[{os.path.basename(folder_path)}]"

    if not os.path.isfile(csv_path):
        logging.warning(f"{album_name} ⚠️ missing {DEFAULT_CSV}，Skip")
        return

    loudest_gain = get_loudest_track_gain(csv_path)
    album_max_gain = get_album_max_gain(csv_path)

    if loudest_gain is None or album_max_gain is None:
        logging.warning(f"{album_name} ⚠️ No valid Gain data, skipped.")
        return

    gain_to_write = min(loudest_gain, album_max_gain)

    if abs(gain_to_write - album_max_gain) < 0.01:
        logging.info(f"{album_name} Loudest Track Gain: {loudest_gain:.2f} dB |  Album Gain Limitation: {album_max_gain:.2f} dB → No need to write")
        return

    logging.info(f"{album_name} Loudest Track Gain: {loudest_gain:.2f} dB | Album Gain Limitation: {album_max_gain:.2f} dB → write: {gain_to_write:.2f} dB")

    for filename in os.listdir(folder_path):
        file_path = Path(folder_path) / filename
        if file_path.suffix.lower() not in VALID_EXTENSIONS:
            continue
        write_gain(file_path, gain_to_write, dry_run)


def main():
    parser = argparse.ArgumentParser(description="Batch write ReplayGain Album Gain tags")
    parser.add_argument("music_dir", help="Music library root directory")
    parser.add_argument("--dry-run", action="store_true", help="Simulate only, do not write tags")
    args = parser.parse_args()

    root_dir = args.music_dir
    dry_run = args.dry_run

    log_file = init_logging()
    num_threads = os.cpu_count() or 2

    album_folders = []
    for dirpath, _, filenames in os.walk(root_dir):
        if DEFAULT_CSV in filenames:
            album_folders.append(dirpath)

    logging.info(f"Threads enabled: {num_threads}")

    if not album_folders:
        logging.warning("⚠️ No album directory containing replaygain.csv was found, skipped processing.")
        logging.info(f"Task completed, log saved to {log_file}")
        return

    logging.info(f"Found a total of {len(album_folders)} albums, starting processing...")

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(process_album, folder, dry_run) for folder in album_folders]
        for _ in as_completed(futures):
            pass

    logging.info(f"Task completed, the log has been saved to {log_file}")


if __name__ == "__main__":
    main()
