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

class SimHost(Host):
	def __init__(self, name = "host"):
		self.liveOperation = False

		Host.__init__(self, name)

		self.enablePersistence = False

	def startSimulation(self):
		#startup all entities
		Host.startSimulation(self)
		
		#simulate time
		for t in range(0,  self.intervals):
			self.timeTick(self.currentTime)
			self.currentTime = self.currentTime + self.timeBase
		
		#do a soft shutdown
		self.shutdown()
			
	def timeTick(self,  time, absolute = True):
		# Modify the state
		self.executeCmdQueue()
		Host.timeTick(self, time, absolute)

		self.requestTickets(time)
		while(len(self.tickets) > 0):
			self.announceNextTicket(time)


		self.storeStates()
		self.postTickLogging(time)
