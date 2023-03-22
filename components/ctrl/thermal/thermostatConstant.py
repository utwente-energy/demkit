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


from ctrl.thermal.thermostat import Thermostat

# Thermostat with constant setpoint for use in e.g. floor heating systems
class ThermostatConstant(Thermostat):
	def __init__(self, name, zone, ctrl, host):
		assert(ctrl == None) # This device does not support an external controller
		Thermostat.__init__(self, name, zone, ctrl, host)

		self.setpoint = None
			
	def startup(self):
		Thermostat.startup(self)

		if self.setpoint is None:
			# No setpoint set, use the average of the jobs
			self.jobs.sort()
			i = -1
			cnt = 0
			total = 0

			for job in self.jobs:
				if job[1]['setpoint'] > 18.0:
					total += job[1]['setpoint']
					cnt += 1

			self.setpoint = round( (total/float(cnt)) * 2.0) / 2.0

		self.temperatureSetpointHeating = self.setpoint
		self.temperatureSetpointCooling = self.setpoint



	def thermostatCtrl(self, time):
		# synchronize zone state:
		self.updateDeviceProperties()
		zoneTemperature = self.devData['temperature']

		if zoneTemperature > self.temperatureSetpointHeating + self.temperatureDeadband[1] and zoneTemperature < self.temperatureSetpointCooling + self.temperatureDeadband[2]:
			self.heatDemand = 0
		else:
			self.heatDemand = self.dev.doPrediction(time, time+self.timeBase, [self.temperatureSetpointHeating], [self.temperatureSetpointCooling], self.dev.minHeat, self.dev.maxHeat, self.timeBase)[0]

		# now set the valve
		self.dev.valveHeat = self.heatDemand

	def initializePredictors(self):
		pass

	def doUpperPrediction(self,  startTime,  endTime):
		result = []
		time = startTime
		while time < endTime:
			# add the sample
			result.append(self.setpoint)
			# Advance time
			time += self.timeBase

		return result

	def doLowerPrediction(self,  startTime,  endTime):
		result = []
		time = startTime
		while time < endTime:
			# add the sample
			result.append(self.setpoint)
			# Advance time
			time += self.timeBase

		return result