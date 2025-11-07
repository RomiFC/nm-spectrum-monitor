import pandas as pd
import os
import re
from enum import Enum

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]

def getAllCsvFiles(path):
    """Searches a directory for csv files, returns a sorted list of those files.

    Args:
        path (string): File path to search for csv files

    Returns:
        list: Sorted list of csv files in the directory
    """
    allFiles = os.listdir(path)
    csvFiles = [f for f in allFiles if f.endswith(".csv")]
    return sorted(csvFiles, key=natural_sort_key)

class Trace:
    DRIFT_SUFFIX = '-D'
    def __init__(self, trace, name):
        """Takes and initializes the trace csv data from the DataFrame passed in `trace`. The data must be in a format that mimics Keysight's trace data, i.e. a header of `Parameter,Value\\n` rows followed by a row labelled `DATA\\n`, and finally, rows containing the `x,y\\n` data points.

        Args:
            trace (DataFrame): Pandas dataframe obtained by calling read_csv() on the file with no header.
            name (string): String containing the csv file name, must be in the format 'RECEIVER-YYYY-MM-DD-#.csv'. Should be the same argument passed to read_csv() to get the 'trace' dataframe.

        Raises:
            TypeError: If 'trace' is not a pandas DataFrame
        """
        if not isinstance(trace, pd.DataFrame):
            raise TypeError('Argument not of type pd.Dataframe')
        self.name = name.replace('.csv', '')
        self.trace = trace

        # Split trace data into two dataframes
        data_index = trace.index[trace[0] == 'DATA'].tolist()[0]
        header = trace.iloc[:data_index]
        data = trace.iloc[(data_index+1):]
        # Sets column 0 to the index column, removes the name of the index column, and renames column 1 to 'Value'
        self.header = header.set_index(0).rename_axis(None).rename(columns={1:'Value'})
        # Resets index column numbers to start at 0
        self.data = data.reset_index(drop=True)

    class Drift:
        def __init__(self, header, data, name):
            """Takes the 'header' and 'data' DataFrames from class Trace and parses the 'DRIFT unified fields' from them. Receiver information is gathered from the file name.

            Args:
                header (DataFrame): Trace.header
                data (DataFrame): Trace.data
                name (string): Trace.name
            """
            self.instrument = 'NMSM'
            self.receiver = name.split('-')[0]
            if 'EMS' in self.receiver:
                self.polarization = 'LV'
            elif 'DFS' in self.receiver:
                self.polarization = 'LV'
                self.scan_az = header.loc['Azimuth'].item()
                self.scan_el = header.loc['Elevation'].item()
            self.intensity_unit = 'dBm'
            self.scan_name = name + Trace.DRIFT_SUFFIX
            self.scan_datetime = header.loc['Time'].item()
            self.frequency = data.loc[:, 0].astype(float) / 1000000 # drift freq is in mhz
            self.intensity = data.loc[:, 1]

        def getDriftDf(self):
            """Formats parameters generated in Drift.__init__ into the DRIFT-compatible format.

            Returns:
                DataFrame: pandas DataFrame in DRIFT-compatible format
            """
            # if 'EMS' in self.receiver:
            #     string = 'instrument,receiver,polarization,intensity_unit,scan_name,scan_datetime,frequency,intensity\n'
            #     string = string + f'{self.instrument},{self.receiver},{self.polarization},{self.intensity_unit},{self.scan_name},{self.scan_datetime},{self.frequency[0]},{self.intensity[0]}\n'
            #     for index in len(self.frequency - 1):
            #         string = string + f',,,,,,{self.frequency[index+1]},{self.intensity[index+1]}'
            # if 'DFS' in self.receiver:
            #     string = 'instrument,receiver,polarization,intensity_unit,scan_name,scan_datetime,scan_az,scan_elfrequency,intensity\n'
            #     string = string + f'{self.instrument},{self.receiver},{self.polarization},{self.intensity_unit},{self.scan_name},{self.scan_datetime},{self.scan_az},{self.scan_el},{self.frequency[0]},{self.intensity[0]}\n'
            #     for index in len(self.frequency - 1):
            #         string = string + f',,,,,,,,{self.frequency[index+1]},{self.intensity[index+1]}'
            if 'EMS' in self.receiver:
                data = {
                    'instrument': self.instrument,
                    'receiver': self.receiver,
                    'polarization': self.polarization,
                    'intensity_unit': self.intensity_unit,
                    'scan_name': self.scan_name,
                    'scan_datetime': self.scan_datetime,
                    'frequency': self.frequency,
                    'intensity': self.intensity
                }
                series_data = {key: pd.Series(value) for key, value in data.items()}
                df = pd.DataFrame(series_data)
            return df

    def generateDriftData(self):
        """Instantiates Trace.Drift and calls Trace.Drift.getDriftDf().

        Returns:
            DataFrame: pandas DataFrame in DRIFT-compatible format
        """
        self.drift = self.Drift(self.header, self.data, self.name)
        return self.drift.getDriftDf()
