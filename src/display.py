#!/usr/bin/python3
"""
Script to display the daily page.
Link it in /etc/cron.daily to run it daily. Must be run as root to access ePaper display.
"""

import datetime
from PIL import Image
from waveshare_epd import epd7in5

image = Image.open(f"out/{datetime.datetime.today().day:1d}.gif")

epd = epd7in5.EPD()
epd.init()
epd.display(epd.getbuffer(image))
epd.sleep()
