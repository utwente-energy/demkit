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

from ctrl.auction.auctioneerCtrl import AuctioneerCtrl


class ShAuctioneerCtrl(AuctioneerCtrl):
    def __init__(self,  name,  host):
        AuctioneerCtrl.__init__(self, name, host) #Parent is empty

        self.ohItem = None
        self.ohTarget = None
        self.ohMode = None
        
        self.ctrlMode = 1
            
    def clearMarket(self):    
        #read objectives from OpenHAB
        if self.ohCtrl != None:
            #see if we need islanding
            self.ctrlMode = int(self.host.getOpenHABItem(self.ohCtrl))
        
        if self.ctrlMode == 1:
            self.host.postOpenHABItem(self.ohItem, 0.2)
            self.nextAuction = self.host.time() + self.auctionInterval*self.timeBase 
            return #no control this interval
        
        if self.ctrlMode == 2:
            self.strictComfort = True
            self.islanding = False
            self.discreteBids = True
        if self.ctrlMode == 3:
            self.strictComfort = False
            self.islanding = True
            self.discreteBids = True
        
        if self.ohTarget != None:
            #see if we need islanding
            self.ctrlTarget = int(self.host.getOpenHABItem(self.ohTarget))
            
            self.maxGeneration = -self.ctrlTarget
            self.minGeneration = -self.ctrlTarget

        #Run the auction
        AuctioneerCtrl.clearMarket(self)
        
        #set the price
        if self.ohItem != None:
            #Price transformation
            p = 0.2 + (self.currentPrice / 10000.0)
            s = str.format("{:.2f}", p)
            self.host.postOpenHABItem(self.ohItem, s)
            
        self.logValue("target", self.ctrlTarget)  
        self.logValue("realprice", p)  
        
        #log some data to OpenHAB
 