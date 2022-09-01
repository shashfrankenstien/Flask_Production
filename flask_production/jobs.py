import time
from datetime import timedelta, datetime as dt
from monthdelta import monthdelta
import re
import threading
import inspect
import traceback

from . import job_logger



class JobExpired(Exception):
	pass


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
		self.func = func
		self.kwargs = kwargs
		self.is_running = False
		self._run_silently = False
		self._generic_err_handler = None
		self._err_handler = None
		self._func_src_code = inspect.getsource(self.func)

	def init(self, calendar, generic_err_handler=None, startup_offset=0):
		'''initialize extra attributes of job'''
		self.calendar = calendar
		self._generic_err_handler = generic_err_handler
		self._startup_offset = startup_offset # look back on tasks if task scheduler just started
		self._run_info = job_logger._JobRunLogger()
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
		return RUNABLE_DAYS[self.interval](date or dt.now(), self.calendar)

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
		last_day_case = interval > sched_day.day and _get_eom(sched_day).day == sched_day.day and _pure_time_passed

		if just_ran or day_passed or time_passed or last_day_case:
			sched_day += monthdelta(1) # switch to next month

		# handle cases where the interval day doesn't occur in all months (ex: 31st)
		if interval > _get_eom(sched_day).day:
			if self._strict_date==False:
				interval = _get_eom(sched_day).day # if strict is false, run on what ever is last day of the month
			else: # strict
				while interval > _get_eom(sched_day).day: # run only on months which have the date
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

