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



from flow.flowEntity import FlowEntity

class FlowSimulator(FlowEntity):
	def __init__(self,  name,  host):
		FlowEntity.__init__(self, name, host)
		
		self.devtype = "flowsim"
		
		self.rootNode = None
		self.nodes = []
		self.edges = []

		self.host.addFlow(self)

	def simulate(self, time, deltatime=0):
		pass
		
	def startup(self):
		self.reset()
		
	def shutdown(self):
		pass	
	
	def reset(self, restoreGrid = True):
		self.resetNodes(restoreGrid)
		self.resetEdges(restoreGrid)
	
	def resetNodes(self, restoreGrid = True):
		for node in self.nodes:
			node.reset(restoreGrid)
		
	def resetEdges(self, restoreGrid = True):
		for edge in self.edges:
			edge.reset(restoreGrid)
		
	def logStats(self, time):
		#all nodes:
		for node in self.nodes:
			node.logStats(time)
		
		#all edges:
		for edge in self.edges:
			edge.logStats(time)
			
	def callOnTree(self, func, *args):
		assert(self.rootNode != None)
		
		#prepare data collection
		d = {}
		d['edges'] = []
		d['nodes'] = []
		
		#call function on the rootnode
		if hasattr(self.rootNode, func):
			r = getattr(self.rootNode, func)(*args)
			d['nodes'].append(r)
		
		# Start the recursive calls
		self.callOnSection(self.rootNode, None, d, func, *args)
		
		#and return results
		return d

	
	def callOnSection(self, thisNode, prevNode, d, func, *args):
		for edge in thisNode.edges:
			nextNode = edge.otherNode(thisNode)             
			if nextNode != prevNode and edge.enabled == True:
				# Check if this edge has the function we are looking for
				if hasattr(edge, func):
					r = getattr(edge, func)(*args)
					d['edges'].append(r)

				# Check if this node has the function we are looking for
				if hasattr(nextNode, func):
					r = getattr(nextNode, func)(*args)
					d['nodes'].append(r)
		
				# Recursive call
				self.callOnSection(nextNode, thisNode, d, func, *args)