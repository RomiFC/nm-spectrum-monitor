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
