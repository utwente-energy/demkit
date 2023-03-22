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


from dev.bufDev import BufDev

import math

# Buffer device
class VirtualBufDev(BufDev):
	def __init__(self,  name,  host, meter = None, ctrl = None, congestionPoint = None):
		BufDev.__init__(self, name,  host, meter = None, ctrl = None, congestionPoint = None)
		self.devtype = "VirtualBuffer"

		# FIXME needs extensions for time varying capacities
		# FIXME perhaps also time varying power?

	def requestTickets(self, time):
		# Virtual buffers are controlled by the parent bufDevMerger
		self.ticketCallback.clear()

	# def startup(self):
	# 	BufDev.startup(self)

		# Added parts

	# def preTick(self, time, deltatime=0):
	# 	# Virtual devices do not act on regular preTicks
	# 	pass
	#
	# def virtualPreTick(self, time, deltatime=0):
	# 	# Instead, the hypervisor (sticking to virtualization terminology) can trigger this function
	# 	BufDev.preTick(self, time)
	#
	#
	def timeTick(self, time, deltatime=0):
		# Virtual devices do not act on regular preTicks
		BufDev.timeTick(self, time, deltatime)
		self.ticketCallback.clear()
	#
	# def virtualTimeTick(self,  time):
	# 	# Instead, the hypervisor (sticking to virtualization terminology) can trigger this function
	# 	BufDev.timeTick(self, time)



	# HACK
	# FIXME: We do need a better way for online control anyway
	# def onlineControl(self):
	# 	BufDev.onlineControl(self)
	# 	try:
	# 		self.lockState.release()
	# 	except:
	# 		pass
	# Other functions are inherited, ensuring that the virtual device model is as similar as possible to normal devices, such that the controllers can remain the same