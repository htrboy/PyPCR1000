# Copyright (C) 2004 by James C. Ahlstrom.
# This free software is licensed for use under the GNU General Public
# License (GPL), see http://www.opensource.org.
# Note that there is NO WARRANTY AT ALL.	USE AT YOUR OWN RISK!!

'''
Change all Print() statements to logging.level (debug, info)

Change Serialport calls to latest pyserial

Not 100% sure what LOGGER was - Look at logic around all 'if LOGGER.state'

Fixed Serial port settings - radio was not getting set to 38400 - this fixed
several issues:  Bandscope works, signal meter works

Added MouseWheel Tuning 
'''

# Edited 5-7-2023 1700

import sys, tkinter
from tkinter.scrolledtext import ScrolledText
from tkinter import ttk
import tkinter.messagebox
import tkinter.colorchooser
import time, _thread, math, os, traceback, string, pickle
from types import *
from serial import Serial
from serial.tools import list_ports
from serial.tools.list_ports import comports
import configparser
import os #troubleshooting
from PIL import Image
import codecs
import logging
import csv

DEBUGGING = 1       # Write debug messages - changing to 'logging' module
LOGGER = None   # This has a write(text) method for logging messages
IniFile = {}	# A dictionary to store state in an INI file

config = configparser.ConfigParser()

# set logging format and level
# TODO: change to log-to-file
logging.basicConfig(format='%(asctime)s,%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
    datefmt='%Y-%m-%d:%H:%M:%S',
    level=logging.INFO) #levels: INFO, WARNING, CRITICAL

SerialPollMillisecs = 10	# Time to poll serial port
ScanMillisecs = 100         # Time to pause at each frequency when scanning the band
bpady = 1		            # Standard padding for equal-height buttons

# Define fonts used by all widgets
bfont = 'helvetica 10'	    # button font
lfont = 'helvetica 10'	    # label font
vfont = 'helvetica 10'	    # font for volume control
mfont = 'helvetica 8'       # S-Meter font

# Define colors used by all widgets
Red	    = '#FF3300'
Black	= '#000000'
White	= '#FFFFFF'
Green	= '#66FF33'
Gray	= '#999999'
Blue	= '#3333FF'
Yellow	= '#FFFF33'
acolor	= '#FFFF33' # active color for text items
scolor	= '#CCCC33' # selected check and radio buttons
ccolor	= '#FFFF33' # active color for right-click buttons
fcolor	= '#FFFFCC' # background for freq display and call
mcolort = '#FFFFFF' # S-Meter text color
mcolorf = '#6633FF' # S-Meter foreground color
mcolorb = '#66CCFF' # S-Meter background color
bcolorb = '#66CC99' # Bandscope background
bcolort = '#000000' # Bandscope text color
bcolorc = '#000000' #'#FFFF00'	# Bandscope center line
bcolorl = '#993300' # Bandscope signal level color
ncolor	= '#FF3300' # Active scanner button color

'''
Interface definition:
app.dispFreq.Set(new_freq)
app.radio.RadioSetBandScope(turn_on)
app.dispMode.Set(new_mode)
app.dispFilter.Set(new_filter)
app.StepBandChange(new_step)

'''

StatusBar = None

def Help(widget, text):
    #logging.debug("def Help")
    """Create help text for widget"""
    widget.help = text
    widget.bind('<Enter>', Enter, add=1)
    widget.bind('<Leave>', Leave, add=1)

def Enter(event):
    if StatusBar.show_help:
        StatusBar.itemconfig(StatusBar.idText, text=event.widget.help)

def Leave(event):
    if StatusBar.show_help:
        StatusBar.itemconfig(StatusBar.idText, text='')

def MouseWheel(event):
    # Attempt to use mousewheel for tuning
    logging.debug("Mousewheel event: %s", event)
    #logging.debug("Mousewheel kw: %s", kw)
    
    #pass #print event

def FormatTb():
    logging.debug("def FormatTb")
    """Write text from a traceback"""
    # changed to if DEBUG
    #if LOGGER:
    if DEBUGGING:
        # logging.error(ty, value, tb = sys.exc_info())
        #tb = traceback.format_exception(ty, value, tb)
        logging.error(tb = sys.exc_info())
        tb = traceback.format_exception(tb)
        logging.debug(''.join(tb))

def GetTextExtent(window, text, font):
    id = window.create_text(0, 0, text=text, font=font, anchor='nw')
    bbox = window.bbox(id)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    window.delete(id)
    return w, h

def MakeFreq(text):
    """Return integer frequency for text."""
    text.strip()
    tail = text[-1] # text must be stripped: text.strip()
    if tail in "Kk":
        mult = 1000
        text = text[0:-1]
    elif tail in "Mm":
        mult = 1000000
        text = text[0:-1]
    else:
        mult = 1
    return int(float(text) * mult)

def ShowFreq(freq):
    """Return a string for frequency"""
    freq = int(freq)

    if freq % 1000 == 0:
        t = str(freq / 1000)
        add = 'k'
    elif abs(freq) > 1000 and freq % 100 == 0:
        t = str(freq / 100)
        add = '.%sk' % t[-1]
        t = t[0:-1]
    else:
        t = str(freq)
        add = ''

    l = len(t)

    if t[0] == '-':
        l = l - 1

    if l > 9:
        t = "%s,%s,%s,%s%s" % (t[0:-9], t[-9:-6], t[-6:-3], t[-3:], add)
    elif l > 6:
        t = "%s,%s,%s%s" % (t[0:-6], t[-6:-3], t[-3:], add)
    elif l > 3:
        t = "%s,%s%s" % (t[0:-3], t[-3:], add)
    else:
        t = t + add

    return t

def BandFileNames():
    """return a list of band file names"""
    l = []
    for name in os.listdir('.'):
        if name[-6:].lower() == '.bands':
            l.append(name)
    return l

def ReadBands(filename):
    """
    Read data in the Bands file
    Button text, Freq Start, Freq End, Freq Step, Mode, Filter, Description
    80m,	3.5M,	4.0m,	100,	LSB,	 2.8k, Ham 80 meters
    
    """
    b = []
    try:
        fp = open(filename, "r")
    except IOError:
        return b

    fp.readline()			# Throw away the header

    for text in fp.readlines():
        data = text.split(',')
        #data.strip(',')
        #data = map(string.strip, data)
        data[1] = MakeFreq(data[1])
        data[2] = MakeFreq(data[2])
        data[3] = MakeFreq(data[3])
        b.append(data)

    fp.close()
    return b

"""This application displays a radio control screen."""
class Application(tkinter.Tk):
    
    def __init__(self):
        tkinter.Tk.__init__(self)
        logging.debug("Started")
        # Read in persistent state from an INI file
        try:
            fp = open(r"PyPCR1000.ini", "r")
        except IOError:
            logging.error("IO Error: %s", IOError)
            #print(IOError)
            pass
        else:
            for line in fp.readlines():
                keyval = line.split('=')
                if len(keyval) == 2:
                    IniFile[keyval[0].strip()] = keyval[1].strip()
            fp.close()
            
        self.files_preserve = [LOGGER]

        self.band_step = 1000
        self.varCall = tkinter.StringVar()
        self.varStation = tkinter.StringVar()
        self.varMultBands = tkinter.IntVar()	# Select multiple bands?
        self.varShowHelp = tkinter.IntVar()		# Show help in status bar?
        self.varShowHelp.set(1)
        self.textDTMF = ''		# DTMF tones received
        self.ReadStations()
        self.win_title = "Python PCR1000"
        self.wm_title(self.win_title)
        self.wm_resizable(1, 1)
        self.screenheight = self.winfo_screenheight()
        self.screenwidth = self.winfo_screenwidth()
        self.one_mm = float(self.screenwidth) / self.winfo_screenmmwidth()
        self.logging = 0
        self.scanner = 0		# 1==scan up, -1==scan down
        self.memscanner = False
        #self.bind('<<HaveInput>>', self.HaveInput)
        self.sequence = 0
        self.radio = PCR1000(self)
        self.wm_protocol("WM_DELETE_WINDOW", self.WmDeleteWindow)
        self.wm_protocol("WM_SAVE_YOURSELF", self.WmDeleteWindow)

        frame = self.frame = tkinter.Frame(self)
        frame.pack(expand=1, fill='both')

        # Help status bar at bottom
        global StatusBar
        StatusBar = tkinter.Canvas(frame, bd=2, relief='groove')
        w, h = GetTextExtent(StatusBar, 'Status', font=bfont)
        StatusBar.statusHeight = h
        StatusBar.configure(height=h)
        StatusBar.idText = StatusBar.create_text(2, 2+h/2, text="", anchor='w', font=bfont)
        StatusBar.pack(side='bottom', anchor='s', fill='x')
        StatusBar.show_help = self.varShowHelp.get()

        # Measure some widget sizes
        Canvas = tkinter.Canvas(frame)
        w, h = GetTextExtent(Canvas, 'Volume', font=vfont)
        w = w * 12 / 10
        b = tkinter.Radiobutton(Canvas, text="USB", font=bfont, width=4, padx=0, pady=bpady, indicatoron=0)
        #b = ttk.Radiobutton(Canvas, text="USB", width=4, padx=0, pady=bpady, indicatoron=0)
        radioW = b.winfo_reqwidth()
        radioH = b.winfo_reqheight()
        b.destroy()
        Canvas.destroy()

        # Left vertical box for power and knobs
        Left = tkinter.Frame(frame, bd=5, relief='groove')
        Left.pack(side='left', anchor='w', fill='y')

        # Populate left box
        bg = Left.cget('background')

        self.power_button = PowerButton(Left, text='Power', font=vfont, width=w, bg=bg, bd=3, relief='raised', command=self.Power)
        self.power_button.SetColorNum(0)
        Help(self.power_button, 'Power button: press to turn radio on and off.')
        self.power_button.pack(side='top', anchor='n', expand=1)

        self.dispVolume = VolumeKnob(Left, text='Volume', font=vfont, highlightthickness=0, button=1, radio=self.radio, width=w, bg=bg, relief='flat')
        Help(self.dispVolume, 'Volume control: press knob and turn.')
        Help(self.dispVolume.iButton, 'Press to mute (set volume to zero), press again to restore.')
        self.dispVolume.pack(side='top', anchor='n', expand=1)

        self.dispSquelch = SquelchKnob(Left, text='Squelch', font=vfont, highlightthickness=0, radio=self.radio, width=w, bg=bg, relief='flat')
        Help(self.dispSquelch, 'Squelch control: press knob and turn.')
        self.dispSquelch.pack(side='top', anchor='n', expand=1)

        self.dispIfShift = IfShiftKnob(Left, text='IF Shift', font=vfont, highlightthickness=0, button=1, radio=self.radio, width=w, bg=bg, relief='flat')
        Help(self.dispIfShift, 'Intermediate frequency shift control: press knob and turn.')
        Help(self.dispIfShift.iButton, 'Press to set to 50% (no IF shift).')
        self.dispIfShift.pack(side='top', anchor='n', expand=1)

        # Top box for display, tuning, ...
        Top = tkinter.Frame(frame)
        Top.pack(side='top', anchor='n', fill='x')

        # TopLeft box for frequency display, signal meter, check buttons
        TopLeft = tkinter.Frame(Top, bd=5, relief='groove')
        TopLeft.pack(side='left', anchor='w')

        # TopRight box for tuning buttons, memory buttons, etc.
        TopRight = tkinter.Frame(Top, bd=5, relief='groove')
        TopRight.pack(side='right', anchor='e', expand=1, fill='x')
        #h = int(self.one_mm * 25.4 + 0.5)

        # frequency display, signal meter
        frm = tkinter.Frame(TopLeft)
        frm.pack(side='top', anchor='nw')

        self.dispFreq = FreqDisplay(frm, app=self, width=radioW * 6, bg=fcolor, radio=self.radio)
        self.dispFreq.pack(side='top', anchor='nw')
        self.dispFreq.Set(self.radio.frequency)
        Help(self.dispFreq, 'To tune, press top of digit to increase, bottom to decrease. The H and L show FM frequency high or low.')

        f = tkinter.Frame(frm)
        f.pack(side='top', anchor='nw', fill='x')

        self.varShift = tkinter.IntVar()
        self.shift_delta = 600000
        b = tkinter.Checkbutton(f, text="+600k", indicatoron=0, width=5, selectcolor=scolor, font=mfont, padx=0, pady=0, activebackground=ccolor, variable=self.varShift, command=self.ShiftButton)
        b.pack(side='right', anchor='ne')
        b.bind('<ButtonPress-3>', self.ShiftButtonMenu)
        Help(b, 'Press to shift frequency temporarily, press again to shift back. Configure with right click.')

        self.dispSignal = SignalMeter(f)
        Help(self.dispSignal, 'Signal strength meter.')
        self.dispSignal.pack(side='right', anchor='nw', expand=1, fill='both')

        # mode, filter and check buttons
        frm = tkinter.Frame(TopLeft)
        frm.pack(side='top', anchor='nw', fill='x')
        self.dispMode = ModeDisplay(frm, self.radio)
        #			height=radioH, relief='groove')
        #self.dispMode.pack_propagate(0)
        self.dispMode.pack(side='top', anchor='nw', fill='x')
        Help(self.dispMode, 'Radio reception mode: lower/upper sideband, AM, CW, narrow/wide FM')

        self.dispFilter = FilterDisplay(frm, self.radio)
        Help(self.dispFilter, 'Radio IF bandwidth')
        self.dispMode.dispFilter = self.dispFilter
        #			height=radioH, relief='groove')
        #self.dispFilter.pack_propagate(0)
        self.dispFilter.pack(side='top', anchor='nw', fill='x')
        self.dispCheckB = CheckButtons(frm, self.radio)
        #			height=radioH, relief='groove')
        #self.dispCheckB.pack_propagate(0)
        self.dispCheckB.pack(side='top', anchor='nw', fill='x')

        frm = tkinter.Frame(TopRight)
        frm.pack(side='top', anchor='n', fill='x')
        fru = tkinter.Frame(frm)
        fru.pack(side='top', anchor='nw', fill='x')
        frd = tkinter.Frame(frm)
        frd.pack(side='bottom', anchor='sw', fill='x')

        b = RepeaterButton(frd, text='<Sta', width=6, font=bfont, pady=bpady, padx=0, command=Shim(self.NextStation, 0))
        Help(b, 'Tune down to the next station in the selected bands. Hold to repeat. Stations are recorded in the file Stations.csv.')
        b.pack(side='left', anchor='w', expand=1, fill='x')

        b = RepeaterButton(frd, width=6, font=bfont, pady=bpady, padx=0, command=Shim(self.NextFrequency, 0), activebackground=ccolor)
        Help(b, 'Tune down by the indicated frequency step, but stay in the bands. Hold to repeat. Configure with right click.')
        b.pack(side='left', anchor='w', expand=1, fill='x')
        b.bind('<ButtonPress-3>', self.StepBandMenu)
        self.dispStepBandD = b

        b = tkinter.Button(frd, text='<Scn', width=6, font=bfont, pady=bpady, padx=0, command=self.ScanDownBand)
        Help(b, 'Start the scanner and scan down in the selected bands. Stop when the squelch opens.')
        b.pack(side='left', anchor='w', expand=1, fill='x')
        self.dispScanDown = b
        self.btnBcolor = b.cget('background') # Save color
        self.btnAcolor = b.cget('activebackground')

        # Memory buttons
        self.Memories = []
        for i in range(5, 10):
            b = tkinter.Button(frd, text="M%s" % i, width=3, pady=bpady, padx=0, font=bfont, activebackground=ccolor, command=Shim(self.MemoryButtonCmd, i), state='disabled')
            Help(b, 'Memory button: press to change to that frequency. Configure with right click.')
            b.pack(side='left', anchor='w')
            b.bind('<ButtonPress-3>', self.MemoryButtonMenu)
            b.index = i
            self.Memories.append(None)

        b = tkinter.Button(frd, text='Unused 2', font=bfont, pady=bpady, width=8, command=self.OnButtonUnused2)
        Help(b, 'Program this button yourself in Python!')
        b.pack(side='right', anchor='e')

        b = RepeaterButton(fru, text='Sta>', width=6, font=bfont, pady=bpady, padx=0, command=Shim(self.NextStation, 1))
        Help(b, 'Tune up to the next station in the selected bands. Hold to repeat. Stations are recorded in the file Stations.csv.')
        b.pack(side='left', anchor='w', expand=1, fill='x')

        b = RepeaterButton(fru, width=6, font=bfont, pady=bpady, padx=0, command=Shim(self.NextFrequency, 1), activebackground=ccolor)
        Help(b, 'Tune up by the indicated frequency step, but stay in the bands. Hold to repeat. Configure with right click.')
        b.pack(side='left', anchor='w', expand=1, fill='x')
        b.bind('<ButtonPress-3>', self.StepBandMenu)
        self.dispStepBandU = b

        b = tkinter.Button(fru, text='Scn>', width=6, font=bfont, pady=bpady, padx=0, command=self.ScanUpBand)
        Help(b, 'Start the scanner and scan up in the selected bands. Stop when the squelch opens.')
        b.pack(side='left', anchor='w', expand=1, fill='x')
        self.dispScanUp = b

        for i in range(0, 5):
            b = tkinter.Button(fru, text="M%s" % i, width=3, pady=bpady, padx=0, font=bfont, activebackground=ccolor, command=Shim(self.MemoryButtonCmd, i), state='disabled')
            Help(b, 'Memory button: press to change to that frequency. Configure with right click.')
            b.pack(side='left', anchor='w')
            b.bind('<ButtonPress-3>', self.MemoryButtonMenu)
            b.index = i
            self.Memories.append(None)

        b = tkinter.Button(fru, text='Memscan', font=bfont, pady=bpady, width=8, command=self.OnButtonMemscan)
        Help(b, 'Scan frequencies in Stations.csv. Resume when squelch re-closes.')
        b.pack(side='right', anchor='e')
        self.dispMemscan = b

        self.StepBandChange(self.band_step)

        # Band buttons: Room for three rows of seven columns
        self.bandRows = []
        for i in range(3):		# Create three rows
            frs = tkinter.Frame(TopRight)
            frs.pack(side='top', anchor='nw', fill='x')
            self.bandRows.append(frs)
        self.Bands = []

        # Call entries
        frm = tkinter.Frame(frame, bd=5, relief='groove')
        frm.pack(side='top', anchor='n', fill='x')

        b = tkinter.Label(frm, text="Call", font=lfont)
        b.pack(side='left', anchor='nw')

        b = tkinter.Entry(frm, bg=fcolor, width=12, textvariable=self.varCall)
        #b.bind('<MouseWheel>', MouseWheel)
        #print b.bind()
        Help(b, 'Enter the call sign of known stations, and hit "Enter". Stations are recorded in the file Stations.csv.')
        b.pack(side='left', anchor='nw')
        b.bind('<Key-Return>', self.SetStation)

        b = tkinter.Entry(frm, bg=fcolor, textvariable=self.varStation)
        Help(b, 'Enter a description of known stations, and hit "Enter". Stations are recorded in the file Stations.csv.')
        b.pack(side='left', anchor='nw', expand=1, fill='x')
        b.bind('<Key-Return>', self.SetStation)

        b = tkinter.Label(frm, font=lfont, text='Config', bd=1, relief='raised')
        Help(b, 'Right click to get a configuration menu.')
        b.pack(side='right', anchor='e')
        b.bind('<ButtonPress-3>', self.ConfigMenu)

        self.dispDTMF = tkinter.Label(frm, font=lfont, width=25, anchor='w', text="	 DTMF Tone:")
        self.dispDTMF.pack(side='right', anchor='ne')
        Help(self.dispDTMF, 'If a DTMF tone is received, it is displayed here.')
        for i in range(0, 2):
            self.SetDtmf("i % 10")

        # Band scope goes in right box bottom
        bscope = self.dispBandScope = BandScope(frame, self, width=1, height=1, bg=bcolorb)
        Help(bscope, 'Bandscope: Right click to configure.	To tune, click grid, or press "Tune" and drag mouse.')
        bscope.pack(side='top', anchor='n', expand=1, fill='both')

        # End of widget create and place



        try:
            self.MakeBands(IniFile['AppBandFileName'])
        except:
            logging.error("'MakeBands' from IniFile failed")
            pass

        #####################################
        ## should SetAll be called here ?? ##
        #####################################        
        logging.debug("APPLICATION: radio.SetAll()")
        self.radio.SetAll()

        self.logging = 1
        #print self.option_get()

    def ConfigMenu(self, event):
        menu = tkinter.Menu(self, tearoff=0)
        menu.add_checkbutton(label='Select multiple bands',	variable=self.varMultBands)
        menu.add_checkbutton(label='Show help at bottom', variable=self.varShowHelp, command=self.HelpCmd)
        menu.add_separator()

        bands = tkinter.Menu(menu, tearoff=0)
        for name in BandFileNames():
            bands.add_command(label=name, command=Shim(self.MakeBands, name))

        menu.add_cascade(label='Load band file', menu=bands)
        menu.add_separator()
        menu.add_command(label="Show serial port...", command=self.OnButtonSerial)
        menu.tk_popup(event.x_root, event.y_root)

    def HelpCmd(self):
        if self.varShowHelp.get():
            StatusBar.show_help = 1
            StatusBar.configure(bd=2, height=StatusBar.statusHeight)
        else:
            StatusBar.show_help = 0
            StatusBar.configure(bd=0, height=0)

    def ReadStations(self):
        #
        # rewrote this function to use csv.Sniffer and 
        # detect the header row of a csv file
        #
        d = {}
        with open(r'./Stations.csv', "r") as file:
            #has_header = csv.Sniffer().has_header(file.read(1024))
            #logging.info("header: %s", has_header)
            #file.seek(0) #rewind
            has_header = True # Sniffer not working - force it
            reader = csv.reader(file)
            if has_header:
                next(reader) #skip the header row
            for text in file.readlines():
                data = text.split(',')
                freq = MakeFreq(data[0].strip())
                d[freq] = data

        file.close()
            
        self.Stations = d
        self.ListStations = list(d.keys())
        self.ListStations.sort()
        self.changedStations = 0


        """
        Read data in Stations.csv
        Frequency,		 Call, Mode, Filter, Description
        146.030m,	 K3MXU,	 nFM,		 15k, Imaginary station
        """
        '''
        Rewriting function to handle header row in csv file
        
        d = {}
        #path ='Stations.csv'	
        #path = r'Stations.csv' 
        #assert os.path.isfile(path)
        fp = open(r"./Stations.csv", "r")
        # with open(path, 'r') as fp:
        #     pass
        #     self.stHeading = fp.readline()		 # Save the heading
    
        #     #print("Check file path")
        #     logging.info("Check file path")

        for text in fp.readlines():
            data = text.split(',')
            freq = MakeFreq(data[0].strip())
            d[freq] = data

        fp.close()

        self.Stations = d
        self.ListStations = list(d.keys())
        #self.ListStations.sort()
        self.changedStations = 0
        '''
    
    
    def WriteStations(self):
        """Write the changed Stations.csv"""
        dict = self.Stations
        text = self.stHeading

        for freq in self.ListStations:
            data = dict[freq]
            t = ','.join(data)
            text = text + t

        fp = open(r"./Stations.csv", "w")
        fp.write(text)
        fp.close()

    # Power off radio
    def WmDeleteWindow(self):
        self.radio.RadioPower(0)
        #if self.changedStations:
        #	 self.WriteStations()
        try:
            fp = open(r"./PyPCR1000.ini", "w")
        except IOError:
            pass
        else:
            for k, v in IniFile.items():
                fp.write("%s=%s\n" % (k, v))
            fp.close()
        self.destroy()

    def ClearBands(self):
        for data in self.Bands:
            data[0].configure(relief='raised')
            data[1] = 0

    def MakeBands(self, name):
        for data in self.Bands:
            data[0].pack_forget()
            data[0].destroy()

        del self.Bands[:]

        filedata = ReadBands(name)
        IniFile['AppBandFileName'] = name
        count = len(filedata)
        row = col = 0
        maxcol = (count + 2) // 3	# number of columns #integer division

        if maxcol < 2:
            maxcol = 2
        elif maxcol > 7:
            maxcol = 7

        for i in range(3 * maxcol): # There are always three rows
            if col == maxcol:
                row = row + 1
                col = 0

            if i < count:
                b = tkinter.Button(self.bandRows[row], text=filedata[i][0], font=bfont, pady=bpady,	state='normal', padx=0, width=5, command=Shim(self.SelectBand, i))
                # self.Bands is a list of [button, selected, filedata]
                self.Bands.append([b, 0, filedata[i]])
            else:
                b = tkinter.Button(self.bandRows[row], text='',	font=bfont, pady=bpady,	state='disabled', padx=0, width=5)
                self.Bands.append([b, 0, []])

            Help(b, 'Band buttons: press to select the band and tune to its start.')
            b.pack(side='left', anchor='nw', expand=1, fill='x')
            col = col + 1

        if count:
            self.SelectBand(0)

    def SelectBand(self, index):
        """
        self.Bands is a list of [button, selected, filedata]
        filedata is [Button text, Freq Start, Freq End, Freq Step, Mode, Filter, Description]
        """
        mult = self.varMultBands.get()

        if mult and self.Bands[index][1]: # Is the band selected?
            self.Bands[index][0].configure(relief='raised')
            self.Bands[index][1] = 0
        else:
            data = self.Bands[index][2]
            self.dispMode.Set(data[4])
            self.dispFilter.Set(data[5])
            self.dispFreq.Set(data[1])
            self.StepBandChange(data[3])

            if not mult:
                self.ClearBands()

            self.Bands[index][0].configure(relief='sunken')
            self.Bands[index][1] = 1

    def DisplayStation(self, freq):
        #if self.Stations.has_key(freq):
        if freq in self.Stations:
            data = self.Stations[freq]
            self.varCall.set(data[1].strip())
            self.varStation.set(data[4].strip())
        else:
            self.varCall.set('')
            self.varStation.set('')

    def NextStation(self, up):
        """ Tune to next station."""
        from bisect import bisect_left, bisect_right

        if not self.ListStations:
            return

        if up:
            i = bisect_right(self.ListStations, self.radio.frequency)
            if i == len(self.ListStations):		# we're at the right end, wrap around
                i = 0
            freq = self.ListStations[i]
        else:
            i = bisect_left(self.ListStations, self.radio.frequency)
            if i == 0:				# we're at the left end, wrap around
                i = len(self.ListStations)
            freq = self.ListStations[i-1]

        self.dispFreq.Set(freq)
        self.dispMode.Set(self.Stations[freq][2])
        self.dispFilter.Set(self.Stations[freq][3])

    def NextFrequency(self, up, wrap=0):
        bands = []
        for b, sel, data in self.Bands:
            if sel: # Band is selected
                if data[1] <= self.radio.frequency <= data[2]:	# We are in this band
                    step = self.band_step
                    if up:
                        freq = ((self.radio.frequency + step) / step) * step
                    else:
                        now = self.radio.frequency
                        freq = (now / step) * step
                        if freq == now:
                            freq = freq - step
                    if data[1] <= freq <= data[2]:	# New freq is still within the band
                        self.dispFreq.Set(freq)
                        return 1
                else:
                    bands.append(data)

        # We need to change bands
        freq = self.radio.frequency
        if up:
            for data in bands:
                if freq <= data[1]:
                    self.dispFreq.Set(data[1])
                    self.StepBandChange(data[3])
                    self.dispMode.Set(data[4])
                    self.dispFilter.Set(data[5])
                    return 1
        else:
            bands.reverse()
            for data in bands:
                if freq >= data[2]:
                    self.dispFreq.Set(data[2])
                    self.StepBandChange(data[3])
                    self.dispMode.Set(data[4])
                    self.dispFilter.Set(data[5])
                    return 1

        # We failed to change to a new frequency.	 If "wrap" then restart.
        if not wrap:
            return

        if up:
            for b, sel, data in self.Bands:
                if sel: # Band is selected
                    self.dispFreq.Set(data[1])
                    self.StepBandChange(data[3])
                    self.dispMode.Set(data[4])
                    self.dispFilter.Set(data[5])
                    return 1
        else:
            bands = []
            bands.extend(self.Bands)
            for b, sel, data in bands:
                if sel: # Band is selected
                    self.dispFreq.Set(data[2])
                    self.StepBandChange(data[3])
                    self.dispMode.Set(data[4])
                    self.dispFilter.Set(data[5])
                    return 1

    def ScanDownBand(self):
        if self.radio.power != 1:
            return
        if self.memscanner:
            self.StopMemscan()
        if self.scanner == 1:
            self.ScanUpBand() # Turn off previous scan
        if self.scanner:
            self.scanner = 0
            self.dispScanDown.config(background=self.btnBcolor, activebackground=self.btnAcolor, relief='raised')
        else:
            self.dispScanDown.config(background=ncolor, activebackground=ncolor, relief='sunken')
            self.scanner = -1
            if self.NextFrequency(0, 1):
                self.after(ScanMillisecs, self.RunScanner)

    def ScanUpBand(self):
        if self.radio.power != 1:
            return
        if self.memscanner:
            self.StopMemscan()
        if self.scanner == -1:
            self.ScanDownBand() # Turn off previous scan
        if self.scanner:
            self.scanner = 0
            self.dispScanUp.config(background=self.btnBcolor, activebackground=self.btnAcolor, relief='raised')
        else:
            self.dispScanUp.config(background=ncolor, activebackground=ncolor, relief='sunken')
            self.scanner = 1
            if self.NextFrequency(1, 1):
                self.after(ScanMillisecs, self.RunScanner)

    def StopScanner(self):
        if self.scanner > 0:
            self.ScanUpBand()
        elif self.scanner < 0:
            self.ScanDownBand()

    # SERIAL PORT
    def RunScanner(self):
        p = self.radio.serialport
        #if p.isOpen() and self.scanner:
        if p.is_open and self.scanner:
            self.after(ScanMillisecs, self.RunScanner)	# Reschedule
            if self.radio.squelch_open:
                self.StopScanner()
            elif self.scanner > 0:
                if not self.NextFrequency(1, 1):
                    self.StopScanner()
            elif self.scanner < 0:
                if not self.NextFrequency(0, 1):
                    self.StopScanner()
            else:
                self.StopScanner()

    def StepBandMenu(self, event):
        menu = tkinter.Menu(self, tearoff=0)

        for t in ('100', '1k', '2k', '2.5k', '5k', '10k', '15k', '20k', '50k', '100k'):
            menu.add_command(label=t, command=Shim(self.StepBandChange, MakeFreq(t)))

        menu.tk_popup(event.x_root, event.y_root)

    def StepBandChange(self, freq):
        text = ShowFreq(freq)
        self.dispStepBandU.config(text=text+'>')
        self.dispStepBandD.config(text='<'+text)
        self.band_step = freq

    def MemoryButtonCmd(self, index):
        tup = self.Memories[index]
        # tup is freq, mode, filter
        if tup:
            self.dispMode.Set(tup[1])
            self.dispFilter.Set(tup[2])
            self.dispFreq.Set(tup[0])

    def MemoryButtonMenu(self, event):
        widget = event.widget
        index = widget.index
        tup = self.Memories[index]	# tup is freq, mode, filter
        menu = tkinter.Menu(self, tearoff=0)
        t = 'Set memory button'
        menu.add_command(label=t, command=Shim(self.MemoryButtonSet, event))

        if tup:
            t = 'Erase %s %s %s' % (ShowFreq(tup[0]), tup[1], tup[2])
        else:
            t = 'Erase'

        menu.add_command(label=t, command=Shim(self.MemoryButtonErase, event))
        menu.tk_popup(event.x_root, event.y_root)

    def MemoryButtonSet(self, event):
        widget = event.widget
        index = widget.index
        self.Memories[index] = (self.radio.frequency, self.radio.mode, self.radio.filter)
        widget.configure(state='normal')

    def MemoryButtonErase(self, event):
        widget = event.widget
        index = widget.index
        self.Memories[index] = None
        widget.configure(state='disabled')

    def ShiftButton(self):
        if self.varShift.get():
            self.shift_back = self.radio.frequency
            self.dispFreq.Set(self.shift_back + self.shift_delta)
        else:
            self.dispFreq.Set(self.shift_back)

    def ShiftButtonMenu(self, event):
        menu = tkinter.Menu(self, tearoff=0)
        lst = ('100k', '600k', '1.2m')
        for t in lst:
            t = '+' + t
            menu.add_command(label=t, command=Shim(self.ShiftButtonChange, event.widget, t))
        for t in lst:
            t = '-' + t
            menu.add_command(label=t, command=Shim(self.ShiftButtonChange, event.widget, t))

        menu.tk_popup(event.x_root, event.y_root)

    def ShiftButtonChange(self, widget, text):
        self.varShift.set(0)
        widget.config(text=text)
        self.shift_delta = MakeFreq(text)

    # The power button was pressed
    def Power(self):			
        logging.debug("APPLICATION: Power = %i", self.radio.power)

        if bool(self.radio.power == 1):				# if Radio is on
            self.radio.RadioPower(0)                # turn it off
            self.power_button.SetColorNum(0) #added
        else:
            self.radio.RadioPower(1)                # Otherwise turn it on
            self.power_button.SetColorNum(1) #added
        if self.radio.power == 1:				    
            self.power_button.SetColorNum(1)
        else:
            self.power_button.SetColorNum(0)

    def SetStation(self, event):
        freq = self.radio.frequency
        call = self.varCall.get().strip()
        call = string.replace(call, ',', ' ') # Remove commas
        desc = self.varStation.get().strip()
        desc = string.replace(desc, ',', ' ')
        #Frequency, Call, Mode, Filter, Description
        self.changedStations = 1
        if not call and not desc:		# delete station
            if freq in self.ListStations:
                self.ListStations.remove(freq)
                del self.Stations[freq]
        elif freq in self.ListStations:
            self.Stations[freq] = [self.Stations[freq][0], call, self.radio.mode, self.radio.filter, desc + '\n']
        else:
            self.ListStations.append(freq)
            self.ListStations.sort()
            self.Stations[freq] = [str(freq), call, self.radio.mode, self.radio.filter, desc + '\n']
        self.WriteStations()

    def OnButtonSerial(self):
        global LOGGER		
        if isinstance(LOGGER, DialogSerial):
            LOGGER.focus_set()	# Do not create two serial dialog boxes
        elif self.radio.serialport:
            LOGGER = DialogSerial(self.radio.serialport, None)
            LOGGER.wm_transient(self)

    # SERIAL PORT
    def ReadSerial(self):
        p = self.radio.serialport
        #if p.isOpen():
        if p.is_open:
            try:
                text = p.read()		# this will time out				
            except:
                FormatTb()
                p.close()
                return
            if text:
                if LOGGER:
                    #LOGGER.write(text)
                    logging.debug(text)                
                self.radio.RadioParseInput(text)

    def OnButtonMemscan(self):
        if self.radio.power != 1:
            return
        if self.scanner:		# band scanning currently in progress, stop
            self.StopScanner()

        if self.memscanner:
            self.StopMemscan()
        else:
            self.StartMemscan()

    # SERIAL PORT
    def RunMemscan(self):
        p = self.radio.serialport
        #if p.isOpen() and self.memscanner:
        if (p.is_open and self.memscanner):
            if self.radio.squelch_open:
                self.after(ScanMillisecs, self.PauseMemscan)
            else:
                self.NextStation(1)						# tune to the next channel
                self.after(ScanMillisecs, self.RunMemscan)	# Reschedule ourself

    def PauseMemscan(self):
        if self.radio.squelch_open:
            self.after(ScanMillisecs, self.PauseMemscan)				# wait for squelch to close
        else:
            self.after(3000, self.HoldForFollowupMemscan)	# delay in case it comes back right away

    def HoldForFollowupMemscan(self):
        if self.radio.squelch_open:
            self.after(ScanMillisecs, self.PauseMemscan)
        else:
            self.after(ScanMillisecs, self.RunMemscan)

    def StopMemscan(self):
        self.memscanner = False
        self.dispMemscan.config(background=self.btnBcolor, activebackground=self.btnAcolor, relief='raised')

    def StartMemscan(self):
        self.memscanner = True
        self.dispMemscan.config(background=ncolor, activebackground=ncolor, relief='sunken')
        self.after(ScanMillisecs, self.RunMemscan)

    def OnButtonUnused2(self):
        pass

    def SetDtmf(self, ch):
        t = self.textDTMF + ch
        t = t[-12:]
        self.textDTMF = t
        self.dispDTMF.config(text='	 DTMF Tone: ' + t)


"""This class implements the interface to an Icom PCR1000 radio."""
class PCR1000:   

    modes = ('LSB', 'CW', 'USB', 'AM', 'nFM', 'wFM')
    dictMode = {'LSB':0, 'CW':3, 'USB':1, 'AM':2, 'nFM':5, 'wFM':6}
    filters = ('2.8k', '6k', '15k', '50k', '230k')
    dictFilter = {'2.8k':0, '6k':1, '15k':2, '50k':3, '230k':4}
    mode2filter = {'LSB':'2.8k', 'CW':'2.8k', 'USB':'2.8k', 'AM':'6k', 'nFM':'15k', 'wFM':'230k'}
    hexDigits = '0123456789aAbBcCdDeEfF'

    # SERIAL PORT
    def __init__(self, app):
        self.app = app
        p = IniFile.get('AppSerialPortName', '0')
        logging.debug("port: %s ", p)
        #self.serialport = Serial(port = "/dev/ttyUSB0", baudrate = 9600, timeout=0.1)
        #self.serialport = Serial(port = "COM1", baudrate = 9600, timeout=0.1)
        self.serialport = Serial(port = p, baudrate = 9600, timeout=0.1)

        if len(p) == 1 and p in '0123456789':
            p = int(p)

        self.power = -1				# radio power status is unknown:-1, off:0, on:1
        self.parse_n = 0			# Number of characters from serial port parsed.
        self.parse_bs = [0] * 17	# data for band scope
        self.bandscope = 1			# band scope: 0==off, 1==on, -1==unavailable
        self.bad_cmd = 0			# count of bad commands
        self.squelch_open = 0
        
        

        # Set initial frequency, filter, etc.
        self.frequency = 1234567890
        self.mode = 'USB'
        self.intmode = self.dictMode[self.mode]
        self.filter = '2.8k'
        self.intfilter = self.dictFilter[self.filter]
        self.AGC = 0
        self.AFC = 0
        self.ATT = 0
        self.NB	 = 0
        self.squelch = float(IniFile.get('Squelch','0.0'))
        self.volume = float(IniFile.get('Volume','0.25'))
        self.ifshift = 0.5

        # Start polling the serial port even though it is not open
        self.PollSerial()

    def PollSerial(self):        
        """Poll the serial port"""
        self.app.after(SerialPollMillisecs, self.PollSerial) # Reschedule the poll
        p = self.serialport

        #if p.isOpen():
        if p.is_open:
            #n = p.inWaiting()
            n = p.in_waiting
            while n:
                try:
                    #text = str(p.read(size=n))
                    text = p.read(size=n)
                except:
                    FormatTb()
                    p.close()
                    break
                else:
                    if LOGGER:
                        LOGGER.write(text)

                    #logging.debug('Pollserial text: %s', text)  

                    self.RadioParseInput(text)

                n = p.inWaiting()

    
    def SerialWrite(self, s):
        logging.debug("RADIO: def SerialWrite")
        p = self.serialport
        
        #p.RTS(True) #new
        
        #if p.isOpen():
        if p.is_open:
            #logging.debug("waiting for CTS high...") #new
            #while not p.getCTS(): #new                
                #pass
            p.write(s.encode())
            logging.debug("wrote %s", s)
            #time.sleep(0.25) #new
            #p.setRTS(False)  #new

    def RadioParseInput(self, text):
        #logging.debug("RADIO: def RadioParseInput")		
        for ch in str(text):
            
            if not self.parse_n:
                if ch in 'GHIN':	# Start of command
                    self.parse_ch0 = ch
                    self.parse_n = 1
                continue
            ch0 = self.parse_ch0
            
            length = self.parse_n
            if ch0 == 'I':
                if length == 1:
                    if ch in '0123':
                        self.parse_ch1 = ch
                        self.parse_n = 2
                    else:
                        self.parse_n = 0
                elif length == 2:
                    if ch in self.hexDigits:
                        self.parse_hex = int(ch, 16)
                        self.parse_n = 3
                    else:
                        self.parse_n = 0
                elif length == 3:
                    if ch in self.hexDigits:
                        ch1 = self.parse_ch1
                        if ch1 == '0':		# I0xx: squelch 04=closed, 07=open
                            data = self.parse_hex * 16 + int(ch, 16)
                            self.squelch_open = data - 4
                            self.app.dispSquelch.Active(data - 4)
                        elif ch1 == '1':	# I1xx: signal strength 00 to FF
                            data = self.parse_hex * 16 + int(ch, 16)
                            self.app.dispSignal.Set(data / 256.0)
                        elif ch1 == '2':	# I2xx: signal centering 00=low, 80=centered, FF=high
                            data = self.parse_hex * 16 + int(ch, 16)
                            self.app.dispFreq.Center(data - 0x80)
                        elif ch1 == '3':	# I31x/I300 :	 DTMF tone present/absent
                            if self.parse_hex == 1:
                                if ch == 'E':
                                    ch = '*'
                                elif ch == 'F':
                                    ch = '#'
                                self.app.SetDtmf(ch)
                    self.parse_n = 0
            elif ch0 == 'N':
                if length == 1:
                    if ch in 'E':
                        self.parse_ch1 = ch
                        self.parse_n = 2
                    else:
                        self.parse_n = 0
                elif length == 2:
                    if ch in '1':
                        self.parse_ch2 = ch
                        self.parse_n = 3
                    else:
                        self.parse_n = 0
                elif ch in self.hexDigits:
                    self.parse_n = self.parse_n + 1
                    if length % 2 == 1:
                        self.parse_hex = int(ch, 16)
                    else:
                        #
                        # The data are 17 2-byte hex digits.	The first is the sample
                        # start index 00 thru F0 and 80 is the center.	The rest are the
                        # 16 samples (signal strength).
                        #
                        data = self.parse_hex * 16 + int(ch, 16)
                        index = (length - 4) / 2  # Python 3 returns FLOAT not INT for division
                        self.parse_bs[int(index)] = data # cast index to INT
                        if length >= 36:			# Band scope packet is complete
                            self.parse_n = 0
                            for i in range(1, 17):	# convert to 0.0 to 1.0
                                self.parse_bs[i] = self.parse_bs[i] / 255.0
                            self.app.dispBandScope.Set(self.parse_bs[0] - 0x80, self.parse_bs[1:])
                else:
                    self.parse_n = 0
            elif ch0 == 'H':						# radio is H100=off, H101=on
                if length == 1:
                    if ch in '1':
                        self.parse_ch1 = ch
                        self.parse_n = 2
                    else:
                        self.parse_n = 0
                elif length == 2:
                    if ch in self.hexDigits:
                        self.parse_hex = int(ch, 16)
                        self.parse_n = 3
                    else:
                        self.parse_n = 0
                elif length == 3:
                    if ch in self.hexDigits:
                        data = self.parse_hex * 16 + int(ch, 16)
                        if data == 1:
                            self.power = 1
                        elif data == 0:
                            self.power = 0
                        else:
                            self.power = -1
                    self.parse_n = 0
            elif ch0 == 'G':	# command status G000=good, G001=bad
                if length == 1:
                    if ch in '0':
                        self.parse_ch1 = ch
                        self.parse_n = 2
                    else:
                        self.parse_n = 0
                elif length == 2:
                    if ch in self.hexDigits:
                        self.parse_hex = int(ch, 16)
                        self.parse_n = 3
                    else:
                        self.parse_n = 0
                elif length == 3:
                    if ch in self.hexDigits:
                        data = self.parse_hex * 16 + int(ch, 16)
                        if data != 0:
                            self.bad_cmd = self.bad_cmd + 1
                    self.parse_n = 0
            else:
                self.parse_n = 0



    '''
    RadioPower LOGIC FLOW NEEDS CLEANUP!!
    PYSERIAL HAS CHANGED - NO NEED FOR RTS/CTS CHECKS??

    '''
    def RadioPower(self, turn_on):        
        logging.debug("RADIO: def RadioPower")
        logging.debug("RadioPower called with %s ", turn_on)
        logging.debug("Serial port status: %s", self.serialport.is_open)
        tries = 2
        if turn_on:                                                                     
            logging.debug("turning on...")
            
            #if not self.serialport.isOpen():
            if not self.serialport.is_open:
                if isinstance(LOGGER, DialogSerial):
                    LOGGER.SetPort()
                    logging.debug("opening serial port...")
                    
                self.serialport.open()
                #if not self.serialport.isOpen():
                if not self.serialport.is_open:
                    #t = "Serial port %s could not be opened.\n" % self.serialport.getPort()
                    logging.debug("Serial port %s could not be opened.\n" % self.serialport.port)
                        
                    #LOGGER.write(t)
                    return
                self.parse_n = 0

            logging.debug("checking LOGGER instance...")
            
            if isinstance(LOGGER, DialogSerial):
                logging.debug("LOGGER State: %s ",(LOGGER.State))
                LOGGER.State()
            
            logging.debug("checking CTS...")
            self.serialport.setRTS(True)
            logging.debug("RTS was set High...") #assert ready to send
            logging.debug("CTS Status: %s", self.serialport.getCTS())

            if not self.serialport.getCTS():
                logging.debug("CTS: " + str(self.serialport.getCTS()))								
                # PCR1000 returns CTS status for power switch on/off
                #t = "Serial port %s shows CTS off.\n" % self.serialport.getPort()
                logging.debug("Serial port %s shows CTS off.\n" % self.serialport.port)
                #LOGGER.write(t)

                logging.debug("returning from check CTS...")                   
                
                
                logging.debug("unknown state #1")

                #self.power = -1 # unknown power status
                

                logging.debug("power status: %s", self.power)
                #return
            
            logging.debug("setting baudrate...")
            #set serial port baudrate			
            #self.serialport.setBaudrate(9600)
            self.power = 1
            self.serialport.baudrate = 9600
            logging.debug("Baudrate set to %i", self.serialport.baudrate)
            
            
            
            #set radio baudrate
            for i in range(0, tries):
                self.SerialWrite("H101\r\n")
                logging.debug("writing H101 for 9600")
                self.app.ReadSerial()

                self.SerialWrite("H1?\r\n")
                logging.debug("Asking radio for baud rate")
                self.app.ReadSerial()
                if self.power == 1:
                    break
            else:
                self.serialport.baudrate = 38400
                for i in range(0, tries):
                    self.SerialWrite("H101\r\n")
                    logging.debug("writing H101 for 38400")

                    self.app.ReadSerial()
                    self.SerialWrite("H1?\r\n")
                    logging.debug("Asking radio for baudrate")

                    self.app.ReadSerial()
                    if self.power == 1:
                        break

            if self.power == 1:
                if self.serialport.baudrate != 38400:
                    self.SerialWrite("G105\r\n")
                    time.sleep(0.1)
                    self.SerialWrite("G105\r\n")
                    time.sleep(0.1)
                    logging.debug("setting baudrate to 38400")
                    self.serialport.baudrate = 38400

                self.SetAll()		# Initialize the radio
                logging.debug("SetAll()...")
                self.SerialWrite("G301\r\n")                

                if isinstance(LOGGER, DialogSerial):
                    LOGGER.State()
                return 1

            else:
                #t = "No response from serial port %s.\n" % self.serialport.getPort()
                logging.debug("No response from serial port %s.\n", self.serialport.port)
                #LOGGER.write(t)
        else:
            #if self.serialport.isOpen():
            if self.serialport.is_open:
                for i in range(0, tries):
                    logging.debug("writing H100\r\n")
                    self.SerialWrite("H100\r\n") #turn radio off

                    self.app.ReadSerial()
                    logging.debug("writing H1?")
                    self.SerialWrite("H1?\r\n")

                    self.app.ReadSerial()
                    if self.power == 0:
                        break
                else:
                    #t = "No Response from serial port %s.\n" % self.serialport.getPort()
                    logging.debug("No Response from serial port %s.\n", self.serialport.port)
                    #LOGGER.write(t)

                self.serialport.close()

            logging.debug("unknown state #2")
            self.power = -1 # unknown power status

            if isinstance(LOGGER, DialogSerial):
                logging.debug("LOGGER STATE: %s", LOGGER.State)
                LOGGER.State()

    def SetAll(self):
        logging.debug("RADIO: def SetAll")
        self.RadioSetAGC(self.AGC)
        self.RadioSetAFC(self.AFC)
        self.RadioSetATT(self.ATT)
        self.RadioSetNB(self.NB)
        self.RadioSetIFshift(self.ifshift)
        self.RadioSetVolume(self.volume)
        self.RadioSetSquelch(self.squelch)
        self.SetFreqModeFilter()
        self.RadioSetBandScope()
        self.app.dispFreq.EnableCenter(self.mode in ('nFM', 'wFM'))

    def SetFreqModeFilter(self):	# Internal function
        logging.debug("RADIO: def SetFreqModeFilter")
        # Ask for squelch update for scanner
        self.SerialWrite("K0%010d%02d%02d00\r\nI0?\r\n" % (self.frequency, self.intmode, self.intfilter))

    def RadioSetAGC(self, i):
        logging.debug("RADIO: def RadioSetAGC")
        self.AGC = i
        self.SerialWrite("J45%02d\r\n" % i)

    def RadioSetAFC(self, i):
        logging.debug("RADIO: def RadioSetAFC")
        self.AFC = i
        self.SerialWrite("J50%02d\r\n" % i)

    def RadioSetATT(self, i):
        logging.debug("RADIO: def RadioSetATT")
        self.ATT = i
        self.SerialWrite("J47%02d\r\n" % i)

    def RadioSetBandScope(self, turn_on=None):
        logging.debug("RADIO: def RadioSetBandScope")
        if turn_on is None:
            turn_on = self.bandscope

        if turn_on:
            if self.mode in ('AM', 'nFM', 'wFM'):
                self.bandscope = 1
                bs = self.app.dispBandScope
                bs.Enable(1)
                if bs.number > 0x10:
                    rate = 0x05
                else:
                    rate = 0x28
                rate = 0x05
                t = "ME00001%02X%02X0100%06d\r\n" % (bs.number, rate, bs.stepsize)
                self.SerialWrite(t)
                return 1
            else:
                self.bandscope = -1
        else:
            self.bandscope = 0
            self.SerialWrite("ME0000120280000001000\r\n")
        self.app.dispBandScope.Enable(0)

    def RadioSetFilter(self, filter):
        logging.debug("RADIO: def RadioSetFilter")
        try:
            self.intfilter = self.dictFilter[filter]
        except KeyError:
            return	# Failure

        self.filter = filter
        self.SetFreqModeFilter()
        return 1

    def RadioSetFreq(self, freq):
        logging.debug("RADIO: def RadioSetFreq")
        if not 100000 <= freq <= 1300000000:
            return	# Failure
        self.frequency = freq
        self.SetFreqModeFilter()
        return 1

    def RadioSetIFshift(self, frac):
        logging.debug("RADIO: def RadioSetIFShift")
        self.ifshift = frac
        self.SerialWrite("J43%02x\r\n" % int(frac * 255))

    def RadioSetMode(self, mode):
        logging.debug("RADIO: def RadioSetMode")
        try:
            self.intmode = self.dictMode[mode]
        except KeyError:
            return	# Failure

        self.mode = mode
        self.SetFreqModeFilter()
        self.RadioSetBandScope()
        self.app.dispFreq.EnableCenter(mode in ('nFM', 'wFM'))
        return 1

    def RadioSetNB(self, i):
        logging.debug("RADIO: def RadioSetNB")
        self.NB = i
        self.SerialWrite("J46%02d\r\n" % i)

    def RadioSetSquelch(self, frac):
        logging.debug("RADIO: def RadioSetSquelch")
        self.squelch = frac
        self.SerialWrite("J41%02x\r\n" % int(frac * 255))

    def RadioSetVolume(self, frac):
        logging.debug("RADIO: def RadioSetVolume")
        self.volume = frac
        self.SerialWrite("J40%02x\r\n" % int(frac * 255))


########## Controls start here

class Shim:
    def __init__(self, func, *args):
        self.func = func
        self.args = args

    def __call__(self):
        self.func(*self.args)

class RepeaterButton(tkinter.Button):
    """A button that repeats its command as it is held down."""
    def __init__(self, master, cnf={}, **kw):
        # Record and remove local options
        self.time0 = 600	# time is in milliseconds
        self.time1 = 500
        self.id = None

        for t in ('app', 'command', 'radio', 'time0', 'time1'):
            try:
                setattr(self, t, kw[t])
                del kw[t]
            except KeyError:
                pass

        tkinter.Button.__init__(self, master, cnf, **kw)
        self.bind('<ButtonPress-1>', self.Press, 1)
        self.bind('<ButtonRelease-1>', self.Release, 1)

    def Repeater(self):
        self.command()
        self.id = self.after(self.time1, self.Repeater)

    def Press(self, event):
        self.command()
        self.id = self.after(self.time0, self.Repeater)

    def Release(self, event):
        self.after_cancel(self.id)

class CheckButtons(tkinter.Frame):
    def __init__(self, master, radio, cnf={}, **kw):
        self.radio = radio
        tkinter.Frame.__init__(self, master, cnf, **kw)
        # various check buttons
        self.varATT = tkinter.IntVar()
        self.varATT.set(self.radio.ATT)
        self.varAGC = tkinter.IntVar()
        self.varAGC.set(self.radio.AGC)
        self.varAFC = tkinter.IntVar()
        self.varAFC.set(self.radio.AFC)
        self.varNB = tkinter.IntVar()
        self.varNB.set(self.radio.NB)
        self.varShift = tkinter.IntVar()

        b = tkinter.Checkbutton(self, text="ATT", indicatoron=0, height=1, width=4,	selectcolor=scolor, font=bfont, pady=bpady,	variable=self.varATT, command=self._CmdATT)
        Help(b, 'Attenuator on/off.')
        b.pack(side='left', anchor='nw', expand=1, fill='both')

        b = tkinter.Checkbutton(self, text="AGC", indicatoron=0, width=4, selectcolor=scolor, font=bfont, pady=bpady, variable=self.varAGC, command=self._CmdAGC)
        Help(b, 'Automatic gain control on/off.')
        b.pack(side='left', anchor='nw', expand=1, fill='both')

        b = tkinter.Checkbutton(self, text="AFC", indicatoron=0, width=4, selectcolor=scolor, font=bfont, pady=bpady, variable=self.varAFC, command=self._CmdAFC)
        Help(b, 'Automatic frequency control on/off.')
        b.pack(side='left', anchor='nw', expand=1, fill='both')

        b = tkinter.Checkbutton(self, text="NB", indicatoron=0, width=4, selectcolor=scolor, font=bfont, pady=bpady, variable=self.varNB, command=self._CmdNB)
        Help(b, 'Noise blanker on/off.')
        b.pack(side='left', anchor='nw', expand=1, fill='both')

    def _CmdATT(self):
        i = self.varATT.get()
        self.radio.RadioSetATT(i)

    def _CmdAGC(self):
        i = self.varAGC.get()
        self.radio.RadioSetAGC(i)

    def _CmdAFC(self):
        i = self.varAFC.get()
        self.radio.RadioSetAFC(i)

    def _CmdNB(self):
        i = self.varNB.get()
        self.radio.RadioSetNB(i)

class RadioButtons(tkinter.Frame):
    def __init__(self, master, cnf={}, **kw):
        tkinter.Frame.__init__(self, master, cnf, **kw)

    def Make(self, value, lst): # Make buttons
        self.varRadio = tkinter.StringVar()
        self.varRadio.set(value)

        for t in lst:
            b = tkinter.Radiobutton(self, text=t, indicatoron=0, pady=bpady, padx=0, variable=self.varRadio, width=4, font=bfont, selectcolor=scolor, value=t, command=self._Cmd)
            b.pack(side='left', anchor='w', expand=1, fill='both')

        #print 'CF radiobutton', b.configure()['padx'], b.configure()['pady']

    def Set(self, var):
        if self._CmdRadio(var):
            self.varRadio.set(var)

class FilterDisplay(RadioButtons):
    def __init__(self, master, radio, cnf={}, **kw):
        RadioButtons.__init__(self, master, cnf, **kw)
        self.radio = radio
        self.Make(self.radio.filter, self.radio.filters)
        self._CmdRadio = self.radio.RadioSetFilter

    def _Cmd(self):
        var = self.varRadio.get()
        self._CmdRadio(var)

class ModeDisplay(RadioButtons):
    def __init__(self, master, radio, cnf={}, **kw):
        RadioButtons.__init__(self, master, cnf, **kw)
        self.radio = radio
        self.dispFilter = None
        self.Make(self.radio.mode, self.radio.modes)
        self._CmdRadio =self.radio.RadioSetMode

    def _Cmd(self):
        var = self.varRadio.get()
        self._CmdRadio(var)
        if self.dispFilter:
            self.dispFilter.Set(self.radio.mode2filter[var])

class SignalMeter(tkinter.Canvas):
    def __init__(self, master, cnf={}, **kw):
        tkinter.Canvas.__init__(self, master, cnf, **kw)
        id = self.create_text(0, 0, text="S", anchor='nw', font=mfont)
        bbox = self.bbox(id)
        height = bbox[3] - bbox[1]
        self.delete(id)
        height = height * 1.2
        self.configure(width=1, height=height)
        self.rect1 = self.create_rectangle(0, 0, 20, 5000, fill=mcolorf)
        self.rect2 = self.create_rectangle(20, 0, 5000, 5000, fill=mcolorb)
        self.bind('<Configure>', self.ConfigureEvent)
        self.drawnItems = []

    def ConfigureEvent(self, event):	# Set the scale after the width is known
        for x in self.drawnItems:
            self.delete(x)

        del self.drawnItems[:]

        self.width = event.width
        y = event.height / 2

        for i in range(1, 10):
            x = self.width * i / 15
            id = self.create_text(x, y, text=str(i), anchor='center', font=mfont, fill=mcolort)
            self.drawnItems.append(id)
        id = self.create_text(self.width * 0.73, y, text='+20', anchor='center', font=mfont, fill=mcolort)
        self.drawnItems.append(id)
        id = self.create_text(self.width * 0.92, y, text='+40', anchor='center', font=mfont, fill=mcolort)
        self.drawnItems.append(id)

    def Set(self, frac):
        x = int(self.width * frac + 0.5)
        self.coords(self.rect1, 0, 0, x, 5000)
        self.coords(self.rect2, x, 0, 5000, 5000)

class FreqDisplay(tkinter.Canvas):
    color_on  = Red # For frequency High/Low display
    color_off = Black
    def __init__(self, master, cnf={}, **kw):
        self.width = None
        # Record and remove local options
        for t in ('app', 'width', 'command', 'radio'):
            try:
                setattr(self, t, kw[t])
                del kw[t]
            except KeyError:
                pass

        tkinter.Canvas.__init__(self, master, cnf, **kw)
        # This widget chooses a text size so that its width is equal to
        # or slightly greater than self.width.	But on Linux, the required
        # font size may not be available, so the text is too small.

        if self.width is None:
            self.width = self.app.screenwidth * 0.2

        self.bg = self.cget('background') # Our background color.
        self.bind('<ButtonPress-1>', self.Button)

        # My attempt to change freq value with mousewheel
        self.bind('<MouseWheel>', self.MouseWheel)
        oldw = None
        points = 8

        for p in range(12, 68, 2):	# Try various font sizes
            id = self.create_text(10, 10, text="1234.567.890.....",	anchor='nw', font='times %d' % p)
            bbox = self.bbox(id)
            self.delete(id)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            if oldw != w: # width increased
                oldw = w
                points = p
            if w > self.width:
                break

        font1 = 'times %d' % points
        id = self.create_text(10, 10, text="0",	anchor='nw', font=font1)
        bbox = self.bbox(id)
        self.delete(id)
        w = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        dsc = height * 0.12
        height = height + dsc
        x = w * 0.2
        self.digits = []
        for i in range(0, 10):
            id	= self.create_text(x, dsc, text="%s" % i, anchor='nw', font=font1)
            self.digits.insert(0, id)
            x = x + w
            if i in (3, 6):
                q = self.create_text(x, dsc, text=".", anchor='nw', font=font1)
                bbox = self.bbox(q)
                x = x + bbox[2] - bbox[0]

        # Create the frequency center indicator High/Low
        x = x + w * 0.3
        font2 = "helvetica %d" % (points / 2)
        self.high	 = self.create_text(x, dsc / 2, text="H", anchor='nw', font=font2)
        self.low	= self.create_text(x, height, text="L", anchor='sw', font=font2)
        bbox = self.bbox(self.low)
        w = bbox[2] - bbox[0]
        x = x + w * 1.2
        self.config(width=max(self.width, x), height=height)
        self.enable_center = 1	# Whether to show the High/Low indicator
        self.Center(0)

    def MouseWheel(self, event):
        id = self.find_closest(event.x, event.y)        
        try:
            id = id[0]
            n = self.digits.index(id)
        except: # Not a digit
            return
        
        if event.delta == 120:
            n = 10 ** n # increase frequency
            
        elif event.delta == -120:
            n = - (10 ** n) # decrease frequency
        
        for i in range(len(self.digits)):
            ch = self.itemcget(self.digits[i], 'text')
            if ch in ' 0':
                continue
            else:
                n = n + (ord(ch) - ord('0')) * 10 ** i
        
        self.Set(n)

    def Button(self, event):
        id = self.find_closest(event.x, event.y)
        try:
            id = id[0]
            n = self.digits.index(id)
        except: # Not a digit
            return

        if event.y < self.winfo_height() / 2: # Top of display
            n = 10 ** n # increase frequency
        else:
            n = - (10 ** n) # decrease frequency

        for i in range(len(self.digits)):
            ch = self.itemcget(self.digits[i], 'text')
            if ch in ' 0':
                continue
            else:
                n = n + (ord(ch) - ord('0')) * 10 ** i

        self.Set(n)

    def Set(self, freq):
        if self.radio.RadioSetFreq(freq):
            j = 9
            for ch in "%10d" % freq:
                self.itemconfig(self.digits[j], text=ch)
                j = j - 1
            self.app.DisplayStation(freq)

    def Center(self, center):
        if not self.enable_center:
            pass
        elif center > 0:	# High
            self.itemconfig(self.high, fill=self.color_on)
            self.itemconfig(self.low, fill=self.color_off)
        elif center < 0:	# Low
            self.itemconfig(self.high, fill=self.color_off)
            self.itemconfig(self.low, fill=self.color_on)
        else:		# Centered
            self.itemconfig(self.high, fill=self.color_off)
            self.itemconfig(self.low, fill=self.color_off)

    def EnableCenter(self, enable): # No/Show the center indicator
        self.enable_center = enable
        if enable:
            self.itemconfig(self.high, fill=self.color_off)
            self.itemconfig(self.low, fill=self.color_off)
        else:
            self.itemconfig(self.high, fill=self.bg)
            self.itemconfig(self.low, fill=self.bg)


# These knobs must be constructed with a specified width to control
# their size.	 Thereafter, their size does not change.
class TuningKnob(tkinter.Canvas):
    text = ''
    textcolor = Black
    font = 'helvetica 12'
    def __init__(self, master, cnf={}, **kw):
        self.button = 0
        # Record and remove local options
        for t in ('app', 'radio', 'text', 'font', 'command', 'fraction',
                            'button'):
            try:
                setattr(self, t, kw[t])
                del kw[t]
            except KeyError:
                pass

        tkinter.Canvas.__init__(self, master, cnf, **kw)
        self.enable = 1 # Whether to send commands to the radio
        self.bind('<ButtonPress-1>', self.ButtonPress)
        self.bind('<ButtonRelease-1>', self.ButtonRelease)
        self.bind('<Button1-Motion>', self.Motion)
        self.Draw()
        self.do_motion = 0

    def Draw(self):
        width = height = self.winfo_reqwidth()
        radius = self.radius = width * 8 / 10 / 2
        self.originx = width / 2
        self.originy = width / 2
        x1 = self.originx - radius
        y1 = self.originy - radius
        x2 = self.originx + radius
        y2 = self.originy + radius
        id = self.create_oval(x1, y1, x2, y2, width=3, outline=Green, fill=Green)
        self.theta = 2.0
        self.radius2 = self.radius * 60 / 100
        self.size = s = self.radius * 30 / 100
        x, y = self.Theta2XY(self.theta, self.radius2)
        id = self.circle = self.create_oval(x - s, y - s, x + s, y + s, outline=Green)

    def Theta2XY(self, theta, radius):
        x = radius * math.cos(theta)
        y = radius * math.sin(theta)
        x = x + self.originx
        y = self.originy - y
        return x, y

    def XY2Theta(self, x, y):
        x = x - self.originx
        y = self.originy - y
        return math.atan2(y, x)

    def ButtonPress(self, event):
        r2 = (event.x - self.originx) ** 2 + (event.y - self.originy) ** 2
        if r2 <= (self.radius * 1.2) ** 2:
            self.do_motion = 1
            self.thetamouse = self.thetatotal = self.XY2Theta(event.x, event.y)
            self.freq0 = self.app.radio.frequency
            self.steptune = self.app.band_step / 10

    def ButtonRelease(self, event):
        self.do_motion = 0

    def Motion(self, event):
        if not self.do_motion:
            return

        thetamouse = self.XY2Theta(event.x, event.y)
        delta = thetamouse - self.thetamouse

        if -3.0 < delta < 3.0:
            pass
        elif delta < 3.0:
            delta = delta + 2 * math.pi
        else:
            delta = delta - 2 * math.pi

        theta = self.theta + delta
        self.thetatotal = self.thetatotal - delta
        x, y = self.Theta2XY(theta, self.radius2)
        s = self.size
        self.coords(self.circle, x - s, y - s, x + s, y + s)
        self.theta = theta
        self.thetamouse = thetamouse
        freq = self.freq0 + int(self.thetatotal * self.steptune)
        self.command(freq)

class ControlKnob(TuningKnob):
    def Draw(self):
        self.img = None # Hopefully this releases the image memory
        small = 5
        width = self.winfo_reqwidth()
        if width < 50:
            p = tkinter.PhotoImage(file='Knob64.gif')
            self.img = p.subsample(2)
            radius = 12
            margin = 4
        elif width < 64:
            p = tkinter.PhotoImage(file='Knob100.gif')
            self.img = p.subsample(2)
            radius = 22
            margin = 4
        elif width < 100:
            self.img = tkinter.PhotoImage(file='Knob64.gif')
            radius = 24
            margin = 8
        else:
            self.img = tkinter.PhotoImage(file='Knob100.gif')
            radius = 44
            margin = 8

        self.originx = width / 2

        if self.button:
            self.iButton = tkinter.Button(self, text=self.text, font=self.font,	bd=0, command=self.OnButton)
            id = self.create_window(self.originx, small, window=self.iButton, anchor='n')
            bb = self.bbox(id)
            h = bb[3] - bb[1]		# button height
            self.originy = h + margin + radius
        elif self.text:
            self.idText = self.create_text(self.originx, small, text=self.text, font=self.font, fill=self.textcolor, anchor='n')
            bb = self.bbox(self.idText)
            h = bb[3] - bb[1]		# text height
            self.originy = small + h + margin + radius
        else:
            self.originy = width / 2

        id = self.create_image(self.originx, self.originy, anchor='center', image=self.img)
        self.radius = radius
        self.total = 0.79 * 2 * math.pi # Fraction of circle available
        #self.total = 2 * math.pi
        self.theta0 = (self.total + math.pi) / 2	# Angle for frac==0
        theta = self.theta0 - self.total * self.fraction	# init value
        x, y = self.Theta2XY(theta, self.radius)
        self.line = self.create_line(self.originx, self.originy, x, y, width=2)
        self.config(height=self.originy + radius + margin + small)

    def ButtonPress(self, event):
        r2 = (event.x - self.originx) ** 2 + (event.y - self.originy) ** 2
        if r2 <= (self.radius * 1.2) ** 2:
            self.do_motion = 1

    def Motion(self, event):
        if self.do_motion:
            thetamouse = self.XY2Theta(event.x, event.y)
            if thetamouse < -1.5708:
                thetamouse = thetamouse + 2 * math.pi
            frac = (self.theta0 - thetamouse) / self.total
            self.Set(frac)

    def Set(self, frac):
        if 0.0 <= frac <= 1.0:
            self.fraction = frac
            theta = self.theta0 - self.total * frac
            x, y = self.Theta2XY(theta, self.radius)
            self.coords(self.line, self.originx, self.originy, x, y)
            if self.enable:
                self.command(frac)

class VolumeKnob(ControlKnob):
    def Draw(self):
        self.fraction = self.radio.volume
        ControlKnob.Draw(self)

    def command(self, frac):
        IniFile['Volume'] = str(frac)
        self.radio.RadioSetVolume(frac)

    def OnButton(self):
        if self.enable:
            self.enable = 0
            self.iButton.config(text='MUTE', font=self.font+' bold', activeforeground=Red, foreground=Red)
            self.radio.RadioSetVolume(0.0)
        else:
            self.enable = 1
            self.iButton.config(text='Volume', font=self.font, activeforeground=self.textcolor, foreground=self.textcolor)
            self.radio.RadioSetVolume(self.fraction)

class IfShiftKnob(ControlKnob):
    def Draw(self):
        self.fraction = 0.5
        self.radio.RadioSetIFshift(0.5)
        ControlKnob.Draw(self)

    def command(self, frac):
        self.radio.RadioSetIFshift(frac)

    def OnButton(self):
        self.Set(0.5)

class SquelchKnob(ControlKnob):
    def Draw(self):
        self.fraction = self.radio.squelch
        ControlKnob.Draw(self)

    def command(self, frac):
        IniFile['Squelch'] = str(frac)
        self.radio.RadioSetSquelch(frac)

    def Active(self, active):
        if active:
            self.itemconfig(self.idText, fill=Green)
        else:
            self.itemconfig(self.idText, fill=self.textcolor)

class PowerButton(tkinter.Canvas):
    font='times 12'
    def __init__(self, master, cnf={}, **kw):
        # Record and remove local options
        for t in ('app', 'text', 'font', 'command'):
            try:
                setattr(self, t, kw[t])
                del kw[t]
            except KeyError:
                pass
        tkinter.Canvas.__init__(self, master, cnf, **kw)
        width = self.winfo_reqwidth()
        small = 5
        id = self.create_text(width/2, small, text=self.text, font=self.font, anchor='n')
        bb = self.bbox(id)
        w = bb[2] - bb[0]
        h = bb[3] - bb[1]
        x = width / 8
        y = h + small
        dy = h * 0.5
        self.lightbulb = self.create_rectangle(x, y, width - x, y + dy)
        self.bind('<ButtonPress-1>', self.ButtonPress)
        self.bind('<ButtonRelease-1>', self.ButtonRelease)
        self.config(height = y + dy + small)

    def ButtonPress(self, event):
        self.config(relief='sunken')

    def ButtonRelease(self, event):
        self.config(relief='raised')
        self.command()

    def SetColor(self, color):
        self.itemconfig(self.lightbulb, fill=color)

    def SetColorNum(self, num):
        logging.debug("power color: %i", num)

        if num == 0:	# Power is off            
            self.itemconfig(self.lightbulb, fill=Gray)
        elif num == 1:	# Power is on
            self.itemconfig(self.lightbulb, fill=Green)
        else:		# startup
            self.itemconfig(self.lightbulb, fill=Yellow)

class BandScope(tkinter.Canvas):
    def __init__(self, master, app, cnf={}, **kw):
        self.app = app
        tkinter.Canvas.__init__(self, master, cnf, **kw)
        self.bg = self.cget('background') # Our background color.
        self.stepsize = 5000
        self.bandwidth = 200000
        self.enable = 0
        self.do_motion = 0
        self.number = 0
        self.rectangles = []
        self.items = []
        self.bind('<ButtonPress-1>', self.ButtonPress)
        self.bind('<ButtonRelease-1>', self.ButtonRelease)
        self.bind('<Configure>', self.ConfigureEvent)
        self.bind('<ButtonPress-3>', self.BandscopeMenu)
        self.top_y = 10
        self.bind('<Enter>', self.Enter)
        self.bind('<MouseWheel>', MouseWheel)
        logging.debug("bind() %s", self.bind())
        #print(self.bind())

    def Enter(self, event):
        logging.debug("Enter event: %s", event)
        #print(event)
        self.focus_set()

    def BandscopeMenu(self, event):
        if event.y < self.top_y and self.tune_x1 <= event.x <= self.tune_x2:
            return	# No menu for click in "Tune" control

        menu = tkinter.Menu(self, tearoff=0)
        if self.app.radio.bandscope:
            menu.add_command(label='Turn off', command=self.Power)
        else:
            menu.add_command(label='Turn on', command=self.Power)

        step = tkinter.Menu(menu, tearoff=0)	# Step size menu
        for t in ('100', '500', '1k', '2k', '2.5k', '5k', '10k', '15k', '20k', '50k', '100k'):
            step.add_command(label=t, command=Shim(self.StepChange, MakeFreq(t)))

        menu.add_cascade(label="Frequency step", menu=step)
        bwidth = tkinter.Menu(menu, tearoff=0)	# Bandwidth menu

        for t in ('50k', '100k', '250k', '500k', '1000k', '2000k'):
            bwidth.add_command(label=t, command=Shim(self.BandwidthChange, MakeFreq(t)))

        menu.add_cascade(label="Bandwidth", menu=bwidth)
        menu.tk_popup(event.x_root, event.y_root)

    def Power(self):
        if self.app.radio.bandscope:
            self.app.radio.RadioSetBandScope(0)
            self.Configure()
        else:
            self.app.radio.RadioSetBandScope(1)
            self.Configure()

    def StepChange(self, freq):
        'Command function for the frequency step size popup menu.'
        self.Configure(stepsize=freq)

    def BandwidthChange(self, freq):
        'Command function for the popup menu.'
        self.Configure(bandwidth=freq)

    def ConfigureEvent(self, event):
        self.Configure()

    def Configure(self, stepsize=None, bandwidth=None):
        'Configure and initialize the band scope.'
        if stepsize is None:
            stepsize = self.stepsize
        else:
            self.stepsize = stepsize

        if bandwidth is None:
            bandwidth = self.bandwidth
        else:
            self.bandwidth = bandwidth

        for r in self.rectangles:
            self.delete(r)

        del self.rectangles[:]

        for r in self.items:
            self.delete(r)

        del self.items[:]

        width = self.width = int(self.winfo_width())
        height = self.height = self.winfo_height()
        pixels = 2		# pixels per sample bin
        number = width // 2	# number of samples # changed to int division operator //
        while number > 256 or number * stepsize > bandwidth:
            pixels = pixels + 1
            number = width // pixels # change to int division operator //

        if number % 2:	# number of samples must be even
            number = number + 1

        self.number = number
        self.origin = (width - number * pixels - pixels) / 2
        self.pixels = pixels
        x1 = self.origin

        # Draw the rectangles for the signal bins.
        # There are number signal bins.	 The tuning bin is number/2.	Relative
        # to the tuning frequency, the bins are numbered range(-number/2, number/2).
        for i in range(0, number):
            x2 = x1 + pixels
            r = self.create_rectangle(x1, height, x2, height, fill=bcolorl, outline='')
            self.rectangles.append(r)
            x1 = x1 + pixels

        # draw the top text and controls
        small = 6
        bandwidth = number * stepsize

        if not self.app.radio.bandscope:
            t = 'Bandscope OFF'
        elif stepsize % 1000 == 0:
            t = "Frequency step %dk" % (stepsize / 1000)
        else:
            t = "Frequency step %d Hz" % stepsize

        x = small

        id = self.create_text(x, small, text=t, fill=bcolort, anchor='nw')
        self.items.append(id)
        self.idStep = id
        bbox = self.bbox(id)
        textheight = bbox[3] - bbox[1]
        y = textheight + small	# bottom of text
        self.top_y = y + small	# top of rectangles; no button click above here
        x =	 x + bbox[2] - bbox[0] + small

        id = self.create_text(x, small, text="bandwidth %dk" % int((bandwidth + 500) / 1000), fill=bcolort, anchor='nw')
        self.items.append(id)
        x = self.origin + pixels * float(number + 1) / 2	# zero freq
        x = int(x + 0.5)
        self.center_x = x

        # draw the "TUNE" control
        id = self.dispTune = self.create_text(x, small, text="Tune", fill=bcolort, activefill=acolor, anchor='n')
        self.tag_bind(id, '<ButtonPress-1>', self.TunePress)
        self.tag_bind(id, '<Button1-Motion>', self.TuneMotion)
        self.items.append(id)
        bbox = self.bbox(id)
        self.tune_x1 = bbox[0]
        self.tune_x2 = bbox[2]
        y = bbox[3] - 1

        id = self.create_line(bbox[0], y, bbox[2], y, fill=bcolorc)
        self.items.append(id)

        # draw the frequency marks
        id = self.create_line(x, y, x, height, fill=bcolorc)
        self.items.append(id)

        if bandwidth < 120000:
            label_mod = 10000
        elif bandwidth < 600000:
            label_mod = 50000
        elif bandwidth < 1200000:
            label_mod = 100000
        else:
            label_mod = 200000

        for freq in range(10000, bandwidth * 3, 10000):
            posx = self.origin + pixels * (float(freq) / stepsize + float(number + 1) /2)
            negx = self.origin + pixels * (float(-freq) / stepsize + float(number + 1) /2)
            if negx < 0 or posx > width:
                break
            if freq % (200000) == 0:
                y = height * 0.6
            elif freq % (100000) == 0:
                if label_mod == 200000:
                    y = height * 0.7
                else:
                    y = height * 0.6
            elif freq % (50000) == 0:
                y = height * 0.8
            else:
                if label_mod >= 200000:
                    continue
                y = height * 0.9
            # Draw the lines
            id = self.create_line(posx, y, posx, height, fill=bcolort)
            self.items.append(id)

            id = self.create_line(negx, y, negx, height, fill=bcolort)
            self.items.append(id)

            # Put a frequency label next to the line
            if freq % label_mod == 0:
                text = "%dk" % (freq / 1000)
                id = self.create_text(posx, y, text="+" + text,	fill=bcolort, anchor='se')
                self.items.append(id)
                id = self.create_text(negx, y, text="-" + text,	fill=bcolort, anchor='sw')
                self.items.append(id)

        self.app.radio.RadioSetBandScope()	# notify radio of change

    def Set(self, start, levels):
        # The "start" is the starting index for the signal levels, and index zero is
        # the center tuning frequency.	The "levels" are the 16 signal levels.
        # The lowest visible line is height-2 to height-1.	The top of the
        # signal level display is self.top_y, just below the text controls.
        if not self.enable:
            return

        height = self.height
        small = height - 4		# small signal level
        delta = self.top_y - small	# maximum signal level change (negative)
        pixels = self.pixels
        index0 = int(start + self.number / 2)	# index0 from 0 to number 
        x1 = self.origin + index0 * pixels

        for level in levels:
            try:
                r = self.rectangles[index0]
            except IndexError:
                pass
            else:
                if level == 0.0:	# level is 0.0 thru 1.0
                    y1 = height
                else:
                    y1 = delta * level + small
                self.coords(r, x1, y1, x1 + pixels, height)
            index0 = index0 + 1
            x1 = x1 + pixels

    def Enable(self, turn_on):
        if not self.rectangles:
            return
        if turn_on:
            self.enable = 1
        else:
            self.enable = 1
            self.Set(-self.number/2, (0,) * self.number)
            self.enable = 0

    def ButtonPress(self, event):
        'Tune to the frequency of the mouse click.'
        if event.y > self.top_y:	# No clicks above text level
            index = (event.x - self.origin) / self.pixels - self.number / 2
            freq = index * self.stepsize
            freq = self.app.radio.frequency + freq
            step = self.app.band_step		# Round to the nearest band step
            freq = ((int(freq) + step / 2) / step) * step
            self.app.dispFreq.Set(freq)

    def ButtonRelease(self, event):
        self.do_motion = 0

    def TunePress(self, event):
        self.do_motion = 1
        self.tune_x = event.x
        self.tune_y = event.y

    def TuneMotion(self, event):
        # The amount of frequency change is proportional to the band step.
        # Delta X increases frequency to the right, decreases to the left.
        # Abs(delta y) increases/decreases freq to the right/left of center,
        # and the speed of delta y is proportional to the distance from center.
        if self.do_motion:
            dist = self.app.band_step * 0.1 * ((event.x - self.tune_x) +
                            abs(event.y - self.tune_y) *
                            float(event.x - self.center_x) / self.center_x * 20)
            self.tune_x = event.x
            self.tune_y = event.y
            self.app.dispFreq.Set(self.app.radio.frequency + int(dist))

class DialogSerial(tkinter.Toplevel):
    def __init__(self, serialport, master, cnf={}, **kw):
        global LOGGER
        global portname
        self.logging = 0
        self.old_logger = LOGGER
        LOGGER = self # temporarily change LOGGER to this dialog box
        self.serialport = serialport
        self.serialport.baudrate = 9600
        
        self.portNames = []
        self.ports = list_ports.comports()
        for port in sorted(self.ports):
            self.portNames.append(port.name)
            
        self.numports = len(self.ports)
        
        self.last_text = '\n' # last character written
        tkinter.Toplevel.__init__(self, master, cnf, **kw)
        self.wm_title("Serial Port Setup and Test")
        self.wm_protocol("WM_DELETE_WINDOW", self.WmDeleteWindow)
        self.wm_protocol("WM_SAVE_YOURSELF", self.WmDeleteWindow)
        self.focus_set()

        self.varOpen = tkinter.BooleanVar
        self.varBaud = tkinter.IntVar()
        self.varBaud.set(self.serialport.baudrate)         
        self.varPort = tkinter.StringVar()  # changed from IntVar (Python3)
        self.varSend = tkinter.StringVar()
        self.varSend.set("H1?")
        self.varPort.set(self.portNames)
        
        self.portIndex = tkinter.IntVar()
        self.portIndex.set(self.portNames.index)

        
        # A HACK TO WORK WITH PYSERIAL VERSION WIERDNESS
        #self.varOpen = serialport.is_open
        #self.varSerOpen = serialport.isOpen()
        self.isOpen = serialport.isOpen()
        self.is_open = serialport.is_open
        self.cts = serialport.getCTS()
        self.dsr = serialport.getDSR()
        self.cd = serialport.getCD()
        self._close = serialport.close()
        #self._port_handle = serialport._port_handle()
        serialport.exclusive = True

        #self.fd = serialport.fd        
        
        frm = tkinter.Frame(self) # top row
        frm.pack(side='top', anchor='nw', fill='x')

        l = tkinter.Label(frm, text='Serial port', font=lfont)
        l.pack(side='left', anchor='w')

        self.widgetPort = []			 # The widgets to select the port
        for port in self.portNames:
            b = tkinter.Radiobutton(frm, text=str(port), padx=3, font=bfont, variable=self.varPort, value=port)            
            b.pack(side='left', anchor='w')
            self.widgetPort.append(b)
        
        # THIS WAS FOR ENTERING PORTNAME MANUALLY
        b = tkinter.Radiobutton(frm, text='Name:', font=bfont, variable=self.varPort, value=-1)
        self.widgetPort.append(b)
        b.pack(side='left', anchor='w')
        
        e = tkinter.Entry(frm, bg=White, width=18, textvariable=self.varPort)
        e.pack(side='left', anchor='w', expand=1, fill='x')
        self.widgetPort.append(e)			 # The last item is the entry widget

        # End of top row


        frm = tkinter.Frame(self) # Second row
        frm.pack(side='top', anchor='nw', fill='x')
        l = tkinter.Label(frm, text='Baud rate', font=lfont)
        l.pack(side='left', anchor='w')

        for baud in (9600, 38400):
            b = tkinter.Radiobutton(frm, text=str(baud), font=bfont, variable=self.varBaud, width=6, value=baud, command=self.SetBaud)
            b.pack(side='left', anchor='w')

        # CHANGE TO USING LIST_PORTS
        #portname = self.serialport.name        
        #portname = b
        #portname = self.portNames.index(b)
        portname = e.get()

        #if type(portname) is IntType:
        if type(portname) is int:
            #self.varPort.set(portname)
            self.port.set(portname)
        else:
            #self.varPort.set("")
            self.varPort.set(portname)        

        # end of second row



        frm = tkinter.Frame(self) # last row
        frm.pack(side='bottom', anchor='s', fill='x')
        l = tkinter.Label(frm, text='Write to port', font=lfont)
        l.pack(side='left', anchor='w')

        b = tkinter.Button(frm, text='Port State', command=self.State, font=bfont)
        b.pack(side='right', anchor='e', padx='8p', pady='2p')

        self.bOpen = tkinter.Button(frm, text='', command=self.Open, font=bfont)
        self.bOpen.pack(side='right', anchor='e', padx='8p', pady='2p')

        entry = tkinter.Entry(frm, bg=White, textvariable=self.varSend)
        entry.pack(side='left', anchor='w', expand=1, fill='x')
        entry.bind('<Key-Return>', self.ToPort)

        # end of last row.



        # remaining space is the text display
        #self.canvas = ScrolledText.ScrolledText(self, width=1, height=10, relief='sunken', bg=White)
        self.canvas = ScrolledText(self, width=1, height=10, relief='sunken', bg=White)
        self.canvas.pack(side='top', anchor='nw', expand=1, fill='both')
        self.logging = 1
        self.State()

    def WmDeleteWindow(self):
        #if not self.serialport.isOpen(self):
        if not self.varOpen:
            self.SetPort()

        global LOGGER

        self.logging = 0
        LOGGER = self.old_logger	# Put back the old LOGGER
        self.destroy()

    def SetBaud(self):
        baud = self.varBaud.get()		
        #self.serialport.setBaudrate(baud)
        #self.serialport.baudrate(baud)
        self.serialport.baudrate = baud

    def SetPort(self):
        #portname = self.varPort.get()
        # THIS WAS TO HANDLE NAME = -1 OF RADIOBUTTON 'NAME'
        #if int(portname) < 0:
        #if int(self.portNames.index(portname)) < 0:
        #	portname = self.varPort.get()

        #self.serialport.setPort(portname)
        #self.serialport.port(portname)
        self.serialport.port = portname
        IniFile['AppSerialPortName'] = str(portname)
        logging.debug("portname: %s", portname)
        #print(str(portname))

    def Open(self):
        #if self.serialport.isOpen(self):
        #if self.serialport.is_open(self):
        if self.serialport.isOpen:
            self.serialport._close
        else:
            self.SetPort()
            try:
                self.serialport.open()
            except:
                FormatTb()
        self.State()

    def State(self):
        #self.serialport = Serial
        d = self.serialport
        self.varBaud.set(self.serialport.baudrate)
        #if d.is_open(self):
        if d.isOpen():
            #if self.Open():
            text = "\n<<Serial port is open: CTS %s, DSR %s, CD %s>>\n" % (d.getCTS(self), d.getDSR(self), d.getCD(self))
            #cts=d.cts
            #dsr=d.dsr
            #cd=d.cd
            #text = "\n<<Serial port is open: CTS %s, DSR %s, CD %s>>\n" % (cts, dsr, cd)
            self.write(text.encode())
            logging.debug(text)
            self.bOpen.configure(text='Close Port')
            for w in self.widgetPort:
                w.configure(state='disabled')
        else:
            self.write("\n<<Serial port is closed>>\n")
            self.bOpen.configure(text='Open Port')
            for w in self.widgetPort:
                w.configure(state='normal')

    def ToPort(self, event):
        #if self.serialport.isOpen(self):
        #if self.serialport.is_open:
        if self.varOpen:
            text = str(self.varSend.get())
            self.serialport.write(text + "\r\n")
            #self.write("\n<Send %s>\n" % text)
    
    def to_bytes(self, s):
        if type(s) is bytes:
            return s
        elif type(s) is str or (sys.version_info[0] < 3 and type(s) is unicode):
            return codecs.encode(s, 'utf-8')
        else:
            raise TypeError("Expected bytes or string, but got %s." % type(s))

    def write(self, text):
        if self.logging:
            #try encoding
            self.to_bytes(text)							
            #text = text.replace(b'\r', b'')
            text = text.replace('\r', '')
            
            if self.last_text == '\n' and text[0:1] == '\n':
                text = text[1:]		# remove a double newline
            if text:
                self.last_text = text[-1]
                self.canvas.insert('end', text)
                self.canvas.see('end')

class StdError:
    """This displays a message box in a second main program."""
    def __init__(self):
        self.text = ''
        sys.stdout = self
        sys.stderr = self

    def write(self, text):
        self.text = self.text + text

    def printer(self):
        if self.text:
            tk = tkinter.Tk()
            tk.wm_title("Standard output and error")
            m = tkinter.Label(tk, text=self.text, justify='left', font=lfont)
            m.pack()
            tk.mainloop()
            self.text = ''

app = None
#StdErr = StdError()
app = Application()
app.mainloop()
#if app:
#	 app.Close()
#StdErr.printer()
