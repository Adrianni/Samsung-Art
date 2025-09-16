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
#   pip3 install -r requirements.txt
from samsungtvws import SamsungTVWS
from PIL import Image
import requests

PHOTO_FILTER_OPTIONS: Dict[str, str] = {
    "none": "none",
    "aqua": "aqua",
    "artdeco": "artdeco",
    "ink": "ink",
    "wash": "wash",
    "pastel": "pastel",
    "feuve": "feuve",
}

MATTE_OPTIONS: Dict[str, str] = {
    "none": "none",
    "myshelf": "myshelf",
    "modernthin": "modernthin",
    "modern": "modern",
    "modernwide": "modernwide",
    "flexible": "flexible",
    "shadowbox": "shadowbox",
    "panoramic": "panoramic",
    "triptych": "triptych",
    "mix": "mix",
    "squares": "squares",
}

MATTE_COLOR_OPTIONS: Dict[str, str] = {
    "black": "black",
    "neutral": "neutral",
    "antique": "antique",
    "warm": "warm",
    "polar": "polar",
    "sand": "sand",
    "seafoam": "seafoam",
    "sage": "sage",
    "burgandy": "burgandy",
    "navy": "navy",
    "apricot": "apricot",
    "byzantine": "byzantine",
    "lavender": "lavender",
    "redorange": "redorange",
    "skyblue": "skyblue",
    "turquoise": "turquoise",
}

PHOTO_FILTER_DISPLAY = "None|Aqua|ArtDeco|Ink|Wash|Pastel|Feuve"
MATTE_DISPLAY = "none|myshelf|modernthin|modern|modernwide|flexible|shadowbox|panoramic|triptych|mix|squares"
MATTE_COLOR_DISPLAY = (
    "black|neutral|antique|warm|polar|sand|seafoam|sage|burgandy|navy|"
    "apricot|byzantine|lavender|redorange|skyblue|turquoise"
)


def create_choice_parser(valid_options: Dict[str, str], display: str, argument_name: str):
    def parser(value: str) -> str:
        key = value.lower()
        if key not in valid_options:
            raise argparse.ArgumentTypeError(
                f"Invalid {argument_name} '{value}'. Valid options: {display}"
            )
        return valid_options[key]

    return parser


def build_matte_identifier(matte: str, matte_color: str) -> str:
    if matte == "none":
        return "none"
    return f"{matte}_{matte_color}"

# Unsplash API access key (set env var UNSPLASH_ACCESS_KEY or edit here)
UNSPLASH_ACCESS_KEY: str = os.environ.get("UNSPLASH_ACCESS_KEY", "")

# -----------------------------
# Argumenter
# -----------------------------
parser = argparse.ArgumentParser(description='Upload images to Samsung Frame TV from Bing Wallpapers, Unsplash, or a local file.')
parser.add_argument('--debug', action='store_true',
                    help='Enable debug mode to check if TV is reachable (logger mer).')
parser.add_argument('--tvip', required=True,
                    help='Comma-separated IP addresses of Samsung Frame TVs')

source_group = parser.add_mutually_exclusive_group(required=True)
source_group.add_argument('--bingwallpaper', action='store_true',
                          help='Use a random Bing Wallpaper')
source_group.add_argument(
    '--unsplash',
    nargs='?',
    const=True,
    metavar='IMAGE_ID',
    help=('Use an Unsplash photo. Provide IMAGE_ID for a specific photo or leave empty '
          'for a random landscape (requires UNSPLASH_ACCESS_KEY)')
)
source_group.add_argument('--image', type=str,
                          help='Path to a local image that should be uploaded instead of a Bing wallpaper')

parser.add_argument(
    '--photo-filter',
    type=create_choice_parser(PHOTO_FILTER_OPTIONS, PHOTO_FILTER_DISPLAY, "photo filter"),
    default='none',
    metavar='FILTER',
    help=f"Photo filter to apply ({PHOTO_FILTER_DISPLAY}).",
)
parser.add_argument(
    '--matte',
    type=create_choice_parser(MATTE_OPTIONS, MATTE_DISPLAY, "matte"),
    default='none',
    metavar='MATTE',
    help=f"Matte style to apply ({MATTE_DISPLAY}).",
)
parser.add_argument(
    '--matte-color',
    type=create_choice_parser(MATTE_COLOR_OPTIONS, MATTE_COLOR_DISPLAY, "matte color"),
    default='black',
    metavar='COLOR',
    help=(
        "Matte color to apply when a matte is selected "
        f"({MATTE_COLOR_DISPLAY}). Ignored when matte is 'none'."
    ),
)

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
# Unsplash (innebygget)
# -----------------------------
def unsplash_get_image(image_id: Optional[str] = None) -> Tuple[Optional[BytesIO], Optional[str], Optional[str]]:
    """Fetch an image from Unsplash. Random if no image_id is provided."""
    if not UNSPLASH_ACCESS_KEY:
        logging.error('Unsplash access key not set. Set UNSPLASH_ACCESS_KEY environment variable.')
        return None, None, None

    if image_id:
        api_url = f"https://api.unsplash.com/photos/{image_id}"
        params: Dict[str, str] = {}
    else:
        api_url = "https://api.unsplash.com/photos/random"
        params = {"orientation": "landscape"}
    try:
        resp = requests.get(
            api_url,
            params=params,
            headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        image_page = data.get("links", {}).get("html")
        raw_url = data.get("urls", {}).get("raw")
        if not raw_url:
            logging.error('Unsplash response missing image URL')
            return None, None, None

        download_url = f"{raw_url}&w=3840&h=2160&fit=crop"
        img_resp = requests.get(download_url, timeout=30)
        img_resp.raise_for_status()
        file_type = img_resp.headers.get('Content-Type', '').split('/')[-1].upper() or 'JPEG'
        return BytesIO(img_resp.content), file_type, image_page or download_url
    except requests.RequestException as e:
        logging.error(f"Failed to fetch Unsplash image: {e}")
        return None, None, None
    except ValueError as e:
        logging.error(f"Failed to parse Unsplash response: {e}")
        return None, None, None

# -----------------------------
# Hovedlogikk
# -----------------------------
tvip_list: List[str] = args.tvip.split(',') if args.tvip else []

if not tvip_list:
    logging.error('No TV IP addresses specified. Please use --tvip')
    sys.exit(1)

utils = Utils(args.tvip, uploaded_files)

BING_SOURCE_NAME = "bing_wallpaper"
UNSPLASH_SOURCE_NAME = "unsplash"

def apply_art_customizations(art_api, tv_ip: str, content_id: str, photo_filter: str, matte_id: str) -> bool:
    if not content_id:
        return False

    customization_sent = False

    filter_desc = "no photo filter" if photo_filter == "none" else f"photo filter '{photo_filter}'"
    try:
        art_api.set_photo_filter(content_id, photo_filter)
        logging.info(f"Applied {filter_desc} on TV at {tv_ip}")
        customization_sent = True
    except Exception as e:
        logging.error(f"Failed to set photo filter '{photo_filter}' for TV at {tv_ip}: {e}")

    matte_desc = "no matte" if matte_id == "none" else f"matte '{matte_id}'"
    try:
        art_api.change_matte(content_id, matte_id)
        logging.info(f"Applied {matte_desc} on TV at {tv_ip}")
        customization_sent = True
    except Exception as e:
        logging.error(f"Failed to set matte '{matte_id}' for TV at {tv_ip}: {e}")

    return customization_sent


def select_image_with_logging(art_api, tv_ip: str, content_id: str, success_message: str) -> None:
    if not content_id:
        logging.error(f"Cannot select artwork on TV at {tv_ip}: missing content id")
        return

    try:
        art_api.select_image(content_id, show=True)
        logging.info(f"{success_message} on TV at {tv_ip}")
    except Exception as e:
        logging.error(f"Failed to select image '{content_id}' on TV at {tv_ip}: {e}")


def process_tv(tv_ip: str, image_data: Optional[BytesIO], file_type: Optional[str],
               image_url: str, remote_filename: Optional[str], source_name: str,
               photo_filter: str, matte_id: str) -> None:
    tv = SamsungTVWS(tv_ip)
    art_api = tv.art()

    # Sjekk Art Mode-støtte
    if not art_api.supported():
        logging.warning(f'TV at {tv_ip} does not support art mode.')
        return

    if remote_filename is None:
        if image_data is None or file_type is None:
            logging.error(f'No image to upload for TV {tv_ip}.')
            return

        try:
            logging.info(f'Uploading image to TV at {tv_ip}')
            remote_filename = art_api.upload(image_data.getvalue(), file_type=file_type, matte=matte_id)
            if remote_filename is None:
                raise RuntimeError('No remote filename returned from TV')

            customization_sent = apply_art_customizations(
                art_api, tv_ip, remote_filename, photo_filter, matte_id
            )

            success_message = 'Image uploaded and displayed'
            if customization_sent:
                success_message = (
                    'Image uploaded and displayed with updated matte/photo filter'
                )

            select_image_with_logging(art_api, tv_ip, remote_filename, success_message)

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
        logging.info(f'Setting existing image on TV at {tv_ip}, skipping upload')
        customization_sent = apply_art_customizations(
            art_api, tv_ip, remote_filename, photo_filter, matte_id
        )

        success_message = 'Existing image selected'
        if customization_sent:
            success_message = 'Existing image refreshed with updated matte/photo filter'

        select_image_with_logging(art_api, tv_ip, remote_filename, success_message)

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
        source_name = BING_SOURCE_NAME
        logging.info(f'Selected source: {source_name} -> {image_url}')

        remote_filename = utils.get_remote_filename(image_url, source_name, tv_ip)

        if remote_filename:
            return None, None, image_url, remote_filename, source_name

        image_data, file_type = bing_get_image(image_url)
        if image_data is None:
            return None, None, None, None, None
    elif args.unsplash is not None:
        unsplash_id = None if args.unsplash is True else args.unsplash
        image_data, file_type, image_url = unsplash_get_image(unsplash_id)
        if image_data is None or image_url is None:
            return None, None, None, None, None
        source_name = UNSPLASH_SOURCE_NAME
        logging.info(f'Selected source: {source_name} -> {image_url}')

        remote_filename = utils.get_remote_filename(image_url, source_name, tv_ip)
        if remote_filename:
            return None, None, image_url, remote_filename, source_name
    else:
        logging.error('No image source specified. Use --bingwallpaper, --unsplash or --image.')
        return None, None, None, None, None

    logging.info('Resizing and cropping the image (3840x2160)...')
    resized_image_data = utils.resize_and_crop_image(image_data)

    return resized_image_data, file_type, image_url, None, source_name

# -----------------------------
# Kjøring
# -----------------------------
selected_photo_filter = args.photo_filter
selected_matte_identifier = build_matte_identifier(args.matte, args.matte_color)

if args.matte == 'none' and args.matte_color != 'black':
    logging.info(
        "Matte color '%s' is ignored because matte is set to 'none'", args.matte_color
    )

for ip in tvip_list:
    image_data, file_type, image_url, remote_filename, source_name = get_image_for_tv(ip)
    process_tv(
        ip,
        image_data,
        file_type,
        image_url,
        remote_filename,
        source_name,
        selected_photo_filter,
        selected_matte_identifier,
    )
