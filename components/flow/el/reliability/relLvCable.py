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

from flow.el.lvCable import LvCable
from util.csvReader import CsvReader

import math
import numpy

# Steady State := IEC 60287
# Dynamic      := Olsen et al.

# Specific parameters can be found in the MSc thesis of Marius Groen, University of Twente, 2018
# Title: Assessing the Effect of Smart Reinforcement Alternatives on the Expected Asset Lifetime of Low Voltage Networks
# Download: http://essay.utwente.nl/74878/1/Groen_MA_EEMCS.pdf
# And references therein

class RelLvCable(LvCable):
	def __init__(self, name, flowSim, nodeFrom, nodeTo, host):
		LvCable.__init__(self, name, flowSim, nodeFrom, nodeTo, host)

		self.devtype = "ElectricityCable"

		self.enableReliability = True  # enables/disables thermal models for speedup

		# Bookkeeping
		self.hottestSpotTemperature60287 = 0.0
		self.jacketTemperature60287 = 0.0
		self.lossOfLifeFactor60287 = 0.0
		self.lossOfLife60287 = 0.0
		self.reliability60287 = 1.0

		self.hottestSpotTemperatureOlsen = 0.0
		self.steadyStateTemperatureOlsen = 0.0
		self.jacketTemperatureOlsen = 0.0
		self.lossOfLifeFactorOlsen = 0.0
		self.lossOfLifeOlsen = 0.0
		self.reliabilityOlsen = 1.0

		self.soilTemperature = 15.0
		self.conductorTemperatureMax = 55.
		self.jacketTemperatureMax = 45.

		# Default cable: V-VMvKsas 4x95Al by Waskonig
		# General Parameters
		self.soilResistivity = 0.75  # Km/W # Conservative values: = 2.5  # Km/W
		self.installedDepth = 0.6  # m
		self.diameter = 44.2e-3  # m

		self.activationEnergy = 72e3  # J/(mol K)
		self.ratedLife = 40 * 365 * 24 * 3600
		self.ratedHotSpotTemperature = 273.15 + 55

		# IEC 60287 Parameters
		self.thermalResistanceConductorSheath = 0.0  # Km/W
		self.thermalResistanceJacket = 0.294

		# Olsen et al. Parameters
		self.cableSections = []  # See startup()
		self.thermalResistances = []
		self.thermalCapacitances = []
		self.cumulativeResistances = numpy.empty(0)
		self.temperatures = numpy.empty(0)
		self.eigenVectors = numpy.empty(0)
		self.eigenValues = numpy.empty(0)

		# Olsen et al. with Differential Equations
		self.temperaturesDE = numpy.empty(0)
		self.minimalTimeConstant = 0.0
		self.TiCi = numpy.empty(0)
		self.Ti1Ci = numpy.empty(0)

		# Soil Temperature CSV (takes the default temperature if left blank)
		self.soilTempFileName = None
		self.soilTempTimeBase = 60
		self.soilTempReader = None

		# Precalculated Values
		self.lifeScaleParameter = None
		self.thermalResistanceSoil = None
		self.thermalResistanceSoilConservative = None

	def startup(self):
		# Soil Temperature
		if self.soilTempFileName is not None:
			self.soilTempReader = CsvReader(self.soilTempFileName, self.soilTempTimeBase)

		# IEC 60287
		gasConstant = 8.3144598
		self.lifeScaleParameter = self.ratedLife * math.exp(
			-self.activationEnergy / (gasConstant * self.ratedHotSpotTemperature))
		self.thermalResistanceSoil = self.soilResistivity / (2. * math.pi) * math.log(
			self.installedDepth / (self.diameter / 2.))

		# Olsen et al.
		if len(self.cableSections) is 0:
			# Default value

			self.cableSections = [CableSection(0.0, 0.0, 0.0, 0.0, 1, 950.0),       # Al
								  CableSection(5.0, 0.68e6, 15.5e-3, 17.1e-3, 2),   # PVC
								  CableSection(6.0, 2.0e6,  17.1e-3, 18.4e-3, 2),   # EPDM
								  CableSection(0.0, 0.0, 0.0, 0.0, 1, 120.8),       # Copper Screen
								  CableSection(5.0, 0.68e6, 18.4e-3, 22.1e-3, 4),   # PVC
								  CableSection(self.soilResistivity, 1.9e6, 22.1e-3, self.installedDepth, 75)]  # Soil

		for section in self.cableSections:
			for i in range(0, section.numberOfSegments):
				self.thermalResistances.append(section.thermalResistances[i])
				self.thermalCapacitances.append(section.thermalCapacitances[i])

		# Correct for R=0 cases
		for i in range(0, len(self.thermalResistances)):
			if not i < len(self.thermalResistances):
				break
			if not self.thermalResistances[i] > 0.0:
				del(self.thermalResistances[i])
				self.thermalCapacitances[i+1] += self.thermalCapacitances[i]
				del(self.thermalCapacitances[i])

		# Check if parameters are comparable for both models
		sumT60287 = self.thermalResistanceConductorSheath + self.thermalResistanceJacket + self.thermalResistanceSoil
		sumOlsen = sum(self.thermalResistances)

		# DEBUG
		assert abs(sumOlsen-sumT60287) < 0.1

		# Create System Matrix for Olsen Model
		m = len(self.thermalResistances)
		A = numpy.zeros(shape=(m, m))
		T = self.thermalResistances
		C = self.thermalCapacitances

		A[0, 0] = -1/(T[0]*C[0])
		A[0, 1] = 1/(T[0]*C[0])

		for i in range(1, m-1):
			A[i, i + 1] = 1/(T[i]*C[i])
			A[i, i] = -(1 / (T[i]*C[i]) + 1 / (T[i-1]*C[i]))
			A[i, i - 1] = 1/(T[i-1]*C[i])

		A[m-1, m-1] = -(1 / (T[m-1]*C[m-1]) + 1 / (T[m-2]*C[m-1]))
		A[m-1, m-2] = 1/(T[m-2]*C[m-1])

		A = numpy.fliplr(numpy.flipud(A))

		# Calculate Eigen Vectors/Values
		w, v = numpy.linalg.eig(A)
		self.eigenValues = w
		self.eigenVectors = v

		# Precalculate Cumulative Thermal Resistance Vector
		accumulator = 0.0
		result = []
		for resistance in reversed(self.thermalResistances):
			accumulator += resistance
			result.append(accumulator)

		self.cumulativeResistances = numpy.asarray(result)

		# Olsen et al. with Differential Equations
		self.TiCi = numpy.multiply(T, C)
		self.Ti1Ci = numpy.multiply([float('nan')] + T[:-1], C)

		self.minimalTimeConstant = numpy.nanmin(self.TiCi)

		LvCable.startup(self)

	def preTick(self, time, deltatime=0):
		if self.soilTempFileName is not None and self.enableReliability:
			self.soilTemperature = self.soilTempReader.readValue(time, self.soilTempTimeBase)

	def estimateReliability(self):
		# Estimates the reliability of the insulation up to this time interval

		# Speedup
		if not self.enableReliability:
			return

		# Get Hottest Spot Temperature in K
		self.estimateHottestSpotTemperature()
		hotSpotT60287 = 273.15 + self.hottestSpotTemperature60287
		# hotSpotTConservative60287 = 273.15 + self.hottestSpotTemperatureConservative60287
		hotSpotTOlsen = 273.15 + self.hottestSpotTemperatureOlsen

		# Calculate Loss of Life
		gasConstant = 8.3144598
		B = self.activationEnergy / gasConstant
		timeStep = self.host.timeInterval()

		self.lossOfLifeFactor60287 = math.exp(B / self.ratedHotSpotTemperature - B / hotSpotT60287)
		self.lossOfLifeFactorOlsen = math.exp(B / self.ratedHotSpotTemperature - B / hotSpotTOlsen)

		self.lossOfLife60287 = self.lossOfLife60287 + timeStep * self.lossOfLifeFactor60287
		self.lossOfLifeOlsen = self.lossOfLifeOlsen + timeStep * self.lossOfLifeFactorOlsen

		# Calculate Reliability
		weibullBeta = 3.3
		self.reliability60287 = math.exp(
			-(self.lossOfLife60287 / (self.lifeScaleParameter * math.exp(B / self.ratedHotSpotTemperature))) ** weibullBeta)
		self.reliabilityOlsen = math.exp(
			-(self.lossOfLifeOlsen / (
					self.lifeScaleParameter * math.exp(B / self.ratedHotSpotTemperature))) ** weibullBeta)

	def estimateHottestSpotTemperature(self):

		# Get maximum conductor losses
		perPhaseLossMax = 0.0
		for conductor in self.conductors():
			loss = self.getLossesPhase(conductor)
			if loss > perPhaseLossMax:
				perPhaseLossMax = loss

		self.estimateHottestSpotTemperatureOlsen(perPhaseLossMax)

	def estimateHottestSpotTemperature60287(self, perPhaseLossMax):
		# Deprecated, use Olsen in stead to calculate steady state temperatures

		# Model according to IEC 60287
		conductors = len(self.conductors())

		# Normalize to per length losses
		perPhaseLossMax = perPhaseLossMax / self.length

		self.hottestSpotTemperature60287 = self.soilTemperature + perPhaseLossMax * (
				self.thermalResistanceConductorSheath + conductors * (
				self.thermalResistanceJacket + self.thermalResistanceSoil))
		self.jacketTemperature60287 = self.hottestSpotTemperature60287 - perPhaseLossMax * (
				self.thermalResistanceConductorSheath + conductors * self.thermalResistanceJacket)

	def estimateHottestSpotTemperatureOlsen(self, perPhaseLossMax):
		# Model according to Olsen et al.

		# Normalize
		conductors = len(self.conductors())
		loss = conductors * perPhaseLossMax / self.length

		# Calculate Steady State Temperatures
		infTemperatures = self.cumulativeResistances * loss

		# Other Inputs
		if len(self.temperatures) is 0:
			self.temperatures = infTemperatures

		prevTemperatures = self.temperatures
		deltaPrevInf = prevTemperatures - infTemperatures
		deltaT = self.host.timeInterval()

		# Determine Constants
		c = numpy.linalg.solve(self.eigenVectors, deltaPrevInf)

		# Calculate Solution to the System of Differential Equations
		ePowers = numpy.exp(self.eigenValues * deltaT)
		self.temperatures = numpy.inner(c * self.eigenVectors, ePowers) + infTemperatures

		# Jacket Temperature
		jacketIndex = len(self.temperatures) - (len(self.temperatures) - self.cableSections[-1].numberOfSegments) - 1

		# Store Results
		self.hottestSpotTemperatureOlsen = self.soilTemperature + self.temperatures[-1]
		self.jacketTemperatureOlsen = self.soilTemperature + self.temperatures[jacketIndex]

		self.hottestSpotTemperature60287 = self.soilTemperature + infTemperatures[-1]
		self.jacketTemperature60287 = self.soilTemperature + infTemperatures[jacketIndex]

	def estimateHottestSpotTemperatureOlsenDE(self, perPhaseLossMax):
		# Differential Equations implementation of the Olsen et al. model.
		# Twice as slow for 60s time base.
		n = len(self.thermalResistances)

		# Normalize
		conductors = len(self.conductors())
		loss = conductors * perPhaseLossMax / self.length

		if len(self.temperaturesDE) is 0:
			infTemperatures = self.cumulativeResistances * loss
			self.temperaturesDE = infTemperatures[::-1]

		# Determine oversampling interval for stability
		deltaT = self.host.timeInterval()
		intervals = math.ceil(1.25 * deltaT / self.minimalTimeConstant)
		subDT = deltaT / intervals

		# Calculate difference equations
		for interval in range(0, int(intervals)):
			prevTempDE = self.temperaturesDE
			prevTempDEm = numpy.append(prevTempDE[-1:], prevTempDE[:-1])
			prevTempDEp = numpy.append(prevTempDE[1:], prevTempDE[:1])
			prevTempDEp[n-1] = 0.  # for last node

			dTempDE = subDT * (prevTempDEp / self.TiCi - (prevTempDE / self.TiCi + prevTempDE / self.Ti1Ci) + prevTempDEm / self.Ti1Ci)

			# Correct first node
			dTempDE[0] = subDT * ((prevTempDE[1] - prevTempDE[0]) / (self.TiCi[0]) + loss / self.thermalCapacitances[0])

			self.temperaturesDE = self.temperaturesDE + dTempDE

		# Store result
		self.hottestSpotTemperatureOlsen = self.soilTemperature + max(self.temperaturesDE)

	def checkViolations(self):
		LvCable.checkViolations(self)
		violation = 0

		# Thermal violations
		if self.jacketTemperature60287 > self.jacketTemperatureMax:
			violation = 1
			self.logWarning("jacket temperature of " + self.name + " violated")

		self.logValue("n-violations.thermal.jacket.steadystate", violation)

		violation = 0
		if self.hottestSpotTemperatureOlsen > self.conductorTemperatureMax:
			violation = 1
			self.logWarning("conductor temperature of " + self.name + " violated")

		self.logValue("n-violations.thermal.conductor.dynamic", violation)

	def getRelativeLossOfLife(self, lossOfLife):
		# Helper method
		if self.host.currentTime == self.host.startTime:
			return lossOfLife / self.host.timeInterval()

		return lossOfLife / (self.host.currentTime - self.host.startTime)

	def getFailureProbability(self, reliability):
		return 1. - reliability

	def logStats(self, time):

		self.logValue("soil-temperature", self.soilTemperature)

		self.logValue("C-hottest-spot-temperature-60287", self.hottestSpotTemperature60287)
		self.logValue("C-jacket-temperature-60287", self.jacketTemperature60287)
		self.logValue("p-loss-of-life-factor-60287", self.lossOfLifeFactor60287)
		self.logValue("p-loss-of-life-relative-60287", self.getRelativeLossOfLife(self.lossOfLife60287))
		self.logValue("p-failure-probability-60287", self.getFailureProbability(self.reliability60287))
		# self.logValue("p-loss-of-life-conservative-relative-60287", self.getRelativeLossOfLife(self.lossOfLifeConservative60287))

		self.logValue("C-hottest-spot-temperature-olsen", self.hottestSpotTemperatureOlsen)
		self.logValue("C-jacket-temperature-olsen", self.jacketTemperatureOlsen)
		self.logValue("p-loss-of-life-factor-olsen", self.lossOfLifeFactorOlsen)
		self.logValue("p-loss-of-life-relative-olsen", self.getRelativeLossOfLife(self.lossOfLifeOlsen))
		self.logValue("p-failure-probability-olsen", self.getFailureProbability(self.reliabilityOlsen))

		LvCable.logStats(self, time)


class CableSection:
	def __init__(self, thermalResistivity=0.0, specificHeat=0.0, innerRadius=0.0, outerRadius=0.0, numberOfSegments=1,
				 customHeatCapacity=None):
		self.thermalResistivity = thermalResistivity  # K m/W
		self.specificHeat = specificHeat  # J/(m^3 K)
		self.innerRadius = innerRadius  # m
		self.outerRadius = outerRadius  # m

		self.numberOfSegments = numberOfSegments
		self.customHeatCapacity = customHeatCapacity  # J/(K m)

		self.thermalResistances = []
		self.thermalCapacitances = []

		for i in range(0, numberOfSegments):
			deltaR = (outerRadius - innerRadius) / numberOfSegments
			Rin = innerRadius + i*deltaR
			Rout = innerRadius + (i+1)*deltaR

			if thermalResistivity > 0.0:
				self.thermalResistances.append(
					thermalResistivity / (2 * math.pi) * math.log(Rout / Rin))  # K m/W
			else:
				self.thermalResistances.append(0.0)

			if customHeatCapacity is not None:
				self.thermalCapacitances.append(customHeatCapacity)
			elif specificHeat > 0.0:
				self.thermalCapacitances.append(
					specificHeat * math.pi * (Rout*Rout - Rin*Rin))  # J/(m K)
			else:
				self.thermalCapacitances.append(0.0)
