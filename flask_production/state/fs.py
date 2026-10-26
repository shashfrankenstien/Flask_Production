import os
import re
import pickle
from datetime import datetime as dt
from collections import defaultdict

from .base import BaseStateHandler

_HIST_DT_FORMAT = "%Y%m%d%H%M%S%f"
_HIST_FILE_PAT = r"(\S+)_(\d+)\.pickle"


def _read_pickle(path):
	with open(path, 'rb') as f:
		return pickle.load(f)


class FileSystemState(BaseStateHandler):

	def __init__(self, uri=None, hist_limit=30) -> None:
		super().__init__()
		if uri is None:
			uri = os.path.join(self._get_current_app_data_directory(), "states")

		if isinstance(hist_limit, bool) or not isinstance(hist_limit, int) or hist_limit < 0:
			raise ValueError("hist_limit must be a non-negative integer")

		self._job_state_dir = uri
		if not os.path.isdir(self._job_state_dir):
			os.makedirs(self._job_state_dir)

		self._job_hist_dir = os.path.join(os.path.dirname(uri), 'states_hist')
		if not os.path.isdir(self._job_hist_dir):
			os.makedirs(self._job_hist_dir)
		self._hist_limit = hist_limit


	def _get_current_app_data_directory(self):
		# create the unique data directory for current app
		# this folder can contain
		# - info file that includes data used to come up with current app signature
		# - job state information

		# check if running as root
		# os.geteuid() is only available on Unix-like systems
		is_unix_root = os.name !='nt' and hasattr(os, 'geteuid') and os.geteuid() == 0
		if is_unix_root:
			share_dir = '/var/lib/flask_production' # if running as root
		else:
			share_dir = os.environ.get('APPDATA') or os.environ.get('XDG_DATA_HOME') or os.path.join(os.environ['HOME'], '.local', 'share')

		cur_app_data_dir_path = os.path.join(
			share_dir,
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
		signature = job_obj.signature_hash()

		if self._job_state_dir is not None:
			state_file = os.path.join(self._job_state_dir, f"{signature}.pickle")
			if os.path.isfile(state_file) and self._hist_limit > 0:
				old_state = _read_pickle(state_file)

				if 'timestamp' in old_state:
					hist_file = os.path.join(self._job_hist_dir, f"{signature}_{old_state['timestamp'].strftime(_HIST_DT_FORMAT)}.pickle")
					os.replace(state_file, hist_file)

			with open(state_file, 'wb') as f:
				logs = job_obj._logs_to_dict()
				pickle.dump({'logs':logs, 'disabled': job_obj.is_disabled, 'timestamp': dt.now()}, f) # we only care about logs

		if self._job_hist_dir is not None:
			hist_files = [f for f in os.listdir(self._job_hist_dir) if f.startswith(signature)]
			if len(hist_files) > self._hist_limit:
				files_to_delete = sorted(hist_files, reverse=True)[self._hist_limit:]
				for f in files_to_delete:
					os.remove(os.path.join(self._job_hist_dir, f))



	def restore_all_job_logs(self, jobs_list):
		jobs = jobs_list.copy() # work on a shallow copy of this list - safer in case the list changes. TODO: maybe use locks instead?
		if self._job_state_dir is not None:
			found_states = []
			for j in jobs:
				filename = f"{j.signature_hash()}.pickle"
				filepath = os.path.join(self._job_state_dir, filename)
				if os.path.isfile(filepath):
					state = _read_pickle(filepath)
					logs = state['logs'] if 'logs' in state else state # doing it this way for backwards compatibility as 'state' was previously 'logs'
					j._logs_from_dict(logs)
					if state.get('disabled'):
						j.disable()
					found_states.append(filename)

			# clean up other states that did not match current jobs list (possible stale)
			for f in os.listdir(self._job_state_dir):
				if f not in found_states:
					os.remove(os.path.join(self._job_state_dir, f))

			print("* scheduler state restored from filesystem *")

		if self._job_hist_dir is not None:
			hist_files = defaultdict(list)
			for f in os.listdir(self._job_hist_dir):
				if matched := re.match(_HIST_FILE_PAT, f):
					sig = matched.groups()[0]
					hist_files[sig].append(f)

			files_to_retain = []
			for j in jobs:
				sig = j.signature_hash()
				if sig in hist_files:
					files_to_retain += hist_files[sig] # mark these as files to keep

			# clean up other states that did not match current jobs list (possible stale)
			for f in os.listdir(self._job_hist_dir):
				if f not in files_to_retain:
					os.remove(os.path.join(self._job_hist_dir, f))
