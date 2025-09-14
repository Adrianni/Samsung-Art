#!/usr/bin/env python3
import sys
import logging
import os
import json
import argparse
from io import BytesIO
import random
from typing import Tuple, Optional, List, Dict
from datetime import datetime, timedelta

# Eksterne pakker som må være installert:
#   pip install samsungtvws pillow requests
from samsungtvws import SamsungTVWS
from PIL import Image
import requests

# -----------------------------
# Argumenter
# -----------------------------
parser = argparse.ArgumentParser(description='Upload images to Samsung Frame TV from Bing Wallpapers or a local file.')
parser.add_argument('--upload-all', action='store_true',
                    help='Upload all images at once (ellers rebruker den eksisterende hvis den finnes).')
parser.add_argument('--debug', action='store_true',
                    help='Enable debug mode to check if TV is reachable (logger mer).')
parser.add_argument('--tvip', required=True,
                    help='Comma-separated IP addresses of Samsung Frame TVs')
parser.add_argument('--same-image', action='store_true',
                    help='Use the same image for all TVs (default: different images)')
parser.add_argument('--debugimage', action='store_true',
                    help='Save downloaded and resized images for inspection')

source_group = parser.add_mutually_exclusive_group(required=True)
source_group.add_argument('--bingwallpaper', action='store_true',
                          help='Use a random Bing Wallpaper')
source_group.add_argument('--image', type=str,
                          help='Path to a local image that should be uploaded instead of a Bing wallpaper')

args = parser.parse_args()

# -----------------------------
# Lagring av opplastede filer
# -----------------------------
upload_list_path = 'uploaded_files.json'
if os.path.isfile(upload_list_path):
    with open(upload_list_path, 'r') as f:
        uploaded_files: List[Dict[str, str]] = json.load(f)
else:
    uploaded_files = []

# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(
    level=logging.DEBUG if args.debug else logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# -----------------------------
# Utils (innebygget)
# -----------------------------
class Utils:
    def __init__(self, tvips: Optional[str], uploaded_files: List[Dict[str, str]]):
        self.tvips = tvips
        self.uploaded_files = uploaded_files
        self.check_tv_ip = len(tvips.split(',')) > 1 if tvips else False  # sjekk tv_ip kun hvis flere TV-er

    @staticmethod
    def resize_and_crop_image(image_data: BytesIO, target_width=3840, target_height=2160) -> BytesIO:
        """Resize og sentrert crop til 3840x2160 (4K) med god kvalitet."""
        with Image.open(image_data) as img:
            img_ratio = img.width / img.height
            target_ratio = target_width / target_height

            if img_ratio > target_ratio:
                # Bredere enn mål – skaler på høyde
                new_height = target_height
                new_width = int(new_height * img_ratio)
            else:
                # Høyere enn mål – skaler på bredde
                new_width = target_width
                new_height = int(new_width / img_ratio)

            img = img.resize((new_width, new_height), Image.LANCZOS)

            # Midt-utsnitt
            left = (new_width - target_width) // 2
            top = (new_height - target_height) // 2
            right = left + target_width
            bottom = top + target_height
            img = img.crop((left, top, right, bottom))

            out = BytesIO()
            img.save(out, format='JPEG', quality=90)
            out.seek(0)
            return out

    def get_remote_filename(self, file_name: str, source_name: str, tv_ip: Optional[str]) -> Optional[str]:
        """Finn tidligere opplastet remote_filename for samme kilde/fil (og ev. TV-ip)."""
        for uploaded_file in self.uploaded_files:
            if uploaded_file['file'] == file_name and uploaded_file['source'] == source_name:
                if self.check_tv_ip:
                    if uploaded_file.get('tv_ip') == tv_ip:
                        return uploaded_file['remote_filename']
                else:
                    return uploaded_file['remote_filename']
        return None

# -----------------------------
# Bing Wallpapers (innebygget)
# -----------------------------
def bing_get_image_url() -> str:
    """
    Velger en tilfeldig dato mellom 2021-08-28 og i dag.
    4K-bilder er tilgjengelig fra https://bing.npanuhin.me/US/en/YYYY-MM-DD.jpg
    """
    start_date: datetime = datetime(2021, 8, 28)
    end_date: datetime = datetime.now()
    random_date: datetime = start_date + timedelta(days=random.randint(0, (end_date - start_date).days))
    formatted_date: str = random_date.strftime("%Y-%m-%d")
    url: str = f"https://bing.npanuhin.me/US/en/{formatted_date}.jpg"
    return url

def bing_get_image(url: str) -> Tuple[Optional[BytesIO], Optional[str]]:
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return BytesIO(resp.content), "JPEG"
    except requests.RequestException as e:
        logging.error(f"Failed to fetch Bing Wallpaper: {e}")
        return None, None

# -----------------------------
# Hovedlogikk
# -----------------------------
tvip_list: List[str] = args.tvip.split(',') if args.tvip else []
use_same_image: bool = args.same_image

if not tvip_list:
    logging.error('No TV IP addresses specified. Please use --tvip')
    sys.exit(1)

utils = Utils(args.tvip, uploaded_files)

SOURCE_NAME = "bing_wallpaper"

def save_debug_image(image_data: BytesIO, filename: str) -> None:
    if args.debugimage and image_data is not None:
        with open(filename, 'wb') as f:
            f.write(image_data.getvalue())
        logging.info(f'Debug image saved as {filename}')

def process_tv(tv_ip: str, image_data: Optional[BytesIO], file_type: Optional[str],
               image_url: str, remote_filename: Optional[str], source_name: str) -> None:
    tv = SamsungTVWS(tv_ip)

    # Sjekk Art Mode-støtte
    if not tv.art().supported():
        logging.warning(f'TV at {tv_ip} does not support art mode.')
        return

    if remote_filename is None:
        if image_data is None or file_type is None:
            logging.error(f'No image to upload for TV {tv_ip}.')
            return

        try:
            logging.info(f'Uploading image to TV at {tv_ip}')
            remote_filename = tv.art().upload(image_data.getvalue(), file_type=file_type, matte="none")
            if remote_filename is None:
                raise RuntimeError('No remote filename returned from TV')

            tv.art().select_image(remote_filename, show=True)
            logging.info(f'Image uploaded and selected on TV at {tv_ip}')

            # Logg opplastingen
            uploaded_files.append({
                'file': image_url,
                'remote_filename': remote_filename,
                'tv_ip': tv_ip if len(tvip_list) > 1 else None,
                'source': source_name
            })
            with open(upload_list_path, 'w') as f:
                json.dump(uploaded_files, f)
        except Exception as e:
            logging.error(f'Error uploading image to TV at {tv_ip}: {e}')
    else:
        if not args.upload_all:
            logging.info(f'Setting existing image on TV at {tv_ip}, skipping upload')
            tv.art().select_image(remote_filename, show=True)

def get_image_for_tv(tv_ip: Optional[str]):
    if args.image:
        image_url = args.image
        source_name = "local_image"
        logging.info(f'Selected source: {source_name} -> {image_url}')

        remote_filename = utils.get_remote_filename(image_url, source_name, tv_ip)
        if remote_filename:
            return None, None, image_url, remote_filename, source_name

        try:
            with open(image_url, 'rb') as f:
                image_data = BytesIO(f.read())
            ext = os.path.splitext(image_url)[1][1:].lower()
            file_type = 'JPEG' if ext in ('jpg', 'jpeg') else ext.upper()
        except Exception as e:
            logging.error(f'Failed to load image {image_url}: {e}')
            return None, None, None, None, None
    elif args.bingwallpaper:
        image_url = bing_get_image_url()
        source_name = SOURCE_NAME
        logging.info(f'Selected source: {source_name} -> {image_url}')

        remote_filename = utils.get_remote_filename(image_url, source_name, tv_ip)

        if remote_filename:
            return None, None, image_url, remote_filename, source_name

        image_data, file_type = bing_get_image(image_url)
        if image_data is None:
            return None, None, None, None, None
    else:
        logging.error('No image source specified. Use --bingwallpaper or --image.')
        return None, None, None, None, None

    save_debug_image(image_data, f'debug_{source_name}_original.jpg')

    logging.info('Resizing and cropping the image (3840x2160)...')
    resized_image_data = utils.resize_and_crop_image(image_data)

    save_debug_image(resized_image_data, f'debug_{source_name}_resized.jpg')

    return resized_image_data, file_type, image_url, None, source_name

# -----------------------------
# Kjøring
# -----------------------------
if len(tvip_list) > 1 and use_same_image:
    # Hent ett bilde og bruk på alle TV-er
    image_data, file_type, image_url, remote_filename, source_name = get_image_for_tv(None)
    for ip in tvip_list:
        process_tv(ip, image_data, file_type, image_url, remote_filename, source_name)
else:
    # Eget (tilfeldig) bilde pr. TV
    for ip in tvip_list:
        image_data, file_type, image_url, remote_filename, source_name = get_image_for_tv(ip)
        process_tv(ip, image_data, file_type, image_url, remote_filename, source_name)
