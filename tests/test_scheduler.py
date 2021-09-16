import os
import time
import threading
import json
from datetime import datetime as dt, timedelta
from monthdelta import monthdelta
from dateutil.parser import parse as date_parse
from flask_production import TaskScheduler
from flask_production.hols import TradingHolidays
from flask_production.sched import LOGGER, BadScheduleError

import pytest

def job(x, y):
	time.sleep(0.1)
	print(x, y)

def pretty_print(d):
	print(json.dumps(d, indent=4, default=str))

def teardown_function(function):
	log_file = 'testlog.log'
	if os.path.isfile(log_file):
		os.remove(log_file)


def test_registry():
	s = TaskScheduler()
	s.every("businessday").at("10:00").do(job, x="hello", y="world") # Job
	s.on('2019-05-16').do(job, x="hello", y="world") # OneTimeJob
	s.every(5).at("10:00").do(job, x="hello", y="world") # RepeatJob
	s.every('2nd').strict_date(False).at("10:00").do(job, x="hello", y="world") # MonthlyJob
	assert len(s.jobs) == 4


def test_badinterval():
	s = TaskScheduler()
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
	assert len(s.jobs) == 1
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


def test_onetime():
	yesterday = dt.now() - timedelta(days=1)
	tomorrow = (dt.now() + timedelta(days=1)).replace(hour=23, minute=59, second=0, microsecond=0)
	s = TaskScheduler()
	s.on(yesterday.strftime("%Y-%m-%d")).at("23:59").do(job, x="hello", y="world")
	s.on(tomorrow.strftime("%Y-%m-%d")).at("23:59").do(job, x="hello", y="world")
	for j in s.jobs:
		assert (j.next_timestamp==dt.timestamp(tomorrow) or j.next_timestamp==0)
	assert len(s.jobs) == 2
	s.check()
	assert len(s.jobs) == 1


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

	assert len(s.jobs) == 4


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
	d = time.time()
	sleep_time = 1
	s = TaskScheduler()
	s.every(sleep_time).do(job, x="hello", y="world", do_parallel=True)
	s.every(sleep_time).do(job, x="hello", y="world", do_parallel=True)
	ts = s.jobs[0].next_timestamp
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
	s.every(1).do(job, x="hello", y="world", do_parallel=True)

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
	s.every(sleep_time).do(failing_job, msg='one', do_parallel=True)
	s.every(sleep_time).do(failing_job, msg='two')
	s.every(sleep_time).do(failing_job, msg='three', do_parallel=True).catch(err_specific)
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
	log_file_path = 'testlog.log'
	s = TaskScheduler(log_filepath=log_file_path)
	s.every(1).do(slow_job, sleep_time=sleep_time, do_parallel=True)
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
	assert(os.path.isfile(log_file_path)==True)
	with open(log_file_path, 'r') as lf:
		assert('Slow job completed' in lf.read())
	for h in LOGGER.handlers:
		h.close()
		LOGGER.removeHandler(h)
	if os.path.isfile(log_file_path): os.remove(log_file_path)
	assert(os.path.isfile(log_file_path)==False)


def test_silent_run():
	def slow_job(sleep_time):
		time.sleep(sleep_time)
		print("Slow job completed")

	sleep_time = 1
	log_file_path = 'testlog.log'
	s = TaskScheduler(log_filepath=log_file_path)
	s.every(1).do(slow_job, sleep_time=sleep_time, do_parallel=True).silently()
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
	assert(os.path.isfile(log_file_path)==True)
	with open(log_file_path, 'r') as lf:
		assert('Slow job completed' in lf.read())
	for h in LOGGER.handlers:
		h.close()
		LOGGER.removeHandler(h)
	if os.path.isfile(log_file_path): os.remove(log_file_path)
	assert(os.path.isfile(log_file_path)==False)


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
	assert len(s.jobs) == 1
	time.sleep(0.5)
	s.check() # will run here, and reschedule to next week
	run_end = s.jobs[0].to_dict()['logs']['end']
	# test if next run greater than 6 days from now
	test_timestamp = time.time()
	assert s.jobs[0].next_timestamp > test_timestamp+(6*24*60*60)
	time.sleep(1)

	# rerun the job
	prev_resched_timestamp = s.jobs[0].next_timestamp
	s.rerun(0)
	time.sleep(1)
	rerun_end = s.jobs[0].to_dict()['logs']['end']
	assert run_end != rerun_end
	# rerun should not reschedule the job
	assert s.jobs[0].next_timestamp == prev_resched_timestamp
