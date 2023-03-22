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

from itertools import islice
import os

class ServerCsvReader():
	def __init__(self, dataSource=None, timeBase=60, timeOffset=None, host=None):
		# params
		self.dataSource = dataSource
		self.timeBase = timeBase
		self.timeOffset = timeOffset

		self.rcache = []
		self.rcacheStart = -1
		self.rcacheSize = int((32 * 24 * 3600) / self.timeBase)

		self.cacheFuture = True  # Allow to cache future data. Useful in case of given simulation data
		self.host = host  # Above feature requires also a host to know wha tis the future

		# Check if the datasource exists
		if dataSource != None:
			assert (os.path.isfile(self.dataSource))  # Check if the file exists

	def readValue(self, time, value=None, timeBase=None, tags=None):
		if timeBase == -1 or timeBase == None:
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
				return total / float(timeBase / self.timeBase)
			except:
				return None  # Gaps in data

		return val

	def readValues(self, startTime, endTime, value=None, timeBase=None, tags=None):
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
		if (value < 0 or value >=  len(self.rcache) ) and self.rcacheStart > -1:
			assert(False) # Data point does not exist!

		# Data does not exist
		if time < self.timeOffset:
			return 0.0 # Could also return None, but it seems that 0 is less likely to break algorithms

		line = int(time / self.timeBase)

		if True: #try:
			if self.rcacheStart == -1 or line < self.rcacheStart or line >= (self.rcacheStart + self.rcacheSize):

				# delete cache
				# FIXME: This can be done more efficiently, but we don't expect to often go back in time
				self.rcache = {}
				self.rcacheStart = -1

				if not self.cacheFuture and time > self.host.time():
					return None
				else:
					if not self.cacheFuture and time + self.rcacheSize * self.timeBase > self.host.time():
						# We should not retrieve futuristic data:
						hostTime = self.host.time()
						startTime = (hostTime - (hostTime % self.timeBase)) - (self.rcacheSize * self.timeBase) + self.timeBase

						self.rcache = self.retrieveValues(startTime, startTime + self.rcacheSize * self.timeBase, value, tags)

						self.rcacheStart = int(startTime / self.timeBase)
					else:
						# read data
						self.rcache = self.retrieveValues(time, time + self.rcacheSize * self.timeBase, value, tags)
						self.rcacheStart = line

			val = self.rcache[value][(line - self.rcacheStart)]

			if val == None:  # In this case, no intermediate point exists
				val = 0

			return val
		else: #except:
			return 0.0

	def flushCache(self):
		# In case the cache needs to be flushed
		self.rcache = {}
		self.rcacheStart = -1


	def retrieveValues(self, startTime, endTime = None, value = None, tags = None):
		startTime += self.timeOffset
		endTime += self.timeOffset

		# Note, in this context the value is the filename
		startLine = int(startTime / self.timeBase)
		endLine = None

		if endTime != None and startTime != endTime:
			endLine = int(endTime / self.timeBase)

		# Now read the data
		with open(self.dataSource,'r') as f:  # https://stackoverflow.com/questions/1767513/read-first-n-lines-of-a-file-in-python
			tmpCache = list(islice(f, startLine, endLine))
		f.close()

		result = []
		for i in range(len(tmpCache[0].split(';'))):
			result.append([])

		for l in tmpCache:
			ln = l.split(';')
			cnt = 0
			for cell in ln:
				try:
					result[cnt].append(float(cell))
				except:
					result[cnt].append(0.0)
					print("ERROR ERROR ", cell, self.dataSource)
				cnt += 1


		return result