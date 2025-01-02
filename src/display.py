#!/usr/bin/python3

import datetime
from PIL import Image
from waveshare_epd import epd7in5

image = Image.open("out/{0:1d}.gif".format(datetime.datetime.today().day))

epd = epd7in5.EPD()
epd.init()
epd.display(epd.getbuffer(image))
epd.sleep()
