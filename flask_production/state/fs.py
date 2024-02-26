import os
import pickle

from .base import BaseStateHandler




class FileSystemState(BaseStateHandler):

	def __init__(self, uri=None) -> None:
		super().__init__()
		if uri is None:
			uri = os.path.join(self._get_current_app_data_directory(), "states")

		self._job_state_dir = uri
		if not os.path.isdir(self._job_state_dir):
			os.makedirs(self._job_state_dir)


	def _get_current_app_data_directory(self):
		# create the unique data directory for current app
		# this folder can contain
		# - info file that includes data used to come up with current app signature
		# - job state information
		cur_app_data_dir_path = os.path.join(
			os.environ.get('APPDATA') or
			os.environ.get('XDG_DATA_HOME') or
			os.path.join(os.environ['HOME'], '.local', 'share'),
			"flask_production_data",
			self._cur_app_unique_info_hash
		)
		if not os.path.isdir(cur_app_data_dir_path):
			os.makedirs(cur_app_data_dir_path)

		# create an *.cwd file that is named after the current working directory name
		# - helps to easily identify the app and manually inspect files in the data folder
		# - contains _cur_app_unique_info used to come up with the self._cur_app_unique_info_hash
		with open(os.path.join(cur_app_data_dir_path, f'{os.path.basename(os.getcwd())}.cwd'), 'w') as f:
			for info in self._cur_app_unique_info:
				f.write(str(info)+"\n")

		return cur_app_data_dir_path


	def save_job_logs(self, job_obj):
		if self._job_state_dir is not None:
			filename = job_obj.signature_hash()
			with open(os.path.join(self._job_state_dir, f"{filename}.pickle"), 'wb') as f:
				logs = job_obj._logs_to_dict()
				pickle.dump({'logs':logs, 'disabled': job_obj.is_disabled}, f) # we only care about logs


	def restore_all_job_logs(self, jobs_list):
		if self._job_state_dir is not None:
			found_states = []
			for j in jobs_list.copy(): # work on a shallow copy of this list - safer in case the list changes. TODO: maybe use locks instead?
				filename = f"{j.signature_hash()}.pickle"
				filepath = os.path.join(self._job_state_dir, filename)
				if os.path.isfile(filepath):
					with open(filepath, 'rb') as f:
						state = pickle.load(f)
						logs = state['logs'] if 'logs' in state else state # doing it this way for backwards compatibility as 'state' was previously 'logs'
						j._logs_from_dict(logs)
						if state.get('disabled'):
							j.disable()
					found_states.append(filename)
					# print("restored", j)
			# clean up other states that did not match current jobs list (possible stale)
			for f in os.listdir(self._job_state_dir):
				if f not in found_states:
					os.remove(os.path.join(self._job_state_dir, f))
