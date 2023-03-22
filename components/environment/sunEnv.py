# Copyright 2023 University of Twente

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from environment.envEntity import EnvEntity
from util.csvReader import CsvReader

import util.helpers
import pytz

import math
from datetime import datetime

from astral import Astral
from astral import Location

class SunEnv(EnvEntity):
	def __init__(self,  name,  host):
		EnvEntity.__init__(self,  name, host)

		self.devtype = "Sun"

		# Environment variables, default is Enschede, NL
		self.latitude = 	52.2215372
		self.longitude = 	6.8936619
		self.timezone = 'Europe/Amsterdam' # This is not a pytz object for Astral!
		self.height = 42

		self.location = Location()

		# Time settings
		self.stdTime = 0 # KNMI data is given for UT (Universal Time), so the longitude is 0.
		self.useInterpolation = True

		# Parameters
		self.rhoGround = 0.2

		# Readable values showing the sun's position, all in degrees:
		self.elevation = 0.0
		self.azimuth = 0.0
		self.zenith = 0.0

		self.irradiationGHI = 0.0	# Global Horizontal Irradiance
		self.irradiationDNI = 0.0	# Direct Normal Irradiance
		self.irradiationDHI = 0.0 	# Diffuse Horizontal Irradiance

		self.currentState = {}

		self.timeBase = 3600 # Default of most weather information sources

		self.irradianceFile = None
		self.irradianceTimeBase = 3600		# Seconds per interval. Default 1 hour for KNMI weather data
		self.irradianceColumn = -1
		self.irradianceReader = None

		self.irradianceDNIFile = None
		self.irradianceDNITimeBase = 3600		# Seconds per interval. Default 1 hour for KNMI weather data
		self.irradianceDNIColumn = -1
		self.irradianceDNIReader = None

		self.irradianceDHIFile = None
		self.irradianceDHITimeBase = 3600		# Seconds per interval. Default 1 hour for KNMI weather data
		self.irradianceDHIColumn = -1
		self.irradianceDHIReader = None

		self.timeOffset = -3600
		if host != None:
			self.timeOffset = host.timeOffset -3600 # KNMI data is in UTC, so we need to subtract one hour in the dataset

		self.irradianceKNMI = True	 # KNMI uses J/cm^2 instead of W/m^2...


		self.reader = None

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
		self.lockState.acquire()
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
		self.lockState.release()

	def getIrradiation(self, time):
		result = {}
		if self.useInterpolation:
			result = dict(self.radiationInterpolation(time))
		else:
			result = dict(self.radiationSimple(time))
		return result

	# These radiation functions calculate the radiation values for a specific time
	def radiationSimple(self, time):
		# Noninterpolated variant
		# Hourly averages do not give appropriate results, so we pick a static time based on the timebase to calculate all values
		# Since the middle of a time interval gives the best representation, this value is used
		result = {}
		modeltime = int(time - (time % self.timeBase) + (self.timeBase / 2))

		d = datetime.fromtimestamp(time, tz=pytz.utc)
		result['elevation'] = self.location.solar_elevation(d)
		result['azimuth'] = self.location.solar_azimuth(d)
		result['zenith'] = self.location.solar_zenith(d)

		result['GHI'] = self.irradianceReader.readValue(modeltime)
		if self.irradianceKNMI:
			result['GHI'] = ( result['GHI'] * 10000 ) / float(self.irradianceTimeBase)

		# Get diffuse and direct irradiance
		if self.irradianceDHIFile != None and self.irradianceDNIFile != None:
			result['DNI'] = self.irradianceDNIReader.readValue(modeltime)
			result['DHI'] = self.irradianceDHIReader.readValue(modeltime)
		else:
			# No files, estimate these values:
			result.update(self.directIrradiation(result['elevation'], result['azimuth'], result['zenith'], result['GHI']) ) # Note, update merges two dicts

		return result

	def radiationInterpolation(self, time):
		result = {}

		d = datetime.fromtimestamp(time, tz=pytz.utc)
		result['elevation'] = self.location.solar_elevation(d)
		result['azimuth'] = self.location.solar_azimuth(d)
		result['zenith'] = self.location.solar_zenith(d)

		t1 = (time - (time%self.timeBase)) - int(self.timeBase/2)
		t2 = (time - (time%self.timeBase)) + int(self.timeBase/2)
		if (time % self.timeBase) >= int(self.timeBase/2):
			t1 += self.timeBase
			t2 += self.timeBase

		assert(t1 <= time <= t2)

		result['GHI'] = util.helpers.interpolatePoint(self.irradianceReader.readValue(t1), self.irradianceReader.readValue(t2), t1, t2, time)
		if self.irradianceKNMI:
			result['GHI'] = ( result['GHI'] * 10000 ) / float(self.irradianceTimeBase)

		# Get diffuse and direct irradiance
		if self.irradianceDNIReader != None and self.irradianceDHIReader != None:
			result['DNI'] = util.helpers.interpolatePoint(self.irradianceDNIReader.readValue(t1), self.irradianceDNIReader.readValue(t2), t1, t2, time)
			result['DHI'] = util.helpers.interpolatePoint(self.irradianceDHIReader.readValue(t1), self.irradianceDHIReader.readValue(t2), t1, t2, time)
		else:
			# No files, estimate these values:
			result.update(self.directIrradiation(result['elevation'], result['azimuth'], result['zenith'], result['GHI']) ) # Note, update merges two dicts

		return result

	def startup(self):
		self.lockState.acquire()
		#initialize the reader
		if self.irradianceReader == None:
			self.irradianceReader = CsvReader(self.irradianceFile, self.irradianceTimeBase, self.irradianceColumn, self.timeOffset)
		if self.irradianceDHIFile != None:
			assert(self.irradiationDHIFile != None)
			self.irradianceDNIReader = CsvReader(self.irradianceDNIFile, self.irradianceDNITimeBase, self.irradianceDNIColumn, self.timeOffset)
			self.irradianceDHIReader = CsvReader(self.irradianceDHIFile, self.irradianceDHITimeBase, self.irradianceDHIColumn, self.timeOffset)

		# Setup the astral location
		self.location.latitude = self.latitude
		self.location.longitude = self.longitude
		self.location.timezone = self.timezone
		self.location.elevation = self.height

		self.lockState.release()

		# Initialize the values
		self.preTick(self.host.time())

		EnvEntity.startup(self)

	def timeTick(self, time, deltatime=0):
		pass
	
	def postTick(self, time, deltatime=0):
		pass
	
	def logStats(self, time):
		self.lockState.acquire()
		self.logValue("Wm2-irradiation.GHI", self.irradiationGHI)
		self.logValue("Wm2-irradiation.DNI", self.irradiationDNI)
		self.logValue("Wm2-irradiation.DHI", self.irradiationDHI)

		self.logValue("deg-elevation", self.elevation)
		self.logValue("deg-azimuth", self.azimuth)
		self.logValue("deg-zenith", self.zenith)
		self.lockState.release()

	def shutdown(self):
		pass	

	def getProperties(self):
		# Get the properties of this device
		r = {}
		r = EnvEntity.getProperties(self)

		return r

##### LOCAL HELPER FUNCTIONS
	def directIrradiation(self, elevation, azimuth, zenith, GHI):
		# Implementation based on the Ruby code published by Javier Goizuta under the MIT License:
		# https://github.com/jgoizueta/solar/blob/master/lib/solar/radiation.rb

		# extraterrestrial horizontal radiation in W/m^2  averaged over the time step
      	# [1991-Duffie pg 37] eq. 1.10.1, 1.10.3

		result = {}
		Gmax = 1367 * math.sin(math.radians(elevation))

		# Determine the clearness index
		clearnessIndex = 0.0
		if Gmax > 0.0:
			clearnessIndex = GHI / Gmax

		# Calculate the diffuse fraction
		# Depends on clearness index and elevation
		# Calculated using this method:
		# 1982 Erbs, Klein, Duffie
		diffuseFraction = 0.165
		if clearnessIndex <= 0.0001:
			diffuseFraction = 0.0
		elif clearnessIndex <= 0.22:
			diffuseFraction = (1.0-0.09*clearnessIndex)
		elif clearnessIndex<= 0.8:
			diffuseFraction = ( 0.9511-0.1604*clearnessIndex + \
						   4.388 * math.pow(clearnessIndex, 2) - \
						   16.638 * math.pow(clearnessIndex, 3) + \
						   12.336 * (math.pow(clearnessIndex, 4)) )

		# irradiance based on this fraction
		DHI =  diffuseFraction * GHI # Diffuse Horizontal Irradiance

		# Beam radiation
		irradiationBeam = GHI - DHI

		# And now calculate DNI based on the elevation of the sun
		# Using this relation:	GHI = DHI + DNI*cos(solar zenith)
		if elevation > 2:
			DNI = min(1367.0, ( irradiationBeam * 1 / math.sin(math.radians(elevation)) ) )

		else:
			DNI = 0.0

		result['DHI'] = DHI
		result['DNI'] = DNI
		return result


	def powerOnPlane(self, inclination, azimuth, time = None, perfect = True):
		# Calculate the direct irradiance on a plane (e.g. solar panel, window)

		# Obtain the current values
		if time is None:
			sunProps = self.currentState
		else:
			if time <= self.host.time() or perfect:
				sunProps = self.getIrradiation(time)
			else:
				sunProps = self.getIrradiation(time)
				sunProps2 =  self.getIrradiation(time - 3600*24)
				for k in sunProps.keys():
					sunProps[k] = 0.5 * sunProps[k] + 0.5*sunProps2[k]

		# NOTE: Azimuth is defined from the north = 0 degrees, running east (i.e. east is 90 degrees).
		if sunProps['GHI'] < 0.001 or sunProps['elevation'] <= 1:
			return 0.0 	# No power (significant) irradiation / avoid division by 0.

		# Calculate Incidence Angle (theta_i)
		planeIncidence = math.degrees( math.acos( \
									math.cos(math.radians(sunProps['zenith'])) * math.cos(math.radians(inclination)) + \
									( math.sin(math.radians(sunProps['zenith'])) * math.sin(math.radians(inclination)) * \
									  math.cos(math.radians(sunProps['azimuth'] - azimuth))	) \
									) )

		# Calculate Gdir
		Gdir = sunProps['DNI'] * math.cos(math.radians(planeIncidence))

		# Calculate the diffuse irradiance (Gdfs)
		factorF = 1 - math.pow( (sunProps['DHI'] / sunProps['GHI']) , 2)

		Gdfs = sunProps['DHI'] * 	( \
						( ( 1 + math.cos(math.radians(inclination))) / 2.0 ) * \
						( 1 + factorF * math.pow(math.sin(math.radians(inclination / 2.0)), 3) ) * \
						( 1 + factorF * math.pow(math.cos(math.radians(planeIncidence)), 2) * math.pow(math.sin(math.radians(sunProps['zenith'])), 3) ) \
						)

		# Ground reflected Irradiance Gref
		Gref = sunProps['GHI'] * self.rhoGround * ( (1 - math.cos(math.radians(inclination))) / 2.0 )

		# Now we can add these and return out results
		return max(0.0, Gdir + Gdfs + Gref)


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

	def doPrediction(self, startTime, endTime, timeBase = None, perfect = False):
		if timeBase is None:
			timeBase = self.timeBase
		result = []

		# FIXME: Could use predictions
		# We can simply use the original function, just loop through all desired time intervals :)
		# For now we do not consider
		time = startTime
		while time < endTime:
			result.append(self.getIrradiation(time))
			time += timeBase

		return result