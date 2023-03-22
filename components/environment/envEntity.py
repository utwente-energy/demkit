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


from core.entity import Entity

import threading

class EnvEntity(Entity):
	def __init__(self,  name,  host):
		Entity.__init__(self,  name, host)
		
		self.devtype = "environment" #change in the entity self
		self.type = "environment"

		self.supportsForecast = False

		self.lockState = threading.Lock()

	def requestTickets(self, time):
		self.ticketCallback.clear()
		self.registerTicket(self.host.staticTicketPreTickEnvs, 'preTick', register=False)  # preTick


	def preTick(self, time, deltatime=0):
		pass
		
	def timeTick(self, time, deltatime=0):
		pass
	
	def postTick(self, time, deltatime=0):
		pass
	
	def startup(self):
		if self.host != None:
			self.host.addEnv(self)

		Entity.startup(self)
		
	def shutdown(self):
		pass	
	
	def logStats(self, time):
		pass
		
	def logValue(self, measurement,  value, time=None, deltatime=None):
#		Old, code which is more generic, but slower. Kept for reference.
# 		tags = {'devtype':self.devtype,  'name':self.name}
# 		values = {measurement:value}
# 		self.host.logValue(self.type,  tags,  values, time)

		data = self.type+",devtype="+self.devtype+",name="+self.name+" "+measurement+"="+str(value)
		self.host.logValuePrepared(data, time, deltatime)

	def getProperties(self):
		# Get the properties of this device
		r = {}

		self.lockState.acquire()
		r['name'] = self.name
		r['timeBase'] = self.timeBase
		r['devtype'] = self.devtype
		self.lockState.release()

		return r