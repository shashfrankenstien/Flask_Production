import sys
from datetime import datetime as dt
import threading

from dateutil import tz
from contextlib import contextmanager
import traceback
import logging

from ._capture import print_capture


# default logging configuration
# logging.captureWarnings(True)
LOG_FORMATTER = logging.Formatter('%(message)s')
LOGGER_NAME = 'flask_production'
LOGGER = logging.getLogger(LOGGER_NAME)
LOGGER.setLevel(logging.INFO)
# stop propagting to root logger
LOGGER.propagate = False




class _PrintLogger(object):
	'''
	logging class to capture any print statements within a job
	also captures start time, end time and error traceback
	'''

	def __init__(self, tzname=None):
		self._lock = threading.Lock()
		self._reset()
		self._tzname = tzname

	@property
	def log(self):
		with self._lock:
			return self._run_log

	@property
	def error(self):
		with self._lock:
			return self._err_log

	@property
	def started_at(self):
		with self._lock:
			return self._started_at

	@property
	def ended_at(self):
		with self._lock:
			return self._ended_at

	def _reset(self):
		'''clear previous run info'''
		with self._lock:
			self._run_log = ''
			self._err_log = ''
			self._started_at = None
			self._ended_at = None

	def _log_callback(self, msg: str):
		'''
		writting to stderr since stdout is being redirected here. Using print() will be circular
		log to file using the logging library if LOGGER handler is set by TaskScheduler
		'''
		if msg.strip()=='':return
		msg = msg.replace('\r\n', '\n') # replace line endings to work correctly
		sys.stderr.write(msg)
		if len(LOGGER.handlers)>0:
			LOGGER.info(msg.strip())
		with self._lock:
			self._run_log += msg

	@contextmanager
	def start_capture(self):
		'''
		begin recording print statements
		'''
		self._reset() # clear previous run info
		with self._lock:
			self._started_at = dt.now(tz=tz.gettz(self._tzname))
		with print_capture(callback=self._log_callback):
			yield
		with self._lock:
			self._ended_at = dt.now(tz=tz.gettz(self._tzname))

	def set_error(self):
		'''called when job throws error'''
		with self._lock:
			self._err_log = traceback.format_exc()

	def to_dict(self):
		with self._lock:
			return dict(
				log=self._run_log,
				err=self._err_log,
				start=self._started_at,
				end=self._ended_at,
			)

	def from_dict(self, info_dict):
		if info_dict.get('start') is not None:
			with self._lock:
				self._run_log = info_dict['log']
				self._err_log = info_dict['err']
				self._started_at = info_dict['start']
				self._ended_at = info_dict['end']
