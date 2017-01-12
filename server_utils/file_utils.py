import glob
import os
from collections import defaultdict
from datetime import datetime, timezone

def to_date_string(timestamp):
	utc_time = datetime.fromtimestamp(timestamp, timezone.utc)
	local_time = utc_time.astimezone()
	return local_time.strftime("%Y-%m-%d %H:%M")



class FileMonitor:
	def __init__(self,extension='.ipynb',folder=['materials','questions']):
		self.ext = extension
		self.folder = folder
		self.cache = dict()
		self._get_files()

	def _get_files(self):
		pattern_match1 = os.path.join(os.getcwd(),*self.folder,'**','*'+self.ext)
		pattern_match2 = os.path.join(os.getcwd(),*self.folder,'*'+self.ext)
		files = glob.glob(pattern_match1)+glob.glob(pattern_match2)
		print(files)
		self.files = {f:os.path.getmtime(f) for f in files}
		for file in set(self.cache.keys()) - set(self.files.keys()):
			del self.cache[file]
		for file in set(self.files.keys()) - set(self.cache.keys()):
			self.cache[file] = dict()

	def refresh(self):
		self._get_files()

	def get_viewable_files(self):
		return [(self.to_relative(f),to_date_string(t)) for f,t in self.files.items()]

	def apply_function(self,f,file):
		if file not in self.files:
			return ""
		new_cache = self.cache[file]
		if f not in new_cache:
			print("Adding to cache")
			new_cache[f] = (f(file),self.files[file])
		else:
			if new_cache[f][1] != self.files[file]:
				print("Updating Cache")
				new_cache[f] = (f(file),self.files[file])
			else:
				print("Returning old Cache")
		return new_cache[f][0]


	def to_relative(self,file_name):
		return os.path.relpath(file_name,os.path.join(os.getcwd(),*self.folder))

