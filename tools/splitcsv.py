#!/usr/bin/python3

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



import sys

if len(sys.argv) == 1:
	print("Error, need two arguments: ./splitcsv.py folder input.file")
p = sys.argv[1]
i = p+'/'+sys.argv[2]


fi = open(i,  'r')
line = fi.readline();
cols = len(line.split(';'))

print("cols to be processed: "+str(cols))

for c in range(0, cols):
	print("col: "+str(c))
	
	out = []
	o = p+'/'+sys.argv[2].split('.')[0]+"-"+str(c)+".csv"
	fo = open(o, 'w')
	
	fi.seek(0)
	for line in fi:
		fo.write(line.rstrip().split(';')[c] + '\n')
		
	fo.close()
