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


#helper function to convert some input data from the ALPG into lists for model creation

def listFromFile(fname):
	result = []
	cnt = 0
	fin = open(fname, 'r')
	for line in fin:
		arr = []
		line = line.split(':')[1]
		line = line.rstrip()
		s = line.split(',')
		for element in s:
			if(element != ''):
				arr.append(float(element))
		result.append(arr)
		cnt += 1
	return result

def listFromFileStr(fname):
	result = []
	cnt = 0
	fin = open(fname, 'r')
	for line in fin:
		arr = []
		line = line.split(':')[1]
		line = line.rstrip()
		s = line.split(',')
		for element in s:
			if(element != ''):
				arr.append((element))
		result.append(arr)
		cnt += 1
	return result

def indexFromFile(fname, hnum):
	cnt = 0
	fin = open(fname, 'r')
	for line in fin:
		line = int(line.split(':')[0])
		if line == hnum:
			return cnt
		cnt += 1
	return -1


