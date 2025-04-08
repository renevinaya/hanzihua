#!/usr/bin/python3
"""
Script to create the pages for each day of a month.
Link it in /etc/cron.monthly to run it monthly. Should be run as non-root.
"""

import re
import sqlite3
import sys
import tempfile
import os
import gzip
from typing import Union, Dict, List
import requests
import boto3
from dragonmapper import transcriptions
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
import config

# Settings
URL_PLECO_FLASHCARD_DATABASE: str = "http://raspi4/sync/phone/pleco/flashbackup.pqb"
URL_CC_CEDICT_DATABASE: str = (
    "https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz"
)
FONT_CHINESE = ImageFont.truetype(
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc", 190
)
FONT_LATIN = ImageFont.truetype(
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf", 40
)
HEIGHT: int = 384
WIDTH: int = 640
# parts of the display are covered by the frame
MAX_WIDTH: int = 540

SIZE: tuple[int, int] = (WIDTH, HEIGHT)
CENTER_HEIGHT: int = int(HEIGHT / 2)
CENTER_WIDTH: int = int(WIDTH / 2)


def main():
    """
    Main function, which downloads the Pleco Database and creates the pages for each day
    """
    # Download Database
    _, pleco_database_file = tempfile.mkstemp(prefix="hanzihua-")

    download_database(pleco_database_file)

    with open(pleco_database_file, "wb") as f:
        with requests.get(URL_PLECO_FLASHCARD_DATABASE) as r:
            f.write(r.content)
    with sqlite3.connect(pleco_database_file) as database:
        # Get categories of flash cards, which are currently selected for learning
        category_entries = database.cursor().execute(
            "select propvalue from pleco_flash_profilesettings "
            + 'where propid="pro_categories" and propvalue not null'
        )
        if category_entries.arraysize < 1:
            print("Please select flash card categories in Pleco")
            sys.exit()

        categories: str | None = None
        for category_entry in category_entries:
            categories = category_entry[0][0:-1]  # Remove trailing comma
        if categories is None or not re.match("[0-9,-]", categories):
            print("Unexpected format for category list: ", categories)
            sys.exit()
        print("Categories:", categories)

        # Get flash cards sorted by score hw=Chinese pron=Pronunciation, defn=Definition
        cards = database.cursor().execute(
            "select c.hw, c.pron, c.defn "
            + "from pleco_flash_scores_1 s, pleco_flash_cards c, pleco_flash_categoryassigns ca "
            + "where c.id = s.card and c.id = ca.card and ca.cat IN("
            + categories
            + ") order by s.score limit 60"
        )

        day_of_month: int = 1
        for hw, pron, defn in cards:
            # Try to create page
            if create_page(day_of_month, defn, hw, pron):
                day_of_month += 1
            if day_of_month == 32:
                break
    # Tidy up
    os.unlink(pleco_database_file)


def download_database(pleco_database_file):
    s3 = boto3.client("s3", region_name=config.REGION)
    databases = s3.list_objects_v2(
        Bucket=config.BUCKET,
        Prefix=config.PREFIX,
    )
    latest_database = databases.get("Contents", [])[0].get("Key", "")
    for database in databases.get("Contents", []):
        if database.get("Key", "") > latest_database:
            latest_database = database.get("Key", "")
    print("Latest database:", latest_database)
    s3.download_file(
        Bucket=config.BUCKET,
        Key=latest_database,
        Filename=pleco_database_file,
    )


def create_page(day_of_month: int, defn: str, hw: str, pron: str) -> bool:
    """
    Creates page for day of month based on database entry.
    Cleans the defintions and return True, if page has been created.
    """
    # Tidy up
    hw = hw.replace("@", "")
    if len(hw) > 3:
        # Skip long words
        print("Too long Chinese:", hw)
        return False
    pron = pron.replace("@", "")
    pron = pron.replace("/", "")
    pron = transcriptions.numbered_to_accented(pron)
    if defn is None:
        if hw in CE_CCDICT:
            defn = CE_CCDICT[hw]
        else:
            print("No Translation:", hw, pron)
            return False
    else:
        defn = defn.split("\n")[0]
        defn = defn.replace("• ", "")
        defn = defn.split("  ")[0]
        defn = defn.split(",")[0]
        defn = defn.split(";")[0]
        defn = defn.split("/")[0]
        defn = defn.strip()
    width_defn = FONT_LATIN.getlength(defn)
    if width_defn > MAX_WIDTH:
        print("Too long translation", hw, pron, defn)
        return False

    # Draw image for each day
    image: Image = Image.new("1", SIZE, color=1)
    draw: ImageDraw = ImageDraw.Draw(image)
    draw_centered_text(CENTER_HEIGHT - 30, hw, FONT_CHINESE, draw)
    draw_centered_text(CENTER_HEIGHT - 150, pron, FONT_LATIN, draw)
    draw_centered_text(CENTER_HEIGHT + 150, defn, FONT_LATIN, draw)
    image.save(f"out/{day_of_month}.gif")
    image.close()
    return True


def draw_centered_text(
    y: Union[int, float], text: str, font: ImageFont.FreeTypeFont, draw: ImageDraw.ImageDraw
):
    """
    Helper function to draw text horizontally centered
    """
    _, _, width_of_text, height_of_text = font.getbbox(text)
    x_position: int = int((WIDTH - width_of_text) / 2)
    y_position: int = int(y - (height_of_text / 2))
    draw.text((x_position, y_position), text, fill=0, font=font)


def get_ce_ccdict() -> Dict[str, str]:
    """
    Downloads database with translations and cleans the translations
    """
    ce_ccdict: Dict[str, str] = {}
    with requests.get(URL_CC_CEDICT_DATABASE) as r:
        ce_ccdict_bytes: bytes = gzip.decompress(r.content)
        for entry_bytes in ce_ccdict_bytes.split(b"\n"):
            line: str = entry_bytes.decode()
            if line.startswith("#"):
                continue
            # Credits:
            # https://github.com/rubber-duck-dragon/rubber-duck-dragon.github.io/blob/master/cc-cedict_parser/parser.py
            line = line.rstrip("/")
            lines: List[str] = line.split("/")
            if len(lines) <= 1:
                continue
            english: str = lines[1]
            char_and_pinyin: List[str] = lines[0].split("[")
            characters: List[str] = char_and_pinyin[0].split()
            simplified: str = characters[1]
            if english.startswith("variant of"):
                continue
            if english.startswith("surname"):
                continue
            ce_ccdict[simplified] = english

    return ce_ccdict


CE_CCDICT: Dict[str, str] = get_ce_ccdict()

main()
