import os, glob, shutil
import time
import threading
import json
from datetime import datetime as dt, timedelta
from monthdelta import monthdelta
from dateutil.parser import parse as date_parse
from dateutil import tz
import pytest

from flask_production import TaskScheduler
from flask_production.hols import TradingHolidays
from flask_production.sched import LOGGER, BadScheduleError
from flask_production.state import FileSystemState, SQLAlchemyState

CUR_APP_DATA_DIR_PATH = FileSystemState()._get_current_app_data_directory()


LOGGING_TEST_FILE = 'testlog.log'
DB_STATE_TEST_FILE = 'teststate.db'


def job(x, y):
	time.sleep(0.1)
	print(x, y)

def pretty_print(d):
	print(json.dumps(d, indent=4, default=str))


def teardown_function(function):
	for h in LOGGER.handlers:
		h.close()
		LOGGER.removeHandler(h)

	for f in glob.glob(LOGGING_TEST_FILE+'*'):
		if os.path.isfile(f):
			os.remove(f)

	if os.path.isfile(DB_STATE_TEST_FILE):
		os.remove(DB_STATE_TEST_FILE)


def teardown_module(module):
	time.sleep(1)
	if os.path.isdir(CUR_APP_DATA_DIR_PATH):
		shutil.rmtree(CUR_APP_DATA_DIR_PATH)



def test_registry():
	s = TaskScheduler()
	s.every("businessday").at("10:00").do(job, x="hello", y="world") # Job
	s.on('2019-05-16').do(job, x="hello", y="world") # OneTimeJob
	s.every(5).at("10:00").do(job, x="hello", y="world") # RepeatJob
	s.every('2nd').strict_date(False).at("10:00").do(job, x="hello", y="world") # MonthlyJob
	assert(len(s.jobs) == 4)


def test_badinterval():
	s = TaskScheduler()
	with pytest.raises(BadScheduleError):
		s.every("day").at(5).do(job, x="hello", y="world")
	with pytest.raises(BadScheduleError):
		s.every("day").at([-1,2]).do(job, x="hello", y="world")
	with pytest.raises(BadScheduleError):
		s.every("potato").at("10:00").do(job, x="hello", y="world")
	with pytest.raises(BadScheduleError):
		s.every("2020-02-30").at("10:00").do(job, x="hello", y="world") # OneTimeJob
	with pytest.raises(BadScheduleError):
		s.every(0).at("10:00").do(job, x="hello", y="world") # RepeatJob
	with pytest.raises(BadScheduleError):
		# error because .strict_date() is not called
		s.every("31st").at("10:00").do(job, x="hello", y="world") # MonthlyJob
	with pytest.raises(BadScheduleError):
		s.every("32nd").strict_date(False).at("10:00").do(job, x="hello", y="world") # MonthlyJob


def test_regular():
	d = dt.now().replace(hour=23, minute=59, second=0, microsecond=0)
	s = TaskScheduler()
	s.every("day").at("23:59").do(job, x="hello", y="world")
	assert (s.jobs[0].next_timestamp==dt.timestamp(d))


def test_day_of_week():
	now = dt.now()
	today_str = now.strftime("%A").lower() # day of the week
	in2sec_str = now.strftime("%H:%M")
	s = TaskScheduler()
	s.every(today_str).at(in2sec_str).do(job, x="hello", y=today_str)
	assert(len(s.jobs) == 1)
	time.sleep(0.5)
	s.check()
	# test if next run greater than 6 days, less than 8 days from now
	test_timestamp = time.time()
	assert s.jobs[0].next_timestamp > test_timestamp+(6*24*60*60)
	assert s.jobs[0].next_timestamp < test_timestamp+(8*24*60*60)


def test_holidays():
	s = TaskScheduler() # default holidays calendar
	s.every("businessday").at("10:00").do(job, x="hello", y="world")
	assert(s.jobs[0]._job_must_run_today(date_parse("2020-04-09"))==True)
	assert(s.jobs[0]._job_must_run_today(date_parse("2020-10-12"))==False) # Columbus Day is a US holiday by default

	s = TaskScheduler(holidays_calendar=TradingHolidays())
	s.every("businessday").at("10:00").do(job, x="hello", y="world")
	assert(s.jobs[0]._job_must_run_today(date_parse("2020-04-09"))==True)
	assert(s.jobs[0]._job_must_run_today(date_parse("2020-04-11"))==False) # saturday
	assert(s.jobs[0]._job_must_run_today(date_parse("2020-10-12"))==True) # test Custom calendar with Columbus Day removed

	s.every("trading-holiday").at("10:00").do(job, x="hello", y="world")
	assert(s.jobs[1]._job_must_run_today(date_parse("2020-01-01"))==True)
	assert(s.jobs[1]._job_must_run_today(date_parse("2020-01-02"))==False)


def test_multi_intraday(): # test list of timestamps for .at()
	sched = TaskScheduler()
	n1 = dt.now().replace(second=0, microsecond=0)
	n2 = (n1+timedelta(minutes=1))
	sched.every("day").at([n1.strftime("%H:%M"), n2.strftime("%H:%M")]).do(job, x="multi", y="intraday")
	assert(sched.jobs[0].next_timestamp==dt.timestamp(n1))
	sched.check()
	assert(sched.jobs[0].next_timestamp==dt.timestamp(n2))


def test_onetime():
	yesterday = dt.now() - timedelta(days=1)
	tomorrow = (dt.now() + timedelta(days=1)).replace(hour=23, minute=59, second=0, microsecond=0)
	sched = TaskScheduler()
	dead_job = sched.on(yesterday.strftime("%Y-%m-%d")).at("23:59").do(job, x="one", y="time")
	assert(dead_job.next_timestamp == 0)
	alive_job = sched.on(tomorrow.strftime("%Y-%m-%d")).at("23:59").do(job, x="one", y="time")
	assert (alive_job.next_timestamp==dt.timestamp(tomorrow))
	assert(len(sched.jobs) == 2)


def test_never():
	sched = TaskScheduler()
	sched.every('on-demand').do(job, x="never", y="never")
	sched.on('never').do(job, x="never", y="never")
	for j in sched.jobs:
		assert (j.next_timestamp==0)
	assert(len(sched.jobs) == 2)
	sched.check()
	assert(len(sched.jobs) == 2)
	sched.jobs[0].run() # run the job directly
	sched.rerun(sched.jobs[1].jobid) # rerun -> runs as a thread
	time.sleep(0.1)
	assert(len(sched.jobs) == 2)
	for j in sched.jobs: # assert again that they were not rescheduled after running
		assert (j.next_timestamp==0)


def test_eom():
	s = TaskScheduler()
	s.every("eom").do(job, x="hello", y="eom")
	eom = dt.fromtimestamp(s.jobs[0].next_timestamp)
	assert((eom + timedelta(days=1)).day == 1)

	s.every("eom-weekday").do(job, x="hello", y="eom")
	eom = dt.fromtimestamp(s.jobs[1].next_timestamp)
	assert(eom.isoweekday() < 6) # make sure it's a weekday
	eom += timedelta(days=1) # count up to the first if next month
	while eom.day != 1:
		assert(eom.isoweekday() >= 6) # if there are any days between eom-weekday and 1st of next month, those have to be weekends (convoluted test. hmm..)
		eom += timedelta(days=1)

	hols = TradingHolidays()
	s.every("eom-businessday", calendar=hols).do(job, x="hello", y="eom")
	eom = dt.fromtimestamp(s.jobs[2].next_timestamp)
	assert(eom.isoweekday() < 6 and eom not in hols)  # make sure it's a businessday
	eom += timedelta(days=1)
	while eom.day != 1:  # if there are any days between eom-businessday and 1st of next month, those have to be weekends or holidays (convoluted test. hmm..)
		assert(eom.isoweekday() >= 6 or eom in hols)
		eom += timedelta(days=1)


def test_monthly():
	def day_suffixed_str(day):
		suffix = 'th' if 11<=day<=13 else {1:'st',2:'nd',3:'rd'}.get(day%10, 'th')
		return str(day) + suffix

	today = dt.now().replace(hour=23, minute=59, second=0, microsecond=0)
	yesterday = (dt.now() - timedelta(days=1)).replace(hour=23, minute=59, second=0, microsecond=0)
	s = TaskScheduler()

	j = s.every(day_suffixed_str(today.day)).strict_date(True).at("23:59").do(job, x="hello", y="world")
	assert(j.next_timestamp==dt.timestamp(today))

	# yesterday's date is scheduled to next month
	j = s.every(day_suffixed_str(yesterday.day)).strict_date(False).at("23:59").do(job, x="hello", y="world")
	assert(j.next_timestamp==dt.timestamp(yesterday+monthdelta(1)))

	# strict_date is False. So 31st will just be the last day of the month
	j = s.every("31st").strict_date(False).at("23:59").do(job, x="hello", y="world")
	eom = (dt.now() + monthdelta(1)).replace(day=1, hour=23, minute=59, second=0, microsecond=0) - timedelta(days=1)
	assert(j.next_timestamp==dt.timestamp(eom))

	# strict_date is True. So next schedule will be when month has 31st
	j = s.every("31st").strict_date(True).at("23:59").do(job, x="hello", y="world")
	day = dt.now()
	while ((day + monthdelta(1)).replace(day=1) - timedelta(days=1)).day != 31:
		day += monthdelta(1)
	assert(j.next_timestamp==dt.timestamp(day.replace(day=31, hour=23, minute=59, second=0, microsecond=0)))

	with pytest.raises(BadScheduleError):
		# error because .strict_date() is not called
		s.every("1st").at("23:59").do(job, x="hello", y="world")

	assert (len(s.jobs) == 4)


def test_repeat():
	d = time.time()
	sleep_time = 1
	s = TaskScheduler()
	s.every(sleep_time).do(job, x="hello", y="world")
	assert (abs(s.jobs[0].next_timestamp - (d+sleep_time)) < 0.1)
	time.sleep(sleep_time+0.5)
	s.check()
	assert (abs(s.jobs[0].next_timestamp - (d+(2*sleep_time))) < 0.1)


def test_repeat_parallel():
	sleep_time = 1
	s = TaskScheduler()
	s.every(sleep_time).do(job, x="hello", y="world", do_parallel=True) # old style (pre v2.4.1)
	s.every(sleep_time).do_parallel(job, x="hello", y="world") # new style (v2.4.1)
	ts = s.jobs[0].next_timestamp
	d = time.time()
	assert (abs(ts - (d+sleep_time)) < 0.1)
	time.sleep(sleep_time+0.5)
	s.check()
	assert (s.jobs[0].next_timestamp == ts) # still not rescheduled
	time.sleep(0.5)
	assert (s.jobs[0].next_timestamp != ts) # rescheduled parallely
	assert (abs(s.jobs[0].next_timestamp - (d+(2*sleep_time))) < 0.1)
	assert (abs(s.jobs[0].next_timestamp - s.jobs[1].next_timestamp) < 0.1)


def test_parallel_stopper():
	def job(x, y):
		time.sleep(2)
		print(x, y)

	s = TaskScheduler(check_interval=1)
	s.every(1).do_parallel(job, x="hello", y="world")

	def stopp():
		# job will start in 1 second, and finish in 3 seconds. Attempting to stop at the 2 second mark
		time.sleep(2)
		print("stopping thread")
		s.stop()
	t = threading.Thread(target=stopp)
	t.start()
	s.start()
	assert(any([j.is_running for j in s.jobs])==False) # successfully stopped all parallel tasks


def test_error_callback():
	sleep_time = 1
	errors = []
	err_count = 0

	def failing_job(msg):
		raise Exception(msg)

	def err(e):
		nonlocal errors, err_count
		cause = str(e).strip().split()[-1] # get last word from traceback
		errors.append(cause)
		err_count += 1

	def err_specific(e):
		nonlocal errors, err_count
		cause = str(e).strip().split()[-1] # get last word from traceback
		errors.append(cause+"_specific")
		err_count += 1

	s = TaskScheduler(on_job_error=err)
	s.every(sleep_time).do_parallel(failing_job, msg='one')
	s.every(sleep_time).do(failing_job, msg='two')
	s.every(sleep_time).do_parallel(failing_job, msg='three').catch(err_specific)
	time.sleep(sleep_time+0.5)
	s.check()
	time.sleep(0.5)
	assert(sorted(errors)==sorted(['one', 'two', 'three_specific'])) # err callbacks were called
	assert(err_count==3)
	assert(s.jobs[0].did_fail()==True)
	pretty_print(s.jobs[0].to_dict())


def test_print_capture():
	def slow_job(sleep_time):
		time.sleep(sleep_time)
		print("Slow job completed")

	sleep_time = 1
	s = TaskScheduler(log_filepath=LOGGING_TEST_FILE)
	s.every(1).do_parallel(slow_job, sleep_time=sleep_time)
	s.check()

	counter = 4
	while counter>0:
		print("outside")
		counter -= 1
		print('running:', s.jobs[0].is_running)
		s.check()
		time.sleep(0.5)
	print("stopping")
	s.join()
	j0 = s.jobs[0].to_dict()
	assert('Slow job completed' in j0['logs']['log'])
	assert('===' in j0['logs']['log'])
	assert('outside' not in j0['logs']['log'])
	assert('stopping' not in j0['logs']['log'])
	pretty_print(j0)
	# test log file
	assert(os.path.isfile(LOGGING_TEST_FILE)==True)
	with open(LOGGING_TEST_FILE, 'r') as lf:
		assert('Slow job completed' in lf.read())



def test_log_rotation():
	def slow_job(sleep_time):
		time.sleep(sleep_time)
		print("Slow job completed")

	sleep_time = 1
	log_size_limit = 200 # NOTE: this has to be longer than 1 line at least
	s = TaskScheduler(log_filepath=LOGGING_TEST_FILE, log_maxsize=log_size_limit)
	s.every(1).do_parallel(slow_job, sleep_time=sleep_time)
	s.check()

	counter = 4
	while counter>0:
		s.check()
		counter -= 1
		time.sleep(0.5)
	print("stopping")
	s.join()

	# test log file
	assert(os.path.isfile(LOGGING_TEST_FILE)==True)
	with open(LOGGING_TEST_FILE, 'r') as lf:
		assert(len(lf.read().encode('utf-8'))<=log_size_limit)

	assert(os.path.isfile(LOGGING_TEST_FILE+".1")==True)
	with open(LOGGING_TEST_FILE+".1", 'r') as lf:
		assert(len(lf.read().encode('utf-8'))<=log_size_limit)



def test_silent_run():
	def slow_job(sleep_time):
		time.sleep(sleep_time)
		print("Slow job completed")

	sleep_time = 1
	s = TaskScheduler(log_filepath=LOGGING_TEST_FILE)
	s.every(1).do_parallel(slow_job, sleep_time=sleep_time).silently()
	s.check()

	counter = 4
	while counter>0:
		print("outside")
		counter -= 1
		print('running:', s.jobs[0].is_running)
		s.check()
		time.sleep(0.5)
	print("stopping")
	s.join()
	j0 = s.jobs[0].to_dict()
	assert('Slow job completed' in j0['logs']['log'])
	assert('===' not in j0['logs']['log'])      # '===' is printed only if job is not silent
	assert('outside' not in j0['logs']['log'])
	assert('stopping' not in j0['logs']['log'])
	pretty_print(j0)
	# test log file
	assert(os.path.isfile(LOGGING_TEST_FILE)==True)
	with open(LOGGING_TEST_FILE, 'r') as lf:
		assert('Slow job completed' in lf.read())



def test_job_docstring():
	def job_with_descr():
		'''job test docsting'''
		print("docstring test")

	def job_without_descr():
		print("no docstring test")

	s = TaskScheduler()
	j_w_descr = s.every(1).do(job_with_descr)
	j_wo_descr = s.every(1).do(job_without_descr)

	assert(j_w_descr.to_dict()['doc']=='job test docsting')
	assert(j_wo_descr.to_dict()['doc']==None)
	pretty_print(j_w_descr.to_dict())


def test_job_rerun():
	now = dt.now()
	today_str = now.strftime("%A").lower() # day of the week
	in2sec_str = now.strftime("%H:%M")
	s = TaskScheduler()
	s.every(today_str).at(in2sec_str).do(job, x="hello", y=today_str)
	assert(len(s.jobs) == 1)
	time.sleep(0.5)
	s.check() # will run here, and reschedule to next week
	run_end = s.jobs[0].to_dict()['logs']['end']
	# test if next run greater than 6 days from now
	test_timestamp = time.time()
	assert(s.jobs[0].next_timestamp > test_timestamp+(6*24*60*60))
	time.sleep(1)

	# rerun the job
	prev_resched_timestamp = s.jobs[0].next_timestamp
	s.rerun(s.jobs[0].jobid)
	time.sleep(1)
	rerun_end = s.jobs[0].to_dict()['logs']['end']
	assert(run_end != rerun_end)
	# rerun should not reschedule the job
	assert(s.jobs[0].next_timestamp == prev_resched_timestamp)



def test_job_disable():
	s = TaskScheduler()
	j = s.every(1).do(job, x="hello", y="state")
	time.sleep(1)
	s.check()
	data = j.to_dict()
	first_run_start = data['logs']['start']
	assert(data['is_disabled']==False)
	assert(first_run_start is not None) # runs fine

	# test job level disable/enable
	j.disable()
	time.sleep(1)
	s.check()
	data = j.to_dict()
	assert(data['is_disabled']==True)
	assert(data['logs']['start'] == first_run_start) # did not run again as it was disabled

	j.enable()
	time.sleep(1)
	s.check()
	data = j.to_dict()
	assert(data['is_disabled']==False)
	assert(data['logs']['start'] > first_run_start) # ran again after enabling

	# test scheduler level disable/enable
	latest_run_start = data['logs']['start']
	s.disable_all()
	time.sleep(1)
	s.check()
	data = j.to_dict()
	assert(data['is_disabled']==True)
	assert(data['logs']['start'] == latest_run_start) # did not run again as it was disabled

	s.enable_all()
	time.sleep(1)
	s.check()
	data = j.to_dict()
	assert(data['is_disabled']==False)
	assert(data['logs']['start'] > latest_run_start) # ran again after enabling




@pytest.mark.filterwarnings("ignore:I/O error")
def test_timezones():
	tomorrow = dt.now() + timedelta(days=1)
	tomorrow_str = tomorrow.strftime("%A").lower() # day of the week
	in2sec_str = tomorrow.strftime("%H:%M")

	s = TaskScheduler()
	with pytest.raises(BadScheduleError):
		s.every(tomorrow_str).at("8:00").timezone("US/US").do(job, x="hello", y=today_str) # bad timezone

	euro = s.every(tomorrow_str).at(in2sec_str).timezone("Europe/London").do(job, x="hello", y=tomorrow.strftime("%A"))
	assert(len(s.jobs) == 1)
	local = s.every(tomorrow_str).at(in2sec_str).timezone("America/New_York").do(job, x="hello", y=tomorrow.strftime("%A"))
	assert((euro.next_timestamp - local.next_timestamp)/60/60 in (-4, -5))

	# test if next run greater than 6 days from now
	# 'now' is in NY time and schedule is in London. So it will automatically be rescheduled to next run
	now = dt.now(tz.gettz("America/New_York"))
	today_str = now.strftime("%A").lower() # day of the week
	in2sec_str = now.strftime("%H:%M")
	s.every(today_str).at(in2sec_str).timezone("Europe/London").do(job, x="hello", y=today_str)
	test_timestamp = now.timestamp()
	assert(s.jobs[-1].next_timestamp > test_timestamp+(6*24*60*60))
	time.sleep(1)

	est = s.on(dt(now.year+1, 12, 1).strftime("%Y-%m-%d")).at("8:00").timezone("America/New_York").do(job, x="hello", y=today_str)
	# gmt = s.on(dt(now.year+1, 12, 1).strftime("%Y-%m-%d")).at("8:00").timezone("Europe/London").do(job, x="hello", y=today_str)
	assert(est.to_datetime(est.next_timestamp).strftime('%Z')=="EST")

	edt = s.on(dt(now.year+1, 6, 1).strftime("%Y-%m-%d")).at("8:00").timezone("America/New_York").do(job, x="hello", y=today_str)
	assert(edt.to_datetime(edt.next_timestamp).strftime('%Z')=="EDT")



def test_fs_persistent_logs():
	s = TaskScheduler() # persist_states=True by default
	j1 = s.every(1).do_parallel(job, x="hello", y="state1")
	j2 = s.every(1).do(job, x="hello", y="state2") # make argument slightly different so that job signature is different
	time.sleep(2)
	s.check()
	time.sleep(1)

	jobs_state_dir = s._state_handler._job_state_dir
	for j in [j1, j2]:
		state_file = os.path.join(jobs_state_dir ,f"{j.signature_hash()}.pickle")
		assert(os.path.isfile(state_file))

		import pickle
		with open(state_file, 'rb') as f:
			state = pickle.load(f)
			data = state['logs']
		assert(isinstance(data['start'], dt))
		assert(isinstance(data['end'], dt))
		assert(state['disabled']==False)

		assert(j._run_info._ended_at==data['end'])

	s = TaskScheduler(persist_states=False)
	j = s.every(1).do(job, x="hello", y="state")
	time.sleep(1)
	s.check()
	assert(s._state_handler is None)
	assert(isinstance(j._run_info._ended_at, dt)) # test if it ran even without persist_states




def test_sqlite_persistent_logs():
	state = SQLAlchemyState(f"sqlite:///{DB_STATE_TEST_FILE}")
	assert(not os.path.isfile(DB_STATE_TEST_FILE)) # file should not be created until first use

	s = TaskScheduler(state_handler=state) # persist_states=True by default
	assert(s._state_handler is not None)

	j = s.every(1).do(job, x="hello", y="state")
	s.every(1).do_parallel(job, x="hello", y="state2") # make argument slightly different so that job signature is different
	time.sleep(2)

	assert(j._run_info._ended_at is None)
	assert(not os.path.isfile(DB_STATE_TEST_FILE)) # file should not be created until first use

	s.check()
	time.sleep(1)

	assert(os.path.isfile(DB_STATE_TEST_FILE)) # file saved at the s.check() call
	assert(j._run_info._ended_at is not None)
	assert(isinstance(j._run_info._ended_at, dt)) # test if state was restored


	# restore saved states
	s = TaskScheduler(state_handler=state)
	j = s.every(1).do(job, x="hello", y="state")

	s.restore_all_job_logs() # need to manually call restore method - will be automatically called if s.start() is used

	assert(j._run_info._ended_at is not None)
	assert(isinstance(j._run_info._ended_at, dt))

	time.sleep(1)
	s.check()
	assert(isinstance(j._run_info._ended_at, dt))
