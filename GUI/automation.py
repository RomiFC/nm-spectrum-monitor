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
            self.default = """# This function is called once when the automation scheduler starts
def initSchedule():
    pass
    
# This function is called every time a scheduler job is run
def onSchedule():
    pass
"""
            self.maxhold = """# This function is called once when the automation scheduler starts
def initSchedule():
    with visaLock:
        Vi.openRsrc.write(":INIT:CONT OFF")
    Spec_An.setAnalyzerValue(startfreq=0, stopfreq=12e9, sweeppoints=4001, tracetype=3, avgcount=100)
    
# This function is called every time a scheduler job is run
def onSchedule():
    with visaLock:
        buffer = Vi.openRsrc.query_ascii_values(":READ:SAN?")
    xAxis = buffer[::2]
    yAxis = buffer[1::2]
    saveTrace(filePath=automation.filePath, xdata=xAxis, ydata=yAxis)
"""
