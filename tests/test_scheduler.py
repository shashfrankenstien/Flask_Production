import os
import time
from datetime import datetime as dt, timedelta
from dateutil.parser import parse as date_parse
from flask_production import TaskScheduler
from flask_production.hols import TradingHolidays

def job(x, y): print(x, y)

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


def test_error_callback():
	d = time.time()
	interval = 1
	error = None
	err_count = 0
	def err(e):
		nonlocal error, err_count
		error = str(e)
		err_count += 1

	def failing_job():
		raise Exception("No Way")

	s = TaskScheduler(on_job_error=err)
	s.every(interval).do(failing_job, do_parallel=True)
	s.every(interval).do(failing_job)
	time.sleep(interval)
	s.check()
	time.sleep(0.2)
	assert(error=="No Way") # err callback was called
	assert(err_count==2)
