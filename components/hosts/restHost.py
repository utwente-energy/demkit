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


from hosts.host import Host
from api.eveApi import EveApi

class RestHost(Host):
	def __init__(self, name="host", port = 5000):
		self.liveOperation = True
		Host.__init__(self, name="host") 
		
		self.enableFlowSim = False
		self.port = port
		self.address = "http://localhost"
		#FIXME: Need some mechanism to obtain the IP Address of the system, for now we hardcode default to localhost. T200


			
	def startup(self):
		Host.startup(self)	
		
		self.restApi = EveApi(self, self.port)

	def timeTick(self, time, absolute = False):
		self.executeCmdQueue()
		if not self.pause:
			Host.timeTick(self, time, absolute)

			self.requestTickets(time)
			while (len(self.tickets) > 0):
				self.announceNextTicket(time)

			self.storeStates()
			self.postTickLogging(time)

		self.executeCmdQueue()
