import os
import time
import threading
import json
from datetime import datetime as dt, timedelta
from dateutil.parser import parse as date_parse
from flask_production import TaskScheduler
from flask_production.hols import TradingHolidays

def job(x, y):
	time.sleep(0.1)
	print(x, y)

def pretty_print(d):
	print(json.dumps(d, indent=4, default=str))

def test_registry():
	s = TaskScheduler()
	s.every("businessday").at("10:00").do(job, x="hello", y="world")
	s.on('2019-05-16').do(job, x="hello", y="world")
	assert len(s.jobs) == 2


def test_regular():
	d = dt.now().replace(hour=23, minute=59, second=0, microsecond=0)
	s = TaskScheduler()
	s.every("day").at("23:59").do(job, x="hello", y="world")
	assert (s.jobs[0].next_timestamp==dt.timestamp(d))


def test_day_of_week():
	now = dt.now()
	today_str = now.strftime("%A").lower()
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
	assert(s.jobs[0]._job_must_run_today(date_parse("2020-04-10"))==True) #Good Friday is not a US holiday by default

	s = TaskScheduler(holidays_calendar=TradingHolidays())
	s.every("businessday").at("10:00").do(job, x="hello", y="world")
	assert(s.jobs[0]._job_must_run_today(date_parse("2020-04-09"))==True)
	assert(s.jobs[0]._job_must_run_today(date_parse("2020-04-10"))==False) #test Custom Good Friday holiday
	assert(s.jobs[0]._job_must_run_today(date_parse("2020-04-11"))==False) #saturday


def test_onetime():
	yesterday = (dt.now() - timedelta(days=1)).replace(hour=23, minute=59, second=0, microsecond=0)
	tomorrow = (dt.now() + timedelta(days=1)).replace(hour=23, minute=59, second=0, microsecond=0)
	s = TaskScheduler()
	s.on(yesterday.strftime("%Y-%m-%d")).at("23:59").do(job, x="hello", y="world")
	s.on(tomorrow.strftime("%Y-%m-%d")).at("23:59").do(job, x="hello", y="world")
	for j in s.jobs:
		assert (j.next_timestamp==dt.timestamp(tomorrow) or j.next_timestamp==0)
	assert len(s.jobs) == 2
	s.check()
	assert len(s.jobs) == 1


def test_repeat():
	d = time.time()
	interval = 1
	s = TaskScheduler()
	s.every(interval).do(job, x="hello", y="world")
	assert (abs(s.jobs[0].next_timestamp - (d+interval)) < 0.1)
	time.sleep(interval)
	s.check()
	assert (abs(s.jobs[0].next_timestamp - (d+(2*interval))) < 0.1)


def test_repeat_parallel():
	d = time.time()
	interval = 1
	s = TaskScheduler()
	s.every(interval).do(job, x="hello", y="world", do_parallel=True)
	s.every(interval).do(job, x="hello", y="world", do_parallel=True)
	ts = s.jobs[0].next_timestamp
	assert (abs(ts - (d+interval)) < 0.1)
	time.sleep(interval)
	s.check()
	assert (s.jobs[0].next_timestamp == ts) # still not rescheduled
	time.sleep(0.2)
	assert (s.jobs[0].next_timestamp != ts) # rescheduled parallely
	assert (abs(s.jobs[0].next_timestamp - (d+(2*interval))) < 0.1)
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
	interval = 1
	errors = []
	err_count = 0

	def failing_job(msg):
		raise Exception(msg)

	def err(e):
		nonlocal errors, err_count
		errors.append(str(e))
		err_count += 1

	def err_specific(e):
		nonlocal errors, err_count
		errors.append(str(e)+"_specific")
		err_count += 1

	s = TaskScheduler(on_job_error=err)
	s.every(interval).do(failing_job, msg='one', do_parallel=True)
	s.every(interval).do(failing_job, msg='two')
	s.every(interval).do(failing_job, msg='three', do_parallel=True).catch(err_specific)
	time.sleep(interval)
	s.check()
	time.sleep(0.2)
	assert(sorted(errors)==sorted(['one', 'two', 'three_specific'])) # err callbacks were called
	assert(err_count==3)
	assert(s.jobs[0].did_fail()==True)
	pretty_print(s.jobs[0].info)


def test_print_capture():
	def slow_job(sleep_time):
		time.sleep(sleep_time)
		print("Slow job completed")

	sleep_time = 1
	s = TaskScheduler()
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
	assert('Slow job completed' in s.jobs[0].info['log'])
	assert('outside' not in s.jobs[0].info['log'])
	assert('stopping' not in s.jobs[0].info['log'])
	pretty_print(s.jobs[0].info)


def test_job_docstring():
	def job_with_descr():
		'''job test docsting'''
		print("docstring test")

	def job_without_descr():
		print("no docstring test")

	s = TaskScheduler()
	j_w_descr = s.every(1).do(job_with_descr)
	j_wo_descr = s.every(1).do(job_without_descr)

	assert(j_w_descr.info['job']['doc']=='job test docsting')
	assert(j_wo_descr.info['job']['doc']==None)
	pretty_print(j_w_descr.info)