# Copyright 2024 University of Twente, Saxion UAS

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Author: Javier Ferreira Gonzalez


from environment.sunEnv import SunEnv
import pytz
import requests
from util.influxdbReader import InfluxDBReader
from json import loads, dumps
import pandas as pd
from pvlib import location

import threading

from datetime import datetime
import dateutil.parser


class MetnoSunEnv(SunEnv):

    def __init__(self, name, host, reader=None):
        """
            Solar predictions from Met.no API website
        """
        SunEnv.__init__(self, name, host)

        self.timeBase = 60

        self.api_user_agent = ""  # User agent for API requests - see https://developer.yr.no/doc/locationforecast/HowTO/

        # by default take the system location
        self.latitude = host.latitude
        self.longitude = host.longitude

        # Create pvllib object for clear sky
        self.loc = location.Location(latitude=float(self.latitude), longitude=float(self.longitude))

        self.lastUpdate = -1
        self.updateInterval = 6 * 3600  # Limit for now to every 6 hours
        self.maximumDataAge = 48 * 3600  # Maximum age allowed for API data
        self.retrieving = False

        self.dataCache = None  # Storage, also for predictions
        self.dataCacheLock = threading.Lock()

        self.supportsForecast = True

        self.reader = reader

        # Mapping of variables to names in InfluxDB. Should become the standard for new classes to access data from InfluxDB easily
        self.varMapping = {
            "elevation": "deg-elevation",
            "azimuth": "deg-azimuth",
            "zenith": "deg-zenith",
            "irradiationGHI": "Wm2-irradiation.GHI",
            "irradiationDHI": "Wm2-irradiation.DHI",
            "irradiationDNI": "Wm2-irradiation.DNI"
        }

    def preTick(self, time, deltatime=0):

        # Retrieve data from API
        if not self.retrieving and (self.host.time() - self.lastUpdate) > self.updateInterval:
            self.retrieving = True
            self.runInThread('retrieveData')

        result = dict(self.getIrradiation(time))

        # Now unpack the dict:
        self.elevation = result['elevation']
        self.azimuth = result['azimuth']
        self.zenith = result['zenith']

        self.irradiationGHI = result['GHI']
        self.irradiationDHI = result['DHI']
        self.irradiationDNI = result['DNI']

        # Update the current state
        self.currentState = dict(result)

    def getIrradiation(self, time):
        return dict(self.radiationSolcast(time))

    # These radiation functions calculate the radiation values for a specific time
    # FIXME make async
    def radiationSolcast(self, time):

        self.lockState.acquire()

        result = {}

        # FIXME Static data from calculations, should be moved out here
        d = datetime.fromtimestamp(time, tz=pytz.utc)
        result['elevation'] = self.location.solar_elevation(d)
        result['azimuth'] = self.location.solar_azimuth(d)
        result['zenith'] = self.location.solar_zenith(d)

        result['GHI'] = self.irradiationGHI
        result['DHI'] = 0    # Met.no doesnt provide this value
        result['DNI'] = 0    # Met.no doesnt provide this value

        # # Retrieve data from API
        # if (self.host.time() - self.lastUpdate) > self.updateInterval and not self.retrieving:
        # 	self.retrieving = True
        # 	self.runInThread('retrieveData')

        self.dataCacheLock.acquire()
        data = self.dataCache
        self.dataCacheLock.release()

        # self.logDebug("Parsing Met.no data for timestamp: " + str(d) + " " + str(time))

        # Go through the API data to get values for the interval
        try:
            # Go through all the values
            for entry in self.dataCache['properties']['timeseries']:
                if "next_1_hours" in entry['data']:

                    t1 = int(dateutil.parser.parse(entry['time']).timestamp()) - (60 * 60)
                    t2 = int(dateutil.parser.parse(entry['time']).timestamp())

                    if t1 <= time <= t2:

                        # Prepping time and data
                        t = entry['time']  # time
                        ts = datetime.strptime(t, '%Y-%m-%dT%H:%M:%S%z')
                        d = entry['data']['instant']['details']

                        clouds = d['cloud_area_fraction']
                        wind = d['wind_speed']
                        temp = d['air_temperature']

                        # Calculate the clear sky irradiance and ghi
                        pdt = pd.DatetimeIndex([t])
                        cs = self.loc.get_clearsky(pdt)

                        clouds = 1 - (min(100, max(0, (clouds))) / 100)
                        ghi = float(cs.iloc[0]['ghi']) * (0.2 + (clouds * 0.98))

                        result['GHI'] = ghi
                        result['DHI'] = 0  # Met.no doesnt provide this value
                        result['DNI'] = 0  # Met.no doesnt provide this value

                        result['time'] = t1

                        # self.logDebug("  Found entry at " + str(entry['time']) + " " + str(result))

                        self.lockState.release()

                        return dict(result)
        except:
            pass

        # If we reach this, no up to date info was available, most likely an error on the API side.
        # We check whether the data is too old.
        if (self.lastUpdate + self.maximumDataAge) < self.host.time():
            # Data too old, we revert to a worst case situation with a maximum irradiation
            r = self.directIrradiation(result['elevation'], result['azimuth'], result['zenith'], 1367)
            result['GHI'] = 1367
            result['DHI'] = r['DHI']
            result['DNI'] = r['DNI']

        self.lockState.release()

        return dict(result)

    def startup(self):
        self.initializeReaders()

        # Setup the astral location
        self.location.latitude = self.latitude
        self.location.longitude = self.longitude
        self.location.timezone = self.timezone
        self.location.elevation = self.height

        # Initialize the values
        self.retrieveData()
        self.preTick(self.host.time())

        if self.host != None:
            self.host.addEnv(self)

    def retrieveData(self):

        dataCache = None

        # Getting the yr data
        # https://yr-weather.readthedocs.io/en/latest/locationforecast/examples.html
        # Replace with your own User-Agent. See MET API Terms of Service for correct user agents.
        user_agent = {"User-Agent": self.api_user_agent}

        try:
            # Retrieve the yr data
            url = "https://api.met.no/weatherapi/locationforecast/2.0/complete?lat=" + str(self.latitude) + "&lon=" + str(self.longitude)
            r = requests.get(url, headers=user_agent)

            if r.status_code != 200:
                self.logWarning(
                    "Error getting Met.no API data <Met.no>. Errorcode: " + str(r.status_code) + "\t\t" + r.text)
                self.retrieving = False
                return

            data = loads(r.text)

            self.logDebug("Retrieving Met.no data:")
            self.logDebug(url + " - " + str(user_agent))
            self.logDebug(str(data))

        except Exception as e:
            self.logWarning("API Met.no service error. Error:" + str(e))
            self.retrieving = False
            return

        if data is not None:
            self.dataCacheLock.acquire()
            self.dataCache = data
            self.dataCacheLock.release()
            self.lastUpdate = self.host.time()

        self.retrieving = False
        return

    def doPrediction(self, startTime, endTime, timeBase=None):
        if timeBase is None:
            timeBase = self.timeBase
        result = []

        # We can simply use the original function, just loop through all desired time intervals :)
        # For now we do not consider
        time = startTime
        while time < endTime:
            result.append(self.radiationSolcast(time))
            time += timeBase

        return result

    def initializeReaders(self):

        if self.reader is None:
            self.reader = InfluxDBReader(self.host.db.prefix + self.type, timeBase=self.timeBase, host=self.host,
                                         database=self.host.db.database, tags={"name": self.name},
                                         value=self.varMapping["elevation"])

    def readValue(self, time, filename=None, timeBase=None, field=None):

        if field != None:
            filename = field

        r = self.reader.readValue(time, filename, timeBase)
        return r

    def readValues(self, startTime, endTime, filename="elevation", timeBase=None, field=None):

        if field != None:
            filename = field

        result = self.reader.readValues(startTime, endTime, self.varMapping[filename], timeBase)
        return result
