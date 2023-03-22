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


class Reader():
	def __init__(self, timeBase = 60, column=-1, timeOffset=None, host=None):
		#params
		self.timeBase = timeBase
		self.timeOffset = timeOffset

		self.rcache = {}
		self.rcacheStart = {}
		self.rcacheSize = int((32*24*3600) / self.timeBase)

		self.cacheFuture = True # Allow to cache future data. Useful in case of given simulation data
		self.host = host 		# Above feature requires also a host to know wha tis the future

	def readValue(self, time, value=None, timeBase = None, tags=None):
		if timeBase == -1 or timeBase ==None:
			timeBase = self.timeBase

		val = self.readCache(time, value, tags)

		if val == None:
			return val
		
		if timeBase > self.timeBase:
			try:
				assert (timeBase % self.timeBase == 0)
				# Resample the profile
				total = 0.0
				for i in range(0, int(timeBase / self.timeBase)):  # Forward looking
					total += self.readValue(time + (i * self.timeBase), value, self.timeBase, tags)
				return total / float( timeBase / self.timeBase )
			except:
				return None # Gaps in data

		return val

	def readValues(self, startTime, endTime, value=None, timeBase = None, tags=None):
		if timeBase == -1 or timeBase == None:
			timeBase = self.timeBase

		result = []
		t = startTime
		while t < endTime:
			result.append(self.readValue(t, value, timeBase, tags))
			t += timeBase

		return result

# Internal functions
	def readCache(self, time, value, tags={}):
		if value not in self.rcache:
			self.rcache[value] = []
		if value not in self.rcacheStart:
			self.rcacheStart[value] = -1

		line = int(time/self.timeBase)

		try:
			if len(self.rcache[value]) == 0 or line < self.rcacheStart[value] or line >= (self.rcacheStart[value] + self.rcacheSize):
				# delete cache
				# FIXME: This can be done more efficiently, but we don't expect to often go back in time
				self.rcache[value] = []
				self.rcacheStart[value] = -1

				if not self.cacheFuture and time > self.host.time():
					return None
				else:
					if not self.cacheFuture and time+self.rcacheSize*self.timeBase > self.host.time():
						# We should not retrieve futuristic data:
						hostTime = self.host.time()
						startTime = (hostTime - (hostTime%self.timeBase)) - (self.rcacheSize*self.timeBase) + self.timeBase

						self.rcache[value] = list(self.retrieveValues(startTime, startTime+self.rcacheSize*self.timeBase, value, tags))

						self.rcacheStart[value] = int(startTime/self.timeBase)
					else:
						# read data
						self.rcache[value] = list(self.retrieveValues(time, time+self.rcacheSize*self.timeBase, value, tags))
						self.rcacheStart[value] = line

			val = self.rcache[value][(line - self.rcacheStart[value])]

			if val == None: # In this case, no intermediate point exists in Influx.
				val = 0

			return val
		except:
			return 0

	def flushCache(self, value = None):
		# In case the cache needs to be flushed
		if value is None:
			self.rcache = {}
			self.rcacheStart = {}
		else:
			self.rcache[value] = []
			self.rcacheStart[value] = -1