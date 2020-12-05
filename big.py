#!/usr/bin/python3

"""
pip3 install pdf2image
pip3 install --user pillow

apt install poppler-utils
or in anaconda powershell
conda install -c conda-forge poppler


apt install dos2unix
  use dos2unix, unix2dos
"""

import sys
print('python executable: ' , sys.executable)

import platform

if platform.node() == 'openmediavault': # running on raspberry. 

	file1 = '/home/pi/ramdisk/nyt_today.pbm'
else:
	file1 = 'src/nyt_today.pbm' # running on windows. will synch directly to ESP flash memory


file2 = '/var/www/openmediavault/nyt_today.pbm' # will be served as static file my my webserver


from PIL import Image, ImageFilter, ImageEnhance, ImageOps

import requests
from datetime import date

"""
# 4.2 inch
epd_w = 400
epd_h = 300
"""

"""
# v1 7.5
epd_w = 640
epd_h = 384
"""


# v2 7.5 inch
epd_w = 800
epd_h = 480



today = date.today()
d = today.strftime('%d')
m = today.strftime('%m')
y = today.strftime('%Y')


nyt =  "https://static01.nyt.com/images/" + str(y) + '/' + str(m) + '/' + str(d) + '/nytfrontpage/scan.pdf'
print(nyt)

#nyt = 'https://static01.nyt.com/images/2020/11/10/nytfrontpage/scan.pdf'

pdf_file = 'nyt_today.pdf'
print('get pdf from NYT into ', pdf_file)

h = requests.head(nyt, allow_redirects=True)
print(h.headers.get('content_type'))

r = requests.get(nyt, allow_redirects=True)
print(type(r.content))

open(pdf_file, 'wb').write(r.content)

#https://stackoverflow.com/questions/46184239/extract-a-page-from-a-pdf-as-a-jpeg
#https://pypi.org/project/pdf2image/

from pdf2image import convert_from_path, convert_from_bytes


#https://www.waveshare.com/wiki/7.5inch_e-Paper_HAT
pages = convert_from_path(pdf_file, dpi=200, grayscale=True) # list of PIL images
im = pages[0]

"""
im.save('nty_today.jpg', 'JPEG')
im.save('nty_today.pbm')    # portable bit map
"""

print('1st page: ', im.format, im.size, im.mode)  # PPM (2442, 4685) L
# L means  luminance, ie grayscale. for color RGB
# PPM portable pixmap
# https://en.wikipedia.org/wiki/Netpbm

# crop top of image, 0 is upper left corner
# region is defined by a 4-tuple, where coordinates are (left, upper, right, lower).

print('epaper aspect ratio ', epd_w/epd_h)

W=im.size[0]
H = W * epd_h / epd_w # would keep aspect ratio

# but rather
H=im.size[1]/2  # see more content vs keeping ratio

print('crop aspect ration ', W/H)

box = (0,100,W,H)
# 100 remove top layer. trial and error
# get top half the page of NYT pdf. 7.5 inch is still a small screen. and we get the headlines

top = im.crop(box)
#top = ImageOps.invert(top) # otherwize, reversed on epaper

#top = top.resize((epd_h, epd_w)) # portrait mode
top = top.resize((epd_w, epd_h)) # use epaper in landscape mode
top = top.filter(ImageFilter.DETAIL)

# based on how you set up the epaper dispay
#top = top.transpose(Image.ROTATE_180) # epaper connector on top

top.show() # will block

top = top.convert('1') # to get portable bit map P4, ie just black and white vs grayscale
print('pbm: ', top.format, top.size, top.mode)



top.save(file1)    # portable bit map

if platform.node() == 'openmediavault': # running on raspberry. 

	# remove 1st two lines to only keep the real bitmap
	with open(file1, 'rb') as fp:
		fp.readline()
		fp.readline()
		buf = fp.read()

	assert len(buf) == epd_w * epd_h // 8

	print(len(buf), epd_w * epd_h //8)

	with open(file1, 'wb') as fp:
		fp.write(buf)

	print('copy to webserver')
	# move to web server as file
	from shutil import copyfile
	copyfile(file1, file2)

"""
hex dump of PBM file Black and White
P4<nl><width><space><height><nl>  then the bitmap starts
000000  50 34 0a 34 30 30 20 33 30 30 0a 00 00 00 00 00  P4.400 300......
"""

