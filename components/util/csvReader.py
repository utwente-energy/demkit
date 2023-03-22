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
from util.reader import Reader
import os

class CsvReader(Reader):
	def __init__(self,  dataSource, timeBase = 900, column = -1, timeOffset=0):
		Reader.__init__(self, timeBase, column, timeOffset)

		#params
		self.dataSource = dataSource
		self.column = column
		self.timeOffset = timeOffset

		# Check if the datasource exists
		if dataSource != None:
			assert(os.path.isfile(self.dataSource)) # Check if the file exists

	def retrieveValues(self, startTime, endTime = None, value = None, tags = None):
		startTime += self.timeOffset
		endTime += self.timeOffset

		# Note, in this context the value is the filename
		startLine = int(startTime / self.timeBase)
		endLine = None

		if endTime != None and startTime != endTime:
			endLine = int(endTime / self.timeBase)

		if value == None:
			value = self.dataSource

		# Now read the data
		with open(value,'r') as f:  # https://stackoverflow.com/questions/1767513/read-first-n-lines-of-a-file-in-python
			tmpCache = list(islice(f, startLine, endLine))
		f.close()

		if self.column is None:
			result = []
			for i in range(tmpCache[0].split(';')):
				result.append([])
			for l in tmpCache:
				ln = l.split(';')
				cnt = 0
				for cell in ln:
					result[cnt].append(float(cell))
					cnt += 1

		if self.column == -1:
			result = []
			for l in tmpCache:
				result.append(float(l))
		else:
			result = []
			for l in tmpCache:
				result.append(float(l.split(';')[self.column]))

		return result