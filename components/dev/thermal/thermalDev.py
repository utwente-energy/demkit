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


from dev.device import Device

class ThermalDevice(Device):
	def __init__(self,  name,  host):
		Device.__init__(self,  name, host)
		
		self.devtype = "Thermal" #change in device self
		self.type = "devices"
		
		#state
		self.totalConsumption = 0.0
		self.temperature = 0.0
		self.commodities = ['HEAT']
	
	# def preTick(self, time, deltatime=0):
	# 	pass
	#
	# def timeTick(self, time, deltatime=0):
	# 	pass
	#
	# def postTick(self, time, deltatime=0):
	# 	pass
	#
	# def startup(self):
	# 	pass
	#
	# def shutdown(self):
	# 	pass
	#
	# def logStats(self, time):
	# 	pass

	def getProperties(self):
		# Get the properties of this device
		r = dict(Device.getProperties(self))

		self.lockState.acquire()
		# Populate the result dict
		r['temperature'] = self.temperature
		self.lockState.release()

		return r