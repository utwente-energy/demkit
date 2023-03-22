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

class Node(FlowEntity):
    def __init__(self,  name,  flowSim, host):
        FlowEntity.__init__(self,  name, host)
        
        self.devtype = "node" 
        self.flowSim = flowSim
        
        #register this node to the flowSim and host
        self.flowSim.nodes.append(self)
        
        self.edges = []
        
    def startup(self):
        self.reset()
        
    def shutdown(self):
        pass    
    
    def reset(self, restoreGrid = True):
        pass
    
    def logStats(self, time):
        pass