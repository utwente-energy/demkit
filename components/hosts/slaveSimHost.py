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



from hosts.zhost import ZHost
from hosts.host import Host
import time as tm
import random

class SlaveSimHost(ZHost):
	def __init__(self, name, res = None):
		ZHost.__init__(self, name, res)

	def startSimulation(self):
		self.zInit()

		self.zSubscribe()
		self.connState = False

		import threading
		newThread = threading.Thread(target=self.zPoll, args=[])
		newThread.start()

		self.zCall("bus", "connectSlave")
		self.connState = True

		# Start the socket loop
		while True:
			while not self.zGetConnectionState():
				self.connState = False
				tm.sleep(10)

			if self.connState == False:
				self.zCall("bus", "connectSlave")
				self.connState = True

			#self.zPoll()


	def shutdown(self):
		Host.shutdown(self)

		# Properly disconnect from the Bus
		try:
			self.zCall("bus", "disconnectSlave")
		except:
			pass

	def retrieveTicketList(self):
		return self.tickets
