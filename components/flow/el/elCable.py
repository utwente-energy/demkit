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

from flow.edge import Edge

class ElCable(Edge):
	def __init__(self,  name,  flowSim, nodeFrom, nodeTo, host):
		Edge.__init__(self,  name, flowSim, nodeFrom, nodeTo, host)

		self.devtype = "ElectricityCable"
		self.hasNeutral = True
		self.phases = 3

		#bookkeeping
		self.current = [complex(0.0, 0.0)] * (self.phases+1)
		self.flowDirection = [1]  * (self.phases+1)
		#order: C-N-O-N (C=Conductor (diagonal of matrix), N=Next conductor, O=Opposite conductor):
		self.impedance = [complex(0.0, 0.0)]  * (self.phases+1)
		#   _-=-_
		#  / (C) \
		# ((N) (N)) <-- this is a LV cable with 4 conductors. Use your imagination ;-)
		#  \ (O) /
		#   ^-=-^

		# Gaia Excel file values to use:
		# [complex(R,X), complex(R_CC_N, X_CC_N), complex(R_CC_T, X_CC_T), complex(R_CC_N, X_CC_N),]
		# In Dutch, T is "Tegenovergestelde", translating into opposite


		# Same definitions can be used for three phase MV cables because In=0.
		# Reference: "Netten voor distributie van electriciteit" by Phase to Phase, 2012, section 8.2.8
		# https://phasetophase.nl/boek/index.html

		# Precalculated values for speedup (see startup())
		self.scaledImpedance = []

		self.length = None    	#in meters
		self.ampacity = None	#amperes
		self.fuse = 0       	#additional limit

		self.enabled = True #Option to disable the cable.
		self.burned = False
		self.powered = [True]  * (self.phases+1) #Option to indicate the cable is powered, in case of a fault towards the transformer

	def voltageDrop(self, phase):
		if phase == 0 and not self.hasNeutral:
			return complex(0.0, 0.0)

		result = complex(0.0, 0.0)
			
		# Use symmetric idea, should also work for three phase MV.
		for i in self.conductors():
			if not self.hasNeutral:
				i -= 1
			result += self.current[((i+phase)%((self.phases+1)))] * self.scaledImpedance[i]

		return result

	def getLossesPhase(self, phase):
		# Use phase = 0 for neutral conductor
		assert(not ((not self.hasNeutral) and (phase == 0)))  # neutral conductor not available

		return abs((self.voltageDrop(phase) * self.current[phase].conjugate()).real)

	def getLosses(self):
		result = 0.0

		for conductor in self.conductors():
			result += self.getLossesPhase(conductor)

		return result

	def determinePhysicalState(self):
		result = False
		for phase in self.conductors():
			if abs(self.current[phase]) > self.ampacity and self.powered[phase]:
				result = True
				self.burned = True
				self.powered[phase] = False
				if not self.powered[phase]:
					self.logWarning("Phase "+str(phase)+" burned!")
				if phase == 0 and not self.powered[phase]:
					self.powered = [False] * (self.phases+1)
		return result

	def updatePhysicalState(self, prevNode, nextNode):
		for phase in self.conductors():
			try:
				if abs(nextNode.voltage[phase]) - abs(prevNode.voltage[phase]) < 0:
					self.flowDirection[phase] = 1
				else:
					self.flowDirection[phase] = -1
			except:
				pass
			# FIXME: Needs to be cleaned, but this is not functional code, only used for visualizations

		# Check if we are powered
		for phase in self.conductors():
			try:
				# if self.powered[phase]:
				if not self.burned:
					self.powered[phase] = prevNode.powered[phase]
					if not self.powered[phase]:
						self.logWarning("Phase "+str(phase)+" not powered!")
				if phase == 0 and not self.powered[phase]:
					self.powered = [False] * (self.phases+1)
					break
			except:
				pass
			# FIXME: Needs to be cleaned, but this is not functional code, only used for visualizations




	def conductors(self):
		# Convention used here is that the first index is always the neutral conductor,
		# also for nodes without a neutral conductor.
		startIndex = 1
		if self.hasNeutral:
			startIndex = 0

		return range(startIndex, len(self.current))

	def getCableLoad(self):
		assert(self.ampacity > 0)
		load = 0.0
		for conductor in self.conductors():
			if abs(self.current[conductor]) > load:
				load = abs(self.current[conductor])
		return 100*(load / self.ampacity)

	def estimateReliability(self):
		pass

	def checkViolations(self):
		violations = 0
		limit = self.ampacity
		if 0 < self.fuse < self.ampacity:
			limit = self.fuse

		for conductor in self.conductors():
			if abs(self.current[conductor]) > limit:
				violations += 1

		if violations > 0:
			self.logWarning("capacity of "+str(violations)+" conductor(s) violated")
		self.logValue("n-violations.capacity", violations)

	def startup(self):
		# Prepare scaled impedance:
		for i in self.conductors():
			if not self.hasNeutral:
				i -= 1
			imp = self.impedance[i] * (self.length/1000.0)
			self.scaledImpedance.append(imp)

	def timeTick(self, time, deltatime=0):
		pass

	def shutdown(self):
		pass

	def reset(self, restoreGrid = True):
		self.current = [complex(0.0, 0.0)] * (self.phases+1)

		if restoreGrid:
			self.powered = [True] * (self.phases+1)
			self.burned = False

	def logStats(self, time):
		for i in range(1, (self.phases+1)):
			self.logValue("A-current.c.L"+str(i), abs(self.current[i]) * self.flowDirection[i])

		if self.hasNeutral:
			self.logValue("A-current.c.N", abs(self.current[0])  * self.flowDirection[0])

		self.logValue("p-load", self.getCableLoad())
		self.logValue("W-power.losses", self.getLosses())
		self.checkViolations()

