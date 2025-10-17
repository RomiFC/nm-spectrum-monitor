# PRIVATE LIBRARIES
import defaultconfig
from frontendio import *
from timestamp import *
from opcodes import *
from loggingsetup import *
from automation import *
from drift import *
from waterfall import *

# OTHER MODULES
import threading
import sys
import os
from datetime import date, datetime, timedelta, timezone
import datetime as dt
from tzlocal import get_localzone
from pyvisa import attributes
import numpy as np
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.cron import CronTrigger
import logging
import decimal
import traceback
import webbrowser
import tomllib
from pathlib import Path

# MATPLOTLIB
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.ticker import EngFormatter
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# TKINTER
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter import filedialog
from tkinter import colorchooser
from tkinter import font
from tkinter.ttk import *
from ttkthemes import ThemedTk
from tkcalendar import Calendar, DateEntry
from tktimepicker import SpinTimePickerModern, constants

# CONSTANTS
IDLE_DELAY = 1.0
ANALYZER_LOOP_DELAY = 0.5
ANALYZER_REFRESH_DELAY = 0.3
MOTOR_LOOP_DELAY = 0.5
STATUS_MONITOR_DELAY = 0.2
RETURN_ERROR = 1
RETURN_SUCCESS = 0
ENABLE = 1
DISABLE = 0
CHUNK_SIZE_DEF = 20480     # Default byte count to read when issuing viRead
CHUNK_SIZE_MIN = 1024
CHUNK_SIZE_MAX = 1048576  # Max chunk size allowed
TIMEOUT_DEF = 2000        # Default VISA timeout value
TIMEOUT_MIN = 1000        # Minimum VISA timeout value
TIMEOUT_MAX = 25000       # Maximum VISA timeout value
AUTO = 1
MANUAL = 0
SWEPT = 'swept'
ZERO = 'zero'
ROOT_PADX = 5
ROOT_PADY = 5
COLOR_GREEN = '#00ff00'
SINGLE_ICON = '\u2192'
CONT_ICON = '\u2B8C'
RESTART_ICON = '\u2B6F'
DEF_WF_PATH = os.getcwd()
DEF_WF_THRESHOLD = 100
DEF_WF_TZ = 'US/Mountain'
DEF_WF_FILETYPE = '.png'
DEF_WF_DPI = 800
WATERFALL_JOB_ID = 'waterfall'
DEF_DRIFT_FROM_PATH = os.getcwd()
DEF_DRIFT_TO_PATH = os.getcwd()
DRIFT_JOB_ID = 'driftprocessing'
LOCAL_TIMEZONE = get_localzone()

# STATE CONSTANTS
class state:
    IDLE = 0
    INIT = 1
    LOOP = 2
    AUTO = 3
    CLEANUP = 4

# TOML CONFIGURATION
try:
    missingHeaders = []
    missingKeys = []
    file = open(Path(__file__).parent.absolute() / 'config.toml', "rb")
    cfg = tomllib.load(file)

    for header in defaultconfig.cfg:
        if str(header) not in cfg:
            missingHeaders.append(header)
            continue
        for key in defaultconfig.cfg[header]:
            if str(key) not in cfg[header]:
                missingKeys.append(header + '.' + key)
except Exception as e:
    cfg_error = e
finally:
    if missingHeaders or missingKeys or 'cfg_error' in locals():
        cfg = defaultconfig.cfg

# ENCODER CONSTANTS (HOME AND COUNTS PER DEGREE)
X_HOME = cfg['calibration']['x_enc_home']
Y_HOME = cfg['calibration']['y_enc_home']
X_CPD = cfg['calibration']['x_countsperrotation'] / 360
Y_CPD = cfg['calibration']['y_countsperrotation'] / 360

# THREADING EVENTS
visaLock = threading.RLock()        # For VISA resources
motorLock = threading.RLock()       # For motor controller
plcLock = threading.RLock()         # For PLC
specPlotLock = threading.RLock()    # For matplotlib spectrum plot
bearingPlotLock = threading.RLock() # For matplotlib antenna direction plot

# AUTOMATION PARAMETERS
executors = {
    'default': ThreadPoolExecutor(cfg['automation']['thread_max_workers']),
}
job_defaults = {
    'coalesce': cfg['automation']['coalesce'],
    'max_instances': cfg['automation']['job_max_instances']
}
automation = Automation(defaultstate=state.IDLE, executors=executors, job_defaults=job_defaults)

# DRIFT/WATERFALL SCHEDULER
dwfScheduler = BackgroundScheduler()

# SPECTRUM ANALYZER PARAMETERS
class Parameter:
    instances = []
    def __init__(self, name, command, log = True):
        """Spectrum analyzer parameter and associated SCPI command.

        Args:
            name (string): Full name to be used in trace csv.
            command (string): SCPI command used to query/set parameter.
            log (bool): Determines whether or not to save the parameter to trace csv. Defaults to True.
        """
        Parameter.instances.append(self)
        self.name = name
        self.command = command
        self.log = log
        self.arg = None
        self.widget = None
        self.value = None

    def update(self, arg = None, widget = None, value=None):
        """Update the argument/value and tkinter widget associated with the parameter.

        Args:
            arg (any, optional): Parameter argument. Defaults to None.
            widget (ttk.Widget or Tkinter_variable, optional): Associated tkinter widget. Defaults to None.
            value(any, optional): Parameter value. Defaults to None.
        """
        if arg is not None:
            self.arg = arg
        if widget is not None:
            self.widget = widget
        if value is not None:
            self.value = value

CenterFreq      = Parameter('Center Frequency', ':SENS:FREQ:CENTER', log=False)
Span            = Parameter('Span', ':SENS:FREQ:SPAN', log=False)
StartFreq       = Parameter('Start Frequency', ':SENS:FREQ:START')
StopFreq        = Parameter('Stop Frequency', ':SENS:FREQ:STOP')
SweepTime       = Parameter('Sweep Time', ':SWE:TIME')
Rbw             = Parameter('RBW', ':SENS:BANDWIDTH:RESOLUTION')
Vbw             = Parameter('VBW', ':SENS:BANDWIDTH:VIDEO')
BwRatio         = Parameter('VBW:3 dB RBW', ':SENS:BANDWIDTH:VIDEO:RATIO', log=False)
Ref             = Parameter('Ref Level', ':DISP:WINDOW:TRACE:Y:RLEVEL', log=False)
NumDiv          = Parameter('Number of Divisions', ':DISP:WINDOW:TRACE:Y:NDIV', log=False)
YScale          = Parameter('Scale/Div', ':DISP:WINDOW:TRACE:Y:PDIV', log=False)
Atten           = Parameter('Attenuation', ':SENS:POWER:RF:ATTENUATION')
SpanType        = Parameter('Swept Span', ':SENS:FREQ:SPAN', log=False)
SweepType       = Parameter('Auto Sweep Time', ':SWE:TIME:AUTO', log=False)
RbwType         = Parameter('Auto RBW', ':SENS:BAND:RES:AUTO', log=False)
VbwType         = Parameter('Auto VBW', ':SENS:BAND:VID:AUTO', log=False)
BwRatioType     = Parameter('Auto VBW:RBW Ratio', ':SENS:BAND:VID:RATIO', log=False)
RbwFilterShape  = Parameter('RBW Filter', ':SENS:BAND:SHAP')
RbwFilterType   = Parameter('RBW Filter BW', ':SENS:BAND:TYPE')
AttenType       = Parameter('Auto Attenuation', ':SENS:POWER:ATT:AUTO', log=False)
XAxisUnit       = Parameter('X Axis Units', None)
XAxisUnit.update(value='Hz')
YAxisUnit       = Parameter('Y Axis Units', ':UNIT:POW')
TraceType       = Parameter('Trace Type', ':TRACE:TYPE')
AvgType         = Parameter('Average Type', ':SENS:AVER:TYPE')
AvgAutoMan      = Parameter('Auto Average Type', ':SENS:AVER:TYPE:AUTO', log=False)
AvgHoldCount    = Parameter('Average/Hold Count', ':SENS:AVER:COUNT', log=False)
SweepPoints     = Parameter('Number of Points', ':SENS:SWEEP:POINTS')
TimeParameter   = Parameter('Time', None)

# real code starts here
def threadHandler(target, args=(), kwargs={}):
    """Generates a new daemon thread to handle blocking routines without blocking main thread.

    Args:
        target (method): Callable object to be invoked by the run() method.
        args (tuple, optional): List or tuple for target invocation. Defaults to ().
        kwargs (dict, optional): Dictionary of keyword arguments for target invocation. Defaults to {}.
    """
    thread = threading.Thread(target = target, args = args, kwargs = kwargs, daemon=True)
    thread.start()

def isNumber(input):
    """is it a number

    Args:
        input (thing): thing to test

    Returns:
        Bool: if it's a number
    """
    try:
        float(f"{input}0")
        return TRUE
    except:
        return FALSE
    
def clearAndSetWidget(widget, arg):
    """Clear the ttk::widget passed in 'widget' and replace it with 'arg' in engineering notation if possible.
    The N9040B and other instruments will return queries in square brackets which python interprets as a list.

    Args:
        widget (ttk.Widget or Tkinter_variable): Widget to clear/set.
        arg (list, str): Value in 'arg[0]' will be taken to set the widget in engineering notation. If that fails, attempt to set the widget to 'arg'.
    """
    try:
        id = widget.winfo_id()
    except:
        id = widget
    logging.debug(f"clearAndSetWidget received widget {id} and argument {arg}")
    # Set radiobutton widgets
    if isinstance(widget, (BooleanVar, IntVar, StringVar)):
        try:
            arg = bool(arg[0])
            widget.set(arg)
        except:
            widget.set(arg)
        finally:
            logging.debug(f"clearAndSetWidget passed argument {arg} ({type(arg)}) to {id} ({type(widget)})")
    # Set entry/combobox widgets
    if isinstance(widget, (tk.Entry, ttk.Entry, ttk.Combobox)):
        state = widget.cget("state")
        if state != NORMAL:
            widget.configure(state=NORMAL)
        widget.delete(0, END)
        # Try to convert string in list to engineering notation
        try:
            arg = float(arg[0])
            x = decimal.Decimal(arg)
            x = x.normalize().to_eng_string()
            widget.insert(0, x)
            logging.debug(f"clearAndSetWidget passed argument {x} ({type(x)}) to {id} ({type(widget)}).")
        except:
            widget.insert(0, arg)
            logging.debug(f"clearAndSetWidget passed argument {arg} ({type(arg)}) to {id} ({type(widget)}).")
        widget.configure(state=state)
    # Set textbox widgets
    if isinstance(widget, (tk.Text,)):
        state = widget.cget("state")
        if state != NORMAL:
            widget.configure(state=NORMAL)
        widget.delete(1.0, END)
        widget.insert(1.0, arg)
        widget.configure(state=state)


def disableChildren(parent):
    """Tries to set the state of the child widgets of parent to 'disable'.

    Args:
        parent (tk:widget): Parent widget whose children should be disabled.
    """
    for child in parent.winfo_children():
        wtype = child.winfo_class()
        if wtype not in ('Frame', 'LabelFrame', 'TFrame', 'TLabelframe'):
            child.configure(state='disable')
        else:
            disableChildren(child)

def enableChildren(parent):
    """Tries to set the state of the child widgets of parent to 'enable' or 'normal'.

    Args:
        parent (tk:widget): Parent widget whose children should be enabled.
    """
    for child in parent.winfo_children():
        wtype = child.winfo_class()
        if wtype not in ('Frame', 'LabelFrame', 'TFrame', 'TLabelframe'):
            try:
                child.configure(state='enable')
            except:
                child.configure(state='normal')
        else:
            enableChildren(child)


class FrontEnd():
    def __init__(self, root, Vi, Motor, PLC):
        """Initializes the top level tkinter interface

        Args:
            root (Tk or ThemedTk): Root tkinter window.
            Vi (VisaIO): Object of VisaIO that contains methods for VISA communication and an opened resource manager.
            Motor (MotorIO): Object of MotorIO that contains methods for serial motor communication.
            PLC (SerialIO): Object of SerialIO that contains methods for serial PLC communication.
        """
        # CONSTANTS
        self.SELECT_TERM_VALUES = ('Line Feed - \\n', 'Carriage Return - \\r')
        # VARIABLES
        self.timeout = TIMEOUT_DEF           # VISA timeout value
        self.chunkSize = CHUNK_SIZE_DEF      # Bytes to read from buffer
        self.instrument = ''                 # ID of the currently open instrument.
        self.motorPort = ''
        self.plcPort = ''
        self.chainSelect = 'SLEEP'
        # TKINTER VARIABLES
        self.sendEnd = BooleanVar()
        self.sendEnd.set(TRUE)
        self.enableTerm = BooleanVar()
        self.enableTerm.set(FALSE)
        # OBJECTS
        self.Vi = Vi
        self.motor = Motor
        self.PLC = PLC
        # STYLING
        self.SELECT_BACKGROUND = cfg['theme']['select_background']
        self.DEFAULT_BACKGROUND = root.cget('bg')
        CLOCK_FONT = cfg['theme']['clock_font']
        FONT = cfg['theme']['font']
        FRAME_PADX = 5
        FRAME_PADY = 5
        BUTTON_PADX = 5
        BUTTON_PADY = 5

        # Root resizing
        root.rowconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)
        root.columnconfigure(1, weight=1)
        # Root frames
        plotFrame = ttk.Frame(root)
        plotFrame.grid(row=0, column=1, sticky=NSEW, padx=ROOT_PADX, pady=ROOT_PADY) 
        controlFrame = tk.Frame(root)
        controlFrame.grid(row=0, column=0, rowspan=2, sticky=NSEW, padx=ROOT_PADX, pady=ROOT_PADY) 
        for i in range(5):
            controlFrame.rowconfigure(i, weight=1)
        for j in range(2):
            controlFrame.columnconfigure(j, uniform=True)
        # Frames for other objects
        self.directionFrame = tk.LabelFrame(plotFrame, text = "Antenna Position")  # Frame that holds matplotlib azimuth/elevation plot
        self.spectrumFrame = tk.LabelFrame(plotFrame, text = "Spectrum Analyzer")   # Frame that holds matplotlib spectrum plot
        self.directionFrame.grid(row = 0, column = 0, sticky = NSEW)
        self.spectrumFrame.grid(row = 0, column = 1, sticky=NSEW)
        plotFrame.rowconfigure(0, weight=1)
        plotFrame.columnconfigure(0, weight=1)
        plotFrame.columnconfigure(1, weight=1)
        # Clock
        self.clockLabel = tk.Label(controlFrame, font=CLOCK_FONT)
        self.clockLabel.grid(row=0, column=0, columnspan=2, padx=FRAME_PADX, pady=FRAME_PADY)
        # Drive Status
        azStatusFrame = tk.LabelFrame(controlFrame, text='Azimuth Drive')
        azStatusFrame.grid(row=1, column=0, sticky=(N, E, W), padx=FRAME_PADX, pady=FRAME_PADY)
        azStatusFrame.columnconfigure(0, weight=1)
        self.azStatus = tk.Button(azStatusFrame, text='STOPPED', font=FONT, state=DISABLED, width=6)
        self.azStatus.grid(row=0, column=0, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        elStatusFrame = tk.LabelFrame(controlFrame, text='Elevation Drive')
        elStatusFrame.grid(row=1, column=1, sticky=(N, E, W), padx=FRAME_PADX, pady=FRAME_PADY)
        elStatusFrame.columnconfigure(0, weight=1)
        self.elStatus = tk.Button(elStatusFrame, text='STOPPED', font=FONT, state=DISABLED, width=6)
        self.elStatus.grid(row=0, column=0, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        # PLC Operations
        chainFrame = tk.LabelFrame(controlFrame, text='PLC Operations')
        chainFrame.grid(row=2, column=0, sticky=(N, E, W), columnspan=2, padx=FRAME_PADX, pady=FRAME_PADY)
        for i in range(2):
            chainFrame.columnconfigure(i, weight=1, uniform=True)
        self.initP1Button = tk.Button(chainFrame, font=FONT, text='INIT', command=lambda:self.PLC.threadHandler(self.PLC.query, (opcodes.P1_INIT.value,), {'delay': 15.0}))
        self.initP1Button.grid(row=0, column=0, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.killP1Button = tk.Button(chainFrame, font=FONT, text='DISABLE', command=lambda:self.PLC.threadHandler(self.PLC.query, (opcodes.P1_DISABLE.value,), {'delay': 10.0}))
        self.killP1Button.grid(row=0, column=1, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.sleepP1Button = tk.Button(chainFrame, font=FONT, text='SLEEP', command=lambda:self.PLC.threadHandler(self.PLC.query, (opcodes.SLEEP.value,)))
        self.sleepP1Button.grid(row=1, column=0, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.returnP1Button = tk.Button(chainFrame, font=FONT, text='RETURN', command=lambda:self.PLC.threadHandler(self.PLC.query, (opcodes.RETURN_OPCODES.value,)))
        self.returnP1Button.grid(row=1, column=1, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.dfs1Button = tk.Button(chainFrame, font=FONT, text='DFS1', command=lambda:self.PLC.threadHandler(self.PLC.query, (opcodes.DFS_CHAIN1.value,)))
        self.dfs1Button.grid(row=2, column=0, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.ems1Button = tk.Button(chainFrame, font=FONT, text='EMS1', command=lambda:self.PLC.threadHandler(self.PLC.query, (opcodes.EMS_CHAIN1.value,)))
        self.ems1Button.grid(row=2, column=1, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.PLC_OUTPUTS_LIST = (self.sleepP1Button, self.dfs1Button, self.ems1Button)              # Mutually exclusive buttons for which only one should be selected
        # Mode
        modeFrame = tk.LabelFrame(controlFrame, text='Motor Operations')
        modeFrame.grid(row=3, column=0, sticky=(N, E, W), columnspan=2, padx=FRAME_PADX, pady=FRAME_PADY)
        modeFrame.columnconfigure(0, weight=1)
        self.standbyButton = tk.Button(modeFrame, text='Standby', font=FONT, bg=self.SELECT_BACKGROUND)
        self.standbyButton.grid(row=0, column=0, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.manualButton = tk.Button(modeFrame, text='Manual', font=FONT, bg=self.DEFAULT_BACKGROUND)
        self.manualButton.grid(row=1, column=0, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.haltButton = tk.Button(modeFrame, text='Halt Movement', font=FONT, bg=self.DEFAULT_BACKGROUND)
        self.haltButton.grid(row=2, column=0, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.killDrivesButton = tk.Button(modeFrame, text='Disable Drives', font=FONT, bg=self.DEFAULT_BACKGROUND)
        self.killDrivesButton.grid(row=3, column=0, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.MODE_BUTTONS_LIST = (self.standbyButton, self.manualButton)
        # Automation
        autoFrame = tk.LabelFrame(controlFrame, text='Automation')
        autoFrame.grid(row=4, column=0, sticky=(N, E, W), columnspan=2, padx=FRAME_PADX, pady=FRAME_PADY)
        autoFrame.columnconfigure(0, weight=1)
        self.autoButton = tk.Button(autoFrame, text='Queue', font=FONT, bg=self.DEFAULT_BACKGROUND)
        self.autoButton.grid(row=0, column=0, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.autoStartStopButton = tk.Button(autoFrame, text='Start / Stop', font=FONT, bg=self.DEFAULT_BACKGROUND)
        self.autoStartStopButton.grid(row=1, column=0, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        # Connection Status
        connectionsFrame = tk.LabelFrame(controlFrame, text='Connection Status')
        connectionsFrame.grid(row=5, column=0, sticky=(N, E, W), columnspan=2, padx=FRAME_PADX, pady=FRAME_PADY)
        for i in range(2):
            connectionsFrame.columnconfigure(i, weight=1)
        visaLabel = tk.Label(connectionsFrame, text='VISA:', font=FONT)
        visaLabel.grid(row=0, column=0, sticky=W, padx=BUTTON_PADX, pady=BUTTON_PADY)
        motorLabel = tk.Label(connectionsFrame, text='MOTOR:', font=FONT)
        motorLabel.grid(row=1, column=0, sticky=W, padx=BUTTON_PADX, pady=BUTTON_PADY)
        plcLabel = tk.Label(connectionsFrame, text='PLC:', font=FONT)
        plcLabel.grid(row=2, column=0, sticky=W, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.visaStatus = tk.Button(connectionsFrame, text='NC', font=FONT, state=DISABLED, width=12)
        self.visaStatus.grid(row=0, column=1, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.motorStatus = tk.Button(connectionsFrame, text='NC', font=FONT, state=DISABLED, width=12)
        self.motorStatus.grid(row=1, column=1, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.plcStatus = tk.Button(connectionsFrame, text='NC', font=FONT, state=DISABLED, width=12)
        self.plcStatus.grid(row=2, column=1, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)

        root.after(1000, self.update_time )

    def initDevice(self, event, device, port):
        """Connects to the respective resource and updates the attribute which stores the resource name.

        Args:
            event (event): Event passed by tkinter
            device (string): Can be 'visa', 'motor', or 'plc'.
            port (string): Name of the VISA ID or COM port to connect to.
        """
        if device == 'visa':
            with visaLock:
                self.Vi.connectToRsrc(port)
                self.instrument = port
                self.scpiApplyConfig(self.timeoutWidget.get(), self.chunkSizeWidget.get())
                try:
                    idn = self.Vi.identify()
                    shortidn = str(idn[0]) + ', ' + str(idn[1]) + ', ' + str(idn[2])
                    self.spectrumFrame.configure(text=shortidn)
                except Exception as e:
                    logging.error(f'{type(e).__name__}: {e}')
                    return
        elif device == 'motor':
            self.motorPort = self.motorSelectBox.get()[:4]
            self.motor.openSerial(self.motorPort)
        elif device == 'plc':
            self.PLC.openSerial(port)
            self.PLC.threadHandler(self.PLC.queryStatus)
            self.plcPort = port

    def setStatus(self, widget, text=None, background=None):
        """Sets the text and background of a widget being used as a status indicator

        Args:
            widget (tk.Button): Tkinter widget being used as a status indicator. ttk.Button will NOT work.
            text (string, optional): Text to replace in the button widget. Defaults to None.
            background (string, optional): Color in any tkinter-compatible format, although ideally hex for compatibility. Defaults to None.
        """
        if text is not None:
            widget.configure(text=text)
        if background is not None:
            widget.configure(background=background)
    
    def onExit( self ):
        """Cleanup""" 
        while (self.motor.ser.is_open):
            self.motor.CloseSerial()
        root.quit()
        logging.info("Program executed with exit code: 0")

    def openHelp(self):
        """Opens help menu on a new toplevel window.
        """
        continueCheck = messagebox.askokcancel(title='Open wiki', message='This will open a new web browser page. Continue?')
        if continueCheck:
            webbrowser.open('https://github.com/RomiFC/RF-DFS/wiki')

    def openConfig(self):
        """Opens configuration menu on a new toplevel window.
        """
        _parent = Toplevel()
        _parent.title('Configure')

        def onRefreshPress():
            """Update the values in the SCPI instrument selection box
            """
            logging.info('Searching for resources...')
            self.instrSelectBox['values'] = self.Vi.rm.list_resources()
            self.motorSelectBox['values'] = list(serial.tools.list_ports.comports())
            self.plcSelectBox['values'] = list(serial.tools.list_ports.comports())
        def onEnableTermPress():
            if self.enableTerm.get():
                self.selectTermWidget.config(state='readonly')
            else:
                self.selectTermWidget.config(state='disabled')  
        def onDisconnectPress(device):
            match device:
                case 'visa':
                    self.Vi.closeSession()
                    self.instrument = ''
                    self.instrSelectBox.set('')
                case 'motor':
                    self.motor.closeSerial()
                    self.motorPort = ''
                    self.motorSelectBox.set('')
                case 'plc':
                    self.PLC.close()
                    self.plcPort = ''
                    self.plcSelectBox.set('')

        # INSTRUMENT SELECTION FRAME & GRID
        connectFrame = ttk.LabelFrame(_parent, borderwidth = 2, text = "Instrument Connections")
        connectFrame.grid(column=0, row=0, padx=20, pady=20, columnspan=3, ipadx=5, ipady=5)
        ttk.Label(
            connectFrame, text = "SCPI:", font = ("Times New Roman", 10)).grid(
            column = 0, row = 0, padx = 5, sticky=W) 
        ttk.Label(
            connectFrame, text = "Motor:", font = ("Times New Roman", 10)).grid(
            column = 0, row = 1, padx = 5, sticky=W) 
        ttk.Label(
            connectFrame, text = "PLC:", font = ("Times New Roman", 10)).grid(
            column = 0, row = 2, padx = 5, sticky=W) 
        self.instrSelectBox = ttk.Combobox(connectFrame, values = self.Vi.rm.list_resources(), width=40)
        self.instrSelectBox.grid(row = 0, column = 1, padx = 10 , pady = 5)
        self.motorSelectBox = ttk.Combobox(connectFrame, values = list(serial.tools.list_ports.comports()), width=40)
        self.motorSelectBox.grid(row = 1, column = 1, padx = 10, pady = 5)
        self.plcSelectBox = ttk.Combobox(connectFrame, values = list(serial.tools.list_ports.comports()), width=40)
        self.plcSelectBox.grid(row = 2, column = 1, padx = 10, pady = 5)
        instrCloseButton = ttk.Button(connectFrame, text = 'Disconnect', command=lambda: onDisconnectPress(device='visa'))
        instrCloseButton.grid(row = 0, column = 2, padx=5)
        motorCloseButton = ttk.Button(connectFrame, text = 'Disconnect', command=lambda: onDisconnectPress(device='motor'))
        motorCloseButton.grid(row = 1, column = 2, padx=5)
        plcCloseButton = ttk.Button(connectFrame, text = 'Disconnect', command=lambda: onDisconnectPress(device='plc'))
        plcCloseButton.grid(row = 2, column = 2, padx=5)
        self.instrSelectBox.set(self.instrument)
        self.motorSelectBox.set(self.motorPort)
        self.plcSelectBox.set(self.plcPort)

        self.instrSelectBox.bind("<<ComboboxSelected>>", lambda event: self.initDevice(event, device='visa', port=self.instrSelectBox.get()))
        self.motorSelectBox.bind("<<ComboboxSelected>>", lambda event: self.initDevice(event, device='motor', port=self.motorSelectBox.get()[:4]))
        self.plcSelectBox.bind("<<ComboboxSelected>>", lambda event: self.initDevice(event, device='plc', port=self.plcSelectBox.get()[:4]))

        # VISA CONFIGURATION FRAME
        configFrame = ttk.LabelFrame(_parent, borderwidth = 2, text = "VISA Configuration")
        configFrame.grid(row = 1, column = 0, padx=20, pady=10, sticky=NSEW, rowspan=2)
        timeoutLabel = ttk.Label(configFrame, text = 'Timeout (ms)')
        timeoutLabel.grid(row = 0, column = 0, pady=5)
        self.timeoutWidget = ttk.Spinbox(configFrame, from_=TIMEOUT_MIN, to=TIMEOUT_MAX, increment=100, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.timeoutWidget.grid(row = 1, column = 0, padx=20, pady=5, columnspan=2)
        self.timeoutWidget.set(self.timeout)
        chunkSizeLabel = ttk.Label(configFrame, text = 'Chunk size (Bytes)')
        chunkSizeLabel.grid(row = 2, column = 0, pady=5)
        self.chunkSizeWidget = ttk.Spinbox(configFrame, from_=CHUNK_SIZE_MIN, to=CHUNK_SIZE_MAX, increment=10240, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.chunkSizeWidget.grid(row = 3, column = 0, padx=20, pady=5, columnspan=2)
        self.chunkSizeWidget.set(self.chunkSize)
        applyButton = ttk.Button(configFrame, text = "Apply Changes", command = lambda:self.scpiApplyConfig(self.timeoutWidget.get(), self.chunkSizeWidget.get()))
        applyButton.grid(row = 7, column = 0, columnspan=2, pady=10)
        # VISA TERMINATION FRAME
        termFrame = ttk.LabelFrame(_parent, borderwidth=2, text = 'Termination Methods')
        termFrame.grid(row = 1, column = 1, padx = 5, pady = 10, sticky=(N, E, W), ipadx=5, ipady=5)
        self.sendEndWidget = ttk.Checkbutton(termFrame, text = 'Send \'End or Identify\' on write', variable=self.sendEnd)
        self.sendEndWidget.grid(row = 0, column = 0, pady = 5)
        self.selectTermWidget = ttk.Combobox(termFrame, text='Termination Character', values=self.SELECT_TERM_VALUES, state='disabled')
        self.selectTermWidget.grid(row = 2, column = 0, pady = 5)
        self.enableTermWidget = ttk.Checkbutton(termFrame, text = 'Enable Termination Character', variable=self.enableTerm, command=lambda:onEnableTermPress())
        self.enableTermWidget.grid(row = 1, column = 0, pady = 5)
        # REFRESH BUTTON
        self.refreshButton = ttk.Button(_parent, text = "Refresh All", command = lambda:onRefreshPress())
        self.refreshButton.grid(row = 2, column = 1, padx=5)

    def resetConfigWidgets(self, *event):
        # DEPRECATED WITH THE REMOVAL OF CONTROL AND CONFIG TABS
        """Event handler to reset widget values to their respective variables

        Args:
            event (event): Argument passed by tkinter event (Varies for each event)
        """
        # These widgets values are stored in variables and will be reset to the variable on function call
        try:
            self.timeoutWidget.set(self.timeout)
            self.chunkSizeWidget.set(self.chunkSize)
            self.instrSelectBox.set(self.instrument)
        except:
            pass
        # These widget values are retrieved from self.Vi.openRsrc and will be reset depending on the values returned
        try:
            self.sendEnd.set(self.Vi.openRsrc.send_end)
            readTerm = repr(self.Vi.openRsrc.read_termination)
            if readTerm == repr(''):
                self.enableTerm.set(FALSE)
                self.selectTermWidget.set('')
            elif readTerm == repr('\n'):
                self.enableTerm.set(TRUE)
                self.selectTermWidget.set(self.SELECT_TERM_VALUES[0])
            elif readTerm == repr('\r'):
                self.enableTerm.set(TRUE)
                self.selectTermWidget.set(self.SELECT_TERM_VALUES[1])
            if self.enableTerm.get():
                self.selectTermWidget.config(state='readonly')
            else:
                self.selectTermWidget.config(state='disabled')  
        except:
            pass
        
    def scpiApplyConfig(self, timeoutArg, chunkSizeArg):
        """Issues VISA commands to set config and applies changes made in the SCPI configuration frame to variables timeout and chunkSize (for resetConfigWidgets)

        Args:
            timeoutArg (string): Argument received from timeout widget which will be tested for type int and within range
            chunkSizeArg (string): Argument received from chunkSize widget which will be tested for type int and within range

        Raises:
            TypeError: ttk::spinbox get() does not return type int or integer out of range for respective variable

        Returns:
            Literal (int): 0 on success, 1 on error.
        """
        # Get the termination character from selectTermWidget
        termSelectIndex = self.selectTermWidget.current()
        if termSelectIndex == 0:
            termChar = '\n'
        elif termSelectIndex == 1:
            termChar = '\r'
        else:
            termChar = ''
        # Get timeout and chunk size values from respective widgets
        try:
            timeoutArg = int(timeoutArg)
            chunkSizeArg = int(chunkSizeArg)
        except:
            raise TypeError('ttk::spinbox get() did not return type int')
        # Test timeout and chunk size for within range
        if timeoutArg < TIMEOUT_MIN or timeoutArg > TIMEOUT_MAX:
            raise TypeError(f'int timeout out of range. Min: {TIMEOUT_MIN}, Max: {TIMEOUT_MAX}')
        if chunkSizeArg < CHUNK_SIZE_MIN or chunkSizeArg > CHUNK_SIZE_MAX:
            raise TypeError(f'int chunkSize out of range. Min: {CHUNK_SIZE_MIN}, Max: {CHUNK_SIZE_MAX}')
        # Call self.Vi.setConfig and if successful, print output and set variables for resetConfigWidgets
        if self.Vi.setConfig(timeoutArg, chunkSizeArg, self.sendEnd.get(), self.enableTerm.get(), termChar) == RETURN_SUCCESS:
            self.timeout = timeoutArg
            self.chunkSize = chunkSizeArg
            logging.info(f'Timeout: {self.Vi.openRsrc.timeout}, Chunk size: {self.Vi.openRsrc.chunk_size}, Send EOI: {self.Vi.openRsrc.send_end}, Termination: {repr(self.Vi.openRsrc.write_termination)}')
            return RETURN_SUCCESS
        else:
            return RETURN_ERROR

    def update_time(self):
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        self.clockLabel.config(text=current_time)
        root.after(1000, self.update_time)

class SpecAn(FrontEnd):
    """Generates tkinter-embedded matplotlib graph of spectrum analyzer.

    Args:
        Vi (class): Instance of VisaIO that contains methods for communicating with SCPI instruments.
        parentWidget (tk::LabelFrame, tk::Frame): Parent widget which will contain graph and control widgets.
    """
    def __init__(self, Vi, parentWidget):
        # FLAGS
        self.contSweepFlag = False
        self.singleSweepFlag = False
        # STATE VARIABLES
        self.loopState = state.IDLE
        # CONSTANTS
        self.RBW_FILTER_SHAPE_VALUES = ('Gaussian', 'Flattop')
        self.RBW_FILTER_SHAPE_VAL_ARGS = ('GAUS', 'FLAT')
        self.RBW_FILTER_TYPE_VALUES = ("-3 dB (Normal)", "-6 dB", "Impulse", "Noise")
        self.RBW_FILTER_TYPE_VAL_ARGS = ('DB3', 'DB6', 'IMP', 'NOISE')
        self.TRACE_TYPE_VALUES = ('Clear/Write', 'Trace Average', 'Max Hold', 'Min Hold')
        self.TRACE_TYPE_VAL_ARGS = ('WRIT', 'AVER', 'MAXH', 'MINH')
        self.AVG_TYPE_VALUES = ('Log-Power (Video)', 'Power (RMS)', 'Voltage')
        self.AVG_TYPE_VAL_ARGS = ('LOG', 'RMS', 'SCALAR')
        # TKINTER VARIABLES
        global tkSweepType, tkSpanType, tkRbwType, tkVbwType, tkBwRatioType, tkAttenType, tkAvgType
        tkSweepType = BooleanVar()
        tkSpanType = BooleanVar()
        tkRbwType = BooleanVar()
        tkVbwType = BooleanVar()
        tkBwRatioType = BooleanVar()
        tkAttenType = BooleanVar()
        tkAvgType = BooleanVar()
        # PLOT PARAMETERS
        self.color = '#1f77b4'
        self.marker = None
        self.linestyle = None
        self.linewidth = None
        self.markersize = None
        # VISA OBJECT
        self.Vi = Vi
        # PARENT
        spectrumFrame = parentWidget
        spectrumFrame.rowconfigure(0, weight=0)     # Prevent this row to resize
        spectrumFrame.rowconfigure(1, weight=1)     # Allow this row from resizing
        spectrumFrame.rowconfigure(2, weight=0)     # Prevent this row from resizing
        spectrumFrame.rowconfigure(3, weight=0)     # Prevent this row from resizing
        spectrumFrame.rowconfigure(4, weight=0)     # Prevent this row from resizing
        spectrumFrame.columnconfigure(0, weight=1)  # Allow this column to resize
        spectrumFrame.columnconfigure(1, weight=0)  # Prevent this column from resizing

        # MATPLOTLIB GRAPH
        self.fig = plt.figure(linewidth=0, edgecolor="#04253a")
        self.ax = self.fig.add_subplot()
        self.ax.set_title("Spectrum Plot")
        self.ax.set_xlabel("Frequency (Hz)")
        self.ax.set_ylabel("Power (dBm)")
        self.ax.autoscale(enable=False, tight=True)
        self.ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())
        self.ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
        self.ax.xaxis.set_major_formatter(ticker.EngFormatter(unit=''))
        self.spectrumDisplay = FigureCanvasTkAgg(self.fig, master=spectrumFrame)
        self.spectrumDisplay.get_tk_widget().grid(row = 0, column = 0, sticky=NSEW, rowspan=5)

        # MEASUREMENT TAB SELECTION
        s = ttk.Style()
        s.layout("Custom.TNotebook.Tab", [])   # clear the list containing notebook tab indexes
        tabText = ['Frequency', 'Bandwidth', 'Amplitude', 'Sweep', 'Trace']
        measurementTab = ttk.Notebook(spectrumFrame, style="Custom.TNotebook")
        self.tab1 = ttk.Frame(measurementTab)
        self.tab2 = ttk.Frame(measurementTab)
        self.tab3 = ttk.Frame(measurementTab)
        self.tab4 = ttk.Frame(measurementTab)
        self.tab5 = ttk.Frame(measurementTab)
        self.tab1.columnconfigure(0, weight=1)
        self.tab2.columnconfigure(0, weight=1)
        self.tab3.columnconfigure(0, weight=1)
        self.tab4.columnconfigure(0, weight=1)
        self.tab5.columnconfigure(0, weight=1)
        measurementTab.add(self.tab1, sticky=NSEW)
        measurementTab.add(self.tab2, sticky=NSEW)
        measurementTab.add(self.tab3, sticky=NSEW)
        measurementTab.add(self.tab4, sticky=NSEW)
        measurementTab.add(self.tab5, sticky=NSEW)
        measurementTab.grid(row=1, column=1, sticky=NSEW)
        tabSelect = ttk.Combobox(spectrumFrame, values=tabText, state='readonly')
        tabSelect.current(0)
        tabSelect.grid(row=0, column=1, sticky=NSEW)
        tabSelect.bind("<<ComboboxSelected>>", lambda event: measurementTab.select(tabSelect.current()))    # Bind combobox selection to notebook tab selection


        # MEASUREMENT TAB 1 (FREQUENCY)
        centerFreqFrame = ttk.LabelFrame(self.tab1, text="Center Frequency")
        centerFreqFrame.grid(row=0, column=0, sticky=NSEW)
        self.centerFreqEntry = ttk.Entry(centerFreqFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.centerFreqEntry.pack(expand=True, fill=BOTH)

        spanFrame = ttk.LabelFrame(self.tab1, text="Span")
        spanFrame.grid(row=1, column=0, sticky=NSEW)
        self.spanEntry = ttk.Entry(spanFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.spanEntry.pack(expand=True, fill=BOTH)
        self.spanSweptButton = ttk.Radiobutton(spanFrame, variable=tkSpanType, text = "Swept Span", value=1)
        self.spanSweptButton.pack(anchor=W, expand=True, fill=BOTH)
        self.spanZeroButton = ttk.Radiobutton(spanFrame, variable=tkSpanType, text = "Zero Span", value=0)
        self.spanZeroButton.pack(anchor=W, expand=True, fill=BOTH)
        self.spanFullButton = ttk.Button(spanFrame, text = "Full Span")
        self.spanFullButton.pack(anchor=S, expand=True, fill=BOTH)

        startFreqFrame = ttk.LabelFrame(self.tab1, text="Start Frequency")
        startFreqFrame.grid(row=2, column=0, sticky=NSEW)
        self.startFreqEntry = ttk.Entry(startFreqFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.startFreqEntry.pack(expand=True, fill=BOTH)

        stopFreqFrame = ttk.LabelFrame(self.tab1, text="Stop Frequency")
        stopFreqFrame.grid(row=3, column=0, sticky=NSEW)
        self.stopFreqEntry = ttk.Entry(stopFreqFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.stopFreqEntry.pack(expand=True, fill=BOTH)

        # MEASUREMENT TAB 2 (BANDWIDTH)
        rbwFrame = ttk.LabelFrame(self.tab2, text="Res BW")
        rbwFrame.grid(row=0, column=0, sticky=NSEW)
        self.rbwEntry = ttk.Entry(rbwFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.rbwEntry.pack(expand=True, fill=BOTH)
        self.rbwAutoButton = ttk.Radiobutton(rbwFrame, variable=tkRbwType, text="Auto", value=AUTO)
        self.rbwAutoButton.pack(anchor=W, expand=True, fill=BOTH)
        self.rbwManButton = ttk.Radiobutton(rbwFrame, variable=tkRbwType, text="Manual", value=MANUAL)
        self.rbwManButton.pack(anchor=W, expand=True, fill=BOTH)
        
        vbwFrame = ttk.LabelFrame(self.tab2, text="Video BW")
        vbwFrame.grid(row=1, column=0, sticky=NSEW)
        self.vbwEntry = ttk.Entry(vbwFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.vbwEntry.pack(expand=True, fill=BOTH)
        self.vbwAutoButton = ttk.Radiobutton(vbwFrame, variable=tkVbwType, text="Auto", value=AUTO)
        self.vbwAutoButton.pack(anchor=W, expand=True, fill=BOTH)
        self.vbwManButton = ttk.Radiobutton(vbwFrame, variable=tkVbwType, text="Manual", value=MANUAL)
        self.vbwManButton.pack(anchor=W, expand=True, fill=BOTH)

        bwRatioFrame = ttk.LabelFrame(self.tab2, text="VBW:RBW")
        bwRatioFrame.grid(row=2, column=0, sticky=NSEW)
        self.bwRatioEntry = ttk.Entry(bwRatioFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.bwRatioEntry.pack(expand=True, fill=BOTH)
        self.bwRatioAutoButton = ttk.Radiobutton(bwRatioFrame, variable=tkBwRatioType, text="Auto", value=AUTO)
        self.bwRatioAutoButton.pack(anchor=W, expand=True, fill=BOTH)
        self.bwRatioManButton = ttk.Radiobutton(bwRatioFrame, variable=tkBwRatioType, text="Manual", value=MANUAL)
        self.bwRatioManButton.pack(anchor=W, expand=True, fill=BOTH)

        rbwFilterShapeFrame = ttk.LabelFrame(self.tab2, text="RBW Filter Shape")
        rbwFilterShapeFrame.grid(row=3, column=0, sticky=NSEW)
        self.rbwFilterShapeCombo = ttk.Combobox(rbwFilterShapeFrame, values = self.RBW_FILTER_SHAPE_VALUES)
        self.rbwFilterShapeCombo.pack(anchor=W, expand=True, fill=BOTH)

        rbwFilterTypeFrame = ttk.LabelFrame(self.tab2, text="RBW Filter Type")
        rbwFilterTypeFrame.grid(row=4, column=0, sticky=NSEW)
        self.rbwFilterTypeCombo = ttk.Combobox(rbwFilterTypeFrame, values = self.RBW_FILTER_TYPE_VALUES)
        self.rbwFilterTypeCombo.pack(anchor=W, expand=True, fill=BOTH)

        # MEASUREMENT TAB 3 (AMPLITUDE)
        refLevelFrame = ttk.LabelFrame(self.tab3, text="Ref Level")
        refLevelFrame.grid(row=0, column=0, sticky=NSEW)
        self.refLevelEntry = ttk.Entry(refLevelFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.refLevelEntry.pack(expand=True, fill=BOTH)

        yScaleFrame = ttk.LabelFrame(self.tab3, text="Scale/Division")
        yScaleFrame.grid(row=1, column=0, sticky=NSEW)
        self.yScaleEntry = ttk.Entry(yScaleFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.yScaleEntry.pack(expand=True, fill=BOTH)

        numDivFrame = ttk.LabelFrame(self.tab3, text="Number of Divisions")
        numDivFrame.grid(row=2, column=0, sticky=NSEW)
        self.numDivEntry = ttk.Entry(numDivFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.numDivEntry.pack(expand=True, fill=BOTH)

        attenFrame = ttk.LabelFrame(self.tab3, text="Mech Atten")
        attenFrame.grid(row=3, column=0, sticky=NSEW)
        self.attenEntry = ttk.Entry(attenFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.attenEntry.pack(expand=True, fill=BOTH)
        self.attenAutoButton = ttk.Radiobutton(attenFrame, variable=tkAttenType, text="Auto", value=AUTO)
        self.attenAutoButton.pack(anchor=W, expand=True, fill=BOTH)
        self.attenManButton = ttk.Radiobutton(attenFrame, variable=tkAttenType, text="Manual", value=MANUAL)
        self.attenManButton.pack(anchor=W, expand=True, fill=BOTH)

        unitPowerFrame = ttk.LabelFrame(self.tab3, text="Unit (Power)")
        unitPowerFrame.grid(row=4, column=0, sticky=NSEW)
        self.unitPowerEntry = ttk.Entry(unitPowerFrame, state="disabled")
        self.unitPowerEntry.pack(expand=True, fill=BOTH)

        # MEASUREMENT TAB 4 (SWEEP)
        sweepPointsFrame = ttk.LabelFrame(self.tab4, text="Points")
        sweepPointsFrame.grid(row=0, column=0, sticky=NSEW)
        self.sweepPointsEntry = ttk.Entry(sweepPointsFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.sweepPointsEntry.pack(expand=True, fill=BOTH)

        sweepTimeFrame = ttk.LabelFrame(self.tab4, text="Sweep Time")
        sweepTimeFrame.grid(row=1, column=0, sticky=NSEW)
        self.sweepTimeEntry = ttk.Entry(sweepTimeFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.sweepTimeEntry.pack(expand=True, fill=BOTH)
        self.sweepAutoButton = ttk.Radiobutton(sweepTimeFrame, variable=tkSweepType, text="Auto", value=AUTO)
        self.sweepAutoButton.pack(anchor=W, expand=True, fill=BOTH)
        self.sweepManButton = ttk.Radiobutton(sweepTimeFrame, variable=tkSweepType, text="Manual", value=MANUAL)
        self.sweepManButton.pack(anchor=W, expand=True, fill=BOTH)

        # MEASUREMENT TAB 5 (TRACE)
        traceTypeFrame = ttk.LabelFrame(self.tab5, text='Trace Type')
        traceTypeFrame.grid(row=0, column=0, sticky=NSEW)
        self.traceTypeCombo = ttk.Combobox(traceTypeFrame, values=self.TRACE_TYPE_VALUES)
        self.traceTypeCombo.pack(anchor=W, expand=True, fill=BOTH)

        # # Possibly needs a firmware update? N9040B doesn't recognize :AVER:COUN:CURR? for some reason
        # currAvgCountFrame = ttk.LabelFrame(self.tab4, text='Current Avg/Hold') # current count is handled by the loop thread, not the typical setAnalyzerValue thread, also not a Parameter
        # currAvgCountFrame.grid(row=1, column=0, sticky=NSEW)
        # self.currAvgCountEntry = ttk.Entry(currAvgCountFrame, state="disabled")
        # self.currAvgCountEntry.pack(anchor=W, expand=True, fill=BOTH)

        avgCountFrame = ttk.LabelFrame(self.tab5, text='Average/Hold Count')
        avgCountFrame.grid(row=2, column=0, sticky=NSEW)
        self.avgCountEntry = ttk.Entry(avgCountFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.avgCountEntry.pack(anchor=W, expand=True, fill=BOTH)

        avgTypeFrame = ttk.LabelFrame(self.tab5, text='Average Type')
        avgTypeFrame.grid(row=3, column=0, sticky=NSEW)
        self.avgTypeCombo = ttk.Combobox(avgTypeFrame, values=self.AVG_TYPE_VALUES)
        self.avgTypeCombo.pack(anchor=W, expand=True, fill=BOTH)
        self.avgAutoButton = ttk.Radiobutton(avgTypeFrame, variable=tkAvgType, text="Auto", value=AUTO)
        self.avgAutoButton.pack(anchor=W, expand=True, fill=BOTH)
        self.avgManButton = ttk.Radiobutton(avgTypeFrame, variable=tkAvgType, text="Manual", value=MANUAL)
        self.avgManButton.pack(anchor=W, expand=True, fill=BOTH)

        # SWEEP BUTTONS
        s.configure('Icon.TButton', font=cfg['theme']['icon_font'], justify=tk.CENTER)
        initButton = ttk.Button(spectrumFrame, text="Initialize", command=self.initAnalyzer)
        initButton.grid(row=2, column=1, sticky=NSEW)
        sweepButtonFrame = tk.Frame(spectrumFrame)
        sweepButtonFrame.grid(row=3, column=1, sticky=NSEW)
        self.sweepButton = ttk.Button(sweepButtonFrame, text="Single/Cont", command=lambda:self.sweepButtonHandler(action='toggle'))
        self.sweepButton.pack(expand=True, fill=BOTH, side=LEFT)
        self.sweepIcon = ttk.Button(sweepButtonFrame, text = SINGLE_ICON, state=ENABLE, style='Icon.TButton', width=2)
        self.sweepIcon.pack(side=RIGHT)
        self.sweepIcon.bind('<Button>', 'break')
        restartButtonFrame = tk.Frame(spectrumFrame)
        restartButtonFrame.grid(row=4, column=1, sticky=NSEW)
        self.restartButton = ttk.Button(restartButtonFrame, text=f'Restart', command=lambda:self.sweepButtonHandler(action='restart'))
        self.restartButton.pack(expand=True, fill=BOTH, side=LEFT)
        self.restartIcon = ttk.Button(restartButtonFrame, text = RESTART_ICON, state=ENABLE, style='Icon.TButton', width=2)
        self.restartIcon.pack(side=RIGHT)
        self.restartIcon.bind('<Button>', 'break')

        self.bindWidgets() 

        # PARAMETERS
        CenterFreq.update(widget=self.centerFreqEntry)
        Span.update(widget=self.spanEntry)
        StartFreq.update(widget=self.startFreqEntry)
        StopFreq.update(widget=self.stopFreqEntry)
        SweepTime.update(widget=self.sweepTimeEntry)
        Rbw.update(widget=self.rbwEntry)
        Vbw.update(widget=self.vbwEntry)
        BwRatio.update(widget=self.bwRatioEntry)
        Ref.update(widget=self.refLevelEntry)
        NumDiv.update(widget=self.numDivEntry)
        YScale.update(widget=self.yScaleEntry)
        Atten.update(widget=self.attenEntry)
        SpanType.update(widget=tkSpanType)
        SweepType.update(widget=tkSweepType)
        RbwType.update(widget=tkRbwType)
        VbwType.update(widget=tkVbwType)
        BwRatioType.update(widget=tkBwRatioType)
        RbwFilterShape.update(widget=self.rbwFilterShapeCombo)
        RbwFilterType.update(widget=self.rbwFilterTypeCombo)
        AttenType.update(widget=tkAttenType)
        YAxisUnit.update(widget=self.unitPowerEntry)
        SweepPoints.update(widget=self.sweepPointsEntry)
        TraceType.update(widget=self.traceTypeCombo)
        AvgType.update(widget=self.avgTypeCombo)
        AvgAutoMan.update(widget=tkAvgType)
        AvgHoldCount.update(widget=self.avgCountEntry)

        # Generate thread to handle live data plot in background
        self.analyzerControlLoopThread = threading.Thread(target=self.analyzerControlLoop, daemon=TRUE)
        self.analyzerDisplayLoopthread = threading.Thread(target=self.analyzerDisplayLoop, daemon=TRUE)

        self.toggleInputs(DISABLE)

    def bindWidgets(self):
        """Binds tkinter events to the widgets' respective commands.
        """
        self.centerFreqEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, centerfreq = self.centerFreqEntry.get()))
        self.spanEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, span = self.spanEntry.get()))
        self.startFreqEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, startfreq = self.startFreqEntry.get()))
        self.stopFreqEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, stopfreq = self.stopFreqEntry.get()))
        self.sweepTimeEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, sweeptime = self.sweepTimeEntry.get()))
        self.rbwEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, rbw = self.rbwEntry.get()))
        self.vbwEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, vbw = self.vbwEntry.get()))
        self.bwRatioEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, bwratio = self.bwRatioEntry.get()))
        self.refLevelEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, ref = self.refLevelEntry.get()))
        self.yScaleEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, yscale = self.yScaleEntry.get()))
        self.numDivEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, numdiv = self.numDivEntry.get()))
        self.attenEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, atten = self.attenEntry.get()))
        self.sweepPointsEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, sweeppoints = self.sweepPointsEntry.get()))
        self.avgCountEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, avgcount = self.avgCountEntry.get()))

        self.sweepAutoButton.configure(command = lambda: self.setAnalyzerThreadHandler(sweeptype=AUTO))
        self.sweepManButton.configure(command = lambda: self.setAnalyzerThreadHandler(sweeptype=MANUAL))
        self.spanSweptButton.configure(command = lambda: self.setAnalyzerThreadHandler(spantype=10e9))
        self.spanZeroButton.configure(command = lambda: self.setAnalyzerThreadHandler(spantype=0))
        self.spanFullButton.bind("<Button-1>", lambda event: self.setAnalyzerThreadHandler(event, startfreq=0, stopfreq=50e9))
        self.rbwAutoButton.configure(command = lambda: self.setAnalyzerThreadHandler(rbwtype=AUTO))
        self.rbwManButton.configure(command = lambda: self.setAnalyzerThreadHandler(rbwtype=MANUAL))
        self.vbwAutoButton.configure(command = lambda: self.setAnalyzerThreadHandler(vbwtype=AUTO))
        self.vbwManButton.configure(command = lambda: self.setAnalyzerThreadHandler(vbwtype=MANUAL))
        self.bwRatioAutoButton.configure(command = lambda: self.setAnalyzerThreadHandler(bwratiotype=AUTO))
        self.bwRatioManButton.configure(command = lambda: self.setAnalyzerThreadHandler(bwratiotype=MANUAL))
        self.rbwFilterShapeCombo.bind("<<ComboboxSelected>>", lambda event: self.setAnalyzerThreadHandler(event, rbwfiltershape = self.rbwFilterShapeCombo.current()))
        self.rbwFilterTypeCombo.bind("<<ComboboxSelected>>", lambda event: self.setAnalyzerThreadHandler(event, rbwfiltertype = self.rbwFilterTypeCombo.current()))
        self.attenAutoButton.configure(command = lambda: self.setAnalyzerThreadHandler(attentype=AUTO))
        self.attenManButton.configure(command = lambda: self.setAnalyzerThreadHandler(attentype=MANUAL))
        self.traceTypeCombo.bind("<<ComboboxSelected>>", lambda event: self.setAnalyzerThreadHandler(event, tracetype = self.traceTypeCombo.current()))
        self.avgTypeCombo.bind("<<ComboboxSelected>>", lambda event: self.setAnalyzerThreadHandler(event, avgtype = self.avgTypeCombo.current()))
        self.avgAutoButton.configure(command = lambda: self.setAnalyzerThreadHandler(avgautoman=AUTO))
        self.avgManButton.configure(command = lambda: self.setAnalyzerThreadHandler(avgautoman=MANUAL))

    def toggleInputs(self, action):
        """Enables or disables the widgets in _frames and _widgets along with all of their children.

        Args:
            action (int): 0 or DISABLE to disable, 1 or ENABLE to enable.
        """
        _frames = (self.tab1, self.tab2, self.tab3, self.tab4, self.tab5)
        _widgets = (self.sweepButton, self.restartButton, self.sweepIcon, self.restartIcon)

        if action == ENABLE:
            for frame in _frames:
                enableChildren(frame)
            for widget in _widgets:
                widget.configure(state='enable')
        elif action == DISABLE:
            for frame in _frames:
                disableChildren(frame)
            for widget in _widgets:
                widget.configure(state='disable')

    def sweepButtonHandler(self, action):
        """Issues scpi commands for the Single/Continuous and Restart buttons with resource lock.

        Args:
            action (string): Can be 'toggle', or 'restart'
        """
        def do():
            with visaLock:
                isContinuous = bool(self.Vi.openRsrc.query_ascii_values("INIT:CONT?")[0])
                if action == 'toggle':
                    if isContinuous:
                        self.Vi.openRsrc.write("INIT:CONT 0")
                    else:
                        self.Vi.openRsrc.write("INIT:CONT 1")
                elif action == 'restart':
                    self.Vi.openRsrc.write("INIT:IMM")
                isContinuous = bool(self.Vi.openRsrc.query_ascii_values(":INIT:CONT?")[0])
                if isContinuous:
                    self.sweepIcon.configure(text=CONT_ICON)
                else:
                    self.sweepIcon.configure(text=SINGLE_ICON)
        thread = threading.Thread(target=do)
        thread.start()

    def setAnalyzerPlotLimits(self, **kwargs):
        """Sets self.ax limits to parameters passed in **kwargs if they exist. If not, gets relevant widget values to set limits.

        Args:
            xmin (float, optional): Minimum X value
            xmax (float, optional): Maximum X value
            ymin (float, optional): Minimum Y value
            ymax (float, optional): Maximum Y value
        """
        if 'xmin' in kwargs and 'xmax' in kwargs:
            self.ax.set_xlim(kwargs["xmin"], kwargs["xmax"])
        else:
            if tkSpanType.get() == 0:
                xmin = 0
                xmax = round(float(self.sweepTimeEntry.get()), 5)
                self.ax.set_xlabel("Time (s)")
            else:
                xmin = float(self.startFreqEntry.get())
                xmax = float(self.stopFreqEntry.get())
                self.ax.set_xlabel("Frequency (Hz)")
            self.ax.set_xlim(xmin, xmax)
        if 'ymin' in kwargs and 'ymax' in kwargs:
            self.ax.set_ylim(kwargs["ymin"], kwargs["ymax"])
        else:
            ymax = float(self.refLevelEntry.get())
            ymin = ymax - float(self.numDivEntry.get()) * float(self.yScaleEntry.get())
            self.ax.set_ylim(ymin, ymax)
        self.ax.margins(0, 0.05)
        self.ax.grid(visible=TRUE, which='major', axis='both', linestyle='-.')

    def setAnalyzerThreadHandler(self, *event, **kwargs):
        """Generates a thread that calls setAnalyzerValue to prevent race conditions.
        """
        _dict = {}
        for key in kwargs:
            _dict[key] = kwargs.get(key)
        thread = threading.Thread(target=self.setAnalyzerValue, kwargs=_dict)
        thread.start()

    def setAnalyzerValue(self, centerfreq=None, span=None, startfreq=None, stopfreq=None, sweeptime=None, rbw=None, vbw=None, bwratio=None, ref=None, numdiv=None, yscale=None, atten=None, spantype=None, sweeptype=None, rbwtype=None, vbwtype=None, bwratiotype=None, rbwfiltershape=None, rbwfiltertype=None, attentype=None, sweeppoints=None, tracetype=None, avgcount=None, avgtype=None, avgautoman=None):
        """Issues command to spectrum analyzer with the value of kwarg as the argument and queries for widget values. If the value is None or if there are no kwargs, query the spectrum analyzer to set widget values instead.
        
        Args:
            centerfreq (float, optional): Center frequency in hertz. Defaults to None.
            span (float, optional): Frequency span in hertz. Defaults to None.
            startfreq (float, optional): Start frequency in hertz. Defaults to None.
            stopfreq (float, optional): Stop frequency in hertz. Defaults to None.
            sweeptime (float, optional): Estimated sweep time in seconds. Defaults to None.
            rbw (float, optional): Resolution bandwidth. Defaults to None.
            vbw (float, optional): Video bandwidth. Defaults to None.
            bwratio (float, optional): RBW:VBW ratio. Defaults to None.
            ref (float, optional): Reference level in dBm. Defaults to None.
            numdiv (float, optional): Number of yscale divisions. Defaults to None. Converted to int by device.
            yscale (float, optional): Scale per division in dB. Defaults to None.
            atten (float, optional): Mechanical attenuation in dB. Defaults to None. Converted to int by device.
            spantype (bool, optional): 1 for swept span, 0 for zero span (time domain). Defaults to None.
            rbwtype (bool, optional): 1 for auto, 0 for manual. Defaults to None.
            vbwtype (bool, optional): 1 for auto, 0 for manual. Defaults to None.
            bwratiotype (bool, optional): 1 for auto, 0 for manual. Defaults to None.
            rbwfiltershape (int, optional): Index of the combobox widget tied to RBW_FILTER_SHAPE_VAL_ARGS. Defaults to None.
            rbwfiltertype (int, optional): Index of the combobox widget tied to RBW_FILTER_TYPE_VAL_ARGS. Defaults to None.
            attentype (bool, optional): 1 for auto, 0 for manual. Defaults to None.
            sweeppoints (float, optional): Number of points to sweep. Defaults to None. Converted to int by device.
            tracetype (int, optional): Index of the combobox widget tied to TRACE_TYPE_VAL_ARGS. Defaults to None.
            avgcount (float, optional): Average/max hold/min hold count. Defaults to None. Converted to int by device.
            avgtype (int, optional): Index of the combobox widget tied to AVG_TYPE_VAL_ARGS. Defaults to None.
            avgautoman (bool, optional): 1 for auto, 0 for manual. Defaults to None.
        """
        # TODO: Make sure all commands have full functionality
        global visaLock
        _list = Parameter.instances

        CenterFreq.update(arg=centerfreq)
        Span.update(arg=span)
        StartFreq.update(arg=startfreq)
        StopFreq.update(arg=stopfreq)
        SweepTime.update(arg=sweeptime)
        Rbw.update(arg=rbw)
        Vbw.update(arg=vbw)
        BwRatio.update(arg=bwratio)
        Ref.update(arg=ref)
        NumDiv.update(arg=numdiv)
        YScale.update(arg=yscale)
        Atten.update(arg=atten)
        SpanType.update(arg=spantype)
        SweepType.update(arg=sweeptype)
        RbwType.update(arg=rbwtype)
        VbwType.update(arg=vbwtype)
        BwRatioType.update(arg=bwratiotype)
        if rbwfiltershape is not None:
            RbwFilterShape.update(arg=self.RBW_FILTER_SHAPE_VAL_ARGS[rbwfiltershape])
        if rbwfiltertype is not None:
            RbwFilterType.update(arg=self.RBW_FILTER_TYPE_VAL_ARGS[rbwfiltertype])
        AttenType.update(arg=attentype)
        YAxisUnit.update(arg=None)
        SweepPoints.update(arg=sweeppoints)
        if tracetype is not None:
            TraceType.update(arg=self.TRACE_TYPE_VAL_ARGS[tracetype])
        AvgHoldCount.update(arg=avgcount)
        if avgtype is not None:
            AvgType.update(arg=self.AVG_TYPE_VAL_ARGS[avgtype])
        AvgAutoMan.update(arg=avgautoman)

        # Sort the list so dictionaries with 'arg': None are placed (and executed) after write commands
        for index in range(len(_list)):
            if _list[index].arg is not None:
                _list.insert(0, _list.pop(index))


        # EXECUTE COMMANDS
        logging.debug(f"setAnalyzerValue generated list of dictionaries '_list' with value {_list}")
        with visaLock:
            for parameter in _list:
                if parameter.command is None:
                    continue
                # Issue command with argument
                if parameter.arg is not None:
                    self.Vi.openRsrc.write(f'{parameter.command} {parameter.arg}')
                # Set widgets without issuing a parameter to command
                try:
                    buffer = self.Vi.openRsrc.query_ascii_values(f'{parameter.command}?') # Default converter is float
                except:
                    buffer = self.Vi.openRsrc.query_ascii_values(f'{parameter.command}?', converter='s')
                logging.verbose(f"Command {parameter.command}? returned {buffer}")
                parameter.update(value=buffer)
                clearAndSetWidget(parameter.widget, buffer)
        # Set plot limits
        with specPlotLock:
            self.setAnalyzerPlotLimits()
        return

    def initAnalyzer(self):
        def init():
            if self.Vi.isSessionOpen() == FALSE:
                logging.error(f"Session to the analyzer is not open. Set up connection with Options > Configure..., then reinitialize.")
                return
            try:
                visaLock.acquire()
                self.Vi.resetAnalyzerState()
                self.Vi.queryPowerUpErrors()
                self.Vi.testBufferSize()
                # Set widget values
                self.setAnalyzerValue()
                visaLock.release()
            except Exception as e:
                logging.error(f'{type(e).__name__}: {e}')
                try:
                    self.Vi.queryErrors()
                except Exception as e:
                    # logging.error(f'{type(e).__name__}: {e}. Could not query errors from device.')
                    pass
                visaLock.release()
            self.toggleInputs(ENABLE)
        thread = threading.Thread(target=init)
        thread.start()

    def analyzerControlLoop(self):
        # TODO deprecate but maybe keep some of the osr checker and visa session checker code
        """Main spectrum analyzer state machine. Initializes spectrum analyzer connection and issues sweeps commands to the device.
        """
        global visaLock, specPlotLock

        while TRUE:
            match self.loopState:
                case state.IDLE:
                    # Prevent this thread from taking up too much utilization
                    self.toggleInputs(DISABLE)
                    time.sleep(IDLE_DELAY)
                    continue

                case state.INIT:
                    # Maintain this loop to prevent fatal error if the connected device is not a spectrum analyzer.
                    if self.Vi.isSessionOpen() == FALSE:
                        logging.error(f"Session to the analyzer is not open. Set up connection with Options > Configure..., then reinitialize.")
                        self.loopState = state.IDLE
                        continue
                    try:
                        visaLock.acquire()
                        self.Vi.resetAnalyzerState()
                        self.Vi.queryPowerUpErrors()
                        self.Vi.testBufferSize()
                        # Set widget values
                        self.setAnalyzerValue()
                        visaLock.release()
                        self.loopState = state.LOOP
                    except Exception as e:
                        logging.error(f'{type(e).__name__}: {e}')
                        try:
                            self.Vi.queryErrors()
                        except Exception as e:
                            # logging.error(f'{type(e).__name__}: {e}. Could not query errors from device.')
                            pass
                        self.toggleInputs(ENABLE)
                        visaLock.release()
                        self.loopState = state.IDLE

                case state.LOOP:
                    # Main analyzer loop
                    # TODO: variable time.sleep based on analyzer sweep time
                    if self.Vi.isSessionOpen() == FALSE:
                        logging.info(f"Lost connection to the analyzer.")
                        self.loopState = state.IDLE
                        continue
                    self.toggleInputs(ENABLE)
                    if self.contSweepFlag or self.singleSweepFlag:
                        visaLock.acquire()
                        try: # Check if the instrument is busy calibrating, settling, sweeping, or measuring 
                            if self.Vi.getOperationRegister() & 0b00011011:
                                continue 
                        except Exception as e:
                            logging.fatal(f'{type(e).__name__}: {e}')
                            logging.fatal("Could not retrieve information from Operation Status Register.")
                            visaLock.release()
                            self.contSweepFlag = False
                            continue
                        try:
                            self.Vi.openRsrc.write(":INIT:SAN")
                        except Exception as e:
                            logging.fatal(f'{type(e).__name__}: {e}')
                            self.contSweepFlag = False
                        visaLock.release()
                        self.singleSweepFlag = False
                        time.sleep(ANALYZER_LOOP_DELAY)
                    else:
                        # Prevent this thread from taking up too much utilization
                        time.sleep(IDLE_DELAY)

    def analyzerDisplayLoop(self):
        """Spectrum analyzer display loop. Constantly fetches the spectrum analyzer xy values and plots it in the matplotlib canvas.
        """
        yAxisOld = []
        while TRUE:
            try:
                visaLock.acquire()
                # :FETCH:SAN? doesn't fetch if a sweep is in progress, this big ole mess is a workaround for that
                startFreq = float(self.Vi.openRsrc.query_ascii_values(":SENS:FREQ:START?")[0])
                stopFreq = float(self.Vi.openRsrc.query_ascii_values(":SENS:FREQ:STOP?")[0])
                sweepPoints = int(self.Vi.openRsrc.query_ascii_values(":SENS:SWEEP:POINTS?")[0])
                yAxis = self.Vi.openRsrc.query_ascii_values(":TRACE:DATA? TRACE1")
                # currAvgCount = self.Vi.openRsrc.query_ascii_values(":SENS:AVER:COUNT:CURR?")
                # clearAndSetWidget(self.currAvgCountEntry, currAvgCount)
                buffer = True
                visaLock.release()
            except Exception as e:
                visaLock.release()
                buffer = None
            if buffer:
                with specPlotLock:
                    try:
                        if 'lines' in locals():     # Remove previous plot if it exists
                            yAxisOld = self.ax.lines[0].get_data()[1].tolist()   # Save the currently plotted y data
                            lines.pop(0).remove()
                        stepSize = (stopFreq - startFreq) / (sweepPoints - 1)
                        xAxis = np.zeros(sweepPoints)
                        xAxis[0] = startFreq
                        for index in range(sweepPoints - 1):
                            xAxis[index + 1] = xAxis[index] + stepSize
                        lines = self.ax.plot(xAxis, yAxis, color=self.color, marker=self.marker, linestyle=self.linestyle, linewidth=self.linewidth, markersize=self.markersize)
                        self.ax.grid(visible=True)
                        self.spectrumDisplay.draw()
                    except Exception as e:
                        logging.fatal(f'{type(e).__name__}: {e}')
                        pass
                if 'yAxisOld' in locals():
                    if yAxis != yAxisOld:
                        TimeParameter.update(value=datetime.now(LOCAL_TIMEZONE).isoformat())
            time.sleep(ANALYZER_REFRESH_DELAY)

    def setPlotThreadHandler(self, color=None, marker=None, linestyle=None, linewidth=None, markersize=None):
        """Generates thread to issue setPlotParam.

        Args:
            color (string, optional): Argument passed to matplotlib.pyplot.plot. Defaults to None.
            marker (string, optional): Argument passed to matplotlib.pyplot.plot. Defaults to None.
            linestyle (string, optional): Argument passed to matplotlib.pyplot.plot. Defaults to None.
            linewidth (float, optional): Argument passed to matplotlib.pyplot.plot. Defaults to None.
            markersize (float, optional): Argument passed to matplotlib.pyplot.plot. Defaults to None.
        """
        thread = threading.Thread(target=self.setPlotParam, daemon=True, args=(color, marker, linestyle, linewidth, markersize))
        thread.start()

    def setPlotParam(self, color=None, marker=None, linestyle=None, linewidth=None, markersize=None):
        """Sets various matplotlib parameters with a threading lock to prevent race conditions. Should be called with setPlotThreadHandler to prevent blocking.

        Args:
            color (string, optional): Argument passed to matplotlib.pyplot.plot. Defaults to None.
            marker (string, optional): Argument passed to matplotlib.pyplot.plot. Defaults to None.
            linestyle (string, optional): Argument passed to matplotlib.pyplot.plot. Defaults to None.
            linewidth (float, optional): Argument passed to matplotlib.pyplot.plot. Defaults to None.
            markersize (float, optional): Argument passed to matplotlib.pyplot.plot. Defaults to None.
        """
        global specPlotLock

        if color is None:
            if self.color is not None:
                color = colorchooser.askcolor(initialcolor=self.color)[1]
            else:
                color = colorchooser.askcolor(initialcolor='#1f77b4')[1]
        with specPlotLock:
            self.color = color
            self.marker = marker
            self.linestyle = linestyle
            self.linewidth = linewidth
            self.markersize = markersize
            
class AziElePlot(FrontEnd):
    """Generates tkinter-embedded matplotlib graph of spectrum analyzer. Requires an instance of FrontEnd to be constructed with the name Front_End.

    Args:
        Motor (class): Instance of MotorIO that contains methods for communicating with the Parker Hannifin Motor Controller.
        parentWidget (tk::LabelFrame, tk::Frame): Parent widget which will contain graph and control widgets.
    """
    def __init__(self, Motor, parentWidget):
        # MOTOR INSTANCE
        self.Motor = Motor

        # PARENT
        self.parent = parentWidget
        self.parent.rowconfigure(0, weight=1)
        self.parent.columnconfigure(0, weight=1)

        # STATE VARIABLES
        self.loopState = state.IDLE
        self.axis0 = False              # Keeps track of drive x and y states so they can be accessed by the main thread to update status buttons in class FrontEnd
        self.axis1 = False

        # VARIABLES
        self.azArrow = None
        self.elArrow = None

        # STYLE
        font = 'Courier 14'
        padx = 2
        pady = 2

        # PLOT
        fig, (self.azAxis, self.elAxis) = plt.subplots(1, 2, subplot_kw=dict(projection='polar'))
        fig.set_size_inches(fig.get_size_inches()[0], fig.get_size_inches()[1] * 0.8)      # Sets to minimum height since two plots can appear large in the root window
        self.azAxis.set_title("Azimuth", va='bottom', y=1.1)
        self.elAxis.set_title("Elevation", va='bottom', y=1.1)
        self.azAxis.set_rticks([0.25, 0.5, 0.75], labels=[])
        self.elAxis.set_rticks([0.25, 0.5, 0.75], labels=[])
        self.azAxis.set_theta_zero_location('N')
        self.azAxis.set_theta_direction(-1)
        self.elAxis.set_thetagrids([0, 30, 60, 90, 120])
        self.azAxis.autoscale(enable=False, tight=True)
        self.elAxis.autoscale(enable=False, tight=True)
        self.azAxis.set_facecolor('#d5de9c')
        self.elAxis.set_facecolor('#d5de9c')
        self.elAxis.axvspan(0, -240/180.*np.pi, facecolor='0.85')
        self.azAxis.grid(color='#316931')
        self.elAxis.grid(color='#316931')

        self.bearingDisplay = FigureCanvasTkAgg(fig, master=self.parent)
        self.bearingDisplay.get_tk_widget().grid(row = 0, column = 0, sticky=NSEW, columnspan=2)


        # CONTROL FRAME
        self.ctrlFrame = ttk.Frame(self.parent)
        self.ctrlFrame.grid(row=2, column=0, sticky=NSEW, columnspan=1)
        for x in range(4):
            self.ctrlFrame.columnconfigure(x, weight=1)
        # FEEDBACK
        azFrame = ttk.Labelframe(self.ctrlFrame, text='Azimuth Angle')
        azFrame.grid(row=0, column=0, sticky=NSEW, padx=padx, pady=pady)
        azCmdFrame = ttk.Labelframe(self.ctrlFrame, text='Last Command')
        azCmdFrame.grid(row=0, column=1, sticky=NSEW, padx=padx, pady=pady)
        elFrame = ttk.Labelframe(self.ctrlFrame, text='Elevation Angle')
        elFrame.grid(row=0, column=2, sticky=NSEW, padx=padx, pady=pady)
        elCmdFrame = ttk.Labelframe(self.ctrlFrame, text='Last Command')
        elCmdFrame.grid(row=0, column=3, sticky=NSEW, padx=padx, pady=pady)
        self.azLabel = ttk.Label(azFrame, font=font, text=f'--')
        self.azLabel.grid(row=0, column=0, sticky=NSEW)
        self.elLabel = ttk.Label(elFrame, font=font, text=f'--')
        self.elLabel.grid(row=0, column=0, sticky=NSEW)
        self.azCmdLabel = ttk.Label(azCmdFrame, font=font, text=f'--')
        self.azCmdLabel.grid(row=0, column=0, sticky=NSEW)
        self.elCmdLabel = ttk.Label(elCmdFrame, font=font, text=f'--')
        self.elCmdLabel.grid(row=0, column=0, sticky=NSEW)
        # CONTROLS
        self.azEntryFrame = ttk.Frame(self.ctrlFrame)
        self.azEntryFrame.grid(row=1, column=0, columnspan=2, sticky=NSEW)
        self.azEntryFrame.columnconfigure(1, weight=1)
        self.elEntryFrame = ttk.Frame(self.ctrlFrame)
        self.elEntryFrame.grid(row=1, column=2, columnspan=2, sticky=NSEW)
        self.elEntryFrame.columnconfigure(1, weight=1)
        azArrows = tk.Label(self.azEntryFrame, text='>>>')
        azArrows.grid(row=0, column=0)
        azEntry = tk.Entry(self.azEntryFrame, font=font, background=azArrows.cget('background'), borderwidth=0, validate="key", validatecommand=(isNumWrapper, '%P'))
        azEntry.grid(row=0, column=1, sticky=NSEW)
        elArrows = tk.Label(self.elEntryFrame, text='>>>')
        elArrows.grid(row=0, column=0)
        elEntry = tk.Entry(self.elEntryFrame, font=font, background=elArrows.cget('background'), borderwidth=0, validate="key", validatecommand=(isNumWrapper, '%P'))
        elEntry.grid(row=0, column=1, sticky=NSEW)

        # BIND ENTRY WIDGETS
        azEntry.bind('<Return>', lambda event: self.threadHandler(self.sendMoveCommand, event, value=azEntry.get(), axis='az'))
        elEntry.bind('<Return>', lambda event: self.threadHandler(self.sendMoveCommand, event, value=elEntry.get(), axis='el'))

        # Arrow demonstration
        self.drawArrow(self.azAxis, 0)
        self.drawArrow(self.elAxis, 90)

        # Generate thread to handle live data plot in background
        motorLoop = threading.Thread(target=self.bearingDisplayLoop, daemon=True)
        motorLoop.start()

    def drawArrow(self, axis, angle):
        """Draws arrow on the matplotlib axis from the origin at the angle specified. Intended for polar plots only.

        Args:
            axis (plt.subplots): Matplotlib axis
            angle (float): Angle in degrees
        """
        # Remove previous plot if it exists, then draw new arrow
        match axis:
            case self.azAxis:
                try:
                    self.azArrow.remove()
                except AttributeError:
                    pass
                self.azArrow = axis.arrow(angle/180.*np.pi, 0, 0, 0.8, alpha = 1, width = 0.03, edgecolor = 'blue', facecolor = 'blue', lw = 3, zorder = 5)
            case self.elAxis:
                try:
                    self.elArrow.remove()
                except AttributeError:
                    pass
                self.elArrow = axis.arrow(angle/180.*np.pi, 0, 0, 0.8, alpha = 1, width = 0.03, edgecolor = 'blue', facecolor = 'blue', lw = 3, zorder = 5)

        self.bearingDisplay.draw()

    def threadHandler(self, target, *event, **kwargs):
        """Generates a new thread to handle IO routines without blocking main thread. For most operations, this should be used instead of calling target methods directly.

        Args:
            event (event): tkinter event which initiates function call
            target (method): Callable object to be invoked by the run() method.
            kwargs (dict, optional): Dictionary of keyword arguments for target invocation. Defaults to {}.
        """
        if not hasattr(AziElePlot, target.__name__):
            logging.error(f'Class AziElePlot does not contain a method with identifier {target.__name__}')
            return
        thread = threading.Thread(target = target, kwargs = kwargs, daemon=True)
        thread.start()
    
    def sendMoveCommand(self, value=None, axis=None):
        """_summary_

        Args:
            value (float, optional): Value in degrees to send as argument to object of MotorIO. Defaults to None.
            axis (string, optional): Either 'az' or 'el' to determine which axis to move. Defaults to None.
        """
        value = float(value)

        if axis == 'az' and value is not None:
            with motorLock:
                self.Motor.write(f'jog inc x {value}')
                time.sleep(0.1)
                self.Motor.flushInput()
            self.azCmdLabel.configure(text = f'{value}{u'\N{DEGREE SIGN}'}')

        elif axis == 'el' and value is not None:
            with motorLock:
                self.Motor.write(f'jog inc y {value}')
                time.sleep(0.1)
                self.Motor.flushInput()
            self.elCmdLabel.configure(text = f'{value}{u'\N{DEGREE SIGN}'}')

        # Disable inputs. If done correctly, the loop thread should enable inputs when bit 516 is 0
        # self.toggleInputs(DISABLE)

    def halt(self):
        """Issues 'JOG OFF X Y' to Motor.
        """
        try:
            with motorLock:
                self.Motor.write('JOG OFF X Y')
                time.sleep(0.1)
                self.Motor.flushInput()
        except Exception as e:
            logging.error(f'{type(e).__name__}: {e}')

    def toggleInputs(self, action):
        """Enables or disables the widgets in _frames and _widgets along with all of their children.

        Args:
            action (int): 0 or DISABLE to disable, 1 or ENABLE to enable.
        """
        _frames = (self.azEntryFrame, self.elEntryFrame)
        _widgets = ()

        if action == ENABLE:
            for frame in _frames:
                enableChildren(frame)
            for widget in _widgets:
                widget.configure(state='normal')
        elif action == DISABLE:
            for frame in _frames:
                disableChildren(frame)
            for widget in _widgets:
                widget.configure(state='disable')

    def setState(self, val):
        """Sets self.loopState to val.

        Args:
            val (int): Should be a constant in class State (state.IDLE, state.INIT, state.LOOP).
        """
        self.loopState = val

    def bearingDisplayLoop(self):
        """Main motor bearing state machine. Initializes motor, drives, prog, etc. and plots direction in the matplotlib canvas.
        """
        while TRUE:
            match self.loopState:
                case state.IDLE:
                    # Prevent this thread from taking up too much utilization
                    self.toggleInputs(DISABLE)
                    time.sleep(IDLE_DELAY)
                    continue
            
                case state.CLEANUP:
                    try:
                        motorLock.acquire()
                        self.Motor.write('DRIVE OFF X Y')
                        self.queryDriveStates()
                    except Exception as e:
                        motorLock.release()
                        logging.error(f'{type(e).__name__}: {e}')
                    self.loopState = state.IDLE

                case state.INIT:
                    self.toggleInputs(DISABLE)
                    try:
                        motorLock.acquire()
                        self.Motor.write('\n')
                        # Check program state and maybe output somewhere or automatically set to prog0
                        prog = self.Motor.query('Prog 0')
                        if 'P00' not in prog:
                            raise NotImplementedError(f'Unexpected response from motor controller: {prog}')
                        
                        self.Motor.write('DRIVE ON X Y')
                        self.queryDriveStates()
                        if self.axis0 == False or self.axis1 == False:
                            raise NotImplementedError('One or more drives did not respond to enable command.')

                        self.loopState = state.LOOP
                    except Exception as e:
                        logging.error(f'{type(e).__name__}: {e}')
                        # Check drive states and output to the buttons on the left hand panel. Enable buttons to allow user to toggle drives
                        self.loopState = state.IDLE
                    finally:
                        motorLock.release()

                case state.LOOP:
                    try:
                        motorLock.acquire()
                        # Check bit 516 (In motion) to determine whether or not to allow inputs
                        # TODO: Find out why bit 516 returns 0 even when moving
                        # response = self.Motor.query('PRINT P516').splitlines()
                        # for i in response:
                        #     match i:
                        #         case '0':
                        #             self.toggleInputs(ENABLE)
                        #         case '1':
                        #             self.toggleInputs(DISABLE)
                        # query P6144 (x) and P6160 (y) for encoder position
                        response = self.Motor.query('PRINT P6144').splitlines()
                        for i in response:
                            if 'P00' in i or 'PRINT' in i:
                                response.remove(i)
                        if len(response) > 1:
                            raise ValueError(f'Encoder query expected 1 line and returned {len(response)}: {response}')
                        xEnc = int(response[0])

                        response = self.Motor.query('PRINT P6160').splitlines()
                        for i in response:
                            if 'P00' in i or 'PRINT' in i:
                                response.remove(i)
                        if len(response) > 1:
                            raise ValueError(f'Encoder query expected 1 line and returned {len(response)}: {response}')
                        yEnc = int(response[0])

                        # Calculate position in degrees
                        xPos = round((xEnc - X_HOME) / X_CPD, 4)
                        yPos = round((yEnc - Y_HOME) / Y_CPD, 4)
                        # Draw arrows on respective axes
                        self.drawArrow(self.azAxis, xPos)
                        self.drawArrow(self.elAxis, yPos)
                        # Set readout widgets
                        self.azLabel.configure(text = f'{xPos}{u'\N{DEGREE SIGN}'}')
                        self.elLabel.configure(text = f'{yPos}{u'\N{DEGREE SIGN}'}')
                        # TODO: Check if motors are moving and enable/disable inputs
                    except Exception as e:
                        logging.error(f'{type(e).__name__}: {e}')
                        self.loopState = state.IDLE
                    finally:
                        motorLock.release()
                        time.sleep(MOTOR_LOOP_DELAY)

    def queryDriveStates(self):
        """Query drives x and y from the motor controller. Sets self.axis0 and self.axis1 to True or False if the drive is enabled or disabled, respectively.

        Raises:
            NotImplementedError: If the motor controller does not return DRIVE ON or DRIVE OFF
        """
        with motorLock:
            # Check if drive responded correctly here and set status buttons.
            drive = self.Motor.query('DRIVE X')
            if 'ON' in drive:
                self.axis0 = True   # set attribute for statusMonitor
            elif 'OFF' in drive:
                self.axis0 = False
            else:
                raise NotImplementedError(f'Unexpected response from AXIS0: {drive}')
            drive = self.Motor.query('DRIVE Y')
            if 'ON' in drive:
                self.axis1 = True   # set attribute for statusMonitor
            elif 'OFF' in drive:
                self.axis0 = False
            else:
                raise NotImplementedError(f'Unexpected response from AXIS1: {drive}')

# Thread target to monitor IO connection status
def statusMonitor(FrontEnd, Vi, Motor, PLC, Azi_Ele):
    """Thread target to monitor IO connection statuses and reflect their state in FrontEnd buttons.
    """
    global autoState
    while True:
        # VISA
        try:
            Vi.openRsrc.session
            FrontEnd.setStatus(FrontEnd.visaStatus, text='Connected')
        except:
            FrontEnd.setStatus(FrontEnd.visaStatus, text='NC')

        # MOTOR
        if Motor.ser.is_open:
            FrontEnd.setStatus(FrontEnd.motorStatus, text='Connected')
        else: 
            FrontEnd.setStatus(FrontEnd.motorStatus, text='NC')
        match Azi_Ele.loopState:
            case state.IDLE:
                for button in FrontEnd.MODE_BUTTONS_LIST:
                    if button is FrontEnd.standbyButton:
                        background=FrontEnd.SELECT_BACKGROUND
                    else:
                        background=FrontEnd.DEFAULT_BACKGROUND
                    FrontEnd.setStatus(button, background=background)
            case state.INIT:
                for button in FrontEnd.MODE_BUTTONS_LIST:
                    FrontEnd.setStatus(button, background=FrontEnd.DEFAULT_BACKGROUND)
            case state.LOOP:
                for button in FrontEnd.MODE_BUTTONS_LIST:
                    if button is FrontEnd.manualButton:
                        background=FrontEnd.SELECT_BACKGROUND
                    else:
                        background=FrontEnd.DEFAULT_BACKGROUND
                    FrontEnd.setStatus(button, background=background)
        match Azi_Ele.axis0:
            case True:
                FrontEnd.setStatus(FrontEnd.azStatus, text='ENABLED')
            case False:
                FrontEnd.setStatus(FrontEnd.azStatus, text='STOPPED')
        match Azi_Ele.axis1:
            case True:
                FrontEnd.setStatus(FrontEnd.elStatus, text='ENABLED')
            case False:
                FrontEnd.setStatus(FrontEnd.elStatus, text='STOPPED')

        # PLC
        if PLC.serial.is_open:
            FrontEnd.setStatus(FrontEnd.plcStatus, text='Connected')
        else: 
            FrontEnd.setStatus(FrontEnd.plcStatus, text='NC')
        match PLC.status:
            case opcodes.SLEEP.value:
                for button in FrontEnd.PLC_OUTPUTS_LIST:
                    if button is FrontEnd.sleepP1Button:
                        background=FrontEnd.SELECT_BACKGROUND
                    else:
                        background=FrontEnd.DEFAULT_BACKGROUND
                    FrontEnd.setStatus(button, background=background)
                FrontEnd.chainSelect = 'SLEEP'
            case opcodes.P1_INIT.value:
                FrontEnd.setStatus(FrontEnd.initP1Button, background=FrontEnd.SELECT_BACKGROUND)
            case opcodes.P1_DISABLE.value:
                for button in FrontEnd.PLC_OUTPUTS_LIST:
                    FrontEnd.setStatus(button, background=FrontEnd.DEFAULT_BACKGROUND)
                FrontEnd.setStatus(FrontEnd.initP1Button, background=FrontEnd.DEFAULT_BACKGROUND)
                FrontEnd.chainSelect = 'SLEEP'
            case opcodes.DFS_CHAIN1.value:
                for button in FrontEnd.PLC_OUTPUTS_LIST:
                    if button is FrontEnd.dfs1Button:
                        background=FrontEnd.SELECT_BACKGROUND
                    else:
                        background=FrontEnd.DEFAULT_BACKGROUND
                    FrontEnd.setStatus(button, background=background)
                FrontEnd.chainSelect = 'DFS1'
            case opcodes.EMS_CHAIN1.value:
                for button in FrontEnd.PLC_OUTPUTS_LIST:
                    if button is FrontEnd.ems1Button:
                        background=FrontEnd.SELECT_BACKGROUND
                    else:
                        background=FrontEnd.DEFAULT_BACKGROUND
                    FrontEnd.setStatus(button, background=background)
                FrontEnd.chainSelect = 'EMS1'
                
        match automation.state:
            case state.IDLE:
                FrontEnd.setStatus(FrontEnd.autoStartStopButton, background=FrontEnd.DEFAULT_BACKGROUND)
            case state.AUTO:
                FrontEnd.setStatus(FrontEnd.autoStartStopButton, background=FrontEnd.SELECT_BACKGROUND)
                
        time.sleep(STATUS_MONITOR_DELAY)

# Root tkinter interface (contains Front_End and standard output console)
root = ThemedTk(theme=cfg['theme']['ttk'])
root.title('New Mexico Spectrum Monitor Control')
root.option_add('*TButton*takeFocus', 0)
root.option_add('*TCombobox*takeFocus', 0)
isNumWrapper = root.register(isNumber)

# Change combobox highlight colors to match entry
dummy = ttk.Entry()
s = ttk.Style()
s.configure("TCombobox",
            selectbackground=dummy.cget('background'),
            selectforeground=dummy.cget('foreground'),
            activebackground=dummy.cget('background'))
dummy.destroy()

# Generate textbox to print standard output/error
stdioFrame = ttk.Frame(root)
stdioFrame.grid(row=1, column=1, sticky=NSEW, padx=ROOT_PADX, pady=ROOT_PADY)
stdioFrame.rowconfigure(0, weight=1)
font=cfg['theme']['terminal_font']
for x in range(5):
    stdioFrame.columnconfigure(x, weight=0)
stdioFrame.columnconfigure(1, weight=1)
consoleFrame = ttk.Frame(stdioFrame)    # So the scrollbar isn't stretched to the width of the rightmost widget in stdioFrame
consoleFrame.grid(column=0, row=0, sticky=NSEW, columnspan=5)
consoleFrame.rowconfigure(0, weight=1)
consoleFrame.columnconfigure(0, weight=1)
console = tk.Text(consoleFrame, height=15)
console.grid(column=0, row=0, sticky=(N, S, E, W))
console.config(state=DISABLED)
# Scrollbar
consoleScroll = ttk.Scrollbar(consoleFrame, orient=VERTICAL, command=console.yview)
console.configure(yscrollcommand=consoleScroll.set)
consoleScroll.grid(row=0, column=1, sticky=NSEW)
# Terminal input
debugLabel = tk.Label(stdioFrame, text='>>>', font=(font))
debugLabel.grid(row=1, column=0, sticky=NSEW)
consoleInput = tk.Entry(stdioFrame, font=(font), borderwidth=0, background=debugLabel.cget('background'))
consoleInput.grid(row=1, column=1, sticky=NSEW)
console.bind('<Button-1>', lambda event: focusHandler(event, consoleInput))
consoleInput.bind('<Return>', lambda event: executeHandler(event, consoleInput.get()))
consoleInput.bind('<Key-Up>', lambda event: commandListHandler(event, direction='up'))
consoleInput.bind('<Key-Down>', lambda event: commandListHandler(event, direction='down'))
# Terminal config
printBool = BooleanVar()
execBool = BooleanVar()
printCheckbutton = tk.Checkbutton(stdioFrame, font=(font), text='Print Return Value', variable=printBool)
printCheckbutton.grid(row=1, column=2)
evalCheckbutton = tk.Checkbutton(stdioFrame, font=(font), text='Evaluate', variable=execBool, onvalue=False, offvalue=True)
evalCheckbutton.grid(row=1, column=3)
execCheckbutton = tk.Checkbutton(stdioFrame, font=(font), text='Execute', variable=execBool)
execCheckbutton.grid(row=1, column=4)

# Helper functions
commandList = []
commandIndex = -1

def focusHandler(event, widget):
    """Used to initiate focus on a widget on a tkinter event. Used to focus the terminal entry when textbox is clicked.

    Args:
        event (event): tkinter event which initiates function call
        widget (tk:widget): Widget to focus on
    """
    widget.focus()
    return('break')     # Prevents class binding from firing (executing the normal event callback)

def commandListHandler(event, direction):
    """Handler function that iterates through previously used terminal commands when the user presses up or down arrow keys.

    Args:
        event (event): tkinter event which initiates function call
        direction (string): 'up' or 'down' (what button did the user press)
    """
    global commandIndex

    consoleInput.delete(0, END)
    if direction == 'up' and commandIndex < len(commandList) - 1:
        commandIndex += 1
    elif direction== 'down' and commandIndex > 0:
        commandIndex -= 1
    consoleInput.insert(0, commandList[commandIndex])    

def executeHandler(event, arg):
    """Handler function that determines whether or not to evaluate/execute a terminal command based on execBool.

    Args:
        event (event): tkinter event which initiates function call
        arg (string): Command to execute/evaluate
    """
    global commandIndex, commandList

    commandIndex = -1               # Reset index so up/down arrows start at the last issued command
    consoleInput.delete(0, END)     # Clear the entry widget
    commandList.insert(0, arg)      # Save the issued command in list at index 0
    logging.terminal(f'>>> {arg}')
    try:
        if execBool.get():
            exec(arg, globals())
        else:
            if printBool.get():
                logging.terminal(f'{eval(arg)}')
            else:
                eval(arg, globals())
    except Exception as e:
        logging.terminal(f'{type(e).__name__}: {e}')

def redirector(inputStr):           # Redirect print/logging statements to the console textbox
    """Redirects print/logging statements to the console textbox and automatically scrolls down.

    Args:
        inputStr (string): String to print/log from sys.stdout.write and sys.stderr.write
    """
    console.config(state=NORMAL)
    console.insert(END, inputStr)
    console.yview(MOVETO, 1)
    console.config(state=DISABLED)

def checkbuttonStateHandler():
    """Handler function that disables the 'Print Return Value' checkbutton when execBool is true.
    """
    if execBool.get():
        printCheckbutton.configure(state=DISABLED)
    else:
        printCheckbutton.configure(state=NORMAL)

def openSaveDialog(type):
    """Function called when the user presses 'Save trace', 'Save image', or 'Save log'.

    Args:
        type (string): Either 'trace', 'log', or 'image'. Determines what file to save.
    """
    if type == 'trace':
        file = filedialog.asksaveasfile(initialdir = os.getcwd(), filetypes=(('Comma separated variables', '*.csv'), ('Text File (Tab delimited)', '*.txt'), ('All Files', '*.*')), defaultextension='.csv')
        if file is not None:
            thread = threading.Thread(saveTrace, args=(file,))
            thread.start()
    elif type == 'log':
        file = filedialog.asksaveasfile(initialdir = os.getcwd(), filetypes=(('Text Files', '*.txt'), ('All Files', '*.*')), defaultextension='.txt')
        if file is not None:
            file.write(console.get('1.0', END))
            file.close()
    elif type == 'image':
        filename = filedialog.asksaveasfilename(initialdir = os.getcwd(), filetypes=(('JPEG', '*.jpg'), ('PNG', '*.png')), defaultextension='.jpg')
        if filename != '':
            Spec_An.fig.savefig(filename)

def saveTrace(f=None, filePath=None, xdata=None, ydata=None):
    """Saves trace as csv to the file object passed in f or the filePath string. If filePath points to an existing file, an iterating integer is appended to the file name until an unused name is found. This function is blocking and should only be called outside of the main thread.

    Args:
        f (file, optional): File object to save to. Defaults to None.
        filePath (string, optional): File path to save to if f is None. Defaults to None.
        xdata (list, optional): List of x data points to save. If None, get x data points from plot. Defaults to None.
        ydata (list, optional): List of y data points to save. If None, get y data points from plot. Defaults to None.

    Raises:
        AttributeError: If both f and filePath is None
    """
    if f is None:
        if filePath is None:
            raise AttributeError('saveTrace did not receive any arguments.')
        x=0
        fileExists = True
        fileJoined = ''
        while fileExists:
            fileName = Front_End.chainSelect + '-' + datetime.now().strftime('%Y-%m-%d') + '-' + str(x) +'.csv'
            fileJoined = os.path.join(filePath, fileName)
            fileExists = os.path.exists(fileJoined)
            x += 1
        f = open(fileJoined, 'w')

    try:
        buffer = ''
        if xdata is None and ydata is None:
            with specPlotLock:
                data = Spec_An.ax.lines[0].get_data()
                xdata = data[0]
                ydata = data[1]
        if '.txt' in f.name:
            delimiter = '\t'
        else:
            delimiter = ','

        for parameter in Parameter.instances:
            if parameter.log == False:
                continue
            if isinstance(parameter.value, (list,)):
                try:
                    value = parameter.value[0].strip("[]{}()#* \n\t")
                except:
                    value = str(parameter.value).strip("[]{}()#* \n\t")
            else:
                value = str(parameter.value).strip("[]{}()#* \n\t")

            buffer = buffer + parameter.name + delimiter + value + '\n'

        buffer = buffer + 'DATA\n'
        for index in range(len(xdata)):
            buffer = buffer + str(xdata[index]) + delimiter + str(ydata[index]) + '\n'
        f.write(buffer)
        f.close()
    except Exception as e:
        logging.error(f'{type(e).__name__}: {e}')
        f.close()

def generateConfigDialog():
    """Opens confirmation message if the user wants to generate a new config file.
    """
    if messagebox.askokcancel(
        message="Would you like to generate the default configuration file loaded with this software version? This will overwrite any preexisting config.toml if present.",
        icon='question',
        title="Are you sure?"
        ):
        defaultconfig.generateConfig()

def initSchedule():
    pass

def onSchedule():
    pass

def generateAutoDialog():
    """Opens a dialog that allows the user to modify the automation queue and file path.
    """
    _listVar = StringVar(value=automation.queue)

    if automation.state != state.IDLE:
        logging.info('Cannot edit queue while task scheduler is active.')
        return

    def _addDateTime():
        _startDate = startDatePicker.get_date()
        _endDate = endDatePicker.get_date()

        _startTimePicker = startTimePicker.time()
        _startTimeString = f'{_startTimePicker[0]}:{_startTimePicker[1]} {_startTimePicker[2]}'
        _startTime = datetime.strptime(_startTimeString, '%I:%M %p').time()
        _startDateTime = datetime.combine(_startDate, _startTime)

        _endTimePicker = endTimePicker.time()
        _endTimeString = f'{_endTimePicker[0]}:{_endTimePicker[1]} {_endTimePicker[2]}'
        _endTime = datetime.strptime(_endTimeString, '%I:%M %p').time()
        _endDateTime = datetime.combine(_endDate, _endTime)

        _intervalPicker = list(intervalPicker.time())
        if _intervalPicker[0] == 0 and _intervalPicker[1] == 0: # workaround for tktimepicker not allowing 24 hours and 0 minutes
            _intervalPicker[0] = 24
        _intervalDelta = timedelta(hours=_intervalPicker[0], minutes=_intervalPicker[1])

        _indexDateTime = _startDateTime + _intervalDelta
        while _indexDateTime <= _endDateTime:
            automation.queue.append(_indexDateTime)
            automation.queue.sort()
            _indexDateTime = _indexDateTime + _intervalDelta
        _listVar.set(automation.queue)

        for i in range(0,len(automation.queue),2):
            queueListbox.itemconfigure(i, background='#f0f0ff')
    
    def _removeDateTime():
        automation.queue.clear()
        _listVar.set(automation.queue)

    def _presetButtonHandler(string):
        saveButton.configure(state=NORMAL)
        clearAndSetWidget(textBox, string)

    def _lastSavedButtonHandler():
        clearAndSetWidget(textBox, automation.textBoxString)
        saveButton.configure(state=DISABLED)

    def _saveButtonStateHandler(event):
        saveButton.configure(state=NORMAL)
    
    def _saveAutomationFunctions(string):
        automation.textBoxString = string
        exec(string, globals())
        saveButton.configure(state=DISABLED)

    def _onTab(event:tk.Event) -> str:
        textBox.insert("insert", " "*4)
        return "break"
    
    def _pickFilePath(entry):
        dir = filedialog.askdirectory()
        if dir is None:
            return
        automation.filePath = dir
        clearAndSetWidget(entry, dir)

    # Toplevel and notebook
    _parent = Toplevel()
    _parent.title('Auto-Sweep Configuration')
    _parent.resizable(False, False)
    _notebook = ttk.Notebook(_parent)
    _notebook.grid(row=0, column=0, sticky=NSEW)
    _frame1 = ttk.Frame(_notebook)
    _frame1.rowconfigure(0, weight=1)
    _frame1.columnconfigure(1, weight=1)
    _frame2 = ttk.Frame(_notebook)
    _notebook.add(_frame1, text='Config', sticky=NSEW)
    _notebook.add(_frame2, text='Scripting')
    _time = datetime.now()
    _period = constants.AM
    if _time.hour > 12:
        _time.replace(hour=_time.hour - 12)
        _period = constants.PM
    # Tab 1 (Config)
    configWidgetsFrame = ttk.Frame(_frame1, width=30)
    configWidgetsFrame.grid(row=0, column=0, padx=ROOT_PADX, pady=ROOT_PADY, sticky=NSEW)
    pathFrame = ttk.Frame(configWidgetsFrame)
    pathFrame.grid(row=0, column=0, padx=ROOT_PADX, columnspan=2, sticky=NSEW)
    pathFrame.columnconfigure(0, weight=0)
    pathFrame.columnconfigure(1, weight=1)
    pathLabel = ttk.Label(pathFrame, text='File Path')
    pathLabel.grid(row=0, column=0, padx=ROOT_PADX, pady=ROOT_PADY, sticky=W)
    pathEntry = ttk.Entry(pathFrame, width=50, state='disabled')
    pathEntry.grid(row=1, column=0, columnspan=2, padx=ROOT_PADX, pady=ROOT_PADY, sticky=NSEW)
    clearAndSetWidget(pathEntry, automation.filePath)
    pathPicker = ttk.Button(pathFrame, text='Browse...', command = lambda: _pickFilePath(pathEntry))
    pathPicker.grid(row=0, column=1, padx=ROOT_PADX, pady=ROOT_PADY, sticky=E)
    sep1 = ttk.Separator(configWidgetsFrame, orient=HORIZONTAL)
    sep1.grid(row=1, column=0, columnspan=2, sticky=NSEW, padx=ROOT_PADX, pady=ROOT_PADY)
    startDateFrame = ttk.Frame(configWidgetsFrame)
    startDateFrame.grid(row=2, column=0, columnspan=2, sticky=NSEW, padx=ROOT_PADX)
    startDateFrame.columnconfigure(0, weight=0)
    startDateFrame.columnconfigure(1, weight=1)
    startLabel = ttk.Label(startDateFrame, text='Start Date & Time')
    startLabel.grid(row=0, column=0, padx=ROOT_PADX, pady=ROOT_PADY, sticky=W)
    startDatePicker = DateEntry(startDateFrame)
    startDatePicker.grid(row=0, column=1, padx=ROOT_PADX, pady=ROOT_PADY, sticky=NSEW)
    startTimePicker = SpinTimePickerModern(startDateFrame, period=_period)
    startTimePicker.grid(row=1, column=0, padx=ROOT_PADX, pady=ROOT_PADY, sticky=NSEW, columnspan=2)
    startTimePicker.addAll(constants.HOURS12)
    startTimePicker.set12Hrs(_time.hour)
    startTimePicker.setMins(_time.minute)
    sep2 = ttk.Separator(configWidgetsFrame, orient=HORIZONTAL)
    sep2.grid(row=3, column=0, columnspan=2, sticky=NSEW, padx=ROOT_PADX, pady=ROOT_PADY)
    endDateFrame = ttk.Frame(configWidgetsFrame)
    endDateFrame.grid(row=4, column=0, columnspan=2, sticky=NSEW, padx=ROOT_PADX)
    endDateFrame.columnconfigure(0, weight=0)
    endDateFrame.columnconfigure(1, weight=1)
    endLabel = ttk.Label(endDateFrame, text='End Date & Time')
    endLabel.grid(row=0, column=0, padx=ROOT_PADX, pady=ROOT_PADY, sticky=W)
    endDatePicker = DateEntry(endDateFrame)
    endDatePicker.grid(row=0, column=1, padx=ROOT_PADX, pady=ROOT_PADY, sticky=NSEW)
    endTimePicker = SpinTimePickerModern(endDateFrame, period=_period)
    endTimePicker.grid(row=1, column=0, padx=ROOT_PADX, pady=ROOT_PADY, sticky=NSEW, columnspan=2)
    endTimePicker.addAll(constants.HOURS12)
    endTimePicker.set12Hrs(_time.hour)
    endTimePicker.setMins(_time.minute)
    sep3 = ttk.Separator(configWidgetsFrame, orient=HORIZONTAL)
    sep3.grid(row=5, column=0, columnspan=2, sticky=NSEW, padx=ROOT_PADX, pady=ROOT_PADY)
    intervalFrame = ttk.Frame(configWidgetsFrame)
    intervalFrame.grid(row=6, column=0, columnspan=2, sticky=NSEW, padx=ROOT_PADX, pady=ROOT_PADY)
    intervalFrame.columnconfigure(0, weight=1)
    intervalFrame.columnconfigure(1, weight=1)
    intervalLabel = ttk.Label(intervalFrame, text='Set Interval')
    intervalLabel.grid(row=0, column=0, sticky=NSEW, padx=ROOT_PADX, pady=ROOT_PADY)
    intervalPicker = SpinTimePickerModern(intervalFrame)
    intervalPicker.grid(row=0, column=1, sticky=NSEW, padx=ROOT_PADX, pady=ROOT_PADY)
    intervalPicker.addAll(constants.HOURS24)
    intervalPicker.set24Hrs(0)
    intervalPicker.setMins(0)

    addButton = ttk.Button(configWidgetsFrame, text="Generate", command=_addDateTime)
    addButton.grid(row=7, column=0, columnspan=1, sticky=NSEW, padx=ROOT_PADX)
    removeButton = ttk.Button(configWidgetsFrame, text="Clear", command=_removeDateTime)
    removeButton.grid(row=7, column=1, columnspan=1, sticky=NSEW, padx=ROOT_PADX)

    queueListbox = tk.Listbox(_frame1, listvariable=_listVar)
    queueListbox.grid(row=0, column=1, sticky=NSEW, padx=ROOT_PADX, pady=ROOT_PADY)
    queueScroll = ttk.Scrollbar(_frame1, orient=VERTICAL, command=queueListbox.yview)
    queueListbox.configure(yscrollcommand=queueScroll.set)
    queueScroll.grid(row=0, column=2, sticky=NSEW)

    for i in range(0,len(automation.queue),2):
        queueListbox.itemconfigure(i, background='#f0f0ff')

    # Tab 2 (Scripting)
    presetsFrame = ttk.LabelFrame(_frame2, text='Presets')
    presetsFrame.grid(row=0, column=0, sticky=NSEW)
    textBox = tk.Text(_frame2, width=120)
    textBox.grid(row=0, column=1, sticky=NSEW)
    textBox.bind("<Tab>", _onTab)
    clearAndSetWidget(textBox, automation.textBoxString)
    button1 = ttk.Button(presetsFrame, text='Default', command=lambda: _presetButtonHandler(automation.presets.default))
    button1.grid(row=0, column=0, sticky=NSEW, padx=5, pady=5)
    button2 = ttk.Button(presetsFrame, text='Clear/Write', command=lambda: _presetButtonHandler(automation.presets.clearwrite))
    button2.grid(row=1, column=0, sticky=NSEW, padx=5, pady=5)
    button3 = ttk.Button(presetsFrame, text='Average', command=lambda: _presetButtonHandler(automation.presets.average))
    button3.grid(row=2, column=0, sticky=NSEW, padx=5, pady=5)
    button4 = ttk.Button(presetsFrame, text='Max Hold', command=lambda: _presetButtonHandler(automation.presets.maxhold))
    button4.grid(row=3, column=0, sticky=NSEW, padx=5, pady=5)
    button5 = ttk.Button(presetsFrame, text='Min Hold', command=lambda: _presetButtonHandler(automation.presets.minhold))
    button5.grid(row=4, column=0, sticky=NSEW, padx=5, pady=5)

    for i in range(7):
        presetsFrame.rowconfigure(i, weight=0)
    presetsFrame.rowconfigure(5, weight=1)
    emptySpace = ttk.Frame(presetsFrame)
    emptySpace.grid(row=5, column=0, sticky=NSEW)
    lastSavedButton = ttk.Button(presetsFrame, text='Load Last Saved', command=lambda: _lastSavedButtonHandler())
    lastSavedButton.grid(row=6, column=0, sticky=NSEW, padx=5, pady=5)
    saveButton = ttk.Button(presetsFrame, text='Save Changes', command=lambda: _saveAutomationFunctions(textBox.get(1.0, "end-1c")), state=DISABLED)
    saveButton.grid(row=7, column=0, sticky=NSEW, padx=5, pady=5)
    textBox.bind('<KeyRelease>', _saveButtonStateHandler)

def autoStartStop():
    """If the automation scheduler is active, pauses it and removes all jobs. If it is paused, add all jobs in automation.queue and resume.
    """
    match automation.state:
        case state.IDLE:
            if automation.queue == []:
                logging.error('Automation queue is empty')
                return
            thread = threading.Thread(target=initSchedule, daemon=True)
            thread.start()
            # if the scheduler isn't paused when adding more than 2 jobs it breaks most of the time
            # changing trigger from date to interval fixes it?
            # also commenting out the sys.stdout/err redirectors fixes it and i have no idea why
            for taskDateTime in automation.queue:
                automation.scheduler.add_job(onSchedule, trigger='date', run_date = taskDateTime)
            automation.scheduler.resume()
            automation.state = state.AUTO
        case state.AUTO:
            automation.scheduler.pause()
            # Remove jobs past execution from the queue
            for _dt in automation.queue[:]:
                if _dt < datetime.now():
                    automation.queue.remove(_dt)
            # Clear the scheduler job store
            for job in automation.scheduler.get_jobs():
                job.remove()

            automation.state = state.IDLE

def generateDriftDialog():
    global DEF_DRIFT_TO_PATH
    # If the DRIFT directory has already been created, update DEF_DRIFT_TO_PATH with that value 
    if DEF_DRIFT_FROM_PATH == DEF_DRIFT_TO_PATH:
        _toPath = os.path.join(DEF_DRIFT_FROM_PATH, 'DRIFT')
        if os.path.isdir(_toPath):
            DEF_DRIFT_TO_PATH = _toPath

    def _scheduleDrift(now=False):
        global DEF_DRIFT_FROM_PATH, DEF_DRIFT_TO_PATH
        _fromPath = fromPathEntry.get()
        _toPath = toPathEntry.get()
        DEF_DRIFT_FROM_PATH = _fromPath
        DEF_DRIFT_TO_PATH = _toPath
        args = (_fromPath, _toPath)
        if now:
            thread = threading.Thread(target=toDriftFormat, args=args, daemon=True)
            thread.start()
            return
        _jobTimePicker = intervalPicker.time()
        _jobTimeString = f'{_jobTimePicker[0]}:{_jobTimePicker[1]} {_jobTimePicker[2]}'
        _jobTime = datetime.strptime(_jobTimeString, '%I:%M %p').time()
        # Check if job is active
        _clearScheduler()
        # Add scheduled cron job
        dwfScheduler.add_job(toDriftFormat, args=args, trigger=CronTrigger(hour=_jobTime.hour, minute=_jobTime.minute), id=DRIFT_JOB_ID, name='Convert to DRIFT Format')

    def _clearScheduler():
        if dwfScheduler.get_job(DRIFT_JOB_ID):
            dwfScheduler.remove_job(DRIFT_JOB_ID)

    def _pickFilePath(entry):
        dir = filedialog.askdirectory()
        if not dir:
            return
        clearAndSetWidget(entry, dir)

    def _makeDriftDir():
        driftdir = makeDriftDir(fromPathEntry.get())
        if driftdir:
            clearAndSetWidget(toPathEntry, driftdir)

    _parent = Toplevel()
    _parent.title('DRIFT Processing')
    _parent.resizable(False, False)
    configWidgetsFrame = ttk.Frame(_parent, width=30)
    configWidgetsFrame.grid(row=0, column=0, padx=ROOT_PADX, pady=ROOT_PADY, sticky=NSEW)
    pathFrame = ttk.Frame(configWidgetsFrame)
    pathFrame.grid(row=0, column=0, padx=ROOT_PADX, columnspan=2, sticky=NSEW)
    pathFrame.columnconfigure(0, weight=0)
    pathFrame.columnconfigure(1, weight=1)
    fromPathLabel = ttk.Label(pathFrame, text='Trace Directory:')
    fromPathLabel.grid(row=0, column=0, padx=ROOT_PADX, pady=ROOT_PADY, sticky=W)
    fromPathEntry = ttk.Entry(pathFrame, width=50, state='disabled')
    fromPathEntry.grid(row=1, column=0, columnspan=2, padx=ROOT_PADX, pady=ROOT_PADY, sticky=NSEW)
    clearAndSetWidget(fromPathEntry, DEF_DRIFT_FROM_PATH)
    fromPathPicker = ttk.Button(pathFrame, text='Browse...', command=lambda: _pickFilePath(fromPathEntry))
    fromPathPicker.grid(row=0, column=1, padx=ROOT_PADX, pady=ROOT_PADY, sticky=E)
    toPathLabel = ttk.Label(pathFrame, text='DRIFT Destination Directory:')
    toPathLabel.grid(row=2, column=0, padx=ROOT_PADX, pady=ROOT_PADY, sticky=W)
    toPathEntry = ttk.Entry(pathFrame, width=50, state='disabled')
    toPathEntry.grid(row=3, column=0, columnspan=2, padx=ROOT_PADX, pady=ROOT_PADY, sticky=NSEW)
    clearAndSetWidget(toPathEntry, DEF_DRIFT_TO_PATH)
    toPathPicker = ttk.Button(pathFrame, text='Browse...', command=lambda: _pickFilePath(toPathEntry))
    toPathPicker.grid(row=2, column=1, padx=ROOT_PADX, pady=ROOT_PADY, sticky=E)
    makeDirButton = ttk.Button(pathFrame, text="Make DRIFT Directory in Current Working Directory", command=_makeDriftDir)
    makeDirButton.grid(row=4, column=0, columnspan=2, sticky=NSEW, padx=ROOT_PADX, pady=ROOT_PADY)
    sep1 = ttk.Separator(configWidgetsFrame, orient=HORIZONTAL)
    sep1.grid(row=1, column=0, columnspan=2, sticky=NSEW, padx=ROOT_PADX, pady=ROOT_PADY)
    paramsFrame = ttk.Frame(configWidgetsFrame)
    paramsFrame.grid(row = 2, column = 0, padx=ROOT_PADX, columnspan=2, sticky=NSEW)
    paramsFrame.columnconfigure(0, weight=1)
    paramsFrame.columnconfigure(1, weight=1)
    intLabel = ttk.Label(paramsFrame, text='Run every day at:')
    intLabel.grid(row=0, column=0, padx=ROOT_PADX, pady=ROOT_PADY, sticky=W)
    intervalPicker = SpinTimePickerModern(paramsFrame, period=constants.AM)
    intervalPicker.grid(row=0, column=1, sticky=NSEW, padx=ROOT_PADX, pady=ROOT_PADY)
    intervalPicker.addAll(constants.HOURS12)
    intervalPicker.set12Hrs(1)
    intervalPicker.setMins(10)
    sep2 = ttk.Separator(configWidgetsFrame, orient=HORIZONTAL)
    sep2.grid(row=3, column=0, columnspan=2, sticky=NSEW, padx=ROOT_PADX, pady=ROOT_PADY)
    buttonFrame = ttk.Frame(configWidgetsFrame)
    buttonFrame.grid(row = 4, column = 0, padx=ROOT_PADX, columnspan=2, sticky=NSEW)
    buttonFrame.columnconfigure(0, weight=1)
    buttonFrame.columnconfigure(1, weight=1)
    scheduleButton = ttk.Button(buttonFrame, text="Schedule Job", command=_scheduleDrift)
    scheduleButton.grid(row=0, column=0, columnspan=1, sticky=NSEW, padx=ROOT_PADX, pady=ROOT_PADY)
    clearButton = ttk.Button(buttonFrame, text="Clear Scheduler", command=_clearScheduler)
    clearButton.grid(row=0, column=1, columnspan=1, sticky=NSEW, padx=ROOT_PADX, pady=ROOT_PADY)
    nowButton = ttk.Button(buttonFrame, text="Run Immediately", command=lambda: _scheduleDrift(now=True))
    nowButton.grid(row=1, column=1, columnspan=2, sticky=NSEW, padx=ROOT_PADX, pady=ROOT_PADY)

def generateWaterfallDialog():
    _fileTypes = ('.png', '.jpg', '.pdf', '.svg')

    def _scheduleWaterfall(now=False):
        global DEF_WF_PATH, DEF_WF_THRESHOLD, DEF_WF_TZ, DEF_WF_FILETYPE, DEF_WF_DPI
        _path = pathEntry.get()
        _threshold = int(thEntry.get())
        _timezone = tzCombo.get()
        _filetype = ftCombo.get()
        _dpi = int(dpiEntry.get())
        args = (_path, _threshold, _timezone, _filetype, _dpi)
        DEF_WF_PATH = _path
        DEF_WF_THRESHOLD = _threshold
        DEF_WF_TZ = _timezone
        DEF_WF_FILETYPE = _filetype
        DEF_WF_DPI = _dpi
        if now:
            thread = threading.Thread(target=makeWaterfalls, args=args, daemon=True)
            thread.start()
            return
        _jobTimePicker = intervalPicker.time()
        _jobTimeString = f'{_jobTimePicker[0]}:{_jobTimePicker[1]} {_jobTimePicker[2]}'
        _jobTime = datetime.strptime(_jobTimeString, '%I:%M %p').time()
        # Check if job is active
        _clearScheduler()
        # Add scheduled cron job
        dwfScheduler.add_job(makeWaterfalls, args=args, trigger=CronTrigger(hour=_jobTime.hour, minute=_jobTime.minute), id=WATERFALL_JOB_ID, name='Generate Waterfall Plot')

    def _clearScheduler():
        if dwfScheduler.get_job(WATERFALL_JOB_ID):
            dwfScheduler.remove_job(WATERFALL_JOB_ID)

    def _pickFilePath(entry):
        dir = filedialog.askdirectory()
        if not dir:
            return
        clearAndSetWidget(entry, dir)

    _parent = Toplevel()
    _parent.title('Waterfall Plot Utility')
    _parent.resizable(False, False)
    configWidgetsFrame = ttk.Frame(_parent, width=30)
    configWidgetsFrame.grid(row=0, column=0, padx=ROOT_PADX, pady=ROOT_PADY, sticky=NSEW)
    pathFrame = ttk.Frame(configWidgetsFrame)
    pathFrame.grid(row=0, column=0, padx=ROOT_PADX, columnspan=2, sticky=NSEW)
    pathFrame.columnconfigure(0, weight=0)
    pathFrame.columnconfigure(1, weight=1)
    pathLabel = ttk.Label(pathFrame, text='File Path:')
    pathLabel.grid(row=0, column=0, padx=ROOT_PADX, pady=ROOT_PADY, sticky=W)
    pathEntry = ttk.Entry(pathFrame, width=50, state='disabled')
    pathEntry.grid(row=1, column=0, columnspan=2, padx=ROOT_PADX, pady=ROOT_PADY, sticky=NSEW)
    clearAndSetWidget(pathEntry, DEF_WF_PATH)
    pathPicker = ttk.Button(pathFrame, text='Browse...', command=lambda: _pickFilePath(pathEntry))
    pathPicker.grid(row=0, column=1, padx=ROOT_PADX, pady=ROOT_PADY, sticky=E)
    sep1 = ttk.Separator(configWidgetsFrame, orient=HORIZONTAL)
    sep1.grid(row=1, column=0, columnspan=2, sticky=NSEW, padx=ROOT_PADX, pady=ROOT_PADY)
    paramsFrame = ttk.Frame(configWidgetsFrame)
    paramsFrame.grid(row = 2, column = 0, padx=ROOT_PADX, columnspan=2, sticky=NSEW)
    paramsFrame.columnconfigure(0, weight=1)
    paramsFrame.columnconfigure(1, weight=1)
    tzLabel = ttk.Label(paramsFrame, text='Timezone:')
    tzLabel.grid(row=0, column=0, padx=ROOT_PADX, pady=ROOT_PADY, sticky=W)
    tzCombo = ttk.Combobox(paramsFrame, values=pytz.common_timezones, state='readonly')
    tzCombo.grid(row=0, column=1, padx=ROOT_PADX, pady=ROOT_PADY, sticky=NSEW)
    clearAndSetWidget(tzCombo, DEF_WF_TZ)
    thLabel = ttk.Label(paramsFrame, text='Threshold:')
    thLabel.grid(row=1, column=0, padx=ROOT_PADX, pady=ROOT_PADY, sticky=W)
    thEntry = ttk.Entry(paramsFrame, validate='key', validatecommand=(isNumWrapper, '%P'))
    thEntry.grid(row=1, column=1, padx=ROOT_PADX, pady=ROOT_PADY, sticky=NSEW)
    clearAndSetWidget(thEntry, DEF_WF_THRESHOLD)
    ftLabel = ttk.Label(paramsFrame, text='File Type:')
    ftLabel.grid(row=2, column=0, padx=ROOT_PADX, pady=ROOT_PADY, sticky=W)
    ftCombo = ttk.Combobox(paramsFrame, values=_fileTypes, state='readonly')
    ftCombo.grid(row=2, column=1, padx=ROOT_PADX, pady=ROOT_PADY, sticky=NSEW)
    clearAndSetWidget(ftCombo, DEF_WF_FILETYPE)
    dpiLabel = ttk.Label(paramsFrame, text='DPI:')
    dpiLabel.grid(row=3, column=0, padx=ROOT_PADX, pady=ROOT_PADY, sticky=W)
    dpiEntry = ttk.Entry(paramsFrame, validate='key', validatecommand=(isNumWrapper, '%P'))
    dpiEntry.grid(row=3, column=1, padx=ROOT_PADX, pady=ROOT_PADY, sticky=NSEW)
    clearAndSetWidget(dpiEntry, DEF_WF_DPI)
    intLabel = ttk.Label(paramsFrame, text='Run every day at:')
    intLabel.grid(row=4, column=0, padx=ROOT_PADX, pady=ROOT_PADY, sticky=W)
    intervalPicker = SpinTimePickerModern(paramsFrame, period=constants.AM)
    intervalPicker.grid(row=4, column=1, sticky=NSEW, padx=ROOT_PADX, pady=ROOT_PADY)
    intervalPicker.addAll(constants.HOURS12)
    intervalPicker.set12Hrs(1)
    intervalPicker.setMins(0)
    sep2 = ttk.Separator(configWidgetsFrame, orient=HORIZONTAL)
    sep2.grid(row=3, column=0, columnspan=2, sticky=NSEW, padx=ROOT_PADX, pady=ROOT_PADY)
    buttonFrame = ttk.Frame(configWidgetsFrame)
    buttonFrame.grid(row = 4, column = 0, padx=ROOT_PADX, columnspan=2, sticky=NSEW)
    buttonFrame.columnconfigure(0, weight=1)
    buttonFrame.columnconfigure(1, weight=1)
    scheduleButton = ttk.Button(buttonFrame, text="Schedule Job", command=_scheduleWaterfall)
    scheduleButton.grid(row=0, column=0, columnspan=1, sticky=NSEW, padx=ROOT_PADX, pady=ROOT_PADY)
    clearButton = ttk.Button(buttonFrame, text="Clear Scheduler", command=_clearScheduler)
    clearButton.grid(row=0, column=1, columnspan=1, sticky=NSEW, padx=ROOT_PADX, pady=ROOT_PADY)
    nowButton = ttk.Button(buttonFrame, text="Run Immediately", command=lambda: _scheduleWaterfall(now=True))
    nowButton.grid(row=1, column=1, columnspan=2, sticky=NSEW, padx=ROOT_PADX, pady=ROOT_PADY)

def openTrace():
    filepath = filedialog.askopenfilename(title="Select a file", filetypes=(('Comma separated variables', '*.csv'),))
    if filepath:
        df = pd.read_csv(filepath, header=None)
        trace = Trace(df, os.path.basename(filepath))
        x = trace.data.loc[:, 0].astype(float)
        y = trace.data.loc[:, 1].astype(float)
        try:
            _dt = datetime.fromisoformat(trace.header.loc['Time'].item()).astimezone(LOCAL_TIMEZONE)
            _time = _dt.strftime("%H:%M:%S") + f' ({LOCAL_TIMEZONE})'
        except:
            _time = trace.header.loc['Time'].item()
        plt.ion()
        fig, ax = plt.subplots()
        ax.plot(x, y)
        ax.set_xlabel(f'Frequency ({trace.header.loc['X Axis Units'].item()})')
        ax.set_ylabel(f'Power ({trace.header.loc['Y Axis Units'].item()})')
        ax.grid(visible=True)
        ax.margins(x=0)
        ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())
        ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
        ax.xaxis.set_major_formatter(EngFormatter(unit='Hz'))
        ax.set_title(f'{os.path.basename(filepath)}\n{_time}')
        fig.canvas.draw()

evalCheckbutton.configure(command=checkbuttonStateHandler)
execCheckbutton.configure(command=checkbuttonStateHandler)

# When sys.std***.write is called (such as on print), call redirector to print in textbox
sys.stdout.write = redirector
sys.stderr.write = redirector

# Check for initialization errors and print in the newly generated terminal window
if 'cfg_error' in globals():
    logging.warning(f'{type(cfg_error).__name__}: {cfg_error}')
if missingHeaders:
    for header in missingHeaders:
        logging.error(f'Missing header [{header}] in config.toml')
if missingKeys:
    for key in missingKeys:
        logging.error(f'Missing key [{key}] in config.toml')
if missingHeaders or missingKeys or 'cfg_error' in globals():
    logging.warning(f'Error loading config.toml, loading default configuration.')

# Generate objects within root window
Vi = VisaIO()
Motor = MotorIO(0, 0)
Relay = SerialIO()

Front_End = FrontEnd(root, Vi, Motor, Relay)
Spec_An = SpecAn(Vi, Front_End.spectrumFrame)
Azi_Ele = AziElePlot(Motor, Front_End.directionFrame)

# Threading stuff
statusMonitorThread = threading.Thread(target=statusMonitor, args = (Front_End, Vi, Motor, Relay, Azi_Ele), daemon=True)
statusMonitorThread.start()
automation.scheduler.start(paused=True)
dwfScheduler.start()
Spec_An.analyzerDisplayLoopthread.start()

# Bind FrontEnd buttons to methods
Front_End.standbyButton.configure(command = lambda: Azi_Ele.setState(state.IDLE))
Front_End.manualButton.configure(command = lambda: Azi_Ele.setState(state.INIT))
Front_End.haltButton.configure(command = lambda: Azi_Ele.halt())
Front_End.killDrivesButton.configure(command = lambda: Azi_Ele.setState(state.CLEANUP))
Front_End.autoButton.configure(command = lambda: generateAutoDialog())
Front_End.autoStartStopButton.configure(command = lambda: autoStartStop())

# Generate menu bars
root.option_add('*tearOff', False)
menubar = Menu(root)
root['menu'] = menubar
menuFile = Menu(menubar)
menuOptions = Menu(menubar)
menuRun = Menu(menubar)
menuHelp = Menu(menubar)
menubar.add_cascade(menu=menuFile, label='File')
menubar.add_cascade(menu=menuOptions, label='Options')
menubar.add_cascade(menu=menuRun, label='Run')
menubar.add_cascade(menu=menuHelp, label='Help')

# File
menuFile.add_command(label='Open trace', command = lambda: openTrace())
menuFile.add_command(label='Quicksave trace', command = lambda: threadHandler(saveTrace, kwargs={'filePath': os.getcwd()}))
menuFile.add_separator()
menuFile.add_command(label='Save trace', command = lambda: openSaveDialog(type='trace'))
menuFile.add_command(label='Save log', command = lambda: openSaveDialog(type='log'))
menuFile.add_command(label='Save image', command = lambda: openSaveDialog(type='image'))
menuFile.add_separator()
menuFile.add_command(label='Generate config.toml', command = generateConfigDialog)
menuFile.add_separator()
menuFile.add_command(label='Exit', command=Front_End.onExit)

# Options
tkLoggingLevel = IntVar()
tkLoggingLevel.set(1)
menuOptions.add_command(label='Configure...', command = Front_End.openConfig)
menuOptions.add_command(label='Change plot color', command = Spec_An.setPlotThreadHandler)
menuOptions.add_separator()
menuOptions.add_radiobutton(label='Logging: Standard', variable = tkLoggingLevel, command = lambda: loggingLevelHandler(tkLoggingLevel.get()), value = 1)
menuOptions.add_radiobutton(label='Logging: Verbose', variable = tkLoggingLevel, command = lambda: loggingLevelHandler(tkLoggingLevel.get()), value = 2)
menuOptions.add_radiobutton(label='Logging: Debug', variable = tkLoggingLevel, command = lambda: loggingLevelHandler(tkLoggingLevel.get()), value = 3)

# Run
menuRun.add_command(label='DRIFT Processing', command = generateDriftDialog)
menuRun.add_command(label='Waterfall Plot Utility', command=generateWaterfallDialog)

# Help
menuHelp.add_command(label='Open wiki...', command=Front_End.openHelp)

root.protocol("WM_DELETE_WINDOW", Front_End.onExit)
root.mainloop()
