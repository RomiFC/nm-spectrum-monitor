import os
from apscheduler.schedulers.background import BackgroundScheduler

class Automation:
    def __init__(self, defaultstate=None, executors=None, job_defaults=None):
        self.queue = []
        self.state = defaultstate
        self.filePath = os.getcwd()
        self.scheduler = BackgroundScheduler(executors=executors, job_defaults=job_defaults)
        self.presets = self.Presets()
        self.textBoxString = self.presets.default

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
    Spec_An.setAnalyzerValue(startfreq=0, stopfreq=12e9, sweeppoints=4001, tracetype=0, rbw=300e3)
    
# This function is called every time a scheduler job is run (in its own thread)
def onSchedule():
    with visaLock:
        Vi.openRsrc.write(":INIT:CONT OFF")
        buffer = Vi.openRsrc.query_ascii_values(":READ:SAN?")
        TimeParameter.update(value=datetime.now(timezone.utc).isoformat())
    xAxis = buffer[::2]
    yAxis = buffer[1::2]
    saveTrace(filePath=automation.filePath, xdata=xAxis, ydata=yAxis)
"""
            self.average = """# This function is called once when the automation scheduler starts (in its own thread)
def initSchedule():
    with visaLock:
        Vi.openRsrc.write(":INIT:CONT OFF")
    Spec_An.setAnalyzerValue(startfreq=0, stopfreq=12e9, sweeppoints=4001, tracetype=1, avgcount=100, rbw=300e3)
    
# This function is called every time a scheduler job is run (in its own thread)
def onSchedule():
    with visaLock:
        Vi.openRsrc.write(":INIT:CONT OFF")
        Vi.openRsrc.write(":INIT:IMM")
        time.sleep(0.25)
        while Vi.getOperationRegister() & 0b00011011:
            time.sleep(0.1)
        buffer = Vi.openRsrc.query_ascii_values(":FETCH:SAN?")
        TimeParameter.update(value=datetime.now(timezone.utc).isoformat())
    xAxis = buffer[::2]
    yAxis = buffer[1::2]
    saveTrace(filePath=automation.filePath, xdata=xAxis, ydata=yAxis)
"""
            self.maxhold = """# This function is called once when the automation scheduler starts (in its own thread)
def initSchedule():
    with visaLock:
        Vi.openRsrc.write(":INIT:CONT OFF")
    Spec_An.setAnalyzerValue(startfreq=0, stopfreq=12e9, sweeppoints=4001, tracetype=2, avgcount=100, rbw=300e3)
    
# This function is called every time a scheduler job is run (in its own thread)
def onSchedule():
    with visaLock:
        Vi.openRsrc.write(":INIT:CONT OFF")
        Vi.openRsrc.write(":INIT:IMM")
        time.sleep(0.25)
        while Vi.getOperationRegister() & 0b00011011:
            time.sleep(0.1)
        buffer = Vi.openRsrc.query_ascii_values(":FETCH:SAN?")
        TimeParameter.update(value=datetime.now(timezone.utc).isoformat())
    xAxis = buffer[::2]
    yAxis = buffer[1::2]
    saveTrace(filePath=automation.filePath, xdata=xAxis, ydata=yAxis)
"""
            self.minhold = """# This function is called once when the automation scheduler starts (in its own thread)
def initSchedule():
    with visaLock:
        Vi.openRsrc.write(":INIT:CONT OFF")
    Spec_An.setAnalyzerValue(startfreq=0, stopfreq=12e9, sweeppoints=4001, tracetype=3, avgcount=100, rbw=300e3)
    
# This function is called every time a scheduler job is run (in its own thread)
def onSchedule():
    with visaLock:
        Vi.openRsrc.write(":INIT:CONT OFF")
        Vi.openRsrc.write(":INIT:IMM")
        time.sleep(0.25)
        while Vi.getOperationRegister() & 0b00011011:
            time.sleep(0.1)
        buffer = Vi.openRsrc.query_ascii_values(":FETCH:SAN?")
        TimeParameter.update(value=datetime.now(timezone.utc).isoformat())
    xAxis = buffer[::2]
    yAxis = buffer[1::2]
    saveTrace(filePath=automation.filePath, xdata=xAxis, ydata=yAxis)
"""
