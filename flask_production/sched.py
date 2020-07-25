import sys
import time
from datetime import timedelta, datetime as dt
from monthdelta import monthdelta
import holidays
import re
import threading
import inspect

from contextlib import contextmanager
import traceback
import logging
# default logging configuration
# logging.captureWarnings(True)
LOG_FORMATTER = logging.Formatter('%(message)s')
LOGGER_NAME = 'flask_production'
LOGGER = logging.getLogger(LOGGER_NAME)
LOGGER.setLevel(logging.INFO)


from ._capture import print_capture

USHolidays = holidays.US()


class _JobRunLogger(object):
	'''
	logging class to capture any print statements within a job
	also captures start time, end time and error traceback
	'''

	def __init__(self):
		self._lock = threading.Lock()
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
			self._started_at = dt.now()
		with print_capture(callback=self._log_callback):
			yield
		with self._lock:
			self._ended_at = dt.now()

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



class Job(object):
	'''standard job class'''

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
		self._func_src_code = inspect.getsource(self.func)

	def init(self, calendar, generic_err_handler=None):
		'''initialize extra attributes of job'''
		self.calendar = calendar
		self._generic_err_handler = generic_err_handler
		self._run_info = _JobRunLogger()
		self.schedule_next_run()
		print(self)
		return self

	def catch(self, err_handler):
		'''register job specific error handler'''
		self._err_handler = err_handler
		return self

	@staticmethod
	def to_timestamp(d):
		return time.mktime(d.timetuple())+d.microsecond/1000000.0

	def schedule_next_run(self, just_ran=False):
		'''compute timestamp of the next run'''
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
		'''test if job should run now'''
		return (time.time() >= self.next_timestamp) and not self.is_running

	def did_fail(self):
		'''test if job failed'''
		return self._run_info.error != ''

	def run(self):
		'''
		begin job run
		redirected all print statements to _JobRunLogger
		call error handlers if provided
		'''
		with self._run_info.start_capture(): # captures all writes to stdout
			self.is_running = True
			try:
				print("========== Job Start [{}] =========".format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
				print("Executing {}".format(self))
				start_time = time.time()
				print("*") # job log seperator
				return self.func(**self.kwargs)
			except Exception as e:
				print(e)
				self._run_info.set_error()
				if self._err_handler is not None:
					self._err_handler(e) # job specific error callback registered through .catch()
				elif self._generic_err_handler is not None:
					self._generic_err_handler(e) # generic error callback from scheduler
			finally:
				print("*") # job log seperator
				print( "Finished in {:.2f} minutes".format((time.time()-start_time)/60))
				self.schedule_next_run(just_ran=True)
				print(self)
				print("========== Job End [{}] =========".format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
				self.is_running = False

	def _next_run_dt(self):
		return dt.fromtimestamp(self.next_timestamp) if self.next_timestamp!=0 else None

	def to_dict(self):
		'''property to access job info dict'''
		return dict(
			func=self.func.__name__,
			src=self._func_src_code,
			doc=self.func.__doc__,
			type=self.__class__.__name__,
			every=self.interval,
			at=self.time_string,
			is_running=self.is_running,
			next_run=self._next_run_dt(),
			logs=self._run_info.to_dict() if hasattr(self, '_run_info') else {}
		)

	def __repr__(self):
		d = self._next_run_dt()
		return "{} {}. Next run = {}".format(
			self.__class__.__name__, self.func.__name__,
			d.strftime("%Y-%m-%d %H:%M:%S") if isinstance(d, dt) else 'Never'
		)


class OneTimeJob(Job):
	'''type of job that runs only once'''

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
	'''type of job that runs every n seconds'''

	def schedule_next_run(self, just_ran=False):
		if not isinstance(self.interval, (int, float)):
			raise Exception("Illegal interval for repeating job. Expected number of seconds")

		if just_ran:
			self.next_timestamp += self.interval
		else:
			self.next_timestamp = time.time() + self.interval


class AsyncJobWrapper(object):
	'''wrapper to run the job on a parallel thread'''

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
	'''task scheduler class to manage and run jobs'''

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
		if self.log_filepath is not None:
			fh = logging.FileHandler(self.log_filepath)
			fh.setFormatter(LOG_FORMATTER)
			LOGGER.addHandler(fh)

	def __current_timestring(self):
		return dt.now().strftime("%H:%M")

	def __valid_datestring(self, d):
		date_fmt = r'^([0-9]{4})-?(1[0-2]|0[1-9])-?(3[01]|0[1-9]|[12][0-9])$'
		return re.match(date_fmt, d) is not None

	def every(self, interval):
		'''
		interval is either one of the keys of Job.RUNABLE_DAYS
		or integer denoting number of seconds for RepeatJob
		'''
		self.interval = interval
		return self

	def at(self, time_string):
		'''
		24 hour time string of when to run job
		example: '15:00' for 3PM
		'''
		if not self.interval: self.interval = 'day'
		self.temp_time = time_string
		return self

	def do(self, func, do_parallel=False, **kwargs):
		'''
		register 'func' for the job
		run in a prallel thread if do_parallel is True
		pass kwargs into 'func' at execution
		'''
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
			generic_err_handler=self.on_job_error
		)
		if do_parallel:
			j = AsyncJobWrapper(j)
		self.jobs.append(j)
		self.temp_time = None
		self.interval = None
		return j

	def check(self):
		'''check if a job is due'''
		for j in self.jobs:
			try:
				if j.is_due(): j.run()
			except JobExpired:
				self.jobs.remove(j)

	def start(self):
		'''blocking function that checks for jobs every 'check_interval' seconds'''
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
		'''wait for any async jobs to complete'''
		for j in self.jobs:
			if isinstance(j, AsyncJobWrapper) and j.is_running: # Kill any running parallel tasks
				j.proc.join()
				print(j, "exited")

	def stop(self):
		'''stop job started with .start() method'''
		self._running_auto = False

