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

class ClientCsvReader():
	def __init__(self,  dataSource, timeBase = 900, column = -1, timeOffset=0, host=None):

		self.dataSource = dataSource
		self.column = column
		self.timeOffset = timeOffset

		self.host = host
		self.server = None

		assert(self.host is not None) # Needs to attach to a host
		assert(self.column > -1)

		# Attach to a server:
		self.server = self.host.attachClientCsvReader(dataSource, timeBase, timeOffset)

		assert(self.server is not None) # Needs to attach to a server


	# FIXME
	def readValue(self, time, value=None, timeBase=None, tags=None):
		return self.server.readValue(time, self.column, timeBase, tags)

	def readValues(self, startTime, endTime, value=None, timeBase=None, tags=None):
		return self.server.readValues(startTime, endTime, self.column, timeBase, tags)

