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


from dev.thermal.thermalDev import ThermalDevice

# Model to
class HeatSourceDev(ThermalDevice):
	def __init__(self,  name,  host):
		ThermalDevice.__init__(self,  name,  host)
		self.devtype = "Source"

		# State variables:
		self.temperature = 60.0 	# in Celsius. This variable will hold the supply temperature of the source

		self.producingPowers = [0, 20000]	# Output power of the source
		self.producingTemperatures = [0, 60.0]	# Output power of the source

		self.zones = []
		self.thermostats = []
		self.dhwTaps = []

		self.capacity = 	0.0
		self.soc = 			0.0
		self.initialSoC = 	0.0

		self.dhwDemand = 0.0
		self.zoneDemand = 0.0

		self.mixHeatCooling = False # Simultaneous heating and cooling

		if self.persistence != None:
			self.watchlist += ["temperature", "soc", "dhwDemand", "zoneDemand"]
			self.persistence.setWatchlist(self.watchlist)

	# Startup is called to initialize the model
	def startup(self):
		self.lockState.acquire()
		assert(len(self.commodities) == 1) # Only one commodity supported for this device (Preferably HEAT)

		self.lockState.release()

		ThermalDevice.startup(self)


	# PreTick is called before the actual time simulation.
	# Use this to update the state based on the state selected in the previous interval
	def preTick(self, time, deltatime=0):
		pass

	# TimeTick is called after all control actions
	def timeTick(self, time, deltatime=0):

		# First check how much demand we have in total for hot water
		self.dhwDemand = self.getDhwDemand(self.producingPowers)

		# Then supply the zones with heat
		producingPowers = list(self.producingPowers)
		producingPowers[0] += self.dhwDemand.real
		producingPowers[-1] += self.dhwDemand.real
		self.zoneDemand = self.getZoneDemand(producingPowers)

		self.lockState.acquire()
		self.consumption[self.commodities[0]] = self.dhwDemand + self.zoneDemand
		self.lockState.release()

	def getDhwDemand(self, producingPowers):
		# check whether we have DHW demand
		if len(self.dhwTaps) == 0:
			return 0.0
		else:
			dhwRequests = self.zGet(self.dhwTaps, 'consumption')
			dhwTotal = 0.0

			for val in dhwRequests.values():
				if val['HEAT'].real > 1:
					dhwTotal += val['HEAT'].real

			# Now supply the heat
			# The general idea is to first supply the taps and if there  is energy left, we can use it to supply the zone
			producedPowerDhw = {}
			producedTemperatureDhw = {}

			consumption = 0.0
			dhwFraction = 0

			# First supply the DHW taps:
			producedTemperatureDhw['HEAT'] = self.producingTemperatures[-1]

			if dhwTotal >= 1:
				dhwFraction = min(1.0, producingPowers[-1]/ float(dhwTotal) )
				consumption = -1 * dhwTotal

			for tap, val in dhwRequests.items():
				if val['HEAT'].real > 1:
					producedPowerDhw['HEAT'] = (val['HEAT'].real * dhwFraction)
				else:
					producedPowerDhw['HEAT'] = 0.0

				self.zSet(tap, 'heatSupply', producedPowerDhw)
				self.zSet(tap, 'heatTemperature', producedTemperatureDhw)

			return consumption

	def getZoneDemand(self, producingPowers):
		if len(self.zones) == 0:
			return 0.0
		else:
			# Check whether we have heat demand of at least one thermostat
			heatDemand = 0
			coolDemand = 0
			heatRequests = self.zGet(self.thermostats, 'heatDemand')
			for val in heatRequests.values():
				if val > 0.1:
					heatDemand += val
				elif val < -0.1:
					coolDemand += val

			# Cutoff the delivery at the capacity of the heatsource
			heatDemand = min(heatDemand, producingPowers[-1])
			coolDemand = max(coolDemand, producingPowers[0])

			# Now supply the heat
			# The general idea is to first supply the taps and if there  is energy left, we can use it to supply the zone
			producedPowerZone = {}
			producedTemperatureZone = {}
			consumption = 0.0
			producedTemperatureZone['HEAT'] = self.producingTemperatures[-1]

			# Heating has priority over cooling
			if heatDemand > 0.1:
				valves = self.zGet(self.zones, 'valveHeat')

				# Calculate the maximum
				totalRequest = 0
				for zone in self.zones:
					if valves[zone] > 0:
						totalRequest += valves[zone]

				for zone in self.zones:
					if valves[zone] > 0:
						producedPowerZone['HEAT'] = (heatDemand / float(totalRequest)) * valves[zone]
					else:
						producedPowerZone['HEAT'] = 0.0

					# transmit the power and temperature to the zones
					self.zSet(zone, 'heatSupply', dict(producedPowerZone))
					self.zSet(zone, 'heatTemperature', producedTemperatureZone)

					# Internal bookkeeping
					consumption -= producedPowerZone['HEAT']

			if coolDemand < -0.1 and (heatDemand <= 0.1 or self.mixHeatCooling):
				valves = self.zGet(self.zones, 'valveHeat')

				# Calculate the maximum
				totalRequest = 0
				for zone in self.zones:
					if valves[zone] > 0:
						totalRequest += valves[zone]

				for zone in self.zones:
					if valves[zone] > 0:
						producedPowerZone['HEAT'] = abs(coolDemand / float(totalRequest)) * valves[zone]
					else:
						producedPowerZone['HEAT'] = 0.0

					# transmit the power and temperature to the zones
					self.zSet(zone, 'heatSupply', dict(producedPowerZone))
					self.zSet(zone, 'heatTemperature', producedTemperatureZone)

					# Internal bookkeeping
					consumption -= producedPowerZone['HEAT']

			if coolDemand >= -0.1 and heatDemand <= 0.1:
				# Turn everything off
				producedPowerZone['HEAT'] = 0.0
				self.zSet(self.zones, 'heatSupply', producedPowerZone)
				self.zSet(self.zones, 'heatTemperature', producedTemperatureZone)

			return consumption

	def logStats(self, time):
		self.lockState.acquire()
		for c in self.commodities:
			self.logValue("W-power.real.c." + c, self.consumption[c].real)
		self.logValue("W-heat.supply.dhwtaps", self.dhwDemand.real )
		self.logValue("W-heat.supply.zones", self.zoneDemand.real )
		self.lockState.release()

#### Function to add thermostats and zones
	def addZone(self, zone):
		self.zones.append(zone)

	def addThermostat(self, thermostat):
		self.thermostats.append(thermostat)

	def addDhwTap(self, dhw):
		self.dhwTaps.append(dhw)


#### INTERFACING TO READ THE STATE BY A CONTROLLER
	# E.G. this is used by a thermostat device to read the current temperature and see if heating is required
	def getProperties(self):
		r = ThermalDevice.getProperties(self) 	# Get the properties of the overall Device class, which already includes global properties

		self.lockState.acquire()
		r['soc'] = self.soc
		r['capacity'] = self.capacity
		self.lockState.release()

		return r