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



# Buffer planning algorithms based on the work of:
# Thijs van der Klauw
#
# Details in the PhD thesis:
# Decentralized Energy Management with Profile Steering: Resource Allocation Problems in Energy Management
# University of Twente, 2017
# https://research.utwente.nl/en/publications/decentralized-energy-management-with-profile-steering-resource-al

# and

# Implementation of the EV charging algorithm where only charging between given bounds (or nothing at all) is accepted.
# Paper: Martijn H. H. Schoot Uiterkamp et al., "Offline and online scheduling of electric vehicle charging with a minimum charging threshold", submitted to SmartGridComm 2018.


import math
import sys


class OptAlg:
	def __init__(self):
		self.fillLevel = 0

	def continuousBufferPlanning(self, desired, chargeRequired, powerMin, powerMax, powerLimitsLower=[], powerLimitsUpper=[], prices=None, beta=1):
		if prices is None:
			prices = [0] * len(desired)

		# Gerwin: Added also option to have positive lower limits:
		positiveLowerBound = False
		for lim in powerLimitsLower:
			if lim > 0.0:
				positiveLowerBound = True
				break

		# Check for negative values, if so, we need to scale!
		# Note, we could have negative upperBounds too, but in that case we need to have a negative PowerMin, so this section is triggered too!
		if powerMin < -0.0001 or powerMin > 0.0001 or positiveLowerBound:
			if len(powerLimitsLower) != len(desired) or len(powerLimitsUpper) != len(desired):
				# scale first
				chargeRequiredNew = chargeRequired - powerMin * len(desired)
				desiredNew = []
				powerMaxNew = powerMax - powerMin
				for i in range(0, len(desired)):
					desiredNew.append(desired[i] - powerMin)

				# And now call the positive only function (the original EV algorithm):
				result = self.continuousBufferPlanningPositive(desiredNew, chargeRequiredNew, powerMaxNew, prices=prices, beta=beta)  # We can omit power limits here as they do not exist apparently

				assert (len(result) == len(desired))
				# scale back the answer
				for i in range(0, len(result)):
					result[i] += powerMin

			else:
				# We have power limits! More code required
				assert (len(powerLimitsLower) == len(powerLimitsLower) == len(desired))  # Length of vectors must be identical

				result = []
				upperLimits = [powerMax] * len(desired)
				lowerLimits = [powerMin] * len(desired)
				remaining = [0.0] * len(desired)
				totalLower = 0.0
				totalUpper = 0.0

				for i in range(0, len(desired)):
					#         In this case we have a higher lower limit than upper limit, this means we are waaaay to restrictive and we just try to get to the point
					#         dead in the center of the two. NOTE: should never happen (dumb user input?)
					#            GERWIN: Dumb user input must result in a hard exit this deep, checks must be in place at a higher level. Hence an assertion here.
					assert (powerLimitsLower[i] <= powerLimitsUpper[i])

					lowerLimits[i] = max(powerMin, powerLimitsLower[i])
					totalLower += max(powerMin, powerLimitsLower[i])
					upperLimits[i] = min(powerMax, powerLimitsUpper[i])
					totalUpper += min(powerMax, powerLimitsUpper[i])

				# If the power bounds are too restrictive we need to find a best possible solution
				if chargeRequired < powerMin * len(desired):
					result = [powerMin] * len(desired)
					return result

				elif chargeRequired > powerMax * len(desired):
					result = [powerMax] * len(desired)
					return result

				elif chargeRequired < totalLower:
					sortedLowerLimits = list(lowerLimits)
					sortedLowerLimits.sort()
					position = 0
					underLimits = totalLower - chargeRequired
					breakpoint = 0
					while position < len(sortedLowerLimits) and (sortedLowerLimits[position] - powerMin) < (underLimits / ((len(desired) - position))):
						underLimits -= sortedLowerLimits[position] - powerMin
						breakpoint = sortedLowerLimits[position]
						position += 1
						# Fixing rounding
						if underLimits < 0.0001:
							underLimits = 0

					for i in range(0, len(desired)):
						if lowerLimits[i] > breakpoint:
							result.append(lowerLimits[i] - (underLimits / (len(desired) - position)))
						else:
							result.append(powerMin)

					self.fillLevel = breakpoint
					assert (len(result) == len(desired))
					return result

				elif chargeRequired > totalUpper:
					# NOTE: This code significantly deviates from the original C++ code due to a mistake
					#     We expect that the original code was a placeholder, forgotten to be changed
					#    This code is adapted based on the same principles in other parts of this optimization module
					#    The original code is left in comments below.
					for i in range(0, len(desired)):
						remaining[i] = powerMax - upperLimits[i]

					sortedRemaining = list(remaining)
					sortedRemaining.sort()
					overLimits = chargeRequired - totalUpper
					breakpoint = 0.0
					position = 0

					while position < len(desired) and (overLimits / (len(desired) - position) > sortedRemaining[position]) and (position < len(sortedRemaining)):
						overLimits -= sortedRemaining[position]
						breakpoint = sortedRemaining[position]
						position += 1
					for i in range(0, len(desired)):
						if remaining[i] > breakpoint:
							result.append(upperLimits[i] + (overLimits / (len(desired) - position)))
						else:
							result.append(powerMax) 

					# NOTE Original and broken code:

					# sortedRemaining = remaining
					# sortedRemaining.sort()
					# position = 0
					# overLimits = chargeRequired - totalUpper
					# breakpoint = 0.0
					#
					# while position < len(sortedRemaining) and (position < len(sortedRemaining) and sortedRemaining[position] < ( overLimits / (len(desired) - position) ) ):
					#     overLimits -= sortedRemaining[position]
					#     breakpoint = sortedRemaining[position]
					#     position += 1
					#     # Fixing rounding
					#     if overLimits < 0.0001:
					#         overLimits = 0
					#
					# for i in range(0, len(desired)):
					#     if(remaining[i] > breakpoint):
					#         result.append(upperLimits[i] + (overLimits / (len(desired) - position) ) )
					#     else:
					#         result.append(powerMax)

					# END OF BROKEN CODE

					self.fillLevel = breakpoint
					assert (len(result) == len(desired))
					return result

				# Now we know we can find a feasible planning within the power limits, so we can use a transformation that will give us the best solution
				# that abides the power limits.
				chargeRequiredNew = chargeRequired - totalLower
				powerMaxNew = powerMax - powerMin
				desiredNew = []
				powerLimitsUpperNew = []

				for i in range(0, len(desired)):
					desiredNew.append(desired[i] - lowerLimits[i])
					powerLimitsUpperNew.append(upperLimits[i] - lowerLimits[i])

				result = self.continuousBufferPlanningPositive(desiredNew, chargeRequiredNew, powerMaxNew, powerLimitsUpperNew, prices=prices, beta=beta)

				assert (len(result) == len(desired))

				for i in range(0, len(result)):
					result[i] += lowerLimits[i]

			assert (len(result) == len(desired))
			return result

		# If PowerMin == 0 we can use the positive only variant (all boils down to that algorithm in the end)
		else:
			result = self.continuousBufferPlanningPositive(desired, chargeRequired, powerMax, powerLimitsUpper, prices=prices, beta=beta)
			assert (len(result) == len(desired))
			return result

	def continuousBufferPlanningPositive(self, desired, chargeRequired, powerMax, powerLimitsUpper=[], prices=None, beta=1):
		if prices is None:
			prices = [0] * len(desired)

		result = [0] * len(desired)
		remainingCharge = chargeRequired

		# Check whether we need to charge anyways (trivial..)
		if (chargeRequired <= 0):
			return result

		# //Check if the request amount cane charged within both the car max power limit and the given power limits of the signal (if they are given)
		# //To this end we separate the power limits out.
		powerLimits = [powerMax] * len(desired)
		if len(powerLimitsUpper) == len(desired):
			for i in range(0, len(desired)):
				powerLimits[i] = min(powerLimitsUpper[i], powerMax)
				if powerLimits[i] < 0:
					assert powerLimits[i] >= -0.0001  # very small negative floats may occur, ignore these.
					powerLimits[i] = 0
				assert (powerLimits[i] >= 0)

		# //First check if the total amount can be charged within the given horizon without going over the maximum power, if not we return the best we can do
		# //which is maximal charging on each time interval.
		if (chargeRequired > powerMax * len(desired)):
			return [powerMax] * len(desired)

		# //If the total amount that needs to be done fits within the device powerMax but does exceed the given power Limits from above, we simply go over the
		# //limits by as little as possible to get our job done. NOTE: this is because sometimes the controller might request power limits which are too stringent
		# //for the device/job at hand.
		elif len(powerLimitsUpper) == len(desired):
			totalAvailable = 0.0
			remaining = [0.0] * len(desired)
			for i in range(0, len(desired)):
				totalAvailable += powerLimits[i]
				remaining[i] = powerMax - powerLimits[i]

			if totalAvailable < chargeRequired:
				sortedRemaining = list(remaining)
				sortedRemaining.sort()
				overLimits = chargeRequired - totalAvailable
				breakpoint = 0.0
				position = 0
				while position < len(desired) and (overLimits / (len(desired) - position) > sortedRemaining[position]) and (position < len(sortedRemaining)):
					overLimits -= sortedRemaining[position]
					breakpoint = sortedRemaining[position]
					position += 1

				for i in range(0, len(desired)):
					if remaining[i] > breakpoint:
						result[i] = powerLimits[i] + (overLimits / (len(desired) - position))
					else:
						result[i] = powerMax  # powerLimits[i]  # Bugfix compared to C++

				self.fillLevel = breakpoint
				assert (len(result) == len(desired))
				return result

		# From here we break slightly with the C++ code
		# Instead of defining two functions, we keep the profile planning here due to it being intertwined along the way
		# If we want to do pure prices, we will jump in the next if-clause and go on in a separate funtion
		# else we can excute the normal code
		if beta == 0:
			# Price steering:
			result = self.continuousBufferPlanningPrices(chargeRequired, powerMax, powerLimitsUpper, prices)

			assert (len(result) == len(desired))
			return result

		lower = 0
		upper = -1

		lowerLevels = list(result)
		upperLevels = list(result)
		if prices is []:
			for i in range(0, len(desired)):
				lowerLevels[i] = -desired[i]
				upperLevels[i] = -desired[i] + powerLimits[i]

		else:
			if beta == 1:
				prices = [0] * len(desired)

			assert (len(prices) == len(desired))
			assert (beta > 0)
			for i in range(0, len(desired)):
				# FIXME ADDED FOR BETA!
				# double u = signal->steeringSignal.at(i)/(2*signal->beta) - signal->desiredProfile.at(i);
				lvl = (prices[i] / (2 * beta)) - desired[i]
				lowerLevels[i] = lvl
				upperLevels[i] = lvl + powerLimits[i]

		sortedLowerLevels = list(lowerLevels)
		sortedUpperLevels = list(upperLevels)
		sortedLowerLevels.sort()
		sortedUpperLevels.sort()

		breakpoint = sortedLowerLevels[0]

		# //Here we do the magic where we solve the problem
		# //The idea is that we determine the breakpoint. This breakpoint allows us to construct the final solution
		while remainingCharge > 0 and upper + 1 < len(desired):
			if (lower + 1 == len(desired)):
				change = min((remainingCharge / (lower - upper)), (sortedUpperLevels[upper + 1] - breakpoint))
				breakpoint += change
				remainingCharge -= change * (lower - upper)
				upper += 1
			elif (upper == lower):
				breakpoint += sortedLowerLevels[lower + 1] - breakpoint
				lower += 1
			elif (sortedLowerLevels[lower + 1] < sortedUpperLevels[upper + 1]):
				change = min((remainingCharge / (lower - upper)), (sortedLowerLevels[lower + 1] - breakpoint))
				breakpoint += change
				remainingCharge -= change * (lower - upper)
				lower += 1
			else:
				change = min((remainingCharge / (lower - upper)), (sortedUpperLevels[upper + 1] - breakpoint))
				breakpoint += change
				remainingCharge -= change * (lower - upper)
				upper += 1

		for i in range(len(desired)):
			if (breakpoint >= upperLevels[i]):
				result[i] = powerLimits[i]
			elif (breakpoint > lowerLevels[i]):
				result[i] = breakpoint - lowerLevels[i]

		self.fillLevel = breakpoint
		assert (len(result) == len(desired))
		return result

	def continuousBufferPlanningPrices(self, chargeRequired, powerMax, powerLimitsUpper, prices):
		assert (prices != None)
		result = [0] * len(prices)

		powerLimits = [powerMax] * len(prices)
		if len(powerLimitsUpper) == len(prices):
			for i in range(0, len(prices)):
				powerLimits[i] = min(powerLimitsUpper[i], powerMax)


		# Here comes the sorting
		sorted = []
		idx = 0
		for val in prices:
			sorted.append([val.real, idx])
			idx += 1
		sorted.sort()

		remainingCharge = chargeRequired
		i = 0
		while remainingCharge > 0 and i < len(prices):
			if remainingCharge > powerLimits[sorted[i][1]]:
				result[sorted[i][1]] = powerLimits[sorted[i][1]]
				remainingCharge -= powerLimits[sorted[i][1]]
				i += 1
			else:
				result[sorted[i][1]] = remainingCharge
				remainingCharge = 0

		assert (len(result) == len(prices))
		return result

	# This is the discrete EV planning algorithm
	# Input:
	#    desired:        vecor with the desired profile
	#    chargeRequired:    the required charge in Wtau
	#    chargingPowers:    vector with the supported powers at which the device can charge (positive, including 0)
	def discreteBufferPlanning(self, desired, chargeRequired, chargingPowers, powerLimitsLower=[], powerLimitsUpper=[], prices=None, beta=1, efficiency=None, intervalMerge=None):
		if prices is None:
			prices = [0] * len(desired)

		if efficiency is None:
			efficiency = [1] * len(chargingPowers)
		else:
			assert (len(efficiency) == len(chargingPowers))

		if intervalMerge is None:
			intervalMerge = [1] * len(desired)
		else:
			assert (len(intervalMerge) == len(desired))

		result = [0] * len(desired)
		remainingCharge = chargeRequired

		chargingPowers.sort()
		assert (len(chargingPowers) > 1)

		# Gerwin: Added also option to have positive lower limits:
		positiveLowerBound = False
		for lim in powerLimitsLower:
			if lim > 0.0:
				positiveLowerBound = True
				break

		# Check for negative values, if so, we need to scale!
		if (positiveLowerBound or chargingPowers[0] < 0):
			if len(powerLimitsLower) != len(desired) or len(powerLimitsUpper) != len(desired):
				# scale first
				chargeRequiredNew = chargeRequired - chargingPowers[0] * sum(intervalMerge)
				chargingPowersNew = []
				desiredNew = []

				for i in range(0, len(chargingPowers)):
					chargingPowersNew.append(chargingPowers[i] - chargingPowers[0])
				for i in range(0, len(desired)):
					desiredNew.append(desired[i] - chargingPowers[0] * efficiency[0])

				result = self.discreteBufferPlanningPositive(desiredNew, chargeRequiredNew, chargingPowersNew, [], prices=prices, beta=beta, efficiency=efficiency, intervalMerge=intervalMerge)

				# scale back the answer
				for i in range(0, len(result)):
					result[i] += chargingPowers[0]

			else:
				# We have to deal with power limits:
				# We have power limits! More code required
				assert (len(powerLimitsLower) == len(powerLimitsLower) == len(desired))  # Length of vectors must be identical

				result = []
				upperLimits = [chargingPowers[-1] * efficiency[-1]] * len(desired)
				lowerLimits = [chargingPowers[0] * efficiency[0]] * len(desired)
				remaining = [0.0] * len(desired)
				totalLower = 0.0
				totalUpper = 0.0

				for i in range(0, len(desired)):
					#         In this case we have a higher lower limit than upper limit, this means we are waaaay to restrictive and we just try to get to the point
					#         dead in the center of the two. NOTE: should never happen (dumb user input?)
					#            GERWIN: Dumb user input must result in a hard exit this deep, checks must be in place at a higher level. Hence an assertion here.
					assert (powerLimitsLower[i] <= powerLimitsUpper[i])

					lowerLimits[i] = chargingPowers[self.lowerChargingIndex(chargingPowers, powerLimitsLower[i], efficiency)]
					totalLower += chargingPowers[self.lowerChargingIndex(chargingPowers, powerLimitsLower[i], efficiency)]  # max(chargingPowers[0], powerLimitsLower[i])
					upperLimits[i] = chargingPowers[self.upperChargingIndex(chargingPowers, powerLimitsUpper[i], efficiency)]
					totalUpper += chargingPowers[self.upperChargingIndex(chargingPowers, powerLimitsUpper[i], efficiency)]

				# If the power bounds are too restrictive we need to find a best possible solution
				if chargeRequired < chargingPowers[0] * sum(intervalMerge):
					result = [chargingPowers[0]] * sum(intervalMerge)
					return result

				elif chargeRequired > chargingPowers[-1] * sum(intervalMerge):
					result = [chargingPowers[-1]] * sum(intervalMerge)
					return result

				elif chargeRequired < totalLower:
					# FIXME: UNSURE WHETHER I NEED TO CONSIDER intervalMerge here
					sortedLowerLimits = list(lowerLimits)
					sortedLowerLimits.sort()
					position = 0
					underLimits = totalLower - chargeRequired
					breakpoint = 0.0
					while ((sortedLowerLimits[position] - chargingPowers[0] * efficiency[0]) * intervalMerge[position] < (underLimits / (len(desired) - position))):
						underLimits -= (sortedLowerLimits[position] - chargingPowers[0] * efficiency[0]) * intervalMerge[position]
						breakpoint = sortedLowerLimits[position]
						position += 1

					# Too restrictive limits, but we can change the desired profile to get close to the limits
					# Solution: Create a new desired profile based on the result that we would obtain for the continuous solution
					# Then call this function recursively without bounds and we should get a provide that abides the desired SoC (and thus constraints)
					newDesired = []
					for i in range(0, len(desired)):
						if lowerLimits[i] > breakpoint:
							newDesired.append(lowerLimits[i] - (underLimits / (len(desired) - position)))
						else:
							newDesired.append(chargingPowers[0] * efficiency[0])

					return self.discreteBufferPlanning(newDesired, chargeRequired, chargingPowers, lowerLimits, upperLimits, prices=prices, beta=beta, efficiency=efficiency, intervalMerge=intervalMerge)

				elif chargeRequired > totalUpper:
					sortedRemaining = remaining
					sortedRemaining.sort()
					position = 0
					overLimits = chargeRequired - totalUpper
					breakpoint = 0.0

					while (position < len(sortedRemaining) and sortedRemaining[position] * intervalMerge[position] < (overLimits / (len(desired) - position))):
						overLimits -= sortedRemaining[position] * intervalMerge[position]
						breakpoint = sortedRemaining[position]
						position += 1

					# Too restrictive limits, but we can change the desired profile to get close to the limits
					# Solution: Create a new desired profile based on the result that we would obtain for the continuous solution
					# Then call this function recursively without bounds and we should get a provide that abides the desired SoC (and thus constraints)
					newDesired = []
					for i in range(0, len(desired)):
						if (remaining[i] > breakpoint):
							newDesired.append(upperLimits[i] + (overLimits / (len(desired) - position)))
						else:
							# do as much as possible
							newDesired.append(chargingPowers[-1] * efficiency[-1])

					return self.discreteBufferPlanning(newDesired, chargeRequired, chargingPowers, lowerLimits, upperLimits, prices=prices, beta=beta, efficiency=efficiency, intervalMerge=intervalMerge)

				# Now we know we can find a feasible planning within the power limits, so we can use a transformation that will give us the best solution
				# that abides the power limits.
				# scale first
				chargeRequiredNew = chargeRequired - totalLower
				chargingPowersNew = []
				desiredNew = []
				powerLimitsUpperNew = []

				for i in range(0, len(chargingPowers)):
					chargingPowersNew.append(chargingPowers[i] - chargingPowers[0])
				for i in range(0, len(desired)):
					desiredNew.append(desired[i] - lowerLimits[i])
					powerLimitsUpperNew.append(upperLimits[i] - lowerLimits[i])

				result = self.discreteBufferPlanningPositive(desiredNew, chargeRequiredNew, chargingPowersNew, powerLimitsUpperNew, prices=prices, beta=beta, efficiency=efficiency, intervalMerge=intervalMerge)

				# scale back the answer
				for i in range(0, len(result)):
					result[i] += lowerLimits[i]

			# Finally, return the result
			assert (len(result) == len(desired))
			return result

		# Otherwise, we are positive and we can just call the normal algorithm
		else:
			result = self.discreteBufferPlanningPositive(desired, chargeRequired, chargingPowers, powerLimitsUpper, prices=prices, beta=beta, efficiency=efficiency, intervalMerge=intervalMerge)

		return result

	def discreteBufferPlanningPositive(self, desired, chargeRequired, chargingPowers, powerLimitsUpper=[], prices=None, beta=1, efficiency=None, intervalMerge=None):
		result = [0] * len(desired)
		remainingCharge = chargeRequired

		if efficiency is None:
			assert (False)
			efficiency = [1] * len(chargingPowers)
		else:
			assert (len(efficiency) == len(chargingPowers))

		if prices is None:
			prices = [0] * len(desired)

		if intervalMerge is None:
			intervalMerge = [1] * len(desired)
		else:
			assert (len(intervalMerge) == len(desired))

		chargingPowers.sort()
		assert (len(chargingPowers) >= 1)

		slopes = []

		# FIXME: ADD SOME PENALTY TO SLOPES WITH HIGH INEFFECIENCY??

		for i in range(0, len(desired)):
			# calculate the first slopes
			# Check if the next slope fits in the powerlimits:
			if len(powerLimitsUpper) == 0 or chargingPowers[1] <= powerLimitsUpper[i]:
				slope = ((prices[i] * chargingPowers[1] * efficiency[1] + beta * intervalMerge[i] * pow((chargingPowers[1] * efficiency[1]) - desired[i], 2) - (prices[i] * chargingPowers[0] * efficiency[0] + beta * intervalMerge[i] * pow((chargingPowers[0] * efficiency[0]) - desired[i], 2))) / (intervalMerge[i] * ((chargingPowers[1] * efficiency[1]) - (chargingPowers[0] * efficiency[0])))).real

				# add the association
				pair = (i, 1)
				association = (slope, pair)
				slopes.append(association)

		# now append the other options:
		while (remainingCharge > 0.001 and len(slopes) > 0):
			# sort the slopes
			slopes.sort()

			i = slopes[0][1][0]
			j = slopes[0][1][1]

			assert (j > 0)

			sigma = min(remainingCharge, intervalMerge[i] * (chargingPowers[j] - chargingPowers[j - 1]))

			result[i] += sigma / intervalMerge[i]
			remainingCharge -= sigma

			slopes.pop(0)

			if (j < len(chargingPowers) - 1):
				if len(powerLimitsUpper) == 0 or chargingPowers[j + 1] <= powerLimitsUpper[i]:
					# add new entry to replace
					slope = ((prices[i] * chargingPowers[j + 1] * efficiency[j + 1] + beta * intervalMerge[i] * pow((chargingPowers[j + 1] * efficiency[j + 1]) - desired[i], 2) - (prices[i] * chargingPowers[j] * efficiency[j] + beta * intervalMerge[i] * pow((chargingPowers[j] * efficiency[j]) - desired[i], 2))) / (intervalMerge[i] * ((chargingPowers[j + 1] * efficiency[j + 1]) - (chargingPowers[j] * efficiency[j])))).real

					# add the association
					pair = (i, j + 1)
					association = (slope, pair)
					slopes.append(association)

		return result

	def lowerChargingIndex(self, chargingPowers, limit, efficiency):
		i = 0
		while chargingPowers[i] * efficiency[i] < limit and i + 1 < len(chargingPowers):
			i += 1
		return i

	def upperChargingIndex(self, chargingPowers, limit, efficiency):
		i = len(chargingPowers) - 1
		while chargingPowers[i] * efficiency[i] > limit and i > 0:
			i -= 1
		return i

	# The main bufferplanning function that does all the magic!
	def bufferPlanning(self, desired, targetSoC, initialSoC, capacity, demand, chargingPowers, powerMin=0, powerMax=0, powerLimitsLower=[], powerLimitsUpper=[], reactivePower=False, prices=None, beta=1, efficiency=None, intervalMerge=None):
		if prices is None:
			prices = [0] * len(desired)

		if efficiency is None:
			if chargingPowers is None or len(chargingPowers) == 0:
				efficiency = [1, 1]
			else:
				efficiency = [1] * len(chargingPowers)
		else:
			assert (len(efficiency) == len(chargingPowers))

		if intervalMerge is None:
			intervalMerge = [1] * len(desired)
		else:
			assert (len(intervalMerge) == len(desired))

		if not isinstance(capacity, list):
			capacity = [capacity] * len(desired)

		assert (initialSoC <= capacity[0])
		assert (len(desired) == len(demand))
		assert (targetSoC <= capacity[-1])
		result = [0] * len(desired)

		for i in range(0, len(powerLimitsLower)):
			powerLimitsLower[i] = powerLimitsLower[i].real
		for i in range(0, len(powerLimitsUpper)):
			powerLimitsUpper[i] = powerLimitsUpper[i].real

		# No support for negative demands yet, doesn't seem to be useful
		for i in range(0, len(demand)):
			assert (demand[i] >= -0.0001)

		# first we need to split off the reactive part since the rest of the comparison code does not like it.
		desiredWithReactive = list(desired)  # copy.deepcopy(desired)
		for i in range(0, len(desired)):
			desired[i] = desired[i].real

		continuousMode = False

		if (len(chargingPowers) == 0):
			# Will use continuous version of Thijs his code, but integrated the discrete chargingpowers to ease the code:
			assert (powerMin < powerMax)
			chargingPowers.append(powerMin)
			chargingPowers.append(powerMax)
			continuousMode = True

		chargingPowers.sort()

		# //Determine the total demand over the planning horizon, as this is how much needs to be charged into the buffer such that the SoC at the end is equal to the SoC at the beginnen
		# //Future work: Determine if we can somehow allow more flexible end SoCs for the planning
		# //Future work: Add the ability to get negative demands, i.e. to have fixed added values into the buffer (is this useful?)
		demandTotal = 0.0
		for i in range(0, len(demand)):
			demandTotal += demand[i] * intervalMerge[i]

		# Check whether the bounds make sense, otherwise, we change the bounds to fit
		if len(powerLimitsUpper) == len(desired) and len(powerLimitsLower) == len(desired):
			for i in range(0, len(desired)):
				if powerLimitsUpper[i] + 0.0001 < chargingPowers[0] * efficiency[0]:
					powerLimitsUpper[i] = chargingPowers[0] * efficiency[0]  # assert(False)
				if powerLimitsLower[i] - 0.0001 > chargingPowers[-1] * efficiency[-1]:
					powerLimitsLower[i] = chargingPowers[-1] * efficiency[-1]  # assert(False)

				if powerLimitsLower[i] > powerLimitsUpper[i]:
					powerLimitsLower[i] = powerLimitsUpper[i]

		# //First we check feasibility of the given demands for the buffer.
		# //We try to plan the maximal power for each time interval and sPlanningee if this gives a lower SoC violation
		# //Then we determine where we had the last problem
		maxSoC = initialSoC
		minSoC = 0.0
		violationIndexMax = -1

		# for i in range(0, len(desired)):
		#     maxSoC += chargingPowers[-1] - demand[i]
		#     maxSoC = min(maxSoC, capacity)
		#     #//If the SoC is negative even if we do maximal charging, then we have a problem.
		#     #//Best we can hope to do is maximal charging.
		#     #//So we try to find the last point for which this occurs and then do continue with an empty buffer from there
		#     if(maxSoC < minSoC):
		#         violationIndexMax = i
		#         minSoC = maxSoC

		for i in range(0, len(desired)):
			if len(powerLimitsUpper) == len(desired):
				if continuousMode:
					# We determine the maxSoC based on the maximum charging power and the limits
					maxSoC += max(powerLimitsUpper[i], chargingPowers[-1] * efficiency[-1]) - demand[i]
				else:
					if powerLimitsUpper[i] < chargingPowers[-1]:
						# Limits are restrictive, get the maximum charging power that fits:
						chargingPowerIdx = len(chargingPowers) - 2
						while chargingPowers[chargingPowerIdx] * efficiency[chargingPowerIdx] > powerLimitsUpper[i] and chargingPowerIdx > 0:
							chargingPowerIdx -= 1

						maxSoC += chargingPowers[chargingPowerIdx] * efficiency[chargingPowerIdx] * intervalMerge[i] - demand[i] * intervalMerge[i]
					else:
						# No restriction, just use the maximum charging power
						maxSoC += chargingPowers[-1] * efficiency[-1] * intervalMerge[i] - demand[i] * intervalMerge[i]
			else:
				maxSoC += chargingPowers[-1] * efficiency[-1] - demand[i] * intervalMerge[i]

			maxSoC = min(maxSoC, capacity[i])

			# //If the SoC is negative even if we do maximal charging, then we have a problem.
			# //Best we can hope to do is maximal charging.
			# //So we try to find the last point for which this occurs and then do continue with an empty buffer from there
			if (maxSoC < minSoC):
				violationIndexMax = i
				minSoC = maxSoC

		# //Next we determine where our scheduling freedom ends for this problem
		# //Note that the demand at the violationIndexMax must exceed powerMax, else there was no problem there to begin with!
		violationIndexMin = violationIndexMax
		while (violationIndexMin > 0 and demand[violationIndexMin - 1] > chargingPowers[-1] * chargingPowers[-1]):
			violationIndexMin -= 1

		# //Here we make the new planning if maximal charging is not enough at some point
		# //If violationIndexMin is larger than 0, then we have some scheduling freedom up to this point
		# //At that point though, the buffer has to be filled to ensure that we get as close as possible to the demand.
		if (violationIndexMax > 0):
			if (violationIndexMin > 0):
				if continuousMode:
					planMaxFirst = self.bufferPlanning(desired[0:violationIndexMin], capacity[violationIndexMin], initialSoC, capacity[0:violationIndexMin], demand[0:violationIndexMin], [], powerMin, powerMax, powerLimitsLower[0:violationIndexMin], powerLimitsUpper[0:violationIndexMin], prices=prices[0:violationIndexMin], beta=beta)
				else:
					planMaxFirst = self.bufferPlanning(desired[0:violationIndexMin], capacity[violationIndexMin], initialSoC, capacity[0:violationIndexMin], demand[0:violationIndexMin], chargingPowers, 0, 0, powerLimitsLower[0:violationIndexMin], powerLimitsUpper[0:violationIndexMin], prices=prices[0:violationIndexMin], beta=beta, efficiency=efficiency, intervalMerge=intervalMerge[0:violationIndexMin])

			# //Next we see if the problem persists till the end of the planning horizon, if it does not
			# //we have some planning freedom left at the end starting with an empty buffer.
			if (violationIndexMax < len(desired) - 1):
				if continuousMode:
					planMaxLast = self.bufferPlanning(desired[violationIndexMax + 1:], targetSoC, 0.0, capacity[violationIndexMax + 1:], demand[violationIndexMax + 1:], [], powerMin, powerMax, powerLimitsLower[violationIndexMax + 1:], powerLimitsUpper[violationIndexMax + 1:], prices=prices[violationIndexMax + 1:], beta=beta)
				else:
					planMaxLast = self.bufferPlanning(desired[violationIndexMax + 1:], targetSoC, 0.0, capacity[violationIndexMax + 1:], demand[violationIndexMax + 1:], chargingPowers, 0, 0, powerLimitsLower[violationIndexMax + 1:], powerLimitsUpper[violationIndexMax + 1:], prices=prices[violationIndexMax + 1:], beta=beta, efficiency=efficiency, intervalMerge=intervalMerge[violationIndexMax + 1:])

			planMaxMiddle = [chargingPowers[-1]] * (violationIndexMax - violationIndexMin + 1)

			if (violationIndexMin > 0):
				result = planMaxFirst
				result.extend(planMaxMiddle)
			else:
				result = planMaxMiddle

			if (violationIndexMax < len(desired) - 1):
				result.extend(planMaxLast)

			return result

		# //First we try to make a naive planning where we ignore the SoC constraints
		# //Then we determine if this naiveplanning works, and if not, where it makes the largest error in SoC
		if continuousMode:
			naivePlan = self.continuousBufferPlanning(desired, targetSoC + demandTotal - initialSoC, powerMin, powerMax, powerLimitsLower, powerLimitsUpper, prices=prices, beta=beta)
		else:
			naivePlan = self.discreteBufferPlanning(desired, targetSoC + demandTotal - initialSoC, chargingPowers, powerLimitsLower, powerLimitsUpper, prices=prices, beta=beta, efficiency=efficiency, intervalMerge=intervalMerge)

		violationIndex = -1
		violationAtIndex = 0.01
		SoC = initialSoC
		upperBound = False

		for i in range(0, len(desired) - 1):
			SoC += naivePlan[i] * intervalMerge[i] - demand[i] * intervalMerge[i]
			if (SoC - capacity[i] > violationAtIndex):
				violationIndex = i
				violationAtIndex = SoC - capacity[i]
				upperBound = True
			elif (-SoC > violationAtIndex):
				violationIndex = i
				violationAtIndex = -SoC
				upperBound = False

		# //In case we actually have an error in the SoC we can replan, splitting the problem at the maximum SoC violation.
		# //This is what we attempt here.
		if (violationIndex > -1):
			if True:  # try:
				if (upperBound):
					if continuousMode:
						planFirst = self.bufferPlanning(desired[0:violationIndex + 1], capacity[violationIndex], initialSoC, capacity[0:violationIndex + 1], demand[0:violationIndex + 1], [], powerMin, powerMax, powerLimitsLower[0:violationIndex + 1], powerLimitsUpper[0:violationIndex + 1], prices=prices[0:violationIndex + 1], beta=beta)
						planLast = self.bufferPlanning(desired[violationIndex + 1:], targetSoC, capacity[violationIndex], capacity[violationIndex + 1:], demand[violationIndex + 1:], [], powerMin, powerMax, powerLimitsLower[violationIndex + 1:], powerLimitsUpper[violationIndex + 1:], prices=prices[violationIndex + 1:], beta=beta)
					else:
						planFirst = self.bufferPlanning(desired[0:violationIndex + 1], capacity[violationIndex+1], initialSoC, capacity[0:violationIndex + 1], demand[0:violationIndex + 1], chargingPowers, 0, 0, powerLimitsLower[0:violationIndex + 1], powerLimitsUpper[0:violationIndex + 1], prices=prices[0:violationIndex + 1], beta=beta, efficiency=efficiency, intervalMerge=intervalMerge[0:violationIndex + 1])
						planLast = self.bufferPlanning(desired[violationIndex + 1:], targetSoC, capacity[violationIndex+1], capacity[violationIndex + 1:], demand[violationIndex + 1:], chargingPowers, 0, 0, powerLimitsLower[violationIndex + 1:], powerLimitsUpper[violationIndex + 1:], prices=prices[violationIndex + 1:], beta=beta, efficiency=efficiency, intervalMerge=intervalMerge[violationIndex + 1:])
				else:
					if continuousMode:
						planFirst = self.bufferPlanning(desired[0:violationIndex + 1], 0.0, initialSoC, capacity[0:violationIndex+1], demand[0:violationIndex + 1], [], powerMin, powerMax, powerLimitsLower[0:violationIndex + 1], powerLimitsUpper[0:violationIndex + 1], prices=prices[0:violationIndex + 1], beta=beta)
						planLast = self.bufferPlanning(desired[violationIndex + 1:], targetSoC, 0.0, capacity[violationIndex + 1:], demand[violationIndex + 1:], [], powerMin, powerMax, powerLimitsLower[violationIndex + 1:], powerLimitsUpper[violationIndex + 1:], prices=prices[violationIndex + 1:], beta=beta)
					else:
						planFirst = self.bufferPlanning(desired[0:violationIndex + 1], 0.0, initialSoC, capacity[0:violationIndex+1], demand[0:violationIndex + 1], chargingPowers, 0, 0, powerLimitsLower[0:violationIndex + 1], powerLimitsUpper[0:violationIndex + 1], prices=prices[0:violationIndex + 1], beta=beta, efficiency=efficiency, intervalMerge=intervalMerge[0:violationIndex + 1])
						planLast = self.bufferPlanning(desired[violationIndex + 1:], targetSoC, 0.0, capacity[violationIndex + 1:], demand[violationIndex + 1:], chargingPowers, 0, 0, powerLimitsLower[violationIndex + 1:], powerLimitsUpper[violationIndex + 1:], prices=prices[violationIndex + 1:], beta=beta, efficiency=efficiency, intervalMerge=intervalMerge[violationIndex + 1:])
				result = planFirst
				result.extend(planLast)
			else:  # except:
				sys.stderr.write()("ERROR: Planning of a buffer device was not feasible. Returning the naive planning and the device will have to fix this.")
				sys.stderr.flush()
				result = naivePlan
		else:
			result = naivePlan

		# Reactive Power control
		# Note that this part is an addition to the algorithms by Thijs vd Klauw.
		# We simply assume that any buffer type can control its reactive power independently
		# Furthermore, we do not consider discrete reactive power ratings yet.
		# The latter is trivial to integrate on the device level by taking the reactive power (or power factor) that is equal or lower than the calculated value.
		if reactivePower:
			# result list gives just the active power result
			totalResult = []
			activeMax = max(abs(chargingPowers[0]), abs(chargingPowers[-1]))  # active power maximum is simply this one
			for i in range(0, len(result)):
				if (activeMax * activeMax) - (result[i].real * result[i].real) < 0:
					assert (False)
				reactiveMax = math.sqrt((activeMax * activeMax) - (result[i].real * result[i].real))  # this is the maximum (also minimum with -1 sign ;-) )
				reactive = max((-1 * reactiveMax), min(desiredWithReactive[i].imag, reactiveMax))
				totalResult.append(complex(result[i], reactive))

			return totalResult

		else:
			return result

	# Algorithm to plan timeshiftable devices, such as washing machines
	# Input
	#    desired:     vector with the desired profile to follow
	#    profile:    vector with the profile of the device
	def timeShiftablePlanning(self, desired, profile, powerLimitsLower=[], powerLimitsUpper=[], prices=None, beta=1):
		result = [0] * len(desired)

		if prices is None:
			prices = [0] * len(desired)

		assert (len(profile) <= len(desired))

		# first try a direct start and determine the costs:
		costs = 0
		penalty = 0
		for i in range(len(desired)):
			if (i < len(profile)):
				costs += (prices[i] * profile[i].real) + (beta * pow((math.sqrt(pow(profile[i].real - desired[i].real, 2) + pow(profile[i].imag - desired[i].imag, 2))), 2))

				sign = 1
				if profile[i].real < 0:
					sign = -1
				if len(powerLimitsUpper) > 0:
					penalty += pow(max(0.0, (sign * abs(profile[i]) - powerLimitsUpper[i])), 2)
				if len(powerLimitsLower) > 0:
					penalty += pow(max(0.0, (powerLimitsLower[i] - sign * abs(profile[i]))), 2)
			else:
				costs += pow(abs(desired[i]), 2)

		bestStart = 0
		bestCosts = costs
		bestPenalty = penalty

		# Boolean to check if it fits in the limits
		valid = False

		# simply shift the whole profile
		for shift in range(1, len(desired) - len(profile)):
			costs = 0
			penalty = 0

			for i in range(len(desired)):
				if (i - shift >= 0 and i - shift < len(profile)):
					costs += (prices[i] * profile[i - shift].real) + (beta * pow((math.sqrt(pow(profile[i - shift].real - desired[i].real, 2) + pow(profile[i - shift].imag - desired[i].imag, 2))), 2))

					sign = 1
					if profile[i - shift].real < 0:
						sign = -1
					if len(powerLimitsUpper) > 0:
						penalty += pow(max(0.0, (sign * abs(profile[i - shift]) - powerLimitsUpper[i - shift])), 2)
					if len(powerLimitsLower) > 0:
						penalty += pow(max(0.0, (powerLimitsLower[i - shift].real - sign * abs(profile[i - shift]))), 2)
				else:
					costs += pow(abs(-desired[i]), 2)

			if penalty <= bestPenalty:
				if costs <= bestCosts and penalty <= bestPenalty + 1:
					bestPenalty = penalty
					bestCosts = costs
					bestStart = shift

		# now we determined the best starttime, build the profile
		for i in range(len(profile)):
			result[bestStart + i] = profile[i]

		# and send back the result
		return result

	# Implementation of the EV charging algorithm where only charging between given bounds (or nothing at all) is accepted.
	# Paper: Martijn H. H. Schoot Uiterkamp et al., "Offline and online scheduling of electric vehicle charging with a minimum charging threshold", submitted to SmartGridComm 2018.
	def continuousBufferPlanningBounds(self, desired, chargeRequired, powerMin, powerMax, powerLimitsUpper=[]):
		# This algorithm starts with a copy of the code mentioned above to handle power limits
		# FIXME: Perhaps we can merge this in the future when this algorithm is validated to be mature in several simulations
		# FIXME: Can this also include prices and beta?
		result = [0.0] * len(desired)
		remainingCharge = chargeRequired

		# Check whether we need to charge anyways (trivial..)
		if (chargeRequired <= 0):
			return result

		# //Check if the request amount can be charged within both the car max power limit and the given power limits of the signal (if they are given)
		# //To this end we separate the power limits out.
		powerLimits = [powerMax] * len(desired)
		if len(powerLimitsUpper) == len(desired):
			for i in range(0, len(desired)):
				powerLimits[i] = min(powerLimitsUpper[i], powerMax)
				if powerLimits[i] < 0:
					assert powerLimits[i] >= -0.0001  # very small negative floats may occur, ignore these.
					powerLimits[i] = 0
				assert (powerLimits[i] >= 0)

		# //First check if the total amount can be charged within the given horizon without going over the maximum power, if not we return the best we can do
		# //which is maximal charging on each time interval.
		if (chargeRequired > powerMax * len(desired)):
			return [powerMax] * len(desired)
		# //If the total amount that needs to be done fits within the device powerMax but does exceed the given power Limits from above, we simply go over the
		# //limits by as little as possible to get our job done. NOTE: this is because sometimes the controller might request power limits which are too stringent
		# //for the device/job at hand.
		elif len(powerLimitsUpper) == len(desired):
			totalAvailable = 0.0
			remaining = [0.0] * len(desired)
			for i in range(0, len(desired)):
				totalAvailable += powerLimits[i]
				remaining[i] = powerMax - powerLimits[i]

			if totalAvailable < chargeRequired:
				sortedRemaining = list(remaining)
				sortedRemaining.sort()
				overLimits = chargeRequired - totalAvailable
				breakpoint = 0.0
				position = 0
				while position < len(desired) and (overLimits / (len(desired) - position) > sortedRemaining[position]) and (position < len(sortedRemaining)):
					overLimits -= sortedRemaining[position]
					breakpoint = sortedRemaining[position]
					position += 1

				for i in range(0, len(desired)):
					if remaining[i] > breakpoint:
						result[i] = powerLimits[i] + (overLimits / (len(desired) - position))
					else:
						result[i] = powerMax  # powerLimits[i]  # Bugfix compared to C++

				return result

		# Until here: exactly the same as continuousBufferPlanningPositive !

		# Check if powerlimits satisfy one of the two conditions for monotonicity (see also the paper)
		sortedDesired = list(desired)
		sortedDesired.sort()
		sortedPowerLimits = [x for y, x in sorted(zip(desired, powerLimits))]

		flag_01 = True
		flag_02 = True
		for i in range(1, len(desired)):
			if sortedPowerLimits[i] < sortedPowerLimits[i - 1]:
				flag_01 = False
				break

		if min(sortedPowerLimits) < 2 * powerMin:
			flag_02 = False

		if flag_01 == False and flag_02 == False:
			assert (False)  # Forbidden state

		# Check if charging requirement is feasible.
		# If requirement is infeasible:  increase requirement to nearest multiple of powerMin and iteratively assign load of powerMin to cheapest intervals
		sortedPowerLimits_normal = list(powerLimits)
		sortedPowerLimits_normal.sort(reverse=True)
		Lower_bound = 0.0
		Upper_bound = 0.0
		flag_03 = False
		for i in range(0, len(desired)):
			Lower_bound += powerMin
			Upper_bound += sortedPowerLimits_normal[i]
			if Lower_bound <= chargeRequired <= Upper_bound:
				flag_03 = True
				break

		if flag_03 == False:
			sortedIndices = [x for y, x in sorted(zip(desired, range(0, len(desired))))]
			remaining_charge = chargeRequired
			for i in range(0, len(desired)):
				if remaining_charge > 0:
					result[sortedIndices[-i - 1]] = min(remaining_charge, powerMin)
					remaining_charge -= powerMin
				else:
					break
			return result

		# Now comes the actual algorithm!
		# For each number of inactive intervals ("lower"), we compute the optimal solution by increasing the fill-level (breakpoint).
		# Finally, we select the solution with smallest objective value and construct the optimal solution.
		# Line numbers in comments represent algorithm line numbers as presented in:
		#      Martijn H. H. Schoot Uiterkamp et al., "Offline and online scheduling of electric vehicle charging with a minimum charging threshold", submitted to SmartGridComm 2018.

		lowerLevels = list(result)
		upperLevels = list(result)
		for i in range(0, len(desired)):
			lowerLevels[i] = -sortedDesired[i] + powerMin
			upperLevels[i] = -sortedDesired[i] + sortedPowerLimits[i]

		sortedLowerLevels = list(lowerLevels)
		sortedUpperLevels = list(upperLevels)
		sortedLowerLevels.sort(reverse=True)
		sortedUpperLevels = [x for y, x in sorted(zip(sortedDesired, sortedUpperLevels))]

		breakpoint = sortedLowerLevels[len(desired) - 1]
		lower = max(0, len(desired) - math.floor(chargeRequired / powerMin))
		Index_corrector = lower
		upper = len(desired) - 1
		Levels_free = [sortedUpperLevels[upper]]
		Num_free = 1
		CurrentObjective_nonFree = 0.0
		for i in range(0, lower):
			CurrentObjective_nonFree += sortedDesired[i] ** 2
		for i in range(lower, upper):
			CurrentObjective_nonFree += sortedLowerLevels[i] ** 2

		breakpoint_next = min(sortedLowerLevels[upper - 1], Levels_free[0])
		#####
		if breakpoint_next == sortedLowerLevels[upper - 1]:
			flag_next_breakpoint = 0
		else:
			flag_next_breakpoint = 1
		#####

		if upper == lower:
			if Num_free == 0:
				pass
			else:
				breakpoint_next = Levels_free[0]
				#####
				flag_next_breakpoint = 1  #####
		else:
			if Num_free == 0:
				breakpoint_next = sortedLowerLevels[upper - 1]
				#####
				flag_next_breakpoint = 0  #####
			else:
				breakpoint_next = min(sortedLowerLevels[upper - 1], Levels_free[0])
				#####
				if breakpoint_next == sortedLowerLevels[upper - 1]:
					flag_next_breakpoint = 0
				else:
					flag_next_breakpoint = 1  #####

		remainingCharge = chargeRequired - (len(desired) - lower) * powerMin
		Optimal_breakpoint = []
		Optimal_objective = []

		def Divisor(remainingCharge, Num_free):
			if Num_free == 0:
				return float('inf')
			else:
				return remainingCharge / Num_free

		Max_lower = 0
		Max_load = 0
		for i in range(0, len(desired)):
			if Max_load + sortedPowerLimits[-i - 1] >= chargeRequired:
				Max_lower = len(desired) - i - 1
				break
			else:
				Max_load += sortedPowerLimits[-i - 1]

		while lower <= upper and lower <= Max_lower:  # Line number 7
			while breakpoint + Divisor(remainingCharge, Num_free) > breakpoint_next:  # Line number 8
				remainingCharge -= Num_free * (breakpoint_next - breakpoint)  # Line number 9
				breakpoint = breakpoint_next
				####if sortedLowerLevels[upper - 1] == breakpoint_next:    # Line number 10
				#####
				if flag_next_breakpoint == 0:  # Line number 10
					#####
					# Line number 11:
					CurrentObjective_nonFree -= sortedLowerLevels[upper - 1] ** 2
					## Binary search procedure to insert upper level in (sorted) list Levels_free:
					left = 0
					right = Num_free - 1
					flag = 0
					while left + 1 < right:
						mid = math.ceil((left + right) / 2.0)
						if Levels_free[mid] == sortedUpperLevels[upper - 1]:
							Levels_free.insert(mid + 1, sortedUpperLevels[upper - 1])
							flag = 1
							break
						elif Levels_free[mid] > sortedUpperLevels[upper - 1]:
							right = mid - 1
						else:
							left = mid + 1
					if flag == 0:
						if sortedUpperLevels[upper - 1] <= left:
							Levels_free.insert(left, sortedUpperLevels[upper - 1])
						elif sortedUpperLevels[upper - 1] >= right:
							Levels_free.insert(right + 1, sortedUpperLevels[upper - 1])
						else:
							Levels_free.insert(left + 1, sortedUpperLevels[upper - 1])
					Num_free += 1
					upper -= 1

				else:
					# Line number 13
					CurrentObjective_nonFree += Levels_free[0] ** 2
					Levels_free.pop(0)
					Num_free -= 1

				# Line number 15
				if upper == lower:
					if Num_free == 0:
						break
					else:
						breakpoint_next = Levels_free[0]
						#####
						flag_next_breakpoint = 1  #####
				else:
					if Num_free == 0:
						breakpoint_next = sortedLowerLevels[upper - 1]
						#####
						flag_next_breakpoint = 0  #####
					else:
						breakpoint_next = min(sortedLowerLevels[upper - 1], Levels_free[0])
						#####
						if breakpoint_next == sortedLowerLevels[upper - 1]:
							flag_next_breakpoint = 0
						else:
							flag_next_breakpoint = 1  #####

			# Lines 17-19
			Optimal_breakpoint.append(breakpoint + remainingCharge / Num_free)
			Optimal_objective.append(CurrentObjective_nonFree + Num_free * Optimal_breakpoint[lower - Index_corrector] ** 2)
			lower += 1
			CurrentObjective_nonFree += sortedDesired[lower - 1] ** 2 - sortedLowerLevels[lower - 1] ** 2
			remainingCharge = powerMin
			breakpoint = Optimal_breakpoint[lower - 1 - Index_corrector]

			if upper == lower:
				if Num_free == 0:
					break
				else:
					breakpoint_next = Levels_free[0]
					#####
					flag_next_breakpoint = 1  #####
			else:
				if Num_free == 0:
					breakpoint_next = sortedLowerLevels[upper - 1]
					#####
					flag_next_breakpoint = 0  #####
				else:
					breakpoint_next = min(sortedLowerLevels[upper - 1], Levels_free[0])
					#####
					if breakpoint_next == sortedLowerLevels[upper - 1]:
						flag_next_breakpoint = 0
					else:
						flag_next_breakpoint = 1  #####

		# Lines 21-23
		Optimal_lower_final = Optimal_objective.index(min(Optimal_objective))
		Optimal_breakpoint_final = Optimal_breakpoint[Optimal_lower_final]
		Optimal_activation = sortedLowerLevels[Optimal_lower_final + Index_corrector]
		## Constructing the optimal solution. Keeping track of remaining charge is required in case some of the desired profiles are the same.
		Remaining_charge = chargeRequired
		for i in range(0, len(desired)):
			if -desired[i] + powerMin <= Optimal_activation:
				result[i] = max(powerMin, min(Optimal_breakpoint_final + desired[i], powerLimits[i]))
				result[i] = max(0, min(result[i], Remaining_charge))
				Remaining_charge -= result[i]

		self.fillLevel = Optimal_breakpoint_final

		return result
