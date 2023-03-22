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


from ctrl.thermal.thermalBufConvCtrl import ThermalBufConvCtrl
from ctrl.auction.thermal.thermalBufConvAuctionCtrl import ThermalBufConvAuctionCtrl

# TimeShiftable controller
class ThermalPaBufConvCtrl(ThermalBufConvCtrl, ThermalBufConvAuctionCtrl):
    def __init__(self,  name,  dev,  ctrl,  host):
        ThermalBufConvAuctionCtrl.__init__(self,  name, None, None, None)
        ThermalBufConvCtrl.__init__(self,   name,  dev,  ctrl,  host)

        self.useEventControl = False
        
        self.devtype = "BufferConverterController"
       
    def preTick(self, time, deltatime=0):
        ThermalBufConvCtrl.preTick(self, time)
        ThermalBufConvAuctionCtrl.preTick(self, time)
        
    def timeTick(self, time, deltatime=0):
        ThermalBufConvCtrl.timeTick(self, time)
        ThermalBufConvAuctionCtrl.timeTick(self, time)