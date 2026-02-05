"""
 * @file defaultconfig.py
 * @author Remy Nguyen (rnguyen@nrao.edu)
 * @brief Sets up default configuration. Should be loaded in main.py in the event of an error loading config.toml.
 * 
 * @date Last Modified: 2025-1-23
 * 
 * @copyright Copyright (c) 2025
 * 
 """

import logging
import tomllib
from pathlib import Path

defaultconfig = """
[config]
analyzer_refresh_seconds = 0.05
motor_refresh_seconds = 0.2
status_monitor_refresh_seconds = 0.2

[drift]
def_from_path = ''
def_to_path = ''

[waterfall]
def_from_path = ''
def_to_path = ''
def_threshold = 100
def_timezone = 'US/Mountain'
def_filetype = '.png'
def_dpi = 600

[automation]
thread_max_workers = 1
coalesce = true
job_max_instances = 1

[calibration]
# Encoder home is the encoder position when the dish is parked (azimuth at true north, elevation straight up).
x_enc_home = -235753513
y_enc_home = 239092664
# Encoder counts per rotation is the amount of counts per 360 degree rotation of the antenna, not the encoder.
x_countsperrotation = 45936033
y_countsperrotation = 45936033

[theme]
ttk = "clearlooks"
select_background = "#00ff00"
clock_font = ['Arial', 15]
terminal_font = ['Courier', 11]
icon_font = ['MS Serif', 12]
font = ['Arial', 12]
"""

defaultcfg = tomllib.loads(defaultconfig)

def generateConfig():
    try:
        f = open(Path(__file__).parent.absolute() / 'config.toml', "w")
        f.write(defaultconfig)
        f.close()
    except Exception as e:
        logging.error('Could not generate config.toml')
        logging.error(e)
    else:
        logging.info('Generated config.toml successfully')

def importToml():
    try:
        missingHeaders = []
        missingKeys = []
        cfg_error = None
        file = open(Path(__file__).parent.absolute() / 'config.toml', "rb")
        cfg = tomllib.load(file)

        for header in defaultcfg:
            if str(header) not in cfg:
                missingHeaders.append(header)
                continue
            for key in defaultcfg[header]:
                if str(key) not in cfg[header]:
                    missingKeys.append(header + '.' + key)
    except Exception as e:
        cfg_error = e
    finally:
        if missingHeaders or missingKeys or cfg_error:
            cfg = defaultcfg
    return (cfg, missingHeaders, missingKeys, cfg_error)

class config:
    def __init__(self, cfg):
        # REFRESH RATES
        self.IDLE_DELAY = 1.0
        self.ANALYZER_REFRESH_DELAY = cfg['config']['analyzer_refresh_seconds']
        self.MOTOR_LOOP_DELAY = cfg['config']['motor_refresh_seconds']
        self.STATUS_MONITOR_DELAY = cfg['config']['status_monitor_refresh_seconds']

        self.Automation = self.automation(cfg)
        self.Calibration = self.calibration(cfg)
        self.Drift = self.drift(cfg)
        self.Waterfall = self.waterfall(cfg)
        self.Theme = self.theme(cfg)

    class automation:
        def __init__(self, cfg):
            self.THREAD_MAX_WORKERS = cfg['automation']['thread_max_workers']
            self.COALESCE = cfg['automation']['coalesce']
            self.MAX_INSTANCES = cfg['automation']['job_max_instances']

    class calibration:
        def __init__(self, cfg):
            self.X_HOME = cfg['calibration']['x_enc_home']
            self.Y_HOME = cfg['calibration']['y_enc_home']
            self.X_CPD = cfg['calibration']['x_countsperrotation'] / 360
            self.Y_CPD = cfg['calibration']['y_countsperrotation'] / 360

    class drift:
        def __init__(self, cfg):
            self.FROM_PATH = cfg['drift']['def_from_path']
            self.TO_PATH = cfg['drift']['def_to_path']
        
    class waterfall:
        def __init__(self, cfg):
            self.FROM_PATH = cfg['waterfall']['def_from_path']
            self.TO_PATH = cfg['waterfall']['def_to_path']
            self.THRESHOLD = cfg['waterfall']['def_threshold']
            self.TZ = cfg['waterfall']['def_timezone']
            self.FILETYPE = cfg['waterfall']['def_filetype']
            self.DPI = cfg['waterfall']['def_dpi']

    class theme:
        def __init__(self, cfg):
            self.TTK = cfg['theme']['ttk']
            self.SELECT_BACKGROUND = cfg['theme']['select_background']
            self.CLOCK_FONT = cfg['theme']['clock_font']
            self.TERMINAL_FONT = cfg['theme']['terminal_font']
            self.ICON_FONT = cfg['theme']['icon_font']
            self.FONT = cfg['theme']['font']