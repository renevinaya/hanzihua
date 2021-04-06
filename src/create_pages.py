#!/usr/bin/python3

# This script is meant to be run by cron monthly
import typing

import requests
import sqlite3
import tempfile
import os
from dragonmapper import transcriptions
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from typing import Union

# Settings
URL_PLECO_FLASHCARD_DATABASE: str = 'http://raspi4/sync/phone/pleco/databases/Pleco%20Flashcard%20Database.pqb'
FONT_CHINESE: ImageFont = ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc', 140)
FONT_LATIN: ImageFont = ImageFont.truetype('/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf', 30)
HEIGHT: int = 384
WIDTH: int = 600

SIZE: (int, int) = (WIDTH, HEIGHT)
CENTER_HEIGHT: int = int(HEIGHT/2)
CENTER_WIDTH: int = int(WIDTH/2)


def main():
    # Download Database
    _, database_file = tempfile.mkstemp(prefix='hanzihua-')
    with open(database_file, "wb") as f:
        with requests.get(URL_PLECO_FLASHCARD_DATABASE) as r:
            f.write(r.content)
    with sqlite3.connect(database_file) as database:
        # Get 31 flash cards sorted by score hw=Chinese pron=Pronunciation, defn=Definition
        # Use flash cards with hard coded definition only
        cards = database.cursor().execute(
            'select c.hw, c.pron, c.defn from pleco_flash_scores_1 s, pleco_flash_cards c ' +
            'where c.id = s.card and c.defn NOT NULL order by s.score limit 31')

        day_of_month: int = 0
        for hw, pron, defn in cards:
            # Tidy up
            day_of_month += 1
            create_page(day_of_month, defn, hw, pron)
    # Tidy up
    os.unlink(database_file)


def create_page(day_of_month, defn, hw, pron):
    hw: str = hw.replace('@', '')
    pron: str = pron.replace('@', '')
    pron: str = transcriptions.numbered_to_accented(pron)
    defn: str = defn.split('\n')[0]
    defn: str = defn.replace('• ', '')
    defn: str = defn.split('  ')[0]
    defn: str = defn.split(',')[0]
    defn: str = defn.split(';')[0]
    defn: str = defn.split('/')[0]
    defn: str = defn.strip()
    print(hw, pron, defn)

    # Draw image for each day
    image: Image = Image.new("1", SIZE, color=1)
    draw: ImageDraw = ImageDraw.Draw(image)
    draw_centered_text(CENTER_HEIGHT - 80, hw, FONT_CHINESE, draw)
    draw_centered_text(CENTER_HEIGHT + 60, pron, FONT_LATIN, draw)
    draw_centered_text(CENTER_HEIGHT + 120, defn, FONT_LATIN, draw)
    image.save("out/{0:1d}.gif".format(day_of_month))
    image.close()


def draw_centered_text(y: Union[int, float], text: str, font: ImageFont, draw: ImageDraw):
    width_of_text, height_of_text = font.getsize(text)
    x_position: int = int((WIDTH-width_of_text)/2)
    y_position: int = int(y - (height_of_text/2))
    draw.text((x_position, y_position), text, fill=0, font=font)


main()