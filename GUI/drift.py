import os
import pandas as pd
import logging

from tracedata import *

tracesToProcess = []

def makeDriftDir(path):
    # Check if DRIFT Directory exists, create it if it does not
    if path is not None:
        path = os.getcwd()
    driftdir = os.path.join(path, 'DRIFT')
    try:
        os.mkdir(driftdir)
        logging.info(f"Folder 'DRIFT' created successfully in the current working directory.")
    except FileExistsError:
        pass
    except OSError as e:
        logging.info(f"Error creating folder: {e}")

def toDriftFormat(tracePath, driftPath):
    # import data
    trace_files = getAllCsvFiles(tracePath)
    drift_files = getAllCsvFiles(driftPath)

    # process all csvs
    for file_name in trace_files:
        # Generate dataframe from csv
        df = pd.read_csv(file_name, header=None)
        trace = Trace(df, file_name)
        # Does the csv have a drift compatible counterpart?
        drift_trace_path = os.path.join(driftPath, trace.name + Trace.DRIFT_SUFFIX + '.csv')
        if os.path.isfile(drift_trace_path):
            continue
        # keep track of traces that need drift processing
        else:
            tracesToProcess.append(trace)

    # make drift formatted csv and write one in the drift directory
    for trace in tracesToProcess:
        df = trace.generateDriftData()
        file_path = os.path.join(driftPath, trace.drift.scan_name + '.csv')
        df.to_csv(file_path, index=False)