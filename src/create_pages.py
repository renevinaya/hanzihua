#!/usr/bin/python3

# This script is meant to be run by cron monthly
import typing

import requests
import sqlite3
import tempfile
import os
import gzip
from dragonmapper import transcriptions
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from typing import Union, Dict, Tuple

# Settings
URL_PLECO_FLASHCARD_DATABASE: str = 'http://raspi4/sync/phone/pleco/databases/Pleco%20Flashcard%20Database.pqb'
URL_CC_CEDICT_DATABASE: str = 'https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz'
FONT_CHINESE: ImageFont = ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc', 200)
FONT_LATIN: ImageFont = ImageFont.truetype('/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf', 40)
HEIGHT: int = 384
WIDTH: int = 640

SIZE: (int, int) = (WIDTH, HEIGHT)
CENTER_HEIGHT: int = int(HEIGHT / 2)
CENTER_WIDTH: int = int(WIDTH / 2)


def main():
    # Download Database
    _, pleco_database_file = tempfile.mkstemp(prefix='hanzihua-')
    with open(pleco_database_file, "wb") as f:
        with requests.get(URL_PLECO_FLASHCARD_DATABASE) as r:
            f.write(r.content)
    with sqlite3.connect(pleco_database_file) as database:
        # Get 31 flash cards sorted by score hw=Chinese pron=Pronunciation, defn=Definition
        cards = database.cursor().execute(
            'select c.hw, c.pron, c.defn from pleco_flash_scores_1 s, pleco_flash_cards c ' +
            'where c.id = s.card order by s.score limit 60')

        day_of_month: int = 1
        for hw, pron, defn in cards:
            # Try to create page
            if create_page(day_of_month, defn, hw, pron):
                day_of_month += 1
            if day_of_month == 32:
                break
    # Tidy up
    os.unlink(pleco_database_file)


def create_page(day_of_month, defn, hw, pron) -> bool:
    # Tidy up
    hw: str = hw.replace('@', '')
    if len(hw) > 3:
        # Skip long words
        print('Too long Chinese:', hw)
        return False
    pron: str = pron.replace('@', '')
    pron: str = transcriptions.numbered_to_accented(pron)
    if defn is None:
        if hw in CE_CCDICT:
            defn = CE_CCDICT[hw]
        else:
            print('No Translation:', hw, pron)
            return False
    else:
        defn: str = defn.split('\n')[0]
        defn: str = defn.replace('• ', '')
        defn: str = defn.split('  ')[0]
        defn: str = defn.split(',')[0]
        defn: str = defn.split(';')[0]
        defn: str = defn.split('/')[0]
        defn: str = defn.strip()
    width_defn, _ = FONT_LATIN.getsize(defn)
    if width_defn > WIDTH:
        print('Too long translation', hw, pron, defn)
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


def draw_centered_text(y: Union[int, float], text: str, font: ImageFont, draw: ImageDraw):
    width_of_text, height_of_text = font.getsize(text)
    x_position: int = int((WIDTH - width_of_text) / 2)
    y_position: int = int(y - (height_of_text / 2))
    draw.text((x_position, y_position), text, fill=0, font=font)


def get_ce_ccdict() -> Dict[str, str]:
    ce_ccdict: Dict[str, str] = {}
    with requests.get(URL_CC_CEDICT_DATABASE) as r:
        ce_ccdict_bytes: bytes = gzip.decompress(r.content)
        for entry_bytes in ce_ccdict_bytes.split(b'\n'):
            line: str = entry_bytes.decode()
            if line.startswith('#'):
                continue
            # Credits:
            # https://github.com/rubber-duck-dragon/rubber-duck-dragon.github.io/blob/master/cc-cedict_parser/parser.py
            line = line.rstrip('/')
            line = line.split('/')
            if len(line) <= 1:
                continue
            english = line[1]
            char_and_pinyin = line[0].split('[')
            characters = char_and_pinyin[0]
            characters = characters.split()
            simplified = characters[1]
            if "surname" != english:
                ce_ccdict[simplified] = english

    return ce_ccdict


CE_CCDICT: Dict[str, str] = get_ce_ccdict()

main()
