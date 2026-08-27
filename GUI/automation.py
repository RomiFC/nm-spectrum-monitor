import os
from apscheduler.schedulers.background import BackgroundScheduler

class Automation:
    def __init__(self, defaultstate=None, executors=None, job_defaults=None):
        self.queue = [] # Stores datetimes of jobs to be executed for the DateTrigger.
        self.state = defaultstate
        self.filePath = os.getcwd() # Where to save traces
        self.scheduler = BackgroundScheduler(executors=executors, job_defaults=job_defaults, daemon=True)
        self.presets = self.Presets()
        self.textBoxString = self.presets.default # Last saved textboxstring

        self.isCronTrigger = True
        self.cronStartDatetime = None
        self.cronInterval = [0, 5]

    class Presets:
        def __init__(self):
            self.default = """# This function is called once when the automation scheduler starts (in its own thread)
def initSchedule():
    pass
    
# This function is called every time a scheduler job is run (in its own thread)
def onSchedule():
    pass
"""
            self.clearwrite = """# This function is called once when the automation scheduler starts (in its own thread)
def initSchedule():
    with visaLock:
        Vi.openRsrc.write(":INIT:CONT OFF")
    Spec_An.setAnalyzerValue(startfreq=0, stopfreq=10e9, sweeppoints=5001, tracetype=0, rbw=300e3)
    
# This function is called every time a scheduler job is run (in its own thread)
def onSchedule():
    with visaLock:
        Vi.openRsrc.write(":INIT:CONT OFF")
        buffer = Vi.openRsrc.query_ascii_values(":READ:SAN?")
        TimeParameter.update(value=datetime.now(LOCAL_TIMEZONE).isoformat())
    xAxis = buffer[::2]
    yAxis = buffer[1::2]
    saveTrace(filePath=automation.filePath, xdata=xAxis, ydata=yAxis)
"""
            self.average = """# This function is called once when the automation scheduler starts (in its own thread)
def initSchedule():
    with visaLock:
        Vi.openRsrc.write(":INIT:CONT OFF")
    
# This function is called every time a scheduler job is run (in its own thread)
def onSchedule():
    START_FREQ = 0
    STOP_FREQ = 10e9
    SWEEP_POINTS = 5001
    RBW = 300e3
    AVG_COUNT = 1000

    Spec_An.setAnalyzerValue(startfreq=START_FREQ, stopfreq=STOP_FREQ, sweeppoints=SWEEP_POINTS, tracetype=1, avgcount=AVG_COUNT, rbw=RBW)

    with visaLock:
        Vi.openRsrc.write(":INIT:CONT OFF")
        Vi.openRsrc.write(":INIT:IMM")
        time.sleep(0.25)
        while Vi.getOperationRegister() & 0b00011011:
            time.sleep(0.1)
        buffer = Vi.openRsrc.query_ascii_values(":FETCH:SAN?")
        TimeParameter.update(value=datetime.now(LOCAL_TIMEZONE).isoformat())
    xAxis = buffer[::2]
    yAxis = buffer[1::2]
    saveTrace(filePath=automation.filePath, xdata=xAxis, ydata=yAxis)
"""
            self.maxhold = """# This function is called once when the automation scheduler starts (in its own thread)
def initSchedule():
    with visaLock:
        Vi.openRsrc.write(":INIT:CONT OFF")
    
# This function is called every time a scheduler job is run (in its own thread)
def onSchedule():
    START_FREQ = 0
    STOP_FREQ = 10e9
    SWEEP_POINTS = 5001
    RBW = 300e3
    AVG_COUNT = 1000

    Spec_An.setAnalyzerValue(startfreq=START_FREQ, stopfreq=STOP_FREQ, sweeppoints=SWEEP_POINTS, tracetype=2, avgcount=AVG_COUNT, rbw=RBW)

    with visaLock:
        Vi.openRsrc.write(":INIT:CONT OFF")
        Vi.openRsrc.write(":INIT:IMM")
        time.sleep(0.25)
        while Vi.getOperationRegister() & 0b00011011:
            time.sleep(0.1)
        buffer = Vi.openRsrc.query_ascii_values(":FETCH:SAN?")
        TimeParameter.update(value=datetime.now(LOCAL_TIMEZONE).isoformat())
    xAxis = buffer[::2]
    yAxis = buffer[1::2]
    saveTrace(filePath=automation.filePath, xdata=xAxis, ydata=yAxis)
"""
            self.maxhold2 = """# This function is called once when the automation scheduler starts (in its own thread)
def initSchedule():
    with visaLock:
        Vi.openRsrc.write(":INIT:CONT OFF")
    
# This function is called every time a scheduler job is run (in its own thread)
def onSchedule():
    START_FREQ = 0
    STOP_FREQ = 10e9
    SWEEP_POINTS = 5001
    RBW = 300e3
    ATTEN = 0
    MAX_HOLD_TIME_SECONDS = 270

    Spec_An.setAnalyzerValue(startfreq=START_FREQ, stopfreq=STOP_FREQ, sweeppoints=SWEEP_POINTS, tracetype=2, rbw=RBW, atten=ATTEN)

    with visaLock:
        Vi.openRsrc.write(":INIT:CONT OFF")
        Vi.openRsrc.write(":TRAC:MODE WRIT; *WAI; :INIT:IMM; *WAI; :TRAC:MODE MAXH")
        startFreq = float(Vi.openRsrc.query_ascii_values(":SENS:FREQ:START?")[0])
        stopFreq = float(Vi.openRsrc.query_ascii_values(":SENS:FREQ:STOP?")[0])
        sweepPoints = int(Vi.openRsrc.query_ascii_values(":SENS:SWEEP:POINTS?")[0])
        Vi.openRsrc.write(":INIT:CONT ON; :INIT:REST")
        time.sleep(MAX_HOLD_TIME_SECONDS)
        while Vi.getOperationRegister() & 0b00011011:
            time.sleep(0.1)
        buffer = Vi.openRsrc.query_ascii_values(":TRAC:DATA? TRACE1")
        TimeParameter.update(value=datetime.now(LOCAL_TIMEZONE).isoformat())
    stepSize = (stopFreq - startFreq) / (sweepPoints - 1)
    xAxis = np.zeros(sweepPoints)
    xAxis[0] = startFreq
    for index in range(sweepPoints - 1):
        xAxis[index + 1] = xAxis[index] + stepSize
    yAxis = buffer
    saveTrace(filePath=automation.filePath, xdata=xAxis, ydata=yAxis)
"""
