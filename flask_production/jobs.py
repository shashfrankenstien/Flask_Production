import time
from datetime import timedelta, datetime as dt
from monthdelta import monthdelta
from dateutil import tz
import re
import threading
import inspect
import hashlib
import traceback

from . import print_logger



class BadScheduleError(Exception):
	pass



def _get_eom(d):
	return ((d + monthdelta(1)).replace(day=1) - timedelta(days=1))

def _is_eom(d, hols):
	eom = _get_eom(d)
	return d.date() == eom.date()

def _is_eom_weekday(d, hols):
	eom = _get_eom(d)
	while eom.isoweekday() >= 6:
		eom -= timedelta(days=1)
	return d.date() == eom.date()

def _is_eom_businessday(d, hols):
	eom = _get_eom(d)
	while eom in hols or eom.isoweekday() >= 6:
		eom -= timedelta(days=1)
	return d.date() == eom.date()



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
	# end of month
	'eom': _is_eom,
	'eom-weekday': _is_eom_weekday,
	'eom-businessday': _is_eom_businessday,
}




class Job(object):
	'''standard job class'''

	@classmethod
	def is_valid_interval(cls, interval):
		'''The generic Job class only supports these interval. See subclasses for others'''
		return interval in RUNABLE_DAYS

	def __init__(self, jobid, every, at, func, kwargs):
		if str(every) == 'holiday':
			print("!!", "="*20, "!!")
			print("'holiday' interval  is deprecated and will be removed. \r\nUse 'weekend' and 'trading-holiday' instead")
			print("!!", "="*20, "!!")
		self.jobid = jobid
		self.interval = every
		self.time_string = at
		self.tzname = None
		self.func = func
		self.kwargs = kwargs
		self.is_running = False
		self._run_silently = False
		self._generic_err_handler = None
		self._err_handler = None
		self._func_src_code = inspect.getsource(self.func)
		# signatures for setters and getters
		self._func_signature = None
		self._job_signature_hash = None
		self._on_complete_cbs = []

	def init(self, calendar, tzname=None, generic_err_handler=None, startup_grace_mins=0):
		'''initialize extra attributes of job'''
		self.calendar = calendar
		self.tzname = tzname
		self._generic_err_handler = generic_err_handler
		self._startup_grace_mins = startup_grace_mins # look back on tasks if task scheduler just started
		self._run_info = print_logger._PrintLogger(tzname=tzname)
		self.schedule_next_run()
		return self

	def silently(self, run_silently=True):
		self._run_silently = run_silently
		return self

	def catch(self, err_handler):
		'''register job specific error handler'''
		self._err_handler = err_handler
		return self

	def register_callback(self, cb):
		'''
		register a callback function to be called when job completes
		- this callback function should expect a job object as argument
		'''
		if callable(cb) and len(inspect.signature(cb).parameters)==1:
			self._on_complete_cbs.append(cb)
		return self

	# important datetime and timezone management methods
	def to_timestamp(self, d: dt):
		return d.timestamp()

	def to_datetime(self, t: float):
		return dt.fromtimestamp(t, tz=tz.gettz(self.tzname))

	def tz_now(self):
		return dt.now(tz=tz.gettz(self.tzname))

	def tz_dt(self, year, month, day, hour=0, minute=0, second=0, microsecond=0):
		d = dt(int(year), int(month), int(day), int(hour), int(minute), int(second), int(microsecond), tzinfo=tz.gettz(self.tzname))
		return tz.resolve_imaginary(d) # handles time that falls in the transition to/from daylight savings
	#

	def attach_upcoming_run_time(self, d: dt, just_ran: bool=False):
		'''
		attaches time to a datetime object based on the value of self.time_string
		note: self.time_string is usually a string of the form %H:%M, but can also be a list of time strings
		- returns earliest datetime that occurs in the future
		- returns None if no datetimes exist in the future
		'''
		dt_list = []
		def _add_dt(at):
			if not isinstance(at, str):
				raise BadScheduleError(f"Invalid time string '{self.time_string}'")
			h, m = at.split(':')
			dt_list.append(self.tz_dt(d.year, d.month, d.day, int(h), int(m)))

		if isinstance(self.time_string, (list,set,tuple)):
			for at in self.time_string:
				_add_dt(at)
		else:
			_add_dt(self.time_string)
		# to find an upcoming time, we need to filter dt_list based on current date and time
		now = self.tz_now().replace(second=0, microsecond=0)
		if just_ran:
			upcoming_list = [n for n in dt_list if n > now]
		else:
			now -= timedelta(minutes=self._startup_grace_mins)
			upcoming_list = [n for n in dt_list if n >= now]
		if len(upcoming_list) == 0:
			return None
		return min(upcoming_list)

	def schedule_next_run(self, just_ran=False):
		'''compute timestamp of the next run'''
		d = self.tz_now()
		upcoming = self.attach_upcoming_run_time(d, just_ran=just_ran)
		if not self._job_must_run_today() or upcoming is None:
			next_day = d + timedelta(days=1)
			while not self._job_must_run_today(next_day):
				next_day += timedelta(days=1)
			upcoming = self.attach_upcoming_run_time(next_day)

		self.next_timestamp = self.to_timestamp(upcoming)

	def _job_must_run_today(self, date=None):
		return RUNABLE_DAYS[self.interval](date or self.tz_now(), self.calendar)

	def is_due(self):
		'''test if job should run now'''
		return (time.time() >= self.next_timestamp) and not self.is_running

	def did_fail(self):
		'''test if job failed'''
		return self._run_info.error != ''

	def func_signature(self):
		'''create human readable function signature'''
		if self._func_signature is None:
			def readable_trim(s):
				if isinstance(s, (list,tuple)):
					return "[..]"
				elif isinstance(s, set):
					return "(..)"
				elif isinstance(s, dict):
					return "{..}"
				else:
					s_str = str(s)[:6] + ".." if len(str(s))>6 else str(s)
					return s_str.replace("<", "*").replace(">", "*") # escaping html
			arguments = ''
			if self.kwargs:
				arguments = '({})'.format(','.join(['{}={}'.format(k, readable_trim(v)) for k,v in self.kwargs.items()]))
			if self.func.__module__ == "__main__":
				self._func_signature = '{}{}'.format(self.func.__qualname__, arguments)
			else:
				self._func_signature = '{}.{}{}'.format(self.func.__module__, self.func.__qualname__, arguments)
		return self._func_signature

	def signature_hash(self):
		'''create unique job signature hash'''
		if self._job_signature_hash is None:
			sig = "{}-{}-{}.{}({})".format(
				self.interval,
				self.time_string,
				self.func.__module__,
				self.func.__qualname__,
				list(self.kwargs.values())
			)
			self._job_signature_hash = hashlib.sha1(sig.encode()).hexdigest()
		return self._job_signature_hash

	def _run(self, is_rerun: bool):
		'''this is an internal runner. see self.run() for more'''
		self.is_running = True
		try:
			if not self._run_silently: # add print statements
				print("========== [{:03}] - Job {} [{}] =========".format(
					self.jobid,
					"Rerun Start" if is_rerun else "Start",
					self.tz_now().strftime("%Y-%m-%d %H:%M:%S %Z")
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
					self.tz_now().strftime("%Y-%m-%d %H:%M:%S %Z")
				))
			self.is_running = False

	def run(self, is_rerun: bool=False):
		'''
		begin job run
		- redirected all print statements to _PrintLogger
		- call error handlers if provided
		- execute registered callback functions
		'''
		with self._run_info.start_capture(): # captures all writes to stdout
			self._run(is_rerun=is_rerun)
		# call any registered on-complete callbacks
		for cb in self._on_complete_cbs:
			try:
				cb(self)
			except Exception as e:
				print("on-complete-cb-error:", str(e))

	def _next_run_dt(self):
		return self.to_datetime(self.next_timestamp) if self.next_timestamp!=0 else None

	def _logs_to_dict(self):
		return self._run_info.to_dict() if hasattr(self, '_run_info') else {}

	def _logs_from_dict(self, logs_dict):
		if hasattr(self, '_run_info'):
			self._run_info.from_dict(logs_dict)

	def to_dict(self):
		'''property to access job info dict'''
		return dict(
			jobid=self.jobid,
			func=self.func.__qualname__,
			signature=self.func_signature(),
			src=self._func_src_code,
			doc=self.func.__doc__,
			type=self.__class__.__name__,
			every=self.interval,
			at=self.time_string,
			tzname=self.tzname,
			is_running=self.is_running,
			next_run=self._next_run_dt(),
			logs=self._logs_to_dict(),
		)

	def __repr__(self):
		d = self._next_run_dt()
		return "{:10} [{:03}] | Next run = {} | {}".format(
			self.__class__.__name__,
			self.jobid,
			d.strftime("%Y-%m-%d %H:%M:%S %Z") if isinstance(d, dt) else 'Never',
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
		Y, m, d = self.interval.split('-')
		n = self.tz_dt(int(Y), int(m), int(d))
		upcoming = self.attach_upcoming_run_time(n, just_ran=just_ran)

		if upcoming is None:
			self.next_timestamp = 0
		else:
			self.next_timestamp = self.to_timestamp(upcoming)

	def is_due(self):
		if self.next_timestamp==0:
			return False
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
		- ex: 31st will fail for months having less than 31 days, 29th will fail for non leap-Feb
		- use 'self._strict_date' when handing dates >= 29:
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

	def schedule_next_run(self, just_ran=False):
		interval = int(self.PATTERN.match(self.interval).groups()[0])
		sched_day = self.tz_now()
		upcoming = self.attach_upcoming_run_time(sched_day, just_ran=just_ran)
		# switch to next month if
		# - task just ran, or
		# - day has already passed, or
		# - day is today, but time has already passed
		# - day is after today, and today is end of month and time has already passed (ex: 31st while current month has 28 or 30 days)
		_pure_time_passed = upcoming is None
		day_passed = interval < sched_day.day # True if day already passed this month
		time_passed = interval == sched_day.day and _pure_time_passed
		last_day_case = interval > sched_day.day and _get_eom(sched_day).day == sched_day.day and _pure_time_passed

		if day_passed or time_passed or last_day_case:
			sched_day += monthdelta(1) # switch to next month

		# handle cases where the interval day doesn't occur in all months (ex: 31st)
		if interval > _get_eom(sched_day).day:
			if self._strict_date==False:
				interval = _get_eom(sched_day).day # if strict is false, run on what ever is last day of the month
			else: # strict
				while interval > _get_eom(sched_day).day: # run only on months which have the date
					sched_day += monthdelta(1)

		n = self.attach_upcoming_run_time(sched_day.replace(day=interval))
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

	def __repr__(self):
		r = self.job.__repr__()
		r = r.replace(self.job.__class__.__name__, self.job.__class__.__name__+"(*)") # (*) indicates asynchronous job
		return r

	def __getattr__(self, name):
		return self.job.__getattribute__(name)

	def is_due(self):
		return self.job.is_due()

	def run(self, *args, **kwargs):
		self.proc = threading.Thread(target=self.job.run, args=args, kwargs=kwargs)
		self.proc.daemon = True
		self.proc.start()



class NeverJob(Job):
	'''type of job that runs only on demand (using TaskMonitor plugin)'''

	@classmethod
	def is_valid_interval(cls, interval):
		return interval in ('on-demand', 'never')

	def schedule_next_run(self, just_ran=False):
		self.next_timestamp = 0

	def is_due(self):
		return False
