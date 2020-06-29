import sys
import time
from datetime import timedelta, datetime as dt
from monthdelta import monthdelta
import holidays
import re
import threading

from contextlib import contextmanager
import traceback
import logging
# default logging configuration
logging.basicConfig(format='%(message)s', level=logging.INFO)
logging.captureWarnings(True)


from ._capture import print_capture

USHolidays = holidays.US()


class _JobRunLogger(object):

	def __init__(self, log_filepath):
		self._lock = threading.Lock()
		self._log_filepath = log_filepath
		logging.basicConfig(filename=self._log_filepath) # setting filepath for _JobRunLogger
		self._reset()

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
		with self._lock:
			self._run_log = ''
			self._err_log = ''
			self._started_at = None
			self._ended_at = None

	def _log_callback(self, msg):
		# writting to stderr since stdout is being redirected here. Using print() will be circular
		sys.stderr.write(msg)
		if self._log_filepath:
			logging.info(msg.strip())
		with self._lock:
			self._run_log += msg

	@contextmanager
	def start_capture(self):
		self._reset()
		with self._lock:
			self._started_at = dt.now()
		with print_capture(callback=self._log_callback):
			yield
		with self._lock:
			self._ended_at = dt.now()

	def set_error(self):
		with self._lock:
			self._err_log = traceback.format_exc()

	def to_dict(self):
		with self._lock:
			return {
				'log': self._run_log,
				'err': self._err_log,
				'start': self._started_at,
				'end': self._ended_at,
			}



class Job(object):

	RUNABLE_DAYS = {
		'day': lambda d, hols : True,
		'weekday': lambda d, hols : d.isoweekday() < 6,
		'weekend': lambda d, hols : d.isoweekday() > 5,
		'businessday': lambda d, hols : d not in hols and d.isoweekday() < 6,
		'holiday': lambda d, hols : d in hols or d.isoweekday() > 5,
		# days of the week
		'monday': lambda d, hols: d.isoweekday() == 1,
		'tuesday': lambda d, hols: d.isoweekday() == 2,
		'wednesday': lambda d, hols: d.isoweekday() == 3,
		'thursday': lambda d, hols: d.isoweekday() == 4,
		'friday': lambda d, hols: d.isoweekday() == 5,
		'saturday': lambda d, hols: d.isoweekday() == 6,
		'sunday': lambda d, hols: d.isoweekday() == 7,
	}

	def __init__(self, every, at, func, kwargs):
		self.interval = every
		self.time_string = at
		self.func = func
		self.kwargs = kwargs
		self.is_running = False
		self._generic_err_handler = None
		self._err_handler = None

	def init(self, calendar, generic_err_handler=None, log_filepath=None):
		self.calendar = calendar
		self._generic_err_handler = generic_err_handler
		self._run_info = _JobRunLogger(log_filepath)
		self.schedule_next_run()
		print(self)
		return self

	def catch(self, err_handler):
		self._err_handler = err_handler
		return self

	@staticmethod
	def to_timestamp(d):
		return time.mktime(d.timetuple())+d.microsecond/1000000.0

	def schedule_next_run(self, just_ran=False):
		h, m = self.time_string.split(':')
		n = dt.now()
		n = dt(n.year, n.month, n.day, int(h), int(m), 0)
		ts = self.to_timestamp(n)
		if self._job_must_run_today() and time.time() < ts+300 and not just_ran:
			self.next_timestamp = ts
		else:
			next_day = n + timedelta(days=1)
			while not self._job_must_run_today(next_day):
				next_day += timedelta(days=1)
			self.next_timestamp = self.to_timestamp(next_day)#next_day.timestamp()

	def _job_must_run_today(self, date=None):
		return self.RUNABLE_DAYS[self.interval](date or dt.now(), self.calendar)

	def is_due(self):
		return (time.time() >= self.next_timestamp) and not self.is_running

	def did_fail(self):
		return self._run_info.error != ''

	def run(self):
		with self._run_info.start_capture(): # captures all writes to stdout
			self.is_running = True
			try:
				print("========== Job Start [{}] =========".format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
				print("Executing {}".format(self))
				start_time = time.time()
				return self.func(**self.kwargs)
			except Exception as e:
				print(e)
				self._run_info.set_error()
				if self._err_handler is not None:
					self._err_handler(e) # job specific error callback registered through .catch()
				elif self._generic_err_handler is not None:
					self._generic_err_handler(e) # generic error callback from scheduler
			finally:
				print( "Finished in {:.2f} minutes".format((time.time()-start_time)/60))
				self.schedule_next_run(just_ran=True)
				print(self)
				print("========== Job End [{}] =========".format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
				self.is_running = False

	@property
	def info(self):
		op = dict(
			job=dict(
				func=self.func.__name__,
				when=self.interval,
				at=self.time_string
			),
			is_running=self.is_running
		)
		if hasattr(self, '_run_info'):
			op.update(self._run_info.to_dict())
		return op

	def __repr__(self):
		return "{} {}. Next run = {}".format(
			self.__class__.__name__, self.func,
			str(dt.fromtimestamp(self.next_timestamp)) if self.next_timestamp!=0 else 'Never'
		)


class OneTimeJob(Job):

	def schedule_next_run(self, just_ran=False):
		H, M = self.time_string.split(':')
		Y, m, d = self.interval.split('-')
		n = dt(int(Y), int(m), int(d), int(H), int(M), 0)

		if just_ran or dt.now() > n + timedelta(minutes=3):
			self.next_timestamp = 0
		else:
			self.next_timestamp = self.to_timestamp(n)

	def is_due(self):
		if self.next_timestamp==0: raise JobExpired('remove me!')
		return super().is_due()


class RepeatJob(Job):

	def schedule_next_run(self, just_ran=False):
		if not isinstance(self.interval, (int, float)):
			raise Exception("Illegal interval for repeating job. Expected number of seconds")

		if just_ran:
			self.next_timestamp += self.interval
		else:
			self.next_timestamp = time.time() + self.interval


class AsyncJobWrapper(object):

	def __init__(self, job):
		self.job = job
		self.proc = None

	def __getattr__(self, name):
		return self.job.__getattribute__(name)

	def is_due(self):
		return self.job.is_due()

	def run(self, *args, **kwargs):
		self.proc = threading.Thread(target=self.job.run, args=args, kwargs=kwargs)
		self.proc.daemon = True
		self.proc.start()


class JobExpired(Exception):
	pass


class TaskScheduler(object):

	def __init__(self,
		check_interval=5,
		holidays_calendar=None,
		on_job_error=None,
		log_filepath=None):

		self.jobs = []
		self.on = self.every
		self._check_interval = check_interval
		self.interval = None
		self.temp_time = None
		if holidays_calendar is not None:
			self.holidays_calendar = holidays_calendar
		else:
			self.holidays_calendar = USHolidays
		self.on_job_error = on_job_error
		self.log_filepath = log_filepath

	def __current_timestring(self):
		return dt.now().strftime("%H:%M")

	def __valid_datestring(self, d):
		date_fmt = r'^([0-9]{4})-?(1[0-2]|0[1-9])-?(3[01]|0[1-9]|[12][0-9])$'
		return re.match(date_fmt, d) is not None

	def every(self, interval):
		self.interval = interval
		return self

	def at(self, time_string):
		if not self.interval: self.interval = 'day'
		self.temp_time = time_string
		return self

	def do(self, func, do_parallel=False, **kwargs):
		if not self.interval: raise Exception('Run .at()/.every().at() before .do()')
		if not self.temp_time: self.temp_time = self.__current_timestring()

		if isinstance(self.interval, (int, float)):
			j = RepeatJob(self.interval, None, func, kwargs)
		elif self.__valid_datestring(self.interval):
			j = OneTimeJob(self.interval, self.temp_time, func, kwargs)
		else:
			j = Job(self.interval, self.temp_time, func, kwargs)

		j.init(
			calendar=self.holidays_calendar,
			generic_err_handler=self.on_job_error,
			log_filepath=self.log_filepath
		)
		if do_parallel:
			j = AsyncJobWrapper(j)
		self.jobs.append(j)
		self.temp_time = None
		self.interval = None
		return j

	def check(self):
		for j in self.jobs:
			try:
				if j.is_due(): j.run()
			except JobExpired:
				self.jobs.remove(j)

	def start(self):
		self._running_auto = True
		try:
			while self._running_auto:
				try:
					self.check()
					time.sleep(self._check_interval)
				except KeyboardInterrupt:
					print("KeyboardInterrupt")
					self.stop()
		finally:
			print("Stopping. Please wait, checking active async jobs ..")
			self.join()
		print(self, "Done!")

	def join(self):
		for j in self.jobs:
			if isinstance(j, AsyncJobWrapper) and j.is_running: # Kill any running parallel tasks
				j.proc.join()
				print(j, "exited")

	def stop(self):
		self._running_auto = False

