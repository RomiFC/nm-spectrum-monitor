import os
import re
import shutil
import logging
import pandas as pd
import matplotlib.dates as mdates
import pytz
import numpy as np
import plotly.express as px
from matplotlib import pyplot as plt
from matplotlib import ticker
from datetime import datetime, timedelta
from collections import Counter, defaultdict

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
    except Exception as e:
        logging.waterfall(f'{type(e).__name__}: {e}')
    
    return _dir

def _makeUniquePath(path: str) -> str:
    """
    If path exists, append an integer before the file extension.
    Example:
        file.png -> file1.png -> file2.png ...
    """
    if not os.path.exists(path):
        return path

    base, ext = os.path.splitext(path)
    i = 1
    while True:
        new_path = f"{base}{i}{ext}"
        if not os.path.exists(new_path):
            return new_path
        i += 1

def regenerateWaterfalls(frompath:str, topath:str, threshold:int = 100, tz:str = 'US/Mountain', filetype:str = '.png', dpi:int=600, moveFlag:bool=False, makeMatpl:bool=True, makePlotly:bool=True, makeAvg:bool=True):
    folders_with_csv = []
    for dirpath, dirnames, filenames in os.walk(frompath):
        if any(filename.lower().endswith('.csv') for filename in filenames):
            folders_with_csv.append(dirpath)
    for folder in folders_with_csv:
        makeWaterfalls(folder, topath, threshold, tz, filetype, dpi, moveFlag=False, makeMatpl=makeMatpl, makePlotly=makePlotly, makeAvg=makeAvg)

def makeWaterfalls(frompath:str, topath:str, threshold:int = 100, tz:str = 'US/Mountain', filetype:str = '.png', dpi:int=600, moveFlag:bool=True, makeMatpl:bool=True, makePlotly:bool=True, makeAvg:bool=True):
    """Searches for csv files located in `frompath`, and if there are an amount of csvs with a unique date and receiver information
    in the file name above `threshold`, make a waterfall plot with them. A plot will only be made if all csv entries have a matching
    start frequency, stop frequency, receiver, date, and number of sweet points. The plot is saved in `topath` as `filetype` and the
    parsed csv files are moved to their own directory if `moveFlag` is true.

    This function also generates an "averaged" csv of the entire waterfall plot and drift format version.

    Args:
        frompath (str): File path to check for csvs.
        topath (str): File path to generate waterfall plots and average csvs into, and to archive processed csvs.
        threshold (int): Minimum count of unique csvs to process. Defaults to 100
        tz (str, optional): Timezone string passed to pytz.timezone, can be 'UTC', 'US/(Pacific/Mountain/Central/Eastern)', etc. Defaults to 'US/Mountain'.
        filetype (str, optional): File extension used in matplotlib.pyplot.savefig. Defaults to '.png'.
        dpi (int, optional): Argument passed to matplotlib.pyplot.savefig. Defaults to 600.
        moveFlag (bool, optional): Determines whether or not to move parsed trace csvs. Defaults to True.
        makeMatpl (bool, optional): Determines whether or not to generate matplotlib waterfall. Defaults to True.
        makePlotly (bool, optional): Determines whether or not to generate plotly.js waterfall. Defaults to True.
        makeAvg (bool, optional): Determines whether or not to generate average trace. Defaults to True.
    """
    if not any([makeMatpl, makePlotly, makeAvg]):
        logging.waterfall('Error: At least one argument of makeMatpl, makePlotly, and makeAvg, must be true.')
        return

    DATE_REGEX = r"(\d{4}-\d{2}-\d{2})"
    TIMEZONE = pytz.timezone(tz)
    CSV_THRESHOLD = threshold
    
    trace_index = defaultdict(list)

    for file_name in getAllCsvFiles(frompath):
        file_path = os.path.join(frompath, file_name)

        try:
            df = pd.read_csv(file_path, header=None)
            trace = Trace(df, file_name)

            # Extract metadata
            t_utc = datetime.fromisoformat(
                trace.header.loc['Time'].item()
            ).astimezone(pytz.utc)
            t_local = t_utc.astimezone(TIMEZONE)

            receiver = file_name.split('-')[0]
            date = t_local.date().isoformat()
            start_freq = float(trace.header.loc['Start Frequency'].item())
            stop_freq = float(trace.header.loc['Stop Frequency'].item())
            n_points = float(trace.header.loc['Number of Points'].item())

            key = (
                receiver,
                date,
                start_freq,
                stop_freq,
                n_points,
            )

            trace_index[key].append({
                "time": t_utc,
                "trace": trace,
                "path": file_path,
                "filename": file_name,
            })

        except Exception as e:
            logging.waterfall(f"Failed parsing {file_name}: {e}")

    groupsToProcess = {
        key: traces
        for key, traces in trace_index.items()
        if len(traces) > CSV_THRESHOLD
    }

    if moveFlag:
        archivedir = _mkdir(topath, 'Archived')
    
    for (receiver, date, startFreq, stopFreq, sweepPoints), traces in groupsToProcess.items():

        # Sort traces by true acquisition time
        traces.sort(key=lambda t: t["time"])

        x = []
        y = []
        z = []

        _year, _month, _ = date.split('-')
        _filename = f'{receiver}-{date}-WATERFALL'

        if moveFlag:
            moveToDir = _mkdir(archivedir, (receiver, _year, _month, _filename))

        for entry in traces:
            trace = entry["trace"]

            freq = trace.data.iloc[:, 0].astype(float)
            amp = trace.data.iloc[:, 1].astype(float)

            if len(x) == 0:
                x.append(freq)
            else:
                # Optional grid sanity check
                if len(freq) != len(x[0]) or not np.allclose(freq, x[0]):
                    logging.warning(f'Waterfall frequency grid mismatch - skipping trace {trace.name}')
                    continue

            z.append(amp)
            y.append(entry["time"].astimezone(TIMEZONE))

            if moveFlag:
                try:
                    shutil.move(entry["path"], moveToDir)
                except (FileExistsError, shutil.Error):
                    pass
                except Exception as e:
                    logging.waterfall(f'{type(e).__name__}: {e}')
                    return
            
        # GENERATE WATERFALL PLOT
        if makeMatpl:
            wfplotdir = _mkdir(topath, 'Waterfall-Plots')
            wfplotfullpath = _mkdir(wfplotdir, (receiver, _year, _month))
            wfplotfullpathandfilename = os.path.join(wfplotfullpath, _filename + filetype)
            wfplotfullpathandfilename = _makeUniquePath(wfplotfullpathandfilename)
            # plot
            mpfig, ax = plt.subplots(layout='constrained')
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
        if makePlotly:
            plotlydir = _mkdir(topath, 'Waterfall-html')
            plotlyfullpath = _mkdir(plotlydir, (receiver, _year, _month))
            plotlyfullpathandfilename = os.path.join(plotlyfullpath, _filename + '.html')
            plotlyfullpathandfilename = _makeUniquePath(plotlyfullpathandfilename)
            pfig = px.imshow(
                z,
                x = np.array(x).squeeze(),      # Frequency (must remove leading dimension)
                y = y,                          # Time (datetime)
                origin="upper",                 # matches Matplotlib invert_yaxis()
                aspect="auto",
                zmin=-80,
                zmax=-30,
                color_continuous_scale="Viridis",
            )

            pfig.update_layout(
                title=_filename,
                xaxis_title="Frequency (Hz)",
                yaxis_title=f"Time ({TIMEZONE.zone})",
                coloraxis_colorbar=dict(title="Magnitude (dBm)"),
            )
            pfig.update_xaxes(tickformat="~s")          # x-axis: engineering notation (like EngFormatter) e.g., 1k, 10M, etc.
            pfig.update_yaxes(tickformat="%H:%M")       # y-axis: datetime formatting (HH:MM)
            pfig.write_html(plotlyfullpathandfilename)  # Save to HTML

        # GENERATES AVERAGE CSV
        if makeAvg:
            avgdir = _mkdir(topath, 'Averages')
            fullavgdir = _mkdir(avgdir, (receiver, _year, _month))
            fullavgdriftdir = _mkdir(avgdir, ('DRIFT', receiver, _year, _month))
            average = np.array((np.array(x[0][:]), np.mean(z, axis=0)))
            # Create pandas dataframe by using the last collected trace header as the average trace header
            datarow = pd.DataFrame({'index': ['DATA',], 'Value': [np.nan,]})
            avgHeader = pd.concat([trace.header.reset_index(), datarow], ignore_index=True)
            avgData = pd.DataFrame(average.T)
            avgData.columns = ['index', 'Value']
            avgCsvDf  = pd.concat([avgHeader, avgData], ignore_index=True)
            avgCsvDf.columns = [0, 1]
            # Create trace object from average csv dataframe and save to csvs in respective directories
            AvgTraceCsvNameJoined = os.path.join(fullavgdir, f'{receiver}-{date}-AVG.csv')
            AvgTraceCsvNameJoined = _makeUniquePath(AvgTraceCsvNameJoined)
            AvgTraceCsvName = os.path.basename(AvgTraceCsvNameJoined)
            AvgTraceName, ext = os.path.splitext(AvgTraceCsvName)
            AvgTrace = Trace(avgCsvDf, AvgTraceName)
            # AvgTrace = Trace(avgCsvDf, f'{receiver}-{date}-AVG.csv')
            AvgTraceDrift = AvgTrace.generateDriftData()
            AvgTraceCsvName = AvgTrace.name + '.csv'
            # Recreate scan name with 'D' in type to denote drift format
            AvgTraceCsvDriftName = AvgTrace.drift.scan_name + '.csv'
            # Join drift file paths and file names
            AvgTraceCsvDriftNameJoined = os.path.join(fullavgdriftdir, AvgTraceCsvDriftName)
            AvgTraceCsvDriftNameJoined = _makeUniquePath(AvgTraceCsvDriftNameJoined)
            # Create csv files
            AvgTrace.trace.to_csv(AvgTraceCsvNameJoined, index=False, header=False)
            logging.waterfall(f'File {AvgTraceCsvName} successfully saved to {fullavgdir}')
            AvgTraceDrift.to_csv(AvgTraceCsvDriftNameJoined, index=False)
            logging.waterfall(f'File {AvgTraceCsvDriftName} successfully saved to {fullavgdriftdir}')

    logging.waterfall('No more plots to generate.')