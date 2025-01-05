#!/usr/bin/python3
"""
Script to display the daily page.
Link it in /etc/cron.daily to run it daily. Must be run as root to access ePaper display.
"""

import datetime
import pathlib
from PIL import Image
from waveshare_epd import epd7in5

folder = pathlib.Path(__file__).parent.resolve()
image = Image.open(f"{folder}/out/{datetime.datetime.today().day:1d}.gif")

epd = epd7in5.EPD()
epd.init()
epd.display(epd.getbuffer(image))
epd.sleep()
