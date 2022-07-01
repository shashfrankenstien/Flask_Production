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
# stop propagting to root logger
LOGGER.propagate = False


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
		'trading-holiday': lambda d, hols : d in hols and d.isoweekday() < 6, # trading-holidays don't count if they fall on weekends
		# days of the week
		'monday': lambda d, hols: d.isoweekday() == 1,
		'tuesday': lambda d, hols: d.isoweekday() == 2,
		'wednesday': lambda d, hols: d.isoweekday() == 3,
		'thursday': lambda d, hols: d.isoweekday() == 4,
		'friday': lambda d, hols: d.isoweekday() == 5,
		'saturday': lambda d, hols: d.isoweekday() == 6,
		'sunday': lambda d, hols: d.isoweekday() == 7,
	}

	@classmethod
	def is_valid_interval(cls, interval):
		'''The generic Job class only supports these interval. See subclasses for others'''
		return interval in cls.RUNABLE_DAYS

	def __init__(self, jobid, every, at, func, kwargs):
		if str(every) == 'holiday':
			print("!!", "="*20, "!!")
			print("'holiday' interval  is deprecated and will be removed. \r\nUse 'weekend' and 'trading-holiday' instead")
			print("!!", "="*20, "!!")
		self.jobid = jobid
		self.interval = every
		self.time_string = at
		self.func = func
		self.kwargs = kwargs
		self.is_running = False
		self._run_silently = False
		self._generic_err_handler = None
		self._err_handler = None
		self._func_src_code = inspect.getsource(self.func)

	def init(self, calendar, generic_err_handler=None, startup_offset=180):
		'''initialize extra attributes of job'''
		self.calendar = calendar
		self._generic_err_handler = generic_err_handler
		self._startup_offset = startup_offset # look back on tasks if task scheduler just started
		self._run_info = _JobRunLogger()
		self.schedule_next_run()
		print(self)
		return self

	def silently(self):
		self._run_silently = True
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
		if self._job_must_run_today() and not just_ran and time.time() < ts+self._startup_offset:
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

	def func_signature(self):
		def readable_trim(s):
			if isinstance(s, list):
				return "[..]"
			elif isinstance(s, set):
				return "(..)"
			elif isinstance(s, list):
				return "{..}"
			else:
				return str(s)[:6] + ".." if len(str(s))>6 else str(s)
		arguments = ''
		if self.kwargs:
			arguments = '({})'.format(','.join(['{}={}'.format(k, readable_trim(v)) for k,v in self.kwargs.items()]))
		return '{}{}'.format(self.func.__name__, arguments)

	def run(self, is_rerun=False):
		'''
		begin job run
		redirected all print statements to _JobRunLogger
		call error handlers if provided
		'''
		with self._run_info.start_capture(): # captures all writes to stdout
			self.is_running = True
			try:
				if not self._run_silently: # add print statements
					print("========== [{:03}] - Job {} [{}] =========".format(
						self.jobid,
						"Rerun Start" if is_rerun else "Start",
						dt.now().strftime("%Y-%m-%d %H:%M:%S")
					))
					print("Executing {}".format(self))
					print("*") # job log seperator
				start_time = time.time()
				return self.func(**self.kwargs)
			except Exception:
				print("Job", self.func_signature(), "failed!")
				err_msg = "Error in {}\n\n\n{}".format(self.func_signature(), traceback.format_exc())
				self._run_info.set_error()
				try:
					if self._err_handler is not None:
						self._err_handler(err_msg) # job specific error callback registered through .catch()
					elif self._generic_err_handler is not None:
						self._generic_err_handler(err_msg) # generic error callback from scheduler
				except:
					traceback.print_exc()
			finally:
				# if the job was forced to rerun, we should not schedule the next run
				if not is_rerun:
					self.schedule_next_run(just_ran=True)
				if not self._run_silently: # add print statements
					print("*") # job log seperator
					print( "Finished in {:.2f} minutes".format((time.time()-start_time)/60))
					print(self)
					print("========== [{:03}] - Job {} [{}] =========".format(
						self.jobid,
						"Rerun End" if is_rerun else "End",
						dt.now().strftime("%Y-%m-%d %H:%M:%S")
					))
				self.is_running = False

	def _next_run_dt(self):
		return dt.fromtimestamp(self.next_timestamp) if self.next_timestamp!=0 else None

	def to_dict(self):
		'''property to access job info dict'''
		return dict(
			jobid=self.jobid,
			func=self.func.__name__,
			signature=self.func_signature(),
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
		return "{:10} [{:03}] | Next run = {} | {}".format(
			self.__class__.__name__,
			self.jobid,
			d.strftime("%Y-%m-%d %H:%M:%S") if isinstance(d, dt) else 'Never',
			self.func_signature()
		)


class OneTimeJob(Job):
	'''type of job that runs only once'''

	@classmethod
	def is_valid_interval(cls, interval):
		try:
			dt.strptime(interval, "%Y-%m-%d")
			return True
		except:
			return False

	def schedule_next_run(self, just_ran=False):
		H, M = self.time_string.split(':')
		Y, m, d = self.interval.split('-')
		n = dt(int(Y), int(m), int(d), int(H), int(M), 0)

		startup_offset_mins = int(self._startup_offset / 60.0) # look back on tasks if task scheduler just started
		if just_ran or dt.now() > n + timedelta(minutes=startup_offset_mins):
			self.next_timestamp = 0
		else:
			self.next_timestamp = self.to_timestamp(n)

	def is_due(self):
		if self.next_timestamp==0: raise JobExpired('remove me!')
		return super().is_due()


class RepeatJob(Job):
	'''type of job that runs every n seconds'''

	@classmethod
	def is_valid_interval(cls, interval):
		return isinstance(interval, (int, float))

	def schedule_next_run(self, just_ran=False):
		if not isinstance(self.interval, (int, float)) or self.interval <= 0:
			raise BadScheduleError("Illegal interval for repeating job. Expected number of seconds")

		if just_ran:
			self.next_timestamp += self.interval
		else:
			self.next_timestamp = time.time() + self.interval


class MonthlyJob(Job):
	'''
	type of job that can be scheduled to run once per month
	example interval 1st, 22nd, 30th
	limitation: we cannot intuitively handle dates >= 29 for all months
		- ex: 29th will fail for non leap-Feb, 31st will fail for months having less than 31 days
		- use '_strict_date' when handing dates >= 29:
			if self._strict_date == True:
				job is scheduled only on months which have the date (ex: 31st)
			elif self._strict_date == False:
				run on the last day of the month if date exceeds current month
	'''

	PATTERN = re.compile(r"^(\d{1,2})(st|nd|rd|th)$", re.IGNORECASE)

	def __init__(self, jobid, every, at, func, kwargs, strict_date):
		if not isinstance(strict_date, bool):
			raise BadScheduleError("call to .strict_date() required for monthly schedule. ex: .every('31st').strict_date(True)..")
		self._strict_date = strict_date
		super().__init__(jobid, every, at, func, kwargs)

	@classmethod
	def is_valid_interval(cls, interval):
		# example intervals - 1st, 22nd, 30th
		match = cls.PATTERN.match(str(interval))
		return match is not None and int(match.groups()[0]) <= 31

	def __last_day_of_month(self, d):
		return ((d + monthdelta(1)).replace(day=1) - timedelta(days=1)).day

	def schedule_next_run(self, just_ran=False):
		interval = int(self.PATTERN.match(self.interval).groups()[0])
		H, M = self.time_string.split(':')
		sched_day = dt.now()
		# switch to next month if
		# - task just ran, or
		# - day has already passed, or
		# - day is today, but time has already passed
		# - day is after today, and today is end of month and time has already passed (ex: 31st while current month has 28 or 30 days)
		day_passed = interval < sched_day.day # True if day already passed this month
		startup_offset_mins = int(self._startup_offset / 60.0) # look back on tasks if task scheduler just started
		_pure_time_passed = (int(H) < sched_day.hour or (int(H) == sched_day.hour and (int(M) + startup_offset_mins ) < sched_day.minute))
		time_passed = interval == sched_day.day and _pure_time_passed
		last_day_case = interval > sched_day.day and self.__last_day_of_month(sched_day) == sched_day.day and _pure_time_passed

		if just_ran or day_passed or time_passed or last_day_case:
			sched_day += monthdelta(1) # switch to next month

		# handle cases where the interval day doesn't occur in all months (ex: 31st)
		if interval > self.__last_day_of_month(sched_day):
			if self._strict_date==False:
				interval = self.__last_day_of_month(sched_day) # if strict is false, run on what ever is last day of the month
			else: # strict
				while interval > self.__last_day_of_month(sched_day): # run only on months which have the date
					sched_day += monthdelta(1)

		n = sched_day.replace(day=interval, hour=int(H), minute=int(M), second=0, microsecond=0)
		self.next_timestamp = self.to_timestamp(n)

	def __repr__(self):
		r = super().__repr__()
		if self._strict_date:
			r = r.replace(self.__class__.__name__, self.__class__.__name__+"[strict]")
		return r


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


class BadScheduleError(Exception):
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
		self.__reset_defaults()

	def __reset_defaults(self):
		self.interval = None
		self.temp_time = None
		self._strict_monthly = None
		self.job_calendar = None

	def __current_timestring(self):
		return dt.now().strftime("%H:%M")

	def every(self, interval, calendar=None):
		'''
		interval is either one of the keys of Job.RUNABLE_DAYS
		or integer denoting number of seconds for RepeatJob
		'''
		self.interval = interval
		self.job_calendar = calendar
		return self

	def strict_date(self, strict):
		'''
		required to be called when scheduling MonthlyJob
		- see MonthlyJob docstring
		'''
		if not MonthlyJob.is_valid_interval(self.interval) or not isinstance(strict, bool):
			raise BadScheduleError(".strict_date(bool) only used for monthly schedule. ex: .every('31st').strict_date(True)..")
		self._strict_monthly = strict
		return self

	def at(self, time_string):
		'''
		24 hour time string of when to run job
		example: '15:00' for 3PM
		'''
		if self.interval is None: self.interval = 'day'
		self.temp_time = time_string
		return self

	def do(self, func, do_parallel=False, **kwargs):
		'''
		register 'func' for the job
		run in a prallel thread if do_parallel is True
		pass kwargs into 'func' at execution
		'''
		if self.interval is None: raise Exception('Run .at()/.every().at() before .do()')
		if self.temp_time is None: self.temp_time = self.__current_timestring()

		new_jobid = len(self.jobs)
		if RepeatJob.is_valid_interval(self.interval):
			j = RepeatJob(new_jobid, self.interval, None, func, kwargs)
		elif OneTimeJob.is_valid_interval(self.interval):
			j = OneTimeJob(new_jobid, self.interval, self.temp_time, func, kwargs)
		elif MonthlyJob.is_valid_interval(self.interval):
			j = MonthlyJob(new_jobid, self.interval, self.temp_time, func, kwargs, strict_date=self._strict_monthly)
		elif Job.is_valid_interval(self.interval):
			j = Job(new_jobid, self.interval, self.temp_time, func, kwargs)
		else:
			raise BadScheduleError("{} is not valid\n".format(self.interval))

		j.init(
			calendar=self.holidays_calendar if self.job_calendar is None else self.job_calendar,
			generic_err_handler=self.on_job_error
		)
		if do_parallel:
			j = AsyncJobWrapper(j)
		self.jobs.append(j)
		self.__reset_defaults()
		return j

	def do_parallel(self, func, **kwargs):
		'''helper function to run task in a separate thread'''
		return self.do(func, do_parallel=True, **kwargs)

	def check(self):
		'''check if a job is due'''
		for j in self.jobs.copy(): # work on copy of this list - safer in case the list changes
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

	def get_job_by_id(self, jobid):
		for j in self.jobs:
			if j.jobid==jobid:
				return j
		return None

	def rerun(self, jobid):
		selected_job = self.get_job_by_id(jobid)
		if selected_job is None:
			raise IndexError("Invalid job id")
		if selected_job.is_running:
			raise RuntimeError("Cannot rerun a running task")
		if not isinstance(selected_job, AsyncJobWrapper):
			selected_job = AsyncJobWrapper(selected_job)
		selected_job.run(is_rerun=True)
