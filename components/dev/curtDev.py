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


from dev.loadDev import LoadDev
from dev.device import Device


class CurtDev(LoadDev):
	def __init__(self,  name,  host, influx=False, reader=None):
		LoadDev.__init__(self,  name,  host, influx, reader)
		
		self.devtype = "Curtailable"
		self.onOffDevice = False

		self.originalConsumption = {}

	def timeTick(self, time, deltatime=0):
		self.prunePlan()

		self.lockState.acquire()
		self.originalConsumption = dict(self.consumption)

		# Perform curtailment / load shedding
		if not self.strictComfort:
			for c in self.commodities:
				#see if we need to override by lower planning:
				if self.smartOperation and c in self.plan and len(self.plan[c]) > 0:
					if self.onOffDevice:
						if self.plan[c][0][1].real < 0.001 and self.plan[c][0][1].real > -0.001:
							self.consumption[c] = complex(0.0, 0.0)
					else:
						p = self.plan[c][0][1]
						#check for up / down:
						if self.consumption[c].real > 0.0001:
							self.consumption[c] = complex(max(0.0, min(self.consumption[c].real, p.real)), 0.0)
						else:
							self.consumption[c] = complex(min(0.0, max(self.consumption[c].real, p.real)), 0.0)

		self.lockState.release()
				
	def logStats(self, time):
		LoadDev.logStats(self, time)

		self.lockState.acquire()
		if self.host.extendedLogging:
			try:
				for c in self.commodities:
					self.logValue("W-power.original.c." + c, self.originalConsumption[c].real)
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
		r['onOffDevice'] = self.onOffDevice
		r['originalConsumption'] = self.originalConsumption
		self.lockState.release()

		return r