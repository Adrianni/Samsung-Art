#!/usr/bin/env python3
import sys
import logging
import os
import json
import argparse
from io import BytesIO
import random
import re
from typing import Tuple, Optional, List, Dict, Iterable, Union, Any
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

GOOGLE_ART_ASSET_BASE_URL = "https://artsandculture.google.com/asset/"
GOOGLE_ART_HEADERS: Dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (FrameArtUploader)"
}
GOOGLE_ART_MANIFEST_REGEX = re.compile(
    r'"(?:iiifManifestUrl|manifestUrl|manifestUri)"\s*:\s*"(.*?)"', re.IGNORECASE
)

# -----------------------------
# Argumenter
# -----------------------------
parser = argparse.ArgumentParser(
    description=(
        'Upload images to Samsung Frame TV from Bing Wallpapers, Unsplash, '
        'Google Arts & Culture, or a local file.'
    )
)
parser.add_argument('--debug', action='store_true',
                    help='Enable debug mode to check if TV is reachable (logger mer).')
parser.add_argument('--tvip', required=True,
                    help='Comma-separated IP addresses of Samsung Frame TVs')

source_group = parser.add_mutually_exclusive_group(required=True)
source_group.add_argument('--bingwallpaper', action='store_true',
                          help='Use a random Bing Wallpaper')
source_group.add_argument(
    '--googleart',
    metavar='ASSET_ID',
    help=(
        'Download an artwork from Google Arts & Culture using the asset ID '
        '(last segment of the asset URL).'
    ),
)
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
        uploaded_files: List[Dict[str, Optional[str]]] = json.load(f)
else:
    uploaded_files: List[Dict[str, Optional[str]]] = []

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
    def __init__(self, tvips: Optional[str], uploaded_files: List[Dict[str, Optional[str]]]):
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

    def get_remote_filename(
        self,
        file_name: Union[str, Iterable[str]],
        source_name: str,
        tv_ip: Optional[str],
    ) -> Optional[str]:
        """Finn tidligere opplastet remote_filename for samme kilde/fil (og ev. TV-ip)."""

        if isinstance(file_name, str):
            candidates: List[str] = [file_name]
        else:
            candidates = [name for name in file_name if name]

        for uploaded_file in self.uploaded_files:
            if uploaded_file.get('source') != source_name:
                continue

            if self.check_tv_ip and uploaded_file.get('tv_ip') != tv_ip:
                continue

            stored_identifiers: List[str] = []
            stored_file = uploaded_file.get('file')
            if stored_file:
                stored_identifiers.append(stored_file)

            display_url = uploaded_file.get('display_url')
            if display_url:
                stored_identifiers.append(display_url)

            image_id = uploaded_file.get('image_id')
            if image_id:
                stored_identifiers.append(image_id)

            for candidate in candidates:
                if candidate in stored_identifiers:
                    return uploaded_file.get('remote_filename')

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
def unsplash_get_image(
    image_id: Optional[str] = None,
) -> Tuple[Optional[BytesIO], Optional[str], Optional[str], Optional[str]]:
    """Fetch an image from Unsplash. Random if no image_id is provided."""
    if not UNSPLASH_ACCESS_KEY:
        logging.error('Unsplash access key not set. Set UNSPLASH_ACCESS_KEY environment variable.')
        return None, None, None, None

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
        image_identifier = data.get("id")
        raw_url = data.get("urls", {}).get("raw")
        if not raw_url:
            logging.error('Unsplash response missing image URL')
            return None, None, None, None

        download_url = f"{raw_url}&w=3840&h=2160&fit=crop"
        img_resp = requests.get(download_url, timeout=30)
        img_resp.raise_for_status()
        file_type = img_resp.headers.get('Content-Type', '').split('/')[-1].upper() or 'JPEG'
        display_url = image_page or download_url
        identifier = image_identifier or display_url
        return BytesIO(img_resp.content), file_type, identifier, display_url
    except requests.RequestException as e:
        logging.error(f"Failed to fetch Unsplash image: {e}")
        return None, None, None, None
    except ValueError as e:
        logging.error(f"Failed to parse Unsplash response: {e}")
        return None, None, None, None

# -----------------------------
# Google Arts & Culture
# -----------------------------
def googleart_decode_json_string(value: str) -> str:
    cleaned = str(value)
    try:
        cleaned = json.loads(f'"{cleaned}"')
    except json.JSONDecodeError:
        pass
    try:
        cleaned = bytes(cleaned, "utf-8").decode("unicode_escape")
    except (UnicodeDecodeError, ValueError):
        pass
    return cleaned.replace(r"\/", "/")


def googleart_extract_manifest_url(page_html: str) -> Optional[str]:
    if not page_html:
        return None
    for match in GOOGLE_ART_MANIFEST_REGEX.finditer(page_html):
        manifest_url = googleart_decode_json_string(match.group(1)).strip()
        if manifest_url.startswith("//"):
            manifest_url = "https:" + manifest_url
        if manifest_url:
            return manifest_url
    return None


def googleart_build_full_image_from_service(service: Any) -> Optional[str]:
    if isinstance(service, list):
        for entry in service:
            result = googleart_build_full_image_from_service(entry)
            if result:
                return result
        return None
    if isinstance(service, dict):
        service_id = service.get("@id") or service.get("id")
        if isinstance(service_id, str) and service_id:
            return service_id.rstrip("/") + "/full/full/0/default.jpg"
    return None


def googleart_extract_from_resource(resource: Any) -> Optional[str]:
    if isinstance(resource, list):
        for entry in resource:
            result = googleart_extract_from_resource(entry)
            if result:
                return result
        return None
    if not isinstance(resource, dict):
        return None
    url_candidate = resource.get("@id") or resource.get("id")
    if isinstance(url_candidate, str) and url_candidate:
        return url_candidate
    service = resource.get("service")
    return googleart_build_full_image_from_service(service)


def googleart_extract_image_url(manifest_data: Dict[str, Any]) -> Optional[str]:
    if not isinstance(manifest_data, dict):
        return None

    sequences = manifest_data.get("sequences")
    if isinstance(sequences, list):
        for sequence in sequences:
            canvases = sequence.get("canvases")
            if not isinstance(canvases, list):
                continue
            for canvas in canvases:
                images = canvas.get("images")
                if not isinstance(images, list):
                    continue
                for image in images:
                    resource = googleart_extract_from_resource(image.get("resource"))
                    if resource:
                        return resource
                    body = googleart_extract_from_resource(image.get("body"))
                    if body:
                        return body

    items = manifest_data.get("items")
    if isinstance(items, list):
        for canvas in items:
            canvas_items = canvas.get("items")
            if not isinstance(canvas_items, list):
                continue
            for annotation_page in canvas_items:
                annotations = annotation_page.get("items")
                if not isinstance(annotations, list):
                    continue
                for annotation in annotations:
                    body = googleart_extract_from_resource(annotation.get("body"))
                    if body:
                        return body
    return None


def googleart_normalize_image_url(image_url: str) -> str:
    cleaned = googleart_decode_json_string(image_url).strip()
    if cleaned.startswith("//"):
        cleaned = "https:" + cleaned
    if "googleusercontent.com" in cleaned and "=" in cleaned:
        base = cleaned.split("=")[0]
        cleaned = base + "=s0"
    return cleaned


def googleart_fetch_manifest(manifest_url: str) -> Optional[Dict[str, Any]]:
    normalized = googleart_decode_json_string(manifest_url).strip()
    if not normalized:
        return None
    if normalized.startswith("//"):
        normalized = "https:" + normalized
    try:
        resp = requests.get(normalized, headers=GOOGLE_ART_HEADERS, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as e:
        logging.debug("Failed to download Google Arts manifest %s: %s", normalized, e)
        return None


def googleart_fetch_manifest_from_api(asset_id: str) -> Optional[Dict[str, Any]]:
    candidate_urls = [
        f"https://content-artsandculture.googleusercontent.com/asset/{asset_id}?m=0",
        f"https://content-artsandculture.googleusercontent.com/asset/{asset_id}",
        f"https://content-artsandculture.googleusercontent.com/asset/{asset_id}?format=json",
    ]
    for url in candidate_urls:
        try:
            resp = requests.get(url, headers=GOOGLE_ART_HEADERS, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            logging.debug("Google Arts metadata request failed for %s: %s", url, e)
            continue
        try:
            data = resp.json()
        except ValueError as e:
            logging.debug("Failed to parse Google Arts metadata from %s: %s", url, e)
            continue
        if isinstance(data, dict):
            manifest_url = (
                data.get("iiifManifestUrl")
                or data.get("manifestUrl")
                or data.get("manifestUri")
                or data.get("assetManifestUrl")
            )
            if manifest_url:
                manifest_data = googleart_fetch_manifest(str(manifest_url))
                if manifest_data:
                    return manifest_data
        if isinstance(data, dict) and data.get("@context"):
            return data
    return None


def googleart_get_image(
    asset_id: str,
) -> Tuple[Optional[BytesIO], Optional[str], Optional[str], Optional[str]]:
    page_url = GOOGLE_ART_ASSET_BASE_URL + asset_id
    html_content = ""
    try:
        resp = requests.get(
            page_url,
            headers=GOOGLE_ART_HEADERS,
            timeout=30,
            allow_redirects=True,
        )
        resp.raise_for_status()
        html_content = resp.text
        page_url = resp.url
    except requests.RequestException as e:
        logging.error(
            "Failed to fetch Google Arts & Culture page for asset '%s': %s",
            asset_id,
            e,
        )

    manifest_data = None
    manifest_url = googleart_extract_manifest_url(html_content)
    if manifest_url:
        manifest_data = googleart_fetch_manifest(manifest_url)
    if manifest_data is None:
        manifest_data = googleart_fetch_manifest_from_api(asset_id)

    image_url = None
    if manifest_data:
        image_url = googleart_extract_image_url(manifest_data)
    if image_url is None:
        logging.error(
            "Failed to determine image URL for Google Arts & Culture asset '%s'",
            asset_id,
        )
        return None, None, None, None

    normalized_image_url = googleart_normalize_image_url(image_url)
    try:
        image_resp = requests.get(
            normalized_image_url, headers=GOOGLE_ART_HEADERS, timeout=30
        )
        image_resp.raise_for_status()
    except requests.RequestException as e:
        logging.error(
            "Failed to download Google Arts & Culture image for asset '%s': %s",
            asset_id,
            e,
        )
        return None, None, None, None

    image_data = BytesIO(image_resp.content)
    image_data.seek(0)
    content_type = image_resp.headers.get('Content-Type', '')
    file_type = (
        content_type.split('/')[-1].upper() if '/' in content_type else 'JPEG'
    )
    if not file_type:
        file_type = 'JPEG'

    return image_data, file_type, asset_id, page_url



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
GOOGLE_ART_SOURCE_NAME = "google_art"

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


def process_tv(
    tv_ip: str,
    image_data: Optional[BytesIO],
    file_type: Optional[str],
    image_identifier: Optional[str],
    display_url: Optional[str],
    remote_filename: Optional[str],
    source_name: str,
    photo_filter: str,
    matte_id: str,
) -> None:
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
            if image_identifier is None:
                logging.warning('Missing image identifier; skipping upload metadata logging.')
            else:
                upload_entry: Dict[str, Optional[str]] = {
                    'file': image_identifier,
                    'remote_filename': remote_filename,
                    'tv_ip': tv_ip if len(tvip_list) > 1 else None,
                    'source': source_name,
                }

                if display_url and display_url != image_identifier:
                    upload_entry['display_url'] = display_url

                if source_name in (UNSPLASH_SOURCE_NAME, GOOGLE_ART_SOURCE_NAME):
                    upload_entry['image_id'] = image_identifier

                uploaded_files.append(upload_entry)

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
    image_identifier: Optional[str] = None
    display_url: Optional[str] = None
    image_data: Optional[BytesIO] = None
    file_type: Optional[str] = None
    source_name: Optional[str] = None

    if args.image:
        image_path = args.image
        source_name = "local_image"
        image_identifier = image_path
        display_url = image_path
        logging.info(f'Selected source: {source_name} -> {image_path}')

        remote_filename = utils.get_remote_filename(image_identifier, source_name, tv_ip)
        if remote_filename:
            return None, None, image_identifier, remote_filename, source_name, display_url

        try:
            with open(image_path, 'rb') as f:
                image_data = BytesIO(f.read())
            ext = os.path.splitext(image_path)[1][1:].lower()
            file_type = 'JPEG' if ext in ('jpg', 'jpeg') else ext.upper()
        except Exception as e:
            logging.error(f'Failed to load image {image_path}: {e}')
            return None, None, None, None, None, None
    elif args.bingwallpaper:
        image_url = bing_get_image_url()
        source_name = BING_SOURCE_NAME
        image_identifier = image_url
        display_url = image_url
        logging.info(f'Selected source: {source_name} -> {image_url}')

        remote_filename = utils.get_remote_filename(image_identifier, source_name, tv_ip)

        if remote_filename:
            return None, None, image_identifier, remote_filename, source_name, display_url

        image_data, file_type = bing_get_image(image_url)
        if image_data is None:
            return None, None, None, None, None, None
    elif args.googleart:
        asset_input = args.googleart.strip()
        if asset_input.startswith("http"):
            asset_input = asset_input.split('?')[0].rstrip('/').split('/')[-1]
        else:
            asset_input = asset_input.split('?')[0].strip().strip('/')

        if not asset_input:
            logging.error('Invalid Google Arts & Culture asset identifier provided.')
            return None, None, None, None, None, None

        source_name = GOOGLE_ART_SOURCE_NAME
        remote_filename = utils.get_remote_filename(asset_input, source_name, tv_ip)
        if remote_filename:
            display_url = GOOGLE_ART_ASSET_BASE_URL + asset_input
            return None, None, asset_input, remote_filename, source_name, display_url

        image_data, file_type, image_identifier, display_url = googleart_get_image(asset_input)
        if image_data is None or image_identifier is None or display_url is None:
            return None, None, None, None, None, None

        source_name = GOOGLE_ART_SOURCE_NAME
        logging.info(f'Selected source: {source_name} -> {display_url}')

        identifier_candidates = [image_identifier, display_url]
        remote_filename = utils.get_remote_filename(identifier_candidates, source_name, tv_ip)
        if remote_filename:
            return None, None, image_identifier, remote_filename, source_name, display_url
    elif args.unsplash is not None:
        unsplash_id = None if args.unsplash is True else args.unsplash
        image_data, file_type, image_identifier, display_url = unsplash_get_image(unsplash_id)
        if image_data is None or image_identifier is None or display_url is None:
            return None, None, None, None, None, None
        source_name = UNSPLASH_SOURCE_NAME
        logging.info(f'Selected source: {source_name} -> {display_url}')

        identifier_candidates = [image_identifier, display_url]
        remote_filename = utils.get_remote_filename(identifier_candidates, source_name, tv_ip)
        if remote_filename:
            return None, None, image_identifier, remote_filename, source_name, display_url
    else:
        logging.error('No image source specified. Use --bingwallpaper, --googleart, --unsplash or --image.')
        return None, None, None, None, None, None

    logging.info('Resizing and cropping the image (3840x2160)...')
    resized_image_data = utils.resize_and_crop_image(image_data)

    if source_name is None or image_identifier is None or display_url is None or file_type is None:
        logging.error('Missing image metadata after processing; skipping upload.')
        return None, None, None, None, None, None

    return resized_image_data, file_type, image_identifier, None, source_name, display_url

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
    image_data, file_type, image_identifier, remote_filename, source_name, display_url = get_image_for_tv(ip)
    process_tv(
        ip,
        image_data,
        file_type,
        image_identifier,
        display_url,
        remote_filename,
        source_name,
        selected_photo_filter,
        selected_matte_identifier,
    )
