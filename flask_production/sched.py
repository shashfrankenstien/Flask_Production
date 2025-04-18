from typing import Union, Callable, List
import time
from datetime import datetime as dt
from logging.handlers import RotatingFileHandler
import warnings

import holidays
from dateutil import tz

from .print_logger import (
	LOGGER,
	LOG_FORMATTER
)

from .jobs import (
	# job types
	Job,
	OneTimeJob,
	RepeatJob,
	MonthlyJob,
	AsyncJobWrapper,
	NeverJob,

	# exceptions
	BadScheduleError
)

from .script_func import ScriptFunc

from .state import (
	BaseStateHandler,
	FileSystemState,
)



USHolidays = holidays.US()


def get_local_timezone_name():
	return tz.gettz(None).tzname(dt.now())



class TaskScheduler(object):
	"""
	TaskScheduler: main class to setup, run and manage jobs

	Args:
	- check_interval (int): how often to check for pending jobs
	- holidays_calendar (holidays.HolidayBase): calendar to use for intervals like `businessday`
	- tzname (str): name of timezone as supported by dateutil.tz
	- on_job_error (function(e)): function to call if any job fail
	- log_filepath (path): file to write logs to
	- log_maxsize (int): byte limit per log file
	- log_backups (int): number of backups of logs to retain
	- startup_grace_mins (int): grace period for tasks in case a schedule was missed because of app restart
	- persist_states (bool): store job logs and read back on app restart
	- state_handler (.state.BaseStateHandler): different handler backends to store job logs
	"""

	def __init__(self,
		check_interval: int=5,
		holidays_calendar: Union[holidays.HolidayBase, None]=None,
		tzname: Union[str, None]=None,
		on_job_error: Union[Callable, None]=None,
		log_filepath: Union[str, None]=None,
		log_maxsize: int=5*1024*1024,
		log_backups: int=1,
		startup_grace_mins: int=0,
		persist_states: bool=True,
		state_handler: Union[BaseStateHandler, None]=None) -> None:

		self.jobs = []
		self._check_interval = check_interval
		self._startup_grace_mins = startup_grace_mins
		self.on_job_error = on_job_error

		tzname = tzname or get_local_timezone_name() # if None, default to local timezone
		if tz.gettz(tzname) is None:
			raise ValueError(f"unknown timezone '{tzname}'")
		self._tz_default = tzname
		print("* Default Timezone:", self._tz_default, "*")

		if holidays_calendar is not None:
			self.holidays_calendar = holidays_calendar
		else:
			self.holidays_calendar = USHolidays

		# setup logging
		self.log_filepath = log_filepath
		if self.log_filepath is not None:
			fh = RotatingFileHandler(
				filename=self.log_filepath,
				maxBytes=log_maxsize,
				backupCount=log_backups
			)
			fh.setFormatter(LOG_FORMATTER)
			LOGGER.addHandler(fh)

		# setup state persistance over app restarts
		self._state_handler = None
		if persist_states:
			self._state_handler = state_handler or FileSystemState()

		# additional job classes
		self._external_job_classes = []

		# set schedule defaults
		self.__reset_defaults()


	def __reset_defaults(self):
		self.interval = None
		self.temp_time = None
		self.tzname = self._tz_default # timezone default
		self._strict_monthly = None
		self.job_calendar = None


	def register_external_job_class(self, jclass):
		if not issubclass(jclass, Job):
			raise ValueError("class must be inherited from 'Job' class")
		self._external_job_classes.append(jclass)


	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
	# -=-=-=-=-=-=-=-=-= New job definition methods =-=-=-=-=-=-=-=-=-
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

	def every(self, interval, calendar=None):
		'''
		interval is either one of the keys of RUNABLE_DAYS
		or integer denoting number of seconds for RepeatJob
		'''
		self.interval = interval
		self.job_calendar = calendar
		return self

	def on(self, *args, **kwargs):
		'''alias of .every() method'''
		return self.every(*args, **kwargs)

	def strict_date(self, strict:bool):
		'''
		required to be called when scheduling MonthlyJob
		- see MonthlyJob docstring
		'''
		if not MonthlyJob.is_valid_interval(self.interval, time_string="00:00") or not isinstance(strict, bool):
			raise BadScheduleError(".strict_date(bool) only used for monthly schedule. ex: .every('31st').strict_date(True)..")
		self._strict_monthly = strict
		return self

	def at(self, time_string):
		'''
		24 hour time string of when to run job
		- example: '15:00' for 3PM
		'''
		if self.interval is None:
			self.every('day')
		self.temp_time = time_string
		return self

	def timezone(self, tzname):
		'''
		timezone string as defined in pytz module
		- example US/Eastern
		- defaults to system timezone
		'''
		test = tz.gettz(tzname)
		if test is None:
			raise BadScheduleError(f"unknown timezone '{tzname}'")
		self.tzname = tzname
		return self

	def tz(self, *args, **kwargs):
		'''alias of .timezone() method'''
		return self.timezone(*args, **kwargs)


	def _create_job(self, func, **kwargs):
		'''
		register 'func' for the job
		- if do_parallel is True, run job in a prallel thread
		- pass kwargs into 'func' at execution
		'''
		if self.interval is None:
			raise Exception('Use .at()/.every().at() before .do()')
		if self.temp_time is None:
			self.temp_time = dt.now(tz.gettz(self.tzname)).strftime("%H:%M")

		new_jobid = len(self.jobs)
		j = None
		for jcls in self._external_job_classes:
			if jcls.is_valid_interval(self.interval, time_string=self.temp_time):
				j = jcls(new_jobid, every=self.interval, at=self.temp_time, func=func, kwargs=kwargs)
				break

		if j is None:
			if RepeatJob.is_valid_interval(self.interval, time_string=None):
				j = RepeatJob(new_jobid, every=self.interval, at=None, func=func, kwargs=kwargs)

			elif OneTimeJob.is_valid_interval(self.interval, time_string=self.temp_time):
				j = OneTimeJob(new_jobid, every=self.interval, at=self.temp_time, func=func, kwargs=kwargs)

			elif MonthlyJob.is_valid_interval(self.interval, time_string=self.temp_time):
				j = MonthlyJob(new_jobid, every=self.interval, at=self.temp_time, func=func, kwargs=kwargs, strict_date=self._strict_monthly)

			elif Job.is_valid_interval(self.interval, time_string=self.temp_time):
				j = Job(new_jobid, every=self.interval, at=self.temp_time, func=func, kwargs=kwargs)

			elif NeverJob.is_valid_interval(self.interval, time_string=None):
				j = NeverJob(new_jobid, every=self.interval, at=None, func=func, kwargs=kwargs)

		if j is None:
			raise BadScheduleError("{} is not valid\n".format(self.interval))

		j.init(
			calendar=self.holidays_calendar if self.job_calendar is None else self.job_calendar,
			tzname=self.tzname,
			generic_err_handler=self.on_job_error,
			startup_grace_mins=self._startup_grace_mins
		)
		# register callbacks to save job logs to file so it can be restored on app restart
		if isinstance(self._state_handler, BaseStateHandler):
			j.register_callback(self._state_handler.save_job_logs, cb_type="onenable")
			j.register_callback(self._state_handler.save_job_logs, cb_type="ondisable")
			j.register_callback(self._state_handler.save_job_logs, cb_type="oncomplete")

		self.__reset_defaults()
		print(j)
		return j


	def do(self, func, do_parallel=False, **kwargs):
		j = self._create_job(func, **kwargs)
		if do_parallel:
			print("================================================")
			print("==== do_parallel boolean argument will be removed")
			print("==== use do_parallel() method  instead")
			print("================================================")
			warnings.warn("do_parallel boolean argument will be removed", category=DeprecationWarning)
			j = AsyncJobWrapper(j)
		self.jobs.append(j)
		return j

	def do_parallel(self, func, **kwargs):
		'''helper function to run job in a separate thread'''
		j = self._create_job(func, **kwargs)
		j = AsyncJobWrapper(j)
		self.jobs.append(j)
		return j

	def run_script(self, script_dir_path:str, script_name:str, script_args:List[str]=[]):
		func = ScriptFunc(script_dir_path, script_name, script_args)
		j = self._create_job(func)
		self.jobs.append(j)
		return j

	def run_script_parallel(self, script_dir_path:str, script_name:str, script_args:List[str]=[]):
		func = ScriptFunc(script_dir_path, script_name, script_args)
		j = self._create_job(func)
		j = AsyncJobWrapper(j)
		self.jobs.append(j)
		return j

	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
	# -=-=-=-=-=-=-=-= Scheduler control methods =-=-=-=-=-=-=-=-=-=-=
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

	def check(self):
		'''check if a job is due'''
		for j in self.jobs.copy(): # work on a shallow copy of this list - safer in case the list changes. TODO: maybe use locks instead?
			if j.is_due() and not j.is_running:
				j.run()


	def restore_all_job_logs(self):
		try:
			if isinstance(self._state_handler, BaseStateHandler):
				self._state_handler.restore_all_job_logs(self.jobs)
		except Exception as e:
			# import traceback
			# traceback.print_exc()
			print("unable to restore states:", str(e))


	def start(self):
		'''blocking function that checks for jobs every 'check_interval' seconds'''
		self.restore_all_job_logs()
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
			if isinstance(j, AsyncJobWrapper) and j.is_running: # wait for any running parallel tasks
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

	def rerun(self, jobid, kwargs: dict=None):
		selected_job = self.get_job_by_id(jobid)
		if selected_job is None:
			raise IndexError("Invalid job id")
		if selected_job.is_running:
			raise RuntimeError("Cannot rerun a running task")
		if not isinstance(selected_job, AsyncJobWrapper):
			selected_job = AsyncJobWrapper(selected_job)
		selected_job.run(is_rerun=True, kwargs=kwargs)

	def disable_all(self):
		for j in self.jobs:
			j.disable()

	def enable_all(self):
		for j in self.jobs:
			j.enable()
