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

class CongestionPoint():
	def __init__(self):
		self.commodities = []

		self.upperLimits = {}
		self.lowerLimits = {}

	def setUpperLimit(self, c, limit):
		self.upperLimits[c] = limit
		if c not in self.commodities:
			self.commodities.append(c)

	def setLowerLimit(self, c, limit):
		self.lowerLimits[c] = limit
		if c not in self.commodities:
			self.commodities.append(c)

	def hasUpperLimit(self, c):
		return c in self.upperLimits

	def hasLowerLimit(self, c):
		return c in self.lowerLimits

	def getUpperLimit(self, c):
		if c in self.upperLimits:
			return self.upperLimits[c]

	def getLowerLimit(self, c):
		if c in self.lowerLimits:
			return self.lowerLimits[c]

	# FIXME: We should implement something to check whether the constraints are met in real-time in the future.
	# FIXME 	For now we just use this class as a placeholder for input into the controller