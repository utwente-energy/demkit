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


from util.influxdbReader import InfluxDBReader
from util.clientCsvReader import ClientCsvReader
import util.helpers

from dev.device import Device

class LoadDev(Device):
	# FIXME: Load Device could use a slight cleanup to rely on instantiated readers in the config itself instead
	# FIXME: Readers themselves could also have a cleanup in the interface to make it easier to use
	def __init__(self,  name,  host, influx=False, reader=None):
		Device.__init__(self,  name,  host)
		
		self.devtype = "Load"
		
		#params
		self.filename = None
		self.filenameReactive = None
		self.column = -1
		self.scaling = 1.0

		self.reader = reader
		self.readerReactive = None
		self.influx = influx
		self.infuxTags = None

		# Subtract data if centralized sensors are used
		self.subtractReaders = []
		# Format per entry: {reader: Reader(), reactive: False, scaling: 1}

		# persistence
		if self.persistence != None:
			# self.watchlist += ["consumption", "plan"]
			self.persistence.setWatchlist(self.watchlist)

	def startup(self):
		self.lockState.acquire()
		if self.reader == None:
			if self.influx:
				self.reader = InfluxDBReader(self.host.db.prefix+self.type, timeBase=self.timeBase, host=self.host, database=self.host.db.database, value = "W-power.real.c."+self.commodities[0])
				self.readerReactive = InfluxDBReader(self.host.db.prefix+self.type, timeBase=self.timeBase, host=self.host, database=self.host.db.database, value="W-power.imag.c." + self.commodities[0])
				if self.infuxTags is None:
					self.reader.tags = {"name": self.name}
					self.readerReactive.tags = {"name": self.name}
				else:
					self.reader.tags = self.infuxTags
					self.readerReactive.tags = self.infuxTags
			elif self.filename is not None:
				self.reader = ClientCsvReader(dataSource=self.filename, timeBase=self.timeBase, column=self.column, timeOffset=self.timeOffset, host=self.host)
				if self.filenameReactive is not None and self.readerReactive is None:
					self.readerReactive = ClientCsvReader(dataSource=self.filenameReactive, timeBase=self.timeBase, column=self.column, timeOffset=self.timeOffset, host=self.host)

		self.lockState.release()

		Device.startup(self)

	def preTick(self, time, deltatime=0):
		self.lockState.acquire()
		for c in self.commodities:	
			if self.host.timeBase <= self.timeBase:
				# if self.filenameReactive != None:
				# 	self.consumption[c] = complex(self.readValue(time), self.readValue(time, self.filenameReactive))
				# else:
				self.consumption[c] = self.readValue(time)
			else:
				assert(self.host.timeBase % self.timeBase == 0)
				#resample the profile:
				total = 0.0
				totalr = 0.0
				for i in range(0, int(self.host.timeBase/self.timeBase)): #Forward looking
					total += self.readValue(time+(i*self.timeBase))
					totalr += self.readValue(time+(i*self.timeBase), self.filenameReactive)
				self.consumption[c] = complex((total / (self.host.timeBase/self.timeBase)), (totalr / (self.host.timeBase/self.timeBase)))
		self.lockState.release()

	def timeTick(self, time, deltatime=0):
		self.prunePlan()
				
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
		self.lockState.release()

#### INTERFACING
	def getProperties(self):
		r = Device.getProperties(self) 	# Get the properties of the overall Device class, which already includes global properties

		self.lockState.acquire()
		# Populate the result dict
		r['filename'] = self.filename
		r['filenameReactive'] = self.filenameReactive
		r['scaling'] = self.scaling
		r['column'] = self.column
		self.lockState.release()

		return r

#### LOCAL HELPERS
	def readValue(self, time, filename=None, timeBase=None):
		if timeBase is None:
			timeBase = self.timeBase

		r = self.reader.readValue(time, timeBase=timeBase)
		if self.readerReactive is not None:
			rr = self.readerReactive.readValue(time, timeBase=timeBase)
			r = complex(r, rr)

		# Subtract other readers
		for s in self.subtractReaders:
			v = s['reader'].readValue(time, timeBase=timeBase) * s['scaling']
			if s['reactive'] is True:
				v = complex(0.0, v)

			# subtract:
			r -= v

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