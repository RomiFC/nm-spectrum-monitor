import os
import pandas as pd
import logging

from tracedata import *

def makeDriftDir(path):
    """Checks if a folder called `DRIFT` exists in `path`, creates it if it does not exist.

    Args:
        path (string): File path to make DRIFT directory in.

    Returns:
        string: Path to drift directory or `None` if there is an error creating it.
    """
    # Check if DRIFT Directory exists, create it if it does not
    if path is None:
        path = os.getcwd()
    driftdir = os.path.join(path, 'DRIFT')
    try:
        os.mkdir(driftdir)
        logging.drift(f"Folder '{driftdir}' created successfully.")
    except FileExistsError as e:
        logging.drift(f'{type(e).__name__}: {e}')
    except OSError as e:
        logging.drift(f"Error creating folder: {e}")
        return None
    return driftdir

def makeDir(path, logfileexistserror = False):
    """Checks if `path` exists, creates it if it does not exist.

    Args:
        path (string): File path to make.
        logfileexistserror (bool): Determines whether or not to log a `FileExistsError` in `path`

    Returns:
        string: Path to directory or `None` if there is an error creating it.
    """
    # Check if DRIFT Directory exists, create it if it does not
    try:
        os.mkdir(path)
        logging.drift(f"Folder '{path}' created successfully.")
    except FileExistsError as e:
        if logfileexistserror:
            logging.drift(f'{type(e).__name__}: {e}')
        else:
            pass
    except OSError as e:
        logging.drift(f"Error creating folder: {e}")
        return None
    return path

def toDriftFormat(tracePath, driftPath):
    """Converts the trace csv files in `tracePath` to DRIFT compatible format and writes them in `driftPath`

    Args:
        tracePath (string): File path to search for trace csv's
        driftPath (string): File path to write DRIFT compatible csv's in
    """
    tracesToProcess = []
    makeDir(driftPath)
    # import data
    trace_files = getAllCsvFiles(tracePath)
    drift_files = getAllCsvFiles(driftPath)

    # process all csvs
    for file_name in trace_files:
        # Generate dataframe from csv
        file_path = os.path.join(tracePath, file_name)
        df = pd.read_csv(file_path, header=None)
        trace = Trace(df, file_name)
        # Does the csv have a drift compatible counterpart?
        try:
            trace.generateDriftData()
        except:
            continue
        drift_trace_path = os.path.join(driftPath, trace.drift.scan_name + '.csv')
        if os.path.isfile(drift_trace_path):
            continue
        # keep track of traces that need drift processing
        else:
            tracesToProcess.append(trace)

    if not tracesToProcess:
        logging.drift('No traces to process.')
        return

    # make drift formatted csv and write one in the drift directory
    for trace in tracesToProcess:
        df = trace.generateDriftData()
        file_path = os.path.join(driftPath, trace.drift.scan_name + '.csv')
        df.to_csv(file_path, index=False)
        logging.drift(f'File {trace.drift.scan_name} successfully saved to {driftPath}')