import os
import sys
import hashlib

from .host_info import get_host_info


class BaseStateHandler:

	def __init__(self) -> None:
		# multiple apps / programs may use this library
		# _cur_app_unique_info is a way to create a unique id for each app
		# it uses:
		# - git url (added 2026-10-25)
		# - current working directory: isolates apps in the same directory from other apps on the system
		# - path to python executabe: isolates apps that use different python installations
		# - full command line:
		# 		- this includes name of the script file: isolates a script / entry point from others
		# 		- command line arguments: isolates when same script is run using different cli arguments
		_host_info = get_host_info()
		self._cur_app_unique_info = [
			_host_info['git_url'], 	# git url if available
			os.getcwd(),  			# current working directory
			sys.executable,			# python executable
			*sys.argv				# script name and all cli arguments
		]
		self._cur_app_unique_info_hash = hashlib.sha1(':'.join(self._cur_app_unique_info).encode()).hexdigest()


	def save_job_logs(self, job_obj):
		pass

	def restore_all_job_logs(self, jobs_list):
		pass
