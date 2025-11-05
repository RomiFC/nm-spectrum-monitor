import os
import re
import shutil
import logging
import pandas as pd
import matplotlib.dates as mdates
import pytz
from matplotlib import pyplot as plt
from matplotlib import ticker
from datetime import datetime, timedelta
from collections import Counter

from tracedata import *

def makeWaterfalls(path, threshold = 100, tz = 'US/Mountain', filetype = '.png', dpi=600):
    """Searches for csv files located in `path`, and if there are an amount of csvs with a unique date and receiver information in the file name above `threshold`, make a waterfall plot with them. The plot is saved in `path` as `filetype` and the parsed csv files are moved to their own directory.


    Args:
        path (str): File path to check for csvs and generate waterfall plot into.
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
    trace_files = getAllCsvFiles(path)

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
        x = []
        y = []
        z = []
        dateToProcess = datesToProcess[0]
        receivers = []
        receiversToProcess = []
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
            # Make directory for specific receiver/date combination
            dirName = f'{receiver}-{dateToProcess}-WATERFALL'
            moveToDir = os.path.join(path, dirName)
            try:
                os.mkdir(moveToDir)
                logging.waterfall(f"Folder '{dirName}' created successfully in the current working directory.")
            except FileExistsError:
                pass
            except OSError as e:
                logging.waterfall(f"Error creating folder: {e}")
            # Iterate through all csv file names, if they match date and receiver, parse them
            for file_name in trace_files:
                hasDate = re.search(DATE_REGEX, file_name)
                csvDate = hasDate.group(1)
                if csvDate == dateToProcess and file_name.split('-')[0] == receiver:
                    file_name_joined = os.path.join(path, file_name)
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
                        print(f"Error: The source file '{file_name_joined}' was not found.")
                    except PermissionError:
                        print(f"Error: Permission denied to move '{file_name_joined}'.")
                    except Exception as e:
                        print(f"An unexpected error occurred: {e}")
            savefigdir  = os.path.join(path, 'Waterfall-Plots')
            try:
                os.mkdir(savefigdir)
                logging.waterfall(f"Folder '{savefigdir}' created successfully in the current working directory.")
            except FileExistsError:
                pass
            except OSError as e:
                logging.waterfall(f"Error creating folder: {e}")
            savefigpath = os.path.join(savefigdir, dirName + filetype)
            # plot
            fig, ax = plt.subplots(layout='constrained')
            mesh = ax.pcolormesh(x, y, z, shading='nearest', vmin=-80, vmax=-30)
            ax.set_title(f'{dirName}')
            ax.set_xlabel("Frequency (Hz)")
            ax.set_ylabel(f'Time ({TIMEZONE.zone})')
            ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())
            ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
            ax.yaxis.set_major_locator(mdates.HourLocator(interval=4))
            ax.xaxis.set_major_formatter(ticker.EngFormatter(unit=''))
            ax.yaxis.set_major_formatter(mdates.DateFormatter('%H:%M', tz=TIMEZONE))
            ax.invert_yaxis()
            plt.colorbar(mesh, label='Magnitude (dBm)')
            plt.savefig(savefigpath, dpi=dpi)
            logging.waterfall(f'File {dirName + filetype} successfully saved to {path}')
        datesToProcess.remove(dateToProcess)

    logging.waterfall('No more plots to generate.')