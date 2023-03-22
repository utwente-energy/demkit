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


import os
import importlib
import sys

class ModelComposer():
	def __init__(self, name):
		self.fileName = str(name)+"_composed"
		self.dir = os.getcwd()
		self.files = []
		self.clear()

	def clear(self):
		# Check if the file exists
		if os.path.isfile(self.fileName+".py"):
			os.remove(self.fileName+".py")

	def add(self, name):
		self.files.append(name)

	def compose(self):
		# Compose all files into one new source file
		sys.stderr.write("Starting model composition into: "+self.fileName+".py\n")
		sys.stderr.flush()
		output = open(self.fileName+".py", "w")

		for source in self.files:
			print("Adding source: "+source)
			input = open(source, 'r', encoding="utf8")
			lines = input.readlines()
			output.writelines(lines)
			output.write("\n")
			input.close()


		output.close()
		sys.stderr.write("Model composition completed\n")
		sys.stderr.flush()

	def load(self):
		sys.stderr.write("Importing composed model: "+self.fileName+"\n")
		sys.stderr.flush()

		importlib.import_module(self.fileName)