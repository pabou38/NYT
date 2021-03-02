#!/usr/bin/python3

###############################
# 12 jan 2021
# 2 mars 2021 
#   check request return code. pdf may not be available
#   use lighttpd , instead of OMV5 nginx. needed to use different urequests because of redirect; and error ???
##############################

"""
pip3 install pdf2image
pip3 install --user pillow

apt install poppler-utils
or in anaconda powershell
conda install -c conda-forge poppler


apt install dos2unix
  use dos2unix, unix2dos
"""
import datetime

x = datetime.datetime.now()
print(x)

print('get pdf from NTY. convert in pbm')

import sys
print('python executable: ' , sys.executable)

import platform

if platform.node() == 'openmediavault': # running on raspberry. 

	# to be copied on web server
	file1 = '/home/pi/ramdisk/nyt_today.pbm'
else:
	# running on windows. will synch directly to ESP flash memory with v scode
	file1 = 'src/nyt_today.pbm' 


# webserver file
#file2 = '/var/www/openmediavault/nyt_today.pbm' # will be served as static file my my webserver
file2 = '/var/www/html/epaper/nyt_today.pbm' # will be served as static file my my webserver
#image/x-portable-bitmap


# debug. access pdf also (browser do not display pbm; just download them)
#file3= '/var/www/openmediavault/nyt_today.pdf' # will be served as static file my my webserver
file3= '/var/www/html/epaper/nyt_today.pdf' # will be served as static file my my webserver


print('web server path for pbm' , file2)

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


################################
# today's file. WARNING. with time difference, may not exists yet
################################

nyt =  "https://static01.nyt.com/images/" + str(y) + '/' + str(m) + '/' + str(d) + '/nytfrontpage/scan.pdf'
print('url nyt:', nyt)

#nyt = 'https://static01.nyt.com/images/2020/11/10/nytfrontpage/scan.pdf'

pdf_file = 'nyt_today.pdf'
print("get TODAY's pdf from NYT into ", pdf_file)



#Make a HEAD request to a web page, and return the HTTP headers:
#HEAD requests are done when you do not need the content of the file, but only the status_code or HTTP headers.
#The requests.Response() Object contains the server's response to the HTTP request.

h = requests.head(nyt, allow_redirects=True)
print('headers: ', h.headers)
print('content type: ', h.headers.get('Content-Type'))


r = requests.get(nyt, allow_redirects=True)

print('get status code : ', r.status_code)
print('get OK : ', r.ok)

print('is redirect : ', r.is_redirect)
print('is permanent redirect : ', r.is_permanent_redirect)
print('elapsed : ', r.elapsed)
print('url : ', r.url)

print('type of content ', type(r.content))


if r.ok == False:
	print('request get failed. maybe the pdf is not yet available')
	sys.exit(1)


# write pdf file
open(pdf_file, 'wb').write(r.content)

#https://stackoverflow.com/questions/46184239/extract-a-page-from-a-pdf-as-a-jpeg
#https://pypi.org/project/pdf2image/

from pdf2image import convert_from_path, convert_from_bytes

#https://www.waveshare.com/wiki/7.5inch_e-Paper_HAT
pages = convert_from_path(pdf_file, dpi=200, grayscale=True) # list of PIL images

# first (and only) page
im = pages[0]

"""
im.save('nty_today.jpg', 'JPEG')
im.save('nty_today.pbm')    # portable bit map
"""

print('1st and only pdf page: ', im.format, im.size, im.mode)  # PPM (2442, 4685) L
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

print('crop aspect ratio to get more content, H is org size /2 , W is org size ', W/H)

box = (0,100,W,H)
# 100 remove top layer. trial and error
# get top half the page of NYT pdf. 7.5 inch is still a small screen. and we get the headlines

top = im.crop(box)
#top = ImageOps.invert(top) # otherwize, reversed on epaper

#top = top.resize((epd_h, epd_w)) # portrait mode
print('resize to epaper, landscape mode')
top = top.resize((epd_w, epd_h)) # use epaper in landscape mode
top = top.filter(ImageFilter.DETAIL)

# based on how you set up the epaper dispay
#top = top.transpose(Image.ROTATE_180) # epaper connector on top

top.show() # will block

top = top.convert('1') # to get portable bit map P4, ie just black and white vs grayscale
print('pbm: ', top.format, top.size, top.mode)

# either ramdisk or src
top.save(file1)    # portable bit map

# if on PI, copy to webserver
if platform.node() == 'openmediavault':

	print('running on raspberry, remove first 2 lines to only keep bitmap')
	# remove 1st two lines to only keep the real bitmap
	# P4<nl><width><space><height><nl>  then the bitmap starts

	with open(file1, 'rb') as fp:
		fp.readline()
		fp.readline()
		buf = fp.read()

	assert len(buf) == epd_w * epd_h // 8

	print('len buf %d, w*h/8 %d' %(len(buf), epd_w * epd_h //8))

	with open(file1, 'wb') as fp:
		fp.write(buf)

	print('copy pbm file to webserver ', file2)
	print('copy pdf file to webserver ', file3)
	# copy pbm file to web server
	# also copy pdf to check thru browser
	# IP/nyt_today.pdf

	# accessing a file is OK; a directory does not work. 403 forbidden. config issue likely

	from shutil import copyfile
	copyfile(file1, file2)
	copyfile(pdf_file, file3)

"""
hex dump of PBM file Black and White
P4<nl><width><space><height><nl>  then the bitmap starts
000000  50 34 0a 34 30 30 20 33 30 30 0a 00 00 00 00 00  P4.400 300......
"""

