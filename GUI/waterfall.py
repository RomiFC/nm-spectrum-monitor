import os
import re
import shutil
import logging
import pandas as pd
import matplotlib.dates as mdates
import pytz
import numpy as np
from matplotlib import pyplot as plt
from matplotlib import ticker
from datetime import datetime, timedelta
from collections import Counter

from tracedata import *

def _mkdir(path: str, subfolder: str | list[str] | tuple[str]):
    if type(subfolder) == str:
        _dir = os.path.join(path, subfolder)
    else:
        _dir = os.path.join(path, *subfolder)
    try:
        os.makedirs(_dir)
        logging.waterfall(f"Folder(s) '{subfolder}' created successfully in {path}")
    except FileExistsError:
        pass
    except OSError as e:
        logging.waterfall(f"Error creating folder: {e}")
    
    return _dir

def makeWaterfalls(frompath, topath, threshold = 100, tz = 'US/Mountain', filetype = '.png', dpi=600):
    """Searches for csv files located in `frompath`, and if there are an amount of csvs with a unique date and receiver information
    in the file name above `threshold`,make a waterfall plot with them. The plot is saved in `topath` as `filetype` and the
    parsed csv files are moved to their own directory.

    This function also generates an "averaged" csv of the entire waterfall plot and drift format version.

    Args:
        frompath (str): File path to check for csvs.
        topath (str): File path to generate waterfall plots and average csvs into, and to archive processed csvs.
        threshold (int): Minimum count of unique csvs to process. Defaults to 100
        tz (str, optional): Timezone string passed to pytz.timezone, can be 'UTC', 'US/(Pacific/Mountain/Central/Eastern)', etc. Defaults to 'US/Mountain'.
        filetype (str, optional): File extension used in matplotlib.pyplot.savefig. Defaults to '.png'.
        dpi (int, optional): Argument passed to matplotlib.pyplot.savefig. Defaults to 600.
    """
    DATE_REGEX = r"(\d{4}-\d{2}-\d{2})"
    TIMEZONE = pytz.timezone(tz)
    CSV_THRESHOLD = threshold
    dateList = []
    datesToProcess = []
    # import data
    trace_files = getAllCsvFiles(frompath)
    # Make a directory for original csvs to move to
    archivedir = _mkdir(topath, 'Archived')

    # Make list of all dates in csv files
    for file_name in trace_files:
        hasDate = re.search(DATE_REGEX, file_name)
        if hasDate:
            date = hasDate.group(1)
            dateList.append(date)
    
    # Count the amount of each unique date TODO: check receiver info from file name
    dateCount = Counter(dateList)
    # If the count is above the threshold, make note of that date in datesToProcess
    for key in dateCount:
        if dateCount[key] > CSV_THRESHOLD:
            datesToProcess.append(key)
    
    # This iteration occurs once for every date in datesToProcess (Once for every date above CSV_THRESHOLD)
    while datesToProcess:
        x = []                                  # Frequency (length n is number of points)
        y = []                                  # Time (length m is number of csvs)
        z = []                                  # Amplitude (shape is m by n)
        dateToProcess = datesToProcess[0]       # Date in YYYY-MM-DD format
        receivers = []                          # All receivers present in csvDate
        receiversToProcess = []                 # All receivers with a count above CSV_THRESHOLD in csvData
        # Make a counter for the different receivers present in the csvs of this date
        for file_name in trace_files:
            hasDate = re.search(DATE_REGEX, file_name)
            csvDate = hasDate.group(1)
            if csvDate == dateToProcess:
                receiver = file_name.split('-')[0]
                receivers.append(receiver)
        receiverCount = Counter(receivers)
        # If a specific receiver is above the threshold, save it in receiversToProcess
        for key in receiverCount:
            if receiverCount[key] > CSV_THRESHOLD:
                receiversToProcess.append(key)
        # For each receiver in receiversToProcess (for this date), parse those csvs, move them, and generate the waterfall plot
        for receiver in receiversToProcess:
            # Extract date information
            _year = dateToProcess.split('-')[0]
            _month = dateToProcess.split('-')[1]
            # Make directory for specific receiver/date combination
            _filename = f'{receiver}-{dateToProcess}-WATERFALL'
            moveToDir = _mkdir(archivedir, (receiver, _year, _month, _filename))

            # Iterate through all csv file names again, if they match date and receiver, parse them
            for file_name in trace_files:
                hasDate = re.search(DATE_REGEX, file_name)
                csvDate = hasDate.group(1)
                if csvDate == dateToProcess and file_name.split('-')[0] == receiver:
                    file_name_joined = os.path.join(frompath, file_name)
                    df = pd.read_csv(file_name_joined, header=None)
                    trace = Trace(df, file_name)
                    if len(x) == 0: # If this is the first element for this date, use its parameters for the dimensions of x/y/z
                        x.append(trace.data.iloc[:, 0].astype(float))
                        z.append(trace.data.iloc[:, 1].astype(float))
                    else: # TODO: check if the dimensions of x/y/z match, extrapolate via padding or interpolate as needed
                        z.append(trace.data.iloc[:, 1].astype(float))
                    dt = datetime.fromisoformat(trace.header.loc['Time'].item()).astimezone(TIMEZONE)
                    y.append(dt)
                    # move the csv to its own directory
                    try:
                        shutil.move(file_name_joined, moveToDir)
                    except FileNotFoundError:
                        logging.waterfall(f"Error: The source file '{file_name_joined}' was not found.")
                        return
                    except PermissionError:
                        logging.waterfall(f"Error: Permission denied to move '{file_name_joined}'.")
                        return
                    except Exception as e:
                        logging.waterfall(f"An unexpected error occurred: {e}")
                        return
            
            # GENERATE WATERFALL PLOT
            wfplotdir = _mkdir(topath, 'Waterfall-Plots')
            wfplotfullpath = _mkdir(wfplotdir, (receiver, _year, _month))
            wfplotfullpathandfilename = os.path.join(wfplotfullpath, _filename + filetype)
            # plot
            fig, ax = plt.subplots(layout='constrained')
            mesh = ax.pcolormesh(x, y, z, shading='nearest', vmin=-80, vmax=-30)
            ax.set_title(f'{_filename}')
            ax.set_xlabel("Frequency (Hz)")
            ax.set_ylabel(f'Time ({TIMEZONE.zone})')
            ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())
            ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
            ax.yaxis.set_major_locator(mdates.HourLocator(interval=4))
            ax.xaxis.set_major_formatter(ticker.EngFormatter(unit=''))
            ax.yaxis.set_major_formatter(mdates.DateFormatter('%H:%M', tz=TIMEZONE))
            ax.invert_yaxis()
            plt.colorbar(mesh, label='Magnitude (dBm)')
            plt.savefig(wfplotfullpathandfilename, dpi=dpi)
            logging.waterfall(f'File {_filename + filetype} successfully saved to {topath}')

            # GENERATE WATERFALL PLOTLY HTML

            # GENERATES AVERAGE CSV
            avgdir = _mkdir(topath, 'Averages')
            fullavgdir = _mkdir(topath, ('Averages', receiver, _year, _month))
            fullavgdriftdir = _mkdir(fullavgdir, ('DRIFT', receiver, _year, _month))
            average = np.array((np.array(x[0][:]), np.mean(z, axis=0)))
            # Create pandas dataframe by using the last collected trace header as the average trace header
            datarow = pd.DataFrame({'index': ['DATA',], 'Value': [np.nan,]})
            avgHeader = pd.concat([trace.header.reset_index(), datarow], ignore_index=True)
            avgData = pd.DataFrame(average.T)
            avgData.columns = ['index', 'Value']
            avgCsvDf  = pd.concat([avgHeader, avgData], ignore_index=True)
            avgCsvDf.columns = [0, 1]
            # Create trace object from average csv dataframe and save to csvs in respective directories
            AvgTrace = Trace(avgCsvDf, f'{receiver}-{dateToProcess}-AVG.csv')
            AvgTraceDrift = AvgTrace.generateDriftData()
            AvgTraceCsvName = AvgTrace.name + '.csv'
            # Recreate scan name with 'D' in type to denote drift format
            AvgTraceCsvDriftName = AvgTrace.drift.scan_name + '.csv'
            # Join file paths and file names
            AvgTraceCsvNameJoined = os.path.join(fullavgdir, AvgTraceCsvName)
            AvgTraceCsvDriftNameJoined = os.path.join(fullavgdriftdir, AvgTraceCsvDriftName)
            # Create csv files
            AvgTrace.trace.to_csv(AvgTraceCsvNameJoined, index=False, header=False)
            logging.waterfall(f'File {AvgTraceCsvName} successfully saved to {fullavgdir}')
            AvgTraceDrift.to_csv(AvgTraceCsvDriftNameJoined, index=False)
            logging.waterfall(f'File {AvgTraceCsvDriftName} successfully saved to {fullavgdriftdir}')

        datesToProcess.remove(dateToProcess)

    logging.waterfall('No more plots to generate.')