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


from costs.costSimulator import CostSimulator

# ``Social'' cost allocation: everyone receives the same share... This also serves as example code. 
class CostSocial(CostSimulator):
	def __init__(self,  name,  host):
		CostSimulator.__init__(self,  name, host)
		self.devtype = "social"
	
	def timeTick(self, time, deltatime=0):
		pass

	def startup(self):
		if self.rootNode == None:
			print("No rootNode set. Please make sure you define "+self.name+".rootNode")
			assert(False)

	def simulate(self, time, deltatime=0):
		# Allocate the losses evenly over the customers
	    losses = self.totalLosses(self.rootNode)
		share = losses / len(self.customers) # share for each customer, i.e., total losses / #customers
		self.allocatedLosses = { c.name : share for c in self.customers } # A customer is a meter or node, but since Python is a mess this works :-)

		self.logStats(time)
            
	def logStats(self, time):
		# Store in database
		for key in sorted(self.allocatedLosses.keys()):
			tags = {'customer': key}
			values = {"n-socialallocloss": self.allocatedLosses[key] }
			self.host.logValue(self.type,  tags,  values)