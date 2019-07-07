import os
import time
from datetime import datetime as dt, timedelta
from dateutil.parser import parse as date_parse
os.chdir('..')
from cherry_flask import TaskScheduler


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
	interval = 2
	s = TaskScheduler()
	s.every(interval).do(job, x="hello", y="world")
	assert (abs(s.jobs[0].next_timestamp - (d+interval)) < 1)
	time.sleep(interval)
	s.check()
	assert (abs(s.jobs[0].next_timestamp - (d+(2*interval))) < 0.1)



# def test_start():
# 	i = 0
# 	def task():
# 		i = i+1
# 	s = TaskScheduler(check_interval=1)
# 	s.every(2).do(task)
# 	t = time.time()
