#!/usr/bin/python3

import datetime
from waveshare_epd import epd7in5
from PIL import Image

image: Image = Image.open("out/{0:1d}.gif".format(datetime.datetime.today().day))

epd = epd7in5.EPD()
epd.init()
epd.display(epd.getbuffer(image))
epd.sleep()
