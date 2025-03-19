# Copyright 2025 University of Twente

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from dev.device import Device

from util.influxdbReader import InfluxDBReader
from util.clientCsvReader import ClientCsvReader

import util.helpers
import math

class SereneBoilerDev(Device):	
	def __init__(self,  name,  host, influx=False, reader=None, readerFlow=None):
		Device.__init__(self,  name,  host)
		self.devtype = "Eboiler"
		
		# NOTE: We base the development of the boilerdevice based on the timeshifters as we want to shift the moment of turning on.

		# The boiler works slightly different. The idea here is as follows: 
		# The jobs specify the times in which no hot water is demanded, but we need to find a moment to turn it on.
		# After we turn it on, we keep it powered till the next job to ensure hot water
		# This way we try to plan the preheating bulk. The remainder of the consumption (ourside jobs) will be based on historical data (from load device)

		#params
		

		self.currentJobIdx = -1
		self.currentJob = {}
		self.available = False
		self.jobProgress = 0

		# TouchTable tests
		self.timeTillDeadline = 0

		#other
		self.jobs = []

		# persistence
		if self.persistence != None:
			self.watchlist += ["jobs", "currentJobIdx", "currentJob", "available", "jobProgress"]
			self.persistence.setWatchlist(self.watchlist)



		### Specific settings for the eboiler

		# next to consumption we surely need to incorporate flow
		self.flowrate = 0

		# A rather worst case setup with 2.5hrs running at 1kW to heat up the water
		# We need to alter this based on the observations per boiler / make it self learning
		self.profile = [complex(1000, 0), complex(1000, 0), complex(1000, 0), complex(1000, 0), complex(1000, 0), complex(1000, 0), complex(1000, 0), complex(1000, 0), complex(1000, 0), complex(1000, 0)]
		
		self.timeBase = 900 		# For now we use 15 min intervals
		self.powerSetting = False 	# This flag will indicate whether the boiler should be turned on or not.

		# From a loaddev to acquire a load profile with forecasts
		#params
		self.filename = None # for the active power
		self.filnameFlow = None
		self.column = -1
		self.scaling = 1.0

		self.reader = reader
		self.readerFlow = readerFlow
		self.influx = influx
		self.infuxTags = None

	def startup(self):
		assert(self.strictComfort) # For now this device only will work in strictComfort mode
		
		self.jobs.sort()

		self.lockState.acquire()
		#find the current job
		i = -1
		for job in self.jobs:
			if job[1]['startTime'] >= self.host.time():
				break
			else:
				i += 1
		self.currentJobIdx = i

		for c in self.commodities:
			self.consumption[c] = complex(0.0, 0.0)

		assert(len(self.commodities)==1) #
		self.commodity = self.commodities[0]

		if self.host.timeBase != self.timeBase:
			self.profile= util.helpers.interpolatetb(self.profile, self.timeBase, self.host.timeBase)
			self.timeBase = self.host.timeBase


		# From a loaddev
		if self.reader == None:
			if self.influx:
				# FIXME: Need to adjust the readers to read the correct data from IECON
				self.reader = InfluxDBReader(self.host.db.prefix+self.type, timeBase=self.timeBase, host=self.host, database=self.host.db.database, value = "W-power.real.c."+self.commodities[0])
				self.readerFlow = InfluxDBReader(self.host.db.prefix+self.type, timeBase=self.timeBase, host=self.host, database=self.host.db.database, value = "W-power.real.c."+self.commodities[0])
				if self.infuxTags is None:
					self.reader.tags = {"name": self.name}
					self.readerFlow.tags = {"name": self.name}
				else:
					self.reader.tags = self.infuxTags
			elif self.filename is not None:
				self.reader = ClientCsvReader(dataSource=self.filename, timeBase=self.timeBase, column=self.column, timeOffset=self.timeOffset, host=self.host)
				if self.filnameFlow is not None
					self.readerFlow = ClientCsvReader(dataSource=self.filenameFlow, timeBase=self.timeBase, column=self.column, timeOffset=self.timeOffset, host=self.host)


		self.lockState.release()

		Device.startup(self)

	def preTick(self, time, deltatime=0):
		# FIXME:
		# I think we also need to add something here to dynamically add jobs every day to keep this thing running in eternity

		self.prunePlan()
		assert(len(self.commodities)==1)
		c = self.commodity

		self.lockState.acquire()

		if self.available and self.powerSetting:
			#Power usage, so yes, we're progressing
			assert(self.host.timeBase >= self.timeBase)
			assert(self.host.timeBase % self.timeBase == 0)
			self.jobProgress += math.ceil(self.host.timeBase / self.timeBase)
			self.jobProgress = min(self.jobProgress, len(self.profile))

			# eboiler changes, keep it on as soon as we have had a power event
			self.powerSetting = True

		#now check if we need to update the state
		if not self.available:
			if self.currentJobIdx+1 < len(self.jobs):
				if self.jobs[self.currentJobIdx+1][1]['startTime'] <= self.host.time():
					#new job to be triggered:
					self.currentJobIdx += 1
					self.currentJob = self.jobs[self.currentJobIdx][1]
					self.jobProgress = 0

					self.available = True

					self.timeTillDeadline = self.currentJob['endTime'] - self.currentJob['startTime']

					# eboiler changes
					self.powerSetting = False
					
					#new job has to start, lets request a planning for it!
					if self.smartOperation and self.controller is not None:
						self.lockState.release()
						self.zCast(self.controller, 'triggerEvent', "stateUpdate")
						self.lockState.acquire()
			
				# eboiler change
				# otherwise, there is not a job and we should turn on/remain on!
				else:
					self.powerSetting = True
			else:
				self.powerSetting = True
					

		else:
			# Update the time:
			self.timeTillDeadline -= self.host.timeBase
			self.currentJob['endTime'] = self.host.time() + self.timeTillDeadline

			# eboiler changes
			if self.currentJob['endTime'] <= self.host.time():
				self.available = False
				self.powerSetting = True



		# From the loaddev
		# FIXME: This reads the load from Influx/CSV. Needs to be replaced with interface to the actual device
		for c in self.commodities:	
			if self.host.timeBase <= self.timeBase:
				self.consumption[c] = self.readValue(time)
				self.flowrate = self.readValueFlow(time)
			else:
				assert(self.host.timeBase % self.timeBase == 0)
				#resample the profile:
				total = 0.0
				totalf = 0.0
				for i in range(0, int(self.host.timeBase/self.timeBase)): #Forward looking
					total += self.readValue(time+(i*self.timeBase))
					totalf += self.readValueFlow(time+(i*self.timeBase), self.filenameFlow)

				self.consumption[c] = complex((total / (self.host.timeBase/self.timeBase)), 0.0)
				self.flowrate = totalf

		self.lockState.release()

		self.lockState.release()

	def timeTick(self, time, deltatime=0):
		self.prunePlan()
		c = self.commodity

		self.lockState.acquire()
		# NOTE: Currently no preemption is supported, but a forced shutdown is!
		if self.available and self.jobProgress == 0:
			self.keepOn = False

		# planned value available, turn on
		if self.available and self.jobProgress < len(self.profile):
			if self.smartOperation and c in self.plan and len(self.plan[c]) > 0:
				# a planning is available and we should run
				if self.plan[self.commodity][0][1].real >= 1:
					self.powerSetting = True

		# No job, turn off
		if not self.available:
			self.keepOn = True


		# eboiler change
		# Here we can add the code to actually send the command to turn on or off the boiler:
		# FIXME: Needs to be implemented
		if self.powerSetting:
			# here we turn it ON
			pass
		else:
			# here we turn it OFF

		# FIXME: Need to add something here to also log the actual data from the boiler through the platform


		self.lockState.release()

	def logStats(self, time):
		self.lockState.acquire()
		try:
			for c in self.commodities:
				self.logValue("W-power.real.c." + c, self.consumption[c].real)
				if self.host.extendedLogging:
					self.logValue("W-power.imag.c." + c, self.consumption[c].imag)

				if self.smartOperation and c in self.plan and len(self.plan[c]) > 0:
					self.logValue("W-power.plan.real.c."+c, self.plan[c][0][1].real)
					if self.host.extendedLogging:
						self.logValue("W-power.plan.imag.c."+c, self.plan[c][0][1].imag)
		except:
			pass

		if self.host.extendedLogging:
			self.logValue("n-state-progress", self.jobProgress)
			self.logValue("n-state-job", self.currentJobIdx)

			if (self.available):
				self.logValue("b-available", 1)
			else:
				self.logValue("b-available", 0)


		# boiler changes
		try:
			self.logValue("m3s-flowrate.outlet", self.flowrate)
			if self.powerSetting:
				self.logValue("S-powerSetting", 1)
			else:
				self.logValue("S-powerSetting", 0)
		except:
			pass

		self.lockState.release()

	def shutdown(self):
		pass

#### INTERFACING
	def getProperties(self):
		r = Device.getProperties(self) 	# Get the properties of the overall Device class, which already includes global properties

		self.lockState.acquire()
		# Populate the result dict
		r['profile'] = self.profile
		r['available'] = self.available

		r['jobs'] = self.jobs
		r['currentJobIdx'] = self.currentJobIdx
		r['currentJob'] = self.currentJob
		r['jobProgress'] = self.jobProgress

		r['filename'] = self.filename
		r['filenameFlow'] = self.filenameFlow
		r['scaling'] = self.scaling
		r['column'] = self.column

		r['flowrate'] = self.flowrate
		self.lockState.release()

		return r


#### LOCAL HELPERS
	def addJob(self, startTime, endTime):
		self.lockState.acquire()
		errorFlag = False

		startTime -= self.timeOffset
		endTime -= self.timeOffset

		j = {}
		assert(startTime < endTime)
		assert(endTime >= startTime + len(self.profile)*self.timeBase)

		j['startTime'] = startTime
		j['endTime'] = min(endTime,  startTime + 24*3600)

		if len(self.jobs) > 0 and j['startTime'] <= self.jobs[-1][1]['endTime']:
			errorFlag = True
			self.logError("Inconsistent job specification!")

		job = (len(self.jobs),  dict(j))

		if not errorFlag:
			self.jobs.append(job)

		self.lockState.release()

	#Device specific helpers:
	def getProfile(self, timeBase):
		r = self.profile
		if timeBase != self.timeBase:
			r = util.helpers.interpolatetb(r, self.timeBase, timeBase)
		return r


#### LOCAL HELPERS LOADDEV
	def readValue(self, time, filename=None, timeBase=None):
		if timeBase is None:
			timeBase = self.timeBase

		r = self.reader.readValue(time, timeBase=timeBase)
		
		if r is not None:
			r = r  * self.scaling

		return r

	def readValues(self, startTime, endTime, filename=None, timeBase=None):
		if timeBase is None:
			timeBase = self.timeBase

		result = []
		time = startTime
		while time < endTime:
			result.append(self.readValue(time, None, timeBase))
			time += timeBase

		return result

	# Flow rate reading
	def readValueFlow(self, time, filename=None, timeBase=None):
		if timeBase is None:
			timeBase = self.timeBase

		r = self.readerFlow.readValueFlow(time, timeBase=timeBase)
		
		if r is not None:
			r = r  * self.scaling

		return r

	def readValuesFlow(self, startTime, endTime, filename=None, timeBase=None):
		if timeBase is None:
			timeBase = self.timeBase

		result = []
		time = startTime
		while time < endTime:
			result.append(self.readValueFlow(time, None, timeBase))
			time += timeBase

		return result