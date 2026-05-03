"""
OCR utilities for extracting Eve Echoes game data from screenshots.

Requires:  Pillow, pytesseract
           System: tesseract-ocr  (apt install tesseract-ocr)
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Any

from PIL import Image, ImageFilter, ImageEnhance


# ── pre-processing ─────────────────────────────────────────────────────────────

def _preprocess(image: Image.Image) -> Image.Image:
    """Convert to greyscale, sharpen and boost contrast for better OCR."""
    image = image.convert("L")
    image = image.filter(ImageFilter.SHARPEN)
    image = ImageEnhance.Contrast(image).enhance(2.0)
    return image


def _ocr(image: Image.Image) -> str:
    """Run tesseract OCR and return extracted text."""
    try:
        import pytesseract  # local import so the module can still be imported without tesseract

        processed = _preprocess(image)
        text = pytesseract.image_to_string(processed, lang="eng")
        return text
    except Exception:
        return ""


def image_from_bytes(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


# ── ISK parsing ───────────────────────────────────────────────────────────────

# Eve Echoes shows ISK with commas or dots as thousand separators,
# optionally followed by "ISK", "isk", "к" (cyrillic K) or "M"/"B" suffix.
_ISK_PATTERNS = [
    # e.g. "1,234,567.89 ISK"  or  "1.234.567,89 ISK"
    re.compile(
        r"([\d]{1,3}(?:[.,\s]\d{3})*(?:[.,]\d{1,2})?)\s*(?:ISK|isk|иск)",
        re.IGNORECASE,
    ),
    # suffixed shorthand: 1.5B  250M  300K
    re.compile(
        r"([\d]+(?:[.,]\d+)?)\s*([KkМмBbGg])\b",
        re.IGNORECASE,
    ),
]

_SUFFIX_MULT = {
    "k": 1_000,
    "к": 1_000,
    "m": 1_000_000,
    "м": 1_000_000,
    "b": 1_000_000_000,
    "g": 1_000_000_000,
}


def _clean_number(raw: str) -> float:
    """Turn '1,234,567.89' or '1.234.567,89' into a plain float."""
    raw = raw.strip()
    # If there's a comma followed by exactly 2 digits at the end → decimal separator
    if re.search(r",\d{2}$", raw):
        raw = raw.replace(".", "").replace(",", ".")
    else:
        raw = raw.replace(",", "").replace(" ", "")
    try:
        return float(raw)
    except ValueError:
        return 0.0


def parse_isk(text: str) -> float:
    """Return the largest ISK value found in *text*, or 0."""
    best = 0.0
    for pat in _ISK_PATTERNS:
        for m in pat.finditer(text):
            if len(m.groups()) == 2 and m.group(2):
                # suffixed
                val = _clean_number(m.group(1))
                mult = _SUFFIX_MULT.get(m.group(2).lower(), 1)
                val *= mult
            else:
                val = _clean_number(m.group(1))
            if val > best:
                best = val
    return best


def extract_isk_from_image(data: bytes) -> float:
    img = image_from_bytes(data)
    return parse_isk(_ocr(img))


# ── kill-mail parsing ─────────────────────────────────────────────────────────

@dataclass
class KillData:
    pilot_name: str = ""
    corp_name: str = ""
    ship_name: str = ""
    isk_value: float = 0.0
    raw_text: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


_SHIP_KEYWORDS = [
    "Heron", "Merlin", "Kestrel", "Condor",  # Caldari
    "Rifter", "Probe", "Burst", "Slasher",   # Minmatar
    "Punisher", "Tormentor", "Executioner",  # Amarr
    "Tristan", "Atron", "Incursus",          # Gallente
    # larger hulls
    "Caracal", "Moa", "Drake", "Ferox", "Raven", "Scorpion",
    "Rupture", "Stabber", "Hurricane", "Tempest", "Typhoon",
    "Maller", "Omen", "Harbinger", "Prophecy", "Abaddon",
    "Thorax", "Brutix", "Myrmidon", "Dominix", "Megathron",
    "Vexor",
    # Cruisers / BC / BS (generic)
    "Cruiser", "Battlecruiser", "Battleship", "Destroyer", "Frigate",
]

_KILLED_PATTERN = re.compile(
    r"(?:killed|destroyed|loss)\s*:?\s*([A-Za-z][A-Za-z0-9 '-]+)",
    re.IGNORECASE,
)
_PILOT_PATTERN = re.compile(
    r"(?:pilot|player|victim)\s*:?\s*([A-Za-z][A-Za-z0-9 '-]+)",
    re.IGNORECASE,
)
_CORP_PATTERN = re.compile(
    r"(?:corp|corporation|alliance)\s*:?\s*([A-Za-z][A-Za-z0-9 '\[\]-]+)",
    re.IGNORECASE,
)


def parse_killmail(text: str) -> KillData:
    kd = KillData(raw_text=text)
    kd.isk_value = parse_isk(text)

    m = _KILLED_PATTERN.search(text)
    if m:
        kd.ship_name = m.group(1).strip()
    else:
        # try to identify ship by keyword
        for kw in _SHIP_KEYWORDS:
            if re.search(r"\b" + kw + r"\b", text, re.IGNORECASE):
                kd.ship_name = kw
                break

    m = _PILOT_PATTERN.search(text)
    if m:
        kd.pilot_name = m.group(1).strip()

    m = _CORP_PATTERN.search(text)
    if m:
        kd.corp_name = m.group(1).strip()

    return kd


def extract_killmail_from_image(data: bytes) -> KillData:
    img = image_from_bytes(data)
    text = _ocr(img)
    return parse_killmail(text)


# ── PvE mission parsing ───────────────────────────────────────────────────────

_MISSION_REWARD_PATTERN = re.compile(
    r"(?:reward|награда|completion|выполнено)[^\d]*([\d,. ]+)\s*(?:ISK|isk)?",
    re.IGNORECASE,
)
_MISSION_NAME_PATTERN = re.compile(
    r"(?:mission|миссия)[:\s]+([A-Za-zА-Яа-я][A-Za-zА-Яа-я0-9 '-]+)",
    re.IGNORECASE,
)


@dataclass
class MissionData:
    mission_name: str = ""
    isk_reward: float = 0.0
    raw_text: str = ""


def parse_mission(text: str) -> MissionData:
    md = MissionData(raw_text=text)
    m = _MISSION_REWARD_PATTERN.search(text)
    if m:
        md.isk_reward = _clean_number(m.group(1))
    else:
        md.isk_reward = parse_isk(text)

    m = _MISSION_NAME_PATTERN.search(text)
    if m:
        md.mission_name = m.group(1).strip()

    return md


def extract_mission_from_image(data: bytes) -> MissionData:
    img = image_from_bytes(data)
    text = _ocr(img)
    return parse_mission(text)


# ── Registration / character name parsing ─────────────────────────────────────

_CHAR_NAME_PATTERN = re.compile(
    r"(?:character|pilot|name|персонаж|пилот|имя)\s*:?\s*([A-Za-z][A-Za-z0-9 '-]{2,30})",
    re.IGNORECASE,
)


def extract_character_name(data: bytes) -> str:
    img = image_from_bytes(data)
    text = _ocr(img)
    m = _CHAR_NAME_PATTERN.search(text)
    if m:
        return m.group(1).strip()
    # fallback: return largest capitalised token
    tokens = re.findall(r"[A-Z][a-z]{2,}(?:\s[A-Z][a-z]{2,})?", text)
    return tokens[0] if tokens else ""


# ── Transaction / deposit parsing ─────────────────────────────────────────────

@dataclass
class TransactionData:
    amount: float = 0.0
    sender: str = ""
    receiver: str = ""
    raw_text: str = ""


_TRANSFER_FROM_PATTERN = re.compile(
    r"(?:from|от)\s*:?\s*([A-Za-z][A-Za-z0-9 '-]+)",
    re.IGNORECASE,
)
_TRANSFER_TO_PATTERN = re.compile(
    r"(?:to|кому)\s*:?\s*([A-Za-z][A-Za-z0-9 '-]+)",
    re.IGNORECASE,
)


def parse_transaction(text: str) -> TransactionData:
    td = TransactionData(raw_text=text)
    td.amount = parse_isk(text)
    m = _TRANSFER_FROM_PATTERN.search(text)
    if m:
        td.sender = m.group(1).strip()
    m = _TRANSFER_TO_PATTERN.search(text)
    if m:
        td.receiver = m.group(1).strip()
    return td


def extract_transaction_from_image(data: bytes) -> TransactionData:
    img = image_from_bytes(data)
    text = _ocr(img)
    return parse_transaction(text)
