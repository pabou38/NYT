
from utime import ticks_ms
start_time = ticks_ms() # note t=time() is in seconds. to measure execution time
print('\n\nboot starting\n\n')

# vs code will infer tab size from from file type
# custo File → Preferences → User Settings tab size and detect

import gc
from machine import deepsleep, idle, RTC, reset_cause, DEEPSLEEP_RESET, DEEPSLEEP
from utime import sleep_ms, sleep, sleep_us, localtime, mktime
from machine import Pin
import framebuf

# check if the device woke from a deep sleep
if reset_cause() == DEEPSLEEP_RESET:
    print('woke from a deep sleep')
else:
    print('fresh boot')

r = RTC()
mem = r.memory()  # content survives deep sleep

print('RTC memory contents (bytes): ', mem)  # bytes

# initialize and increment RTC memory.  digit as string
if mem == b'':
    print('RTC memory empty. initializing with "0" ..')
    mem = "0"
    r.memory(mem)

mem_int = int(mem)

# avoid gosts
if mem_int == 9:
    avoid_ghost = True  # could be used to do some housekeeping on the display every x deep sleep
    mem_int = 1
    print('will fill buffer with 1 = white')
else:
    avoid_ghost = False
    mem_int = mem_int + 1
    print('no need to fill with white yet')

mem = str(mem_int)
r.memory(mem)
print('writing to RTC memory for next boot: str, int ', mem, mem_int)

# power led removed with cuter to save power during deep sleep
# on board red led is GPIO 2

# to signal we are running. will be set to off just before going to deep sleep
led = Pin(2, Pin.OUT, value=0)
led.on()


"""
framebuffer:
This module provides a general frame buffer which can be used to create bitmap 
images, which can then be sent to a display.
http://docs.micropython.org/en/latest/library/framebuf.html
buffer is an object with a buffer protocol which must be large enough to contain every pixel 
defined by the width, height and format of the FrameBuffer.
"""

################################################
# create framebuf from local PBM file in ESP32 flash memory
################################################
def frame_local():
    print('get PBM from flash memory')
    gc.collect()
    free = gc.mem_free(); alloc = gc.mem_alloc()
    print("mem free %d, alloc %d, sum %d, percent free %0.2f"  %(free, alloc, free+alloc, free/(free+alloc)))

    pbm_file = 'nyt_today.pbm'
    print('\nread portable bitmap file')

    fp = open(pbm_file, 'rb')
    print('type: ', fp.readline()) # P4
    dim = fp.readline()
    w = int(dim.split()[0])
    h = int(dim.split()[1])
    print('portable bitmap file: w %d, h %d' %(w,h))
    size = w*h//8

    gc.collect()
    free = gc.mem_free(); alloc = gc.mem_alloc()
    print("mem free %d, alloc %d, sum %d, percent free %0.2f"  %(free, alloc, free+alloc, free/(free+alloc)))
    #The bytearray type is a mutable sequence of integers in the range 0 <= x < 256
    buf = bytearray(size) # [0] class int
    print('buf bytearray allocated. object with a buffer protocol ' , len(buf), type(buf))

    for i in range(size):
        x = fp.read(1)
        x = int.from_bytes(x,'little')
        buf[i] = x

    fp.close()

    gc.collect()
    print('delta free: ', free - gc.mem_free())

    # buf need to be bytearray, not bytes TypeError: object with buffer protocol required
    fb = framebuf.FrameBuffer(buf, w, h, framebuf.MONO_HLSB)
    print('framebuffer created' , type(fb))
    return (fb, buf)


#########################################################
# create framebuf from web server's PBM file
#########################################################
def frame_remote():

    print('create frame buffer from webserver pbm file')
    gc.collect()
    free = gc.mem_free(); alloc = gc.mem_alloc()
    print("mem free %d, alloc %d, sum %d, percent free %0.2f"  %(free, alloc, free+alloc, free/(free+alloc)))

    # use lighttpd to serve static files
    s = "http://192.168.1.206:81/epaper/nyt_today.pbm"
    print('\ngetting pbm file from my web server', s)

    # use urequest from https://github.com/pfalcon/pycopy-lib. else redirect not implemented error , at least on nginx/OMV5

    import urequests
    response = urequests.get(s) # response is object
    """
    requests status code:  200
    request reason:  b'OK'
    """

    print('requests status code: ', response.status_code)
    print('request reason: ', response.reason)

    if response.status_code != 200:
        print('request get FAILED, sleeping for 1 hour')
        sleeptime_msec = 1*60*60*1000  # one hour
        deepsleep(sleeptime_msec)

    #print(response.text) # actual content of http request if text, json
    #parsed = response.json())  # dictionary

    buf = response.content # response in bytes
    print('request content: ', type(buf), len(buf)) #content  <class 'bytes'> 48000

    response.close()

    size = len(buf) # 800 * 480 // 8

    # buf is bytes, and framebuff needs bytearray , otherwize TypeError: object with buffer protocol required
    # not enough ram to have both
    # workaround: save buf as temp file, delete bytes buf to reclaim memory
    # create bytearray and read temp file one by one to avoid creating another big buffer

    print('create temp.pbm file with buf bytes content')
    with open('temp.pbm', 'wb') as fp:
        fp.write(buf)

    # reclaim buf bytes memory
    gc.collect()
    free = gc.mem_free(); alloc = gc.mem_alloc()
    print("mem free %d, alloc %d, sum %d, percent free %0.2f"  %(free, alloc, free+alloc, free/(free+alloc)))
    del buf
    gc.collect()
    free = gc.mem_free(); alloc = gc.mem_alloc()
    print("mem free %d, alloc %d, sum %d, percent free %0.2f"  %(free, alloc, free+alloc, free/(free+alloc)))

    buf = bytearray(size) # elements are of class int
    print('bytearray allocated. ie an object with a buffer protocol ', len(buf), type(buf))

    print('read temp.pbm file')
    with open('temp.pbm', 'rb') as fp:
        for i in range(size):
            x = fp.read(1)
            x = int.from_bytes(x, 'little')
            buf[i] = x

    # buf need to be bytearray, not bytes. TypeError: object with buffer protocol required
    fb = framebuf.FrameBuffer(buf, 800, 640, framebuf.MONO_HLSB)
    print('framebuffer created', type(fb)) # TypeError: object of type 'FrameBuffer' has no len()
    return(fb, buf)


############################################################
#  boot
############################################################

import os
import sys
from esp import flash_size
from esp32 import raw_temperature
import ntptime

from machine import Pin, SPI, freq
from machine import deepsleep, idle, RTC, reset_cause, DEEPSLEEP_RESET, DEEPSLEEP

from utime import sleep_ms, sleep, sleep_us
from micropython import mem_info, const, stack_use


"""
Pins 1 and 3 are REPL UART TX and RX respectively
Pins 6, 7, 8, 11, 16, and 17 are used for connecting the embedded flash, and are not recommended for other uses
Pins 34-39 are input only, and also do not have internal pull-up resistors
The pull value of some pins can be set to Pin.PULL_HOLD to reduce power consumption during deepsleep.

"""

print(os.uname(), '\n')

print ("implementation: ",sys.implementation)  # no ()
print ("platform: ", sys.platform)
print ("version: ",sys.version)
print ("sys.path: ", sys.path) # list
print ("modules imported: ", sys.modules) # dict

print('cpu frequency: %d Mhz' %(freq()/1000000))
print('flash size in Mbytes: ', flash_size()/(1024.0*1024.0))
print ('ESP32 internal temp %d' %(int(raw_temperature()-32)*5.0/9.0))

#esp.osdebug(None)
#to display flash size
#import port_diag

import uos
# do not include for 512k port, no file system
# free file system
i= uos.statvfs('/')
fs = i[1]*i[2]/(1024.0*1024.0)
free= i[0]*i[4]/(1024.0*1024.0)
per = (float(free)/float(fs))
print('file system size %0.1f, free %0.1f, free in percent %0.1f' %(fs, free, per))

#uos.dupterm(None, 1) # disable REPL on UART(0)

def start_repl():
    # need to import once webrepl_setup from a usb/ttl connection to set password
    # creates webrepl_cfg.py (not visible in uPyCraft, visible w: os.listdir()
    # cannot just browse to IP, need client http://micropython.org/webrepl/
    import webrepl 
    print('import webrepl_setup once to set password')
    print('start webrepl: use http://micropython.org/webrepl/ to access or use local webrepl.html')
    print('ws://192.168.1.5:8266/')
    webrepl.start()


def wifi_connect(ssid,psk):
    import network
    from time import sleep_ms
    i=0
    ok = True
    sta_if = network.WLAN(network.STA_IF)
    
    sta_if.active(True)
    print('set static IP')
    sta_if.ifconfig(('192.168.1.5', '255.255.255.0','192.168.1.1', '8.8.8.8'))
    sta_if.connect(ssid, psk)

    while not sta_if.isconnected():
        sleep_ms(300)
        i = i + 1
        if i >=10:
            ok=False
            break
         
    if ok == True: 
        sleep_ms(10)  
        print('\n\nconnected. network config:', sta_if.ifconfig())
        print ('status: ', sta_if.status())
        print('ssid: ', ssid)
        return (sta_if)
    else:
        print('cannot connect to %s' %(ssid))
        return(None)
  # return None or sta_id 


"""
credential for wifi stored in mynet.py

net = [
['ssid1', 'pass1'] , \
['ssid2', 'pass2'] , \
['ssd3', 'pass3'], \
['ssid4', 'pass4'] \
]
"""

########################################################
# update epaper with content. either pdf or all white
# buf already allocated and updated
# use modified library
########################################################
def refresh_epaper(buf):
    miso = Pin(12) # not used
    sck = Pin(13)
    mosi = Pin(14) # DIN
    cs = Pin(15)
    busy = Pin(25)
    dc = Pin(27)
    rst = Pin(26)

    s = ticks_ms()

    spi = SPI(2, baudrate=20000000, polarity=0, phase=0, sck=sck, miso=miso, mosi=mosi)
    print('SPI started')

    import epaper4in2_mod # modified W and H
    e = epaper4in2_mod.EPD(spi, cs, dc, rst, busy)

    e.init()
    print('epaper initialized, display frame')

    e.display_frame(buf)

    print('displayed. put to sleep')
    e.sleep_75()

    print('epaper execution time (ms): ', ticks_ms()-s)


###############################################
# start wifi
# set local time with ntp
###############################################

import mynet
print(mynet.net)

wifi_ok = False
for i in range(len(mynet.net)): # try all networks
    print("\ntrying to connect to wifi %s ...\n" %(mynet.net[i][0]))
    wifi = wifi_connect(mynet.net[i][0], mynet.net[i][1])

    if wifi != None:
        print('\n************** wifi connected **************\n')
        wifi_ok = True
        break

if wifi_ok == False:
    print('could not connect to any wifi')
    sleeptime_msec = 24*60*60*1000  # one day
    print('deep sleep hr', sleeptime_msec/(3600*1000))
    led.off()
    deepsleep(sleeptime_msec)

else: # wifi OK
# set local time from ntp server. not used yet. but for a future version maybe
    try: # protect from timeout in ntp
        print('local time before ntp: ', localtime())
        print('set time with ntp')
        ntptime.settime()
        print('UTC time after ntp: ', localtime())
    except Exception as e:  
        print('exception in ntp ', str(e))

"""
    # micropython does not handle local time
    localtime(mktime(localtime() + 1 * 3600))
    print('local time: ', localtime())
"""

########################################################
# memory analysis
########################################################

# ESP32 4MB, heap is 111168 bytes. note: stack is fixed 15360 / 1024 = 15Kio
gc.collect()
free = gc.mem_free(); alloc = gc.mem_alloc()
print("\nmem free %d, alloc %d, sum %d, percent free %0.2f"  %(free, alloc, free+alloc, free/(free+alloc)))

# garbage collection can be executed manually, if alloc fails, or if 25% of currently free heap becomes occupied
#gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())

print("stack used: ", stack_use())
print("mem info (1 for memory map): ", mem_info()) 

################################################################
# every so often, based on RTC memory, fill screen with white, than go to sleep for a while
################################################################

if avoid_ghost:
    print('write entiere screen with white to avoid ghosts')
    buf = bytearray(800 * 480 // 8)
    fb = framebuf.FrameBuffer(buf, 800, 480, framebuf.MONO_HLSB)
    white = 1
    # frame buffer is all white
    fb.fill(white)
    refresh_epaper(buf)

    sleeptime_msec = 10*60*1000  # 10 mn
    print('deep sleep after un-gosthing the screen', sleeptime_msec/(3600*1000))
    deepsleep(sleeptime_msec)

##############################################
# build framebuffer with pbm content
##############################################

# if running big.py on windows, the pbm file is already in ESP32 flash memory (synched with vscode and pymaker)
#(fb,buf) = frame_local() 

# get pbm file from raspberry PI web server
(fb,buf) = frame_remote() 


print('toggle led to signal epaper refresh')
for i in range(5):
    led.on()
    sleep_ms(200) # blynk led to signal we are about to refresh
    led.off()
    sleep_ms(200) # 
led.off()

refresh_epaper(buf)

for i in range(5):
    led.on()
    sleep_ms(200) # blynk led to signal refresh done
    led.off()
    sleep_ms(200) 
led.off()

sleeptime_msec = 24*60*60*1000  # one day
print('deep sleep hr', sleeptime_msec/(3600*1000))
print ('script execution time(ms): ', ticks_ms()-start_time)
deepsleep(sleeptime_msec)

print('boot ends')

"""
41 sec execution, 31 sec in epaper
"""


"""
https://docs.micropython.org/en/latest/reference/constrained.html

The information that is printed is implementation dependent, 
but currently includes the amount of stack and heap used. 
In verbose mode (1) it prints out the entire heap indicating 
which blocks are used and which are free.  . free block

Each letter represents a single block of memory, a block being 16 bytes. 
So each line of the heap dump represents 0x400 bytes or 1KiB of RAM.

00000: h=hhhhBM.LDSShDhB=.B=Bhh=SB=h====h===hh==h======================
00400: ================================================================

03800: ...........h========h============...............................
(22 lines all free)
09400: ....

15 + 22 lines + 4x16 bytes.  37x1024 + 64 = 37952 . GC: total: 37952, used: 8000, free: 29952

stack: 2128 out of 8192
"""
