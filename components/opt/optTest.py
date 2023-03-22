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



# planning algorithms used with profile steering
# File for small tests, but not a unit test!

import math
#import optAlgLimits
import optAlg


r01 = optAlg.OptAlg.continuousBufferPlanningBounds(0,[1.2, 1.0, 4.0],2.9,1,2,[5,5,4])
print(r01)
r02 = optAlg.OptAlg.continuousBufferPlanningPositive(0,[1,1.2,4],3.3,2,[5,5,4])
print(r02)

#opt = optAlgLimits.OptAlgLimits()


# June 18, 2018: test of lowerbound_algorithm:


#Continuous test
# just something to test these algorithms
l = []
for i in range(0, 96):
	l.append(2000*math.sin(i/10))

x = []
for i in range(0,96):
	x.append(i)


# # An EV
c = 96000
d = [0] * len(l)

ll = [-1000] * len(l)
ul = [1000] * len(l)

# def bufferPlanning(self, desired, targetSoC, initialSoC, capacity, demand, chargingPowers, powerMin = 0, powerMax = 0, powerLimitsLower = [], powerLimitsUpper = [], reactivePower = False):
#r1 = optAlg.OptAlg.bufferPlanning(l, 48000, 0, c, d, [], 0, 3700)
#print(r1)

soc1 = [0] *96
#for i in range(1, 96):
#	soc1[i] = soc1[i-1] + 0.25*r1[i-1]



#A Battery
c = 96000


#r2 = optAlg.bufferPlanning(l, 48000, 58000, c, d, [], -3700, 3700)
# print(r2)

#soc2 = [12000] *96
#for i in range(1, 96):
#	soc2[i] = soc2[i-1] + 0.25*r2[i-1]


#
d= []
for i in range(0, 96):
	d.append(max(0,1000*math.sin((i+48)/10)))




#A Buffer Converter
c = 50000
# print(d)

# def bufferPlanning(self, desired, targetSoC, initialSoC, capacity, demand, chargingPowers, powerMin = 0, powerMax = 0, powerLimitsLower = [], powerLimitsUpper = [], reactivePower = False):
#r3 = opt.bufferPlanning(l, 25000, 25000, c, d, [], 0, 3700)
# print(r3)

soc3 = [5000] *96
#for i in range(1, 96):
#	soc3[i] = soc3[i-1] + 0.25*r3[i-1] - 0.25*d[i-1]

#A Washing Machine
w = [100,2000,2000, 500, 500, 500, 1000, 200]
#r4 = opt.timeShiftablePlanning(l, w)
# print(r4)

import matplotlib.pyplot as plt
#plt.plot(x,l,x,r1, x, r2, x, r3, x, r4)
#plt.show()

#plt.plot(x,soc1, x, soc2, x, soc3)
#plt.show()



#Discrete test
#just something to test these algorithms
l = []
for i in range(0, 96):
	l.append(2000*math.sin(i/10))

x = []
for i in range(0,96):
	x.append(i)


ll = [-2500] * len(l)
ul = [2500] * len(l)

#An EV

c = 96000
p = [0, 1000, 1250, 1500, 1750, 2000, 2250, 2500, 2750, 3000, 3250, 3500]
d = [0] * len(l)

#r1 = opt.bufferPlanning(l, c, 0, c, d, p, 0, 0)
#print(r1)

soc1 = [0] *96
#for i in range(1, 96):
#	soc1[i] = soc1[i-1] + 0.25*r1[i-1]

#A Battery
p = [-3000, -2500, -2000, -1500, -1000, 0, 1000, 1500, 2000, 2500, 3000]
d = [0] * len(l)

#r2 = opt.bufferPlanning(l, 48000, 48000, c, d, p, 0, 0)
#print(r2)

soc2 = [12000] *96
#for i in range(1, 96):
#	soc2[i] = soc2[i-1] + 0.25*r2[i-1]

#A Buffer Converter
d= []
for i in range(0, 96):
	d.append(max(0,1500*math.sin((i+48)/10)))

p = [0, 1000, 1250, 1500, 1750, 2000, 2250, 2500, 2750, 3000, 3250, 3500]
c = 20000000

# def bufferPlanning(self, desired, targetSoC, initialSoC, capacity, demand, chargingPowers, powerMin = 0, powerMax = 0, powerLimitsLower = [], powerLimitsUpper = [], reactivePower = False):
#r3 = opt.bufferPlanning(l, 100000, 20000, c, d, p, 0, 0)
#print(r3)

soc3 = [5000] *96
#for i in range(1, 96):
#	soc3[i] = soc3[i-1] + 0.25*r3[i-1] - 0.25*d[i-1]

# A washing Machine
w = [100,2000,2000, 500, 500, 500, 1000, 200]
#r4 = opt.timeShiftablePlanning(l, w)
#print(r4)

import matplotlib.pyplot as plt
#plt.plot(x,l,x,r1, x, r2, x, r3, x, r4)
#plt.show()

#plt.plot(x,soc1, x, soc2, x, soc3)
#plt.show()
