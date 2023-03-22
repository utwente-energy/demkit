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

# Just a small test script to see if demand functions are doing what we expect them to do
# THIS IS NOT A UNITTEST
print("hi world")

from demandFunction import DemandFunction

f1 = DemandFunction()
f1.addPoint(1000, -1000)
f1.addPoint(100, 0)
f1.addPoint(0, 1000)
print("print") 
print(f1.function)

print(f1.demandForPrice(-1000))
print(f1.demandForPrice(0))
print(f1.demandForPrice(1000))
print(f1.demandForPrice(400))
print("P4D")
print(f1.priceForDemand(1000))
print(f1.priceForDemand(60))
print(f1.priceForDemand(0))

f2 = DemandFunction()
f2.addLine(3700, 1380, -1000, 400)
f2.addLine(0, 0, 401, 1000)
print("print") 
print(f2.function)

print(f2.demandForPrice(-1000))
print(f2.demandForPrice(0))
print(f2.demandForPrice(1000))
print(f2.demandForPrice(400))

f1.addFunction(f2)
print(f1.function)



f2 = DemandFunction()
f2.addPoint(0, 0)
print("print") 
print(f2.function)

print(f2.demandForPrice(-1000))
print(f2.demandForPrice(0))
print(f2.demandForPrice(1000))
print(f2.demandForPrice(400))

f2.resetFunction()
print(f2.function)

f2 = DemandFunction()
f2.addLine(3700, 1380, -800, 400)
f2.addLine(0, 0, 401, 800)
print("print") 
print(f2.function)

print(f2.demandForPrice(-1000))
print(f2.demandForPrice(0))
print(f2.demandForPrice(1000))
print(f2.demandForPrice(400))

f2.resetFunction()
print(f2.function)

f2.addLine(1,1,-1000, 1000)
print(f2.surface())

f3 = DemandFunction()
f3.addLine(2,2,-1000, 0)
f3.addLine(0,0,1, 1000)
print(f3.surface())
print(f2.difference(f3))
