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

from collections import OrderedDict

class DemandFunction():
	def __init__(self, minPrice = -2000, maxPrice = 2000, minComfort = -1000, maxComfort = 1000):
		#Local params
		self.minPrice = minPrice
		self.maxPrice = maxPrice
		self.minComfort = minComfort
		self.maxComfort = maxComfort
		self.function = OrderedDict()
	
	def sort(self):
		# A sort function, this is all we need and the default solution (the one below) just is ugly.
		self.function = OrderedDict(sorted(self.function.items(), key=lambda t: t[0]))
	
	def clear(self):
		self.function = OrderedDict()
	
	def checkFunction(self):
		pass
	
	def removePoint(self, price):
		if price in self.function:
			del self.function[price]
			return True
		return False
	
	# Add a point, be careful, it will remove (new)illegal points after addition!    
	def addPoint(self, demand, price):
		price = int(round(price))
		
		assert(price >= self.minPrice)
		assert(price <= self.maxPrice)
		
		if price in self.function:
			del self.function[price]

		self.function[price] = demand
		self.sort()
		self.fixLeftRight(price)
		
	# Again: Caution, this will simply overwrite stuff!    
	def addLine(self, maxDemand, minDemand, minPrice, maxPrice):
		minPrice = int(round(minPrice))
		maxPrice = int(round(maxPrice))
		
		assert(minPrice >= self.minPrice)
		assert(maxPrice <= self.maxPrice)    
		assert(minPrice <= maxPrice) #If both prices are the same, a single point will be the result
		assert(minDemand <= maxDemand)
				
		#First remove all points in the range:
		for price in list(self.function.keys()):
			if price >= minPrice and price <= maxPrice:
				del self.function[price]
		
		#Now add the two points
		self.function[minPrice] = maxDemand
		self.function[maxPrice] = minDemand
		self.sort()
		self.fixLeft(minPrice)
		self.fixRight(maxPrice)
		
	def addFunction(self, other, overwrite = True):
		# Note, we assume the same market here as also considered by Koen Kok on the PowerMatcher
		assert(self.minPrice == other.minPrice)
		assert(self.maxPrice == other.maxPrice)
		
		#check if this function is empty:
		if len(self.function) == 0:
			self.function = other.function
			return True
		
		#Check if the other function is empty:
		if len(other.function) == 0:
			# Move along, nothing to see here!
			return True
		
		#otherwise, let us merge the two:
		result = OrderedDict()
		
		#obtain a list of all keys in both functions:
		for price in list(self.function.keys()):
			result[price] = self.demandForPrice(price) + other.demandForPrice(price)

		for price in list(other.function.keys()):
			if price not in self.function:
				result[price] = self.demandForPrice(price) + other.demandForPrice(price)
								
		if overwrite:			
			self.function = result  
			self.sort()
			return True    
		else:
			r = DemandFunction()
			r.function = result
			r.sort()
			r.minPrice = self.minPrice
			r.maxPrice = self.maxPrice
			return r
		
		return False
	
	def subtractFunction(self, other, overwrite = True):
		# Note, we assume the same market here as also considered by Koen Kok on the PowerMatcher
		assert(self.minPrice == other.minPrice)
		assert(self.maxPrice == other.maxPrice)
		
		#check if this function is empty:
		if len(self.function) == 0:
			self.function = other.function
			return True
		
		#Check if the other function is empty:
		if len(other.function) == 0:
			# Move along, nothing to see here!
			return True
		
		#otherwise, let us merge the two:
		result = OrderedDict()
		
		#obtain a list of all keys in both functions:
		for price in list(self.function.keys()):
			result[price] = self.demandForPrice(price) - other.demandForPrice(price)

		for price in list(other.function.keys()):
			if price not in self.function:
				result[price] = self.demandForPrice(price) - other.demandForPrice(price)
					
		if overwrite:			
			self.function = result  
			self.sort()
			return True    
		else:
			r = DemandFunction()
			r.function = result
			r.sort()
			r.minPrice = self.minPrice
			r.maxPrice = self.maxPrice
			return r
		
		return False   
					
					
	def demandForPrice(self, price):
		assert(price >= self.minPrice)
		assert(price <= self.maxPrice)
		
		items = list(self.function.items())

		#check if the bidding function provides options anyway:
		if len(items) == 0:
			return 0 # no options.
		elif len(items) == 1:
			return items[0][1] #Only one option, so this is easy too.
		
		if price in self.function:
			return self.function[price]
		elif price <= items[0][0]: #Check the first item
			return items[0][1]
		elif price >= items[-1][0]: #or overflow on the other side
			return items[-1][1]
		else:
			#Unfortunately, we do not have a direct hit... Let's interpolate between the points
			idx = 1
			while items[idx][0] < price: #loop through the list to find the two corresponding indices
				idx += 1
				assert(idx < len(items))
				
			#now we should have the correct index, get left and right:
			left = idx - 1
			right = idx
			
			demandDelta = items[left][1] - items[right][1]
			priceDelta = items[right][0] - items[left][0]
			assert(priceDelta > 0)
			
			demand = items[left][1] - ((demandDelta / priceDelta) * (price - items[left][0]))
			return demand
	
		return 0 #We should never get here though
	
	
	def priceForDemand(self, demand):
		# First make a convenient list of the items
		items = list(self.function.items())   
		
		#check if the bidding function provides options anyway:
		if len(items) <= 1:
			return 0 # no options, price doesn't really matter...
		
		#check if we are out of bounds:
		if demand >= items[0][1]:
			return self.minPrice
		elif demand <= items[-1][1]:
			return self.maxPrice
		
		#Otherwise, iterate but check for exact matches as well:
		idx = 0
		while items[idx][1] >= demand:
			if items[idx][1] == demand:
				return items[idx][0]
			idx += 1
			assert(idx < len(items))
		
		#Indices in which this demand lies:
		left = idx-1    
		right = idx
		
		demandDelta = items[left][1] - items[right][1]
		priceDelta = items[right][0] - items[left][0]

		# Straight line, we need to avoid division by 0:
		if demandDelta == 0:
			# Select the lowest price:
			return items[left][0]
			
		price = items[left][0] + ((priceDelta / demandDelta) * (items[left][1] - demand))
		return price
		
	# Fixes the function to make it concave after the insertion of a point/line
	# Note: The developer of the demand function is responsible for the demand function creation and should know what he/she is doing!
	def fixLeft(self, price):
		items = list(self.function.items()) 
		
		if len(items) < 2:
			return
		
		#first find the spot were we need to start
		idx = 0
		while items[idx][0] < price:
			idx += 1
			assert(idx < len(items))
			
		#Get the demand for the last addition    
		demand = items[idx][1]
			
		#And now check the left side of the price spectrum, demand needs to increase    
		idx -= 1
		if(idx >= 0):
			assert(items[idx][0] < price)
				
			while idx >= 0:
				if(items[idx][1] < demand):
					self.function[items[idx][0]] = demand
				demand = self.function[items[idx][0]]
				idx -= 1           
	
	def fixRight(self, price):
		items = list(self.function.items()) 
		
		if len(items) < 2:
			return
		
		#first find the spot were we need to start
		idx = len(items) - 1
		while items[idx][0] > price:
			idx -= 1
			assert(idx < len(items))
			
		#Get the demand for the last addition    
		demand = items[idx][1]
			
		#And now check the left side of the price spectrum, demand needs to increase    
		idx += 1
		if(idx < len(items)):
			assert(items[idx][0] > price)
				
			while idx < len(items):
				if(items[idx][1] > demand):
					self.function[items[idx][0]] = demand
				demand = self.function[items[idx][0]]
				idx += 1 
		
	def fixLeftRight(self, price):
		#Check if the left side is consistent
		self.fixLeft(price)
		
		#Check if the right side is consistent
		self.fixRight(price)    
	
	
	# Calculates the difference between two functions, required to see the change
	def difference(self, other):
		# Note, we assume the same market here as also considered by Koen Kok on the PowerMatcher
		assert(self.minPrice == other.minPrice)
		assert(self.maxPrice == other.maxPrice)
		
		# Note: next comment is a trick to speedup things, however it should be tested more whether it is useful in practice.
		# if(len(self.function)+len(other.function)) > 50:
		# 	return 1000000 #just return a big number, this triggers a new function request to clean up! ;)

		#Create a new temp function in which we subtract the two functions
		diff = self.subtractFunction(other, False).surface()

		# Now measure the total area of the original function
		surface = self.surface()
		
		# Calculate the size of changed area wrt the original
		if surface != 0:
			result = diff / surface
		else:
			result = diff #or perhaps max int?
		
		return result
	
	
	def surface(self):
		result = 0
		
		# Make a list of all keys (prices) in the both functions
		prices = []
		for price in list(self.function.keys()):
			prices.append(price)
				
		# Make sure that both ends of the price spectrum are included
		if self.minPrice not in prices:
			prices.append(self.minPrice)
		if self.maxPrice not in prices:
			prices.append(self.maxPrice)
			
		#check for zero crossings:
		if self.demandForPrice(self.minPrice) > 0 and self.demandForPrice(self.maxPrice) < 0:
			zeroPrice = self.priceForDemand(0)
			if zeroPrice not in prices:
				prices.append(zeroPrice)
			
		for i in range(0, (len(prices)-1)):
			left = self.demandForPrice(prices[i])
			right = self.demandForPrice(prices[i+1])
			
			#first calculate the rectangle:
			result += abs(min(left, right) * (prices[i+1] - prices[i]))
			
			if left == min(left, right):
				#right is longer, add that triangle
				result += abs((right - left) * (prices[i+1] - prices[i]) * 0.5)
			else:
				result += abs((left - right) * (prices[i+1] - prices[i]) * 0.5)
		
		return result

	def printFunction(self):
		print(self.function)