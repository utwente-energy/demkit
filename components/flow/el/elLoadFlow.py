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


import numpy as np
import os
import math

from flow.flowSimulator import FlowSimulator
from flow.el.mvLvTransformer import MvLvTransformer

class ElLoadFlow(FlowSimulator):
	def __init__(self,  name,  host):
		FlowSimulator.__init__(self,  name, host)

		self.devtype = "ElectricityLoadflow"

		#params:
		# FIXME: Should become a more global param like with devices and controllers
		self.statsLogging = False

		self.maxIterations = 100
		self.maxError = 0.000001

		#Stats logging:
		self.stats = {}
		self.prepareStatsLists()

		self.controller = None

		# Normal simulation behaviour in which we automatically restore the grid
		self.autoRestoreGrid = True
		# Simulate the grid state with burned fused
		self.burnFuses = False

		# Make a graphical representation
		self.createGraph = False
		self.dotGraph = None

		# Frequency specific settings
		self.islanding = True
		self.nominalFrequency = 50.0	 	# Hz
		self.frequency = 50.0
		self.frequencyConstant =  0.00004 	# 2Hz deviation for 50kW (fmax - fmin)/Pmax

		# Simulation status
		self.currentIteration = 0

		# Documentation on frequency:
		# Page 104 of this book gives some ideas
		# https://books.google.nl/books?id=Gb1zCgAAQBAJ&pg=PA104&lpg=PA104&dq=relation+power+surplu+frequency&source=bl&ots=ausQ1cVvDp&sig=J_ysCa6eQGnX_qjwPZn9uwLEQJc&hl=nl&sa=X&ved=0ahUKEwj3lZfeiLjKAhVBBBoKHZO1CTkQ6AEIHzAA#v=onepage&q=relation%20power%20surplus%20frequency&f=false

		# And these papers give the same type of formulas for the frequency and provide droop control strategies:
		# http://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=6379246
		# http://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=985003
		# http://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=1626398
		# http://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=1708993


	# As it seems, we can just assume a linear relation between power shortage/surplus and under/over frequency.
	def simulate(self, time, deltatime=0):
		iters = self.executeLoadflow(self.maxIterations, self.maxError)

		# Set the frequency:
		if self.islanding:
			if self.getSlackEnergy().real >= 0:
				self.frequency = self.nominalFrequency - (abs(self.getSlackEnergy()) * self.frequencyConstant)
			else:
				self.frequency = self.nominalFrequency - (-1 * abs(self.getSlackEnergy()) * self.frequencyConstant)

		for node in self.nodes:
			node.estimateReliability()

		for edge in self.edges:
			edge.estimateReliability()

		self.logValue("n-iterations.loadflow", iters)

	def startup(self):
		if self.rootNode == None:
			self.host.logError("No rootNode set. Please make sure you define "+self.name+".rootNode")
			assert(False)
		nodeList = []
		self.checkModelForLoops(self.rootNode, None, nodeList)

		if self.createGraph:
			self.makeDotSchematic(self.rootNode, None)
			self.dotGraph.render(filename="schematics/Network")

		self.reset()

	def shutdown(self):
		#Write stats at the end
		if self.statsLogging:
			self.logOverallStats()

	def executeLoadflow(self, iters, error):
		assert(self.rootNode != None)
		success = False

		self.reset(self.autoRestoreGrid)

		loop = True
		numIters = 0
		while loop:
			self.reset(False)
			for i in range(0, iters):
				self.currentIteration = i
				self.doForwardBackwardSweep(self.rootNode, None)
				numIters += 1

				if i>0 and self.checkConvergence(error):
					success = True
					break;

			if self.burnFuses:
				loop = self.determinePhysicalState(self.rootNode, None)
			else:
				loop = False

		if self.burnFuses:
			self.updatePhysicalState(self.rootNode, None)

		if not success:
			self.host.logWarning("Loadflow calculation did not converge to a solution!")
			return -1
		else:
			return numIters

	def doForwardBackwardSweep(self, thisNode, prevNode):
		for edge in thisNode.edges:
			nextNode = edge.otherNode(thisNode)
			if nextNode != prevNode and edge.enabled == True:
				nextNode.doForwardSweep(thisNode, edge)
				self.doForwardBackwardSweep(nextNode, thisNode)
				nextNode.doBackwardSweep(edge)

	def checkConvergence(self, error):
		for node in self.nodes:
			if node.getConvergenceError() > error:
				return False
		return True

	# Function to determine the state and "burn" fuses for a physical representation of the grid
	def determinePhysicalState(self, thisNode, prevNode):
		result = False
		for edge in thisNode.edges:
			nextNode = edge.otherNode(thisNode)
			if nextNode != prevNode: # and edge.enabled == True:
				# The following construction is required to determine the change of a grid due to blown fuses
				# Due to selectivity, we need to start with blowing fuses at the end
				# And then start a new loadflow cycle to see if more burns as currents have changed
				# This model does not include time delays/cooling/wearing of fuses, but determines the "end state" so to speak
				change = self.determinePhysicalState(nextNode, thisNode)
				if not change:
					change = edge.determinePhysicalState()
				if change:
					result = True
		return result

	# Function to determine flow direction in cables
	# FIXME Does not include transformer limit yet! This in fact is another edge, so a small cable section would suffice in modelling!
	def updatePhysicalState(self, thisNode, prevNode):
		for edge in thisNode.edges:
			nextNode = edge.otherNode(thisNode)
			if nextNode != prevNode: # and edge.enabled == True:
				edge.updatePhysicalState(thisNode, nextNode)
				nextNode.updatePhysicalState(edge)
				self.updatePhysicalState(nextNode, thisNode)


	def checkModelForLoops(self, thisNode, prevNode, nodeList):
		nodeList.append(thisNode)
		for cable in thisNode.edges:
			nextNode = cable.otherNode(thisNode)
			if nextNode != prevNode:
				if nextNode in nodeList:
					self.host.logError("Error, loops found! error at: "+self.name)
					break
				#all good, continue
				self.checkModelForLoops(nextNode, thisNode, nodeList)

	def getSlackEnergy(self):
		power = complex(0.0, 0.0)
		for cable in self.rootNode.edges:
			if cable.hasNeutral:
				for i in range(1, 4):
					power += self.rootNode.getLNVoltage(i)*cable.current[i].conjugate()
			else:
				for i in range(1, 4):
					power += self.rootNode.voltage[i] * cable.current[i].conjugate()
		return power

	def getLosses(self):
		slackPower = self.getSlackEnergy().real

		consumption = 0.0
		for node in self.nodes:
			consumption += node.getConsumption().real
		losses = abs(slackPower - consumption)

		return losses

	def reset(self, restoreGrid = True):
		self.resetNodes(restoreGrid)
		self.resetEdges(restoreGrid)

	def logStats(self, time):
		#Some own Logging
		self.logValue("W-losses", self.getLosses())
		self.logValue("W-power.slackbus", self.getSlackEnergy().real)
		self.logValue("var-power.slackbus", self.getSlackEnergy().imag)
		if self.getSlackEnergy().real >= 0:
			self.logValue("VA-power.slackbus", abs(self.getSlackEnergy()))
		else:
			self.logValue("VA-power.slackbus", -1*abs(self.getSlackEnergy())) #let the sign depend on the active power since it is convenient.
		if self.islanding:
			self.logValue("Hz-frequency", self.frequency)

		#Massive data logging for stats
		if self.statsLogging:
			assert(False)
			self.logIntervalStats()







	# Make a schematic
	def makeDotSchematic(self, thisNode, prevNode):
		from graphviz import Graph

		# Create a new graph if needed
		if self.dotGraph is None:
			self.dotGraph = Graph("Network", format='svg')

		# Draw the current node
		self.dotGraph.node(thisNode.name)

		# For all but the root node, draw edges
		if prevNode is not None:
			self.dotGraph.edge(prevNode.name, thisNode.name)

		# Recursive call
		for edge in thisNode.edges:
			nextNode = edge.otherNode(thisNode)
			if nextNode != prevNode and edge.enabled == True:
				self.makeDotSchematic(nextNode, thisNode)









	def prepareStatsLists(self):
		self.stats['PowerP'] = []
		self.stats['PowerQ'] = []
		self.stats['PowerS'] = []
		self.stats['Cable'] = []
		self.stats['Voltage'] = []
		self.stats['VoltageL1'] = []
		self.stats['VoltageL2'] = []
		self.stats['VoltageL3'] = []
		self.stats['VoltageN'] = []
		self.stats['VUF'] = []
		self.stats['Losses'] = []
		self.stats['Plan'] = []
		self.stats['Plan2'] = []
		self.stats['Plan15'] = []
		self.stats['Plan215'] = []

		self.stats['VoltageLvMin'] = []
		self.stats['VoltageLvMax'] = []
		self.stats['VufLvMax'] = []

		self.stats['CurrentMax'] = []
		self.stats['HotSpotTemperatureMax_SteadyState'] = []
		self.stats['HotSpotTemperatureMax_Dynamic'] = []
		self.stats['JacketTemperatureMax_SteadyState'] = []
		self.stats['JacketTemperatureMax_Dynamic'] = []
		self.stats['LossOfLifeFactor_SteadyState'] = []
		self.stats['LossOfLifeFactor_Dynamic'] = []
		self.stats['HotSpotTemperatureTransformer'] = []
		self.stats['LossOfLifeFactorTransformer'] = []

		self.plan15 = 0
		self.plan215 = 0
		self.plancnt = 0


	def logIntervalStats(self):
		self.stats['PowerP'].append(self.getSlackEnergy().real)
		self.stats['PowerQ'].append(self.getSlackEnergy().imag)
		if self.getSlackEnergy().real >= 0:
			self.stats['PowerS'].append(abs(self.getSlackEnergy()))
		else:
			self.stats['PowerS'].append(-1*abs(self.getSlackEnergy()))

		self.stats['Losses'].append(self.getLosses())


		if self.controller != None:
			p = self.controller.getOriginalPlan(self.host.time())
			self.stats['Plan'].append(abs(p - self.getSlackEnergy().real))
			self.stats['Plan2'].append(abs( (p*p) - (self.getSlackEnergy().real*self.getSlackEnergy().real) ) )

			self.plan15 += abs(p - self.getSlackEnergy().real)
			self.plan215 += abs( (p*p) - (self.getSlackEnergy().real*self.getSlackEnergy().real) )
			self.plancnt += 1
			if self.plancnt == 15:
				self.plan15 = self.plan15 / 15.0
				self.plan215 = self.plan215 / 15.0
				self.stats['Plan15'].append(self.plan15)
				self.stats['Plan215'].append(self.plan215)
				self.plancnt = 0

			self.logValue("DeviationFormPlan", abs(p - self.getSlackEnergy().real))

		# Node Stats
		vminLV = 10000000000
		vmaxLV = 0
		vufmaxLV = 0
		for n in self.nodes:
			if max(n.nominalVoltage) < 280.0:
				# LV
				for i in range(1,4):
					self.stats['Voltage'].append(abs(n.getLNVoltage(i)))
					vminLV = min(vminLV, (abs(n.getLNVoltage(i))))
					vmaxLV = max(vmaxLV, (abs(n.getLNVoltage(i))))
					vufmaxLV = max(vufmaxLV, (abs(n.getUnbalance())))

				self.stats['VoltageL1'].append(abs(n.getLNVoltage(1)))
				self.stats['VoltageL2'].append(abs(n.getLNVoltage(2)))
				self.stats['VoltageL3'].append(abs(n.getLNVoltage(3)))
				self.stats['VoltageN'].append(abs(n.voltage[0]))
				self.stats['VUF'].append(abs(n.getUnbalance()))
			else:
				# MV
				pass

			# Note: assumes one transformer
			if isinstance(n, Transformer) and hasattr(n, "hottestSpotTemperature"):
				hstTrafo = n.hottestSpotTemperature
				lossOfLifeFactorTransformer = n.lossOfLifeFactor
				lossOfLifeTransformer = n.getRelativeLossOfLife()

				self.logValue("C-temperature.transformer.hotspot", hstTrafo)
				self.logValue("p-lossoflifefactor.transformer", lossOfLifeFactorTransformer)
				self.logValue("p-lossoflife.transformer", lossOfLifeTransformer)

				self.stats['HotSpotTemperatureTransformer'].append(hstTrafo)
				self.stats['LossOfLifeFactorTransformer'].append(lossOfLifeFactorTransformer)

		self.logValue("V-voltage.lv.minimum", vminLV)
		self.logValue("V-voltage.lv.maximum", vmaxLV)
		self.logValue("p-unbalance.VUF.lv.maximum", vufmaxLV)

		self.stats['VoltageLvMin'].append(vminLV)
		self.stats['VoltageLvMax'].append(vmaxLV)
		self.stats['VufLvMax'].append(vufmaxLV)


		# Edge Stats
		cablemax = 0
		currentMax = 0.
		hstCable60287Max = 0
		hstCableMaxDynamic = 0
		jcktCable60287Max = 0.
		jcktCableOlsenMax = 0.
		lossOfLifeFactor60287Max = 0.
		lossOfLifeFactorDynamicMax = 0.
		lossOfLife60287Max = 0.0
		lossOfLifeDynamicMax = 0.0
		randomRelCable = None  # need this later
		for e in self.edges:
			self.stats['Cable'].append(e.getCableLoad())
			cablemax = max(cablemax, e.getCableLoad())

			for conductor in e.conductors():
				currentMax = max(currentMax, abs(e.current[conductor]))

			self.stats['CurrentMax'].append(currentMax)

			if hasattr(e, "hottestSpotTemperature60287"):
				hstCable60287Max = max(hstCable60287Max, e.hottestSpotTemperature60287)
				hstCableMaxDynamic = max(hstCableMaxDynamic, e.hottestSpotTemperatureOlsen)
				jcktCable60287Max = max(jcktCable60287Max, e.jacketTemperature60287)
				jcktCableOlsenMax = max(jcktCableOlsenMax, e.jacketTemperatureOlsen)
				lossOfLifeFactor60287Max = max(lossOfLifeFactor60287Max, e.lossOfLifeFactor60287)
				lossOfLifeFactorDynamicMax = max(lossOfLifeFactorDynamicMax, e.lossOfLifeFactorOlsen)
				lossOfLife60287Max = max(lossOfLife60287Max, e.lossOfLife60287)
				lossOfLifeDynamicMax = max(lossOfLifeDynamicMax, e.lossOfLifeOlsen)
				randomRelCable = e

		self.logValue("p-load.cable.maximum", cablemax)

		if randomRelCable is not None:
			self.logValue("C-temperature.cable.60287.hotspot.maximum", hstCable60287Max)
			self.logValue("C-temperature.cable.dynamic.hotspot.maximum", hstCableMaxDynamic)
			self.logValue("p-lossoflife.cable.60287.relative.maximum", randomRelCable.getRelativeLossOfLife(lossOfLife60287Max))
			self.logValue("p-lossoflife.cable.dynamic.relative.maximum", randomRelCable.getRelativeLossOfLife(lossOfLifeDynamicMax))

			self.stats['HotSpotTemperatureMax_SteadyState'].append(hstCable60287Max)
			self.stats['HotSpotTemperatureMax_Dynamic'].append(hstCableMaxDynamic)
			self.stats['JacketTemperatureMax_SteadyState'].append(jcktCable60287Max)
			self.stats['JacketTemperatureMax_Dynamic'].append(jcktCableOlsenMax)
			self.stats['LossOfLifeFactor_SteadyState'].append(lossOfLifeFactor60287Max)
			self.stats['LossOfLifeFactor_Dynamic'].append(lossOfLifeFactorDynamicMax)




	def logOverallStats(self):
		for key in self.stats.keys():
			#If it is empty, we should make a zero element and get zero stats to fill up in the csv
			if len(self.stats[key]) <= 0:
				self.stats[key] = [0]

			fname = "stats/loadflow/"+str(key)+".csv"

			#If the file doesnt exist, make a first row telling what column is what exactly
			if not os.path.exists(fname):
				s = "name;p99;p95;p75;p50;p25;p5;p1;max;min;mean;sum" #function has trailing \n
				self.host.logCsvLine("stats/loadflow/"+str(key)+".csv", s)

			#Now write down the stats
			s = ""
			a = np.array(self.stats[key])

			s += self.host.name
			s += ";"+str(np.percentile(a, 99))
			s += ";"+str(np.percentile(a, 95))
			s += ";"+str(np.percentile(a, 75))
			s += ";"+str(np.percentile(a, 50))
			s += ";"+str(np.percentile(a, 25))
			s += ";"+str(np.percentile(a, 5))
			s += ";"+str(np.percentile(a, 1))
			s += ";"+str(np.amax(a))
			s += ";"+str(np.amin(a))
			s += ";"+str(np.mean(a))
			s += ";"+str(np.sum(a))

			self.host.logCsvLine(fname, s)

		# Count violations
		# 1. Get violations rules
		minVoltageLV = 10000000.
		maxVoltageLV = 0.
		maxVufLV = 0.
		for n in self.nodes:
			minVoltageLV = min(minVoltageLV, n.minVoltage)
			v = n.maxVoltage
			if v < 280.0:
				maxVoltageLV = max(maxVoltageLV, n.maxVoltage)
				maxVufLV = max(maxVufLV, n.maxVuf)

		# 2. Check for violations and log in console
		minVoltageViolations = sum(v < minVoltageLV for v in self.stats['VoltageLvMin'])
		maxVoltageViolations = sum(v > maxVoltageLV for v in self.stats['VoltageLvMax'])
		vufViolations = sum(v > maxVufLV for v in self.stats['VufLvMax'])

		self.logMsg("Voltage violations: " +
					str(minVoltageViolations) + "x undervoltage, " +
					str(maxVoltageViolations) + "x overvoltage, " +
					str(vufViolations) + "x VUF violations.")
