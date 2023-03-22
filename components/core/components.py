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

from dev.loadDev import LoadDev				# Static load device model
from dev.curtDev import CurtDev				# Also a static load, but one that van be turned off (curtailed/shed)
from dev.btsDev import BtsDev				# BufferTimeShiftable Device, used for electric vehicles
from dev.tsDev import TsDev					# Timeshiftable Device, used for whitegoods
from dev.bufDev import BufDev				# Buffer device, used for storage, such as batteries
from dev.bufConvDev import BufConvDev		# BufferConverter device, used for heatpumps with heat store

from dev.electricity.solarPanelDev import SolarPanelDev			# Solar panel
from dev.thermal.solarCollectorDev import SolarCollectorDev 	# solar collector

# Thermal Devices
from dev.thermal.zoneDev2R2C import ZoneDev2R2C
from dev.thermal.zoneDev1R1C import ZoneDev1R1C
from dev.thermal.heatSourceDev import HeatSourceDev
from dev.thermal.thermalBufConvDev import ThermalBufConvDev
from dev.thermal.heatPumpDev import HeatPumpDev
from dev.thermal.combinedHeatPowerDev import CombinedHeatPowerDev
from dev.thermal.gasBoilerDev import GasBoilerDev
from dev.thermal.dhwDev import DhwDev
from ctrl.thermal.thermostat import Thermostat


# Environment
from environment.sunEnv import SunEnv
from environment.weatherEnv import WeatherEnv

from dev.meterDev import MeterDev			# Meter device that aggregates the load of all individual devices


# Controllers
from ctrl.congestionPoint import CongestionPoint	# Import a congestion point
from ctrl.loadCtrl import LoadCtrl			# Static load controller for predictions
from ctrl.curtCtrl import CurtCtrl			# Static Curtailable load controller for predictions
from ctrl.btsCtrl import BtsCtrl    		# BufferTimeShiftable Controller
from ctrl.tsCtrl import TsCtrl				# Timeshiftable controller
from ctrl.bufCtrl import BufCtrl			# Buffer controller
from ctrl.bufConvCtrl import BufConvCtrl 	# BufferConverter

from ctrl.groupCtrl import GroupCtrl		# Group controller to control multiple devices, implements Profile Steering

from ctrl.thermal.thermalBufConvCtrl import ThermalBufConvCtrl

from ctrl.auction.btsAuctionCtrl import BtsAuctionCtrl
from ctrl.auction.tsAuctionCtrl import TsAuctionCtrl
from ctrl.auction.bufAuctionCtrl import BufAuctionCtrl
from ctrl.auction.bufConvAuctionCtrl import BufConvAuctionCtrl
from ctrl.auction.loadAuctionCtrl import LoadAuctionCtrl
from ctrl.auction.curtAuctionCtrl import CurtAuctionCtrl
from ctrl.auction.aggregatorCtrl import AggregatorCtrl
from ctrl.auction.auctioneerCtrl import AuctioneerCtrl
from ctrl.auction.thermal.thermalBufConvAuctionCtrl import ThermalBufConvAuctionCtrl

# Planned Auction controllers, follows same reasoning
from ctrl.plannedAuction.paBtsCtrl import PaBtsCtrl
from ctrl.plannedAuction.paLoadCtrl import PaLoadCtrl
from ctrl.plannedAuction.paCurtCtrl import PaCurtCtrl
from ctrl.plannedAuction.paBufCtrl import PaBufCtrl
from ctrl.plannedAuction.paBufConvCtrl import PaBufConvCtrl
from ctrl.plannedAuction.paTsCtrl import PaTsCtrl
from ctrl.plannedAuction.paGroupCtrl import PaGroupCtrl
from ctrl.plannedAuction.thermal.thermalPaBufConvCtrl import ThermalPaBufConvCtrl

# Import physical network
from flow.el.lvNode import LvNode
from flow.el.lvCable import LvCable
from flow.el.elLoadFlow import ElLoadFlow