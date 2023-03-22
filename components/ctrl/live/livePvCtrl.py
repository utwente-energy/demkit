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


import copy
import threading
from ctrl.loadCtrl import LoadCtrl
from sklearn import linear_model



# FIXME: Inherit from CurtCtrl in the future
# However, for now we omit the option to perform curtailment

class LivePvCtrl(LoadCtrl):
	#Make some init function that requires the host to be provided
	def __init__(self,  name,  dev, ctrl, sun, host):
		LoadCtrl.__init__(self,  name,  dev,  ctrl,  host)

		self.sun = sun
		self.lastModelTraining = -1

		# Temporary overriding
		# self.predictionAdaption = False

		# Model parameters
		self.model = []
		self.maxProduction = [] # Holds the maximum observed production (as negative value!) for each bin
		self.binSize = 1800 # timespan of one bin in the regression model
		self.bins = None # Variable will be set automatically on startup

		self.regressionTimeBase = 60	# in seconds
		self.historySize = 21*24*3600 	# in seconds

		# NOTE: All time indexes here are in UTC!
		# For DEMKit, this works fine as everything works in UTC
		# It is just that we humans need to take care of it when debugging ;-)

		self.lockModel = threading.Lock()
		self.training = False

		if self.persistence != None:
			self.watchlist += ["lastModelTraining", "model", "bins", "binSize", "regressionTimeBase", "historySize"]
			self.persistence.setWatchlist(self.watchlist)

	def startup(self):
		self.bins = int(86400/self.binSize) # 1 day = 86400 seconds

		LoadCtrl.startup(self)

		if self.lastModelTraining < self.host.time() - 24*3600:
			if self.lastModelTraining == -1:
				self.trainModel()
			else:
				self.runInThread('trainModel')

	def timeTick(self, time, deltatime=0):
		LoadCtrl.timeTick(self, time)

		# Retrain the model if it is too "old" (1 day now)
		if self.lastModelTraining < self.host.time() - 24*3600 and not self.training:
			self.training = True
			self.runInThread('trainModel')



#### PREDICTION CODE
	def doPrediction(self,  startTime,  endTime, adapt=False):
		# Get the sun prediction
		sunPrediction = copy.deepcopy( self.zCall(self.sun, 'doPrediction', startTime , endTime, self.timeBase) )
		result = self.predictProduction(sunPrediction, startTime,  endTime)
		return result


### Training the model based on the historical data
	def trainModel(self):
		self.lastModelTraining = self.host.time()

		self.updateDeviceProperties()
		time = self.host.time()
		time -= time%(24*3600) # Align data to start of a day

		# Step 1: get historical data of the PV panel:
		pvData = list(self.zCall(self.dev, 'readValues', time - self.historySize, time, None, self.regressionTimeBase ) )

		# Step 2: Get historical weather data from the sun object
		ghi = list(self.zCall(self.sun, 'readValues', time - self.historySize, time, "irradiationGHI", self.regressionTimeBase ) )
		dni = list(self.zCall(self.sun, 'readValues', time - self.historySize, time, "irradiationDNI", self.regressionTimeBase ) )

		pvData = list(pvData[0:len(ghi)])

		# Do some magic here, PV training model
		# Split the data in bins of an hour (or configurable)
		# Might want to lower the timebase when getting data for more points.

		# See: https://stackoverflow.com/questions/11479064/multiple-linear-regression-in-python

		# Create the lists
		maxProduction = [0] * self.bins
		predBins = []
		prodBins = []
		for i in range(0, self.bins):
			predBins.append([])
			prodBins.append([])

			# Add the trivial solution: No irradiance is no production:
			prodBins[i].append(0.0)
			predBins[i].append([0.0, 0.0])

		assert(len(pvData) == len(ghi) == len(dni))

		for i in range(0,len(ghi)):
			# Check if we have data in all vectors
			b = int( ( (i*self.regressionTimeBase) % 86400 ) / self.binSize ) # selecting the right bin b


			if ghi[i] is None:
				ghi[i] = 0
			if dni[i] is None:
				dni[i] = 0
			if pvData[i] is None:
				pvData[i] = 0

			# Append data to the right vector
			prodBins[b].append(pvData[i].real)
			predBins[b].append([ghi[i], dni[i]])

			# Select the maximum observed production for a given bin
			if pvData[i].real < maxProduction[b]:
				maxProduction[b] = pvData[i].real

		self.lockModel.acquire()

		# Now apply a linear regression:
		self.model = []
		for b in range(0, self.bins):
			learning = linear_model.LinearRegression()
			learning.fit(predBins[b], prodBins[b])

			# Save the data
			self.model.append(list(learning.coef_))

		# Copy the production list:
		self.maxProduction = list(maxProduction)

		self.lockModel.release()
		self.training = False


	def predictProduction(self, sunData, startTime, endTime):
		result = []

		time = startTime
		idx = 0

		self.lockModel.acquire()

		while time < endTime:
			b = int( ( time % 86400 ) / self.binSize ) # selecting the right bin b
			result.append(min(0, max(sunData[idx]['GHI']*self.model[b][0] + sunData[idx]['DNI']*self.model[b][1], self.maxProduction[b]) ) )

			time += self.timeBase
			idx += 1

		self.lockModel.release()

		return result
