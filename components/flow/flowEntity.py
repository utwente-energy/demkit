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

class FlowEntity(Entity):
	def __init__(self,  name,  host):
		Entity.__init__(self, name, host)
		
		self.devtype = "flow" 
		self.type = "flow"

		host.addComponent(self)

	def requestTickets(self, time):
		self.ticketCallback.clear()
		self.registerTicket(self.host.staticTicketLoadFlow, 'simulate', register=False)  # timeTick
		self.registerTicket(self.host.staticTicketRTLoadFlow, 'simulate', register=False)  # timeTick

	# def announceTicket(self, time, number):
	# 	if number == 30000:
	# 		self.simulate(time)

	def preTick(self, time, deltatime=0):
		pass

	def timeTick(self, time, deltatime=0):
		pass

	def startup(self):
		pass
		
	def shutdown(self):
		pass	

	def simulate(self, time, deltatime=0):
		pass

	def logValue(self, measurement,  value, time=None, deltatime=None):
# 		tags = {'devtype':self.devtype,  'name':self.name}
# 		values = {measurement:value}
# 		self.host.logValue(self.type,  tags,  values)
		
		data = self.type+",devtype="+self.devtype+",name="+self.name+" "+measurement+"="+str(value)
		self.host.logValuePrepared(data, time, deltatime)