#!/usr/bin/python3

# This script is meant to be run by cron monthly

import requests
import sqlite3
import tempfile
import os
import dragonmapper.transcriptions

# Settings
URL_PLECO_FLASHCARD_DATABASE: str = 'http://raspi4/sync/phone/pleco/databases/Pleco%20Flashcard%20Database.pqb'

# Download Database
_, database_file = tempfile.mkstemp(prefix='hanzihua-')

with open(database_file, "wb") as f:
    with requests.get(URL_PLECO_FLASHCARD_DATABASE) as r:
        f.write(r.content)

with sqlite3.connect(database_file) as database:
    # Get 31 flash cards sorted by score hw=Chinese pron=Pronunciation, defn=Definition
    # Use flash cards with hard coded definition only
    cards = database.cursor().execute('select c.hw, c.pron, c.defn from pleco_flash_scores_1 s, pleco_flash_cards c ' +
                                      'where c.id = s.card and c.defn NOT NULL order by s.score limit 31')

    for hw, pron, defn in cards:
        # Tidy up
        hw: str = hw.replace('@', '')
        pron: str = pron.replace('@', '')
        pron: str = dragonmapper.transcriptions.numbered_to_accented(pron)
        defn: str = defn.split('\n')[0]
        defn: str = defn.replace('• ', '')
        defn: str = defn.split('  ')[0]
        defn: str = defn.split(',')[0]
        defn: str = defn.split(';')[0]
        defn: str = defn.split('/')[0]
        defn: str = defn.strip()
        print(hw, pron, defn)

# Tidy up
os.unlink(database_file)
