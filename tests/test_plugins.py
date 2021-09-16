from flask import Flask
from flask_production import CherryFlask, TaskScheduler
from flask_production.plugins import ReadOnlyTaskMonitor

import time
import pytest

app = Flask(__name__)
sched = TaskScheduler()
monitor = ReadOnlyTaskMonitor(app, sched=sched, display_name="Web Test")

toggle = False

@app.route("/", methods=['GET'])
def main():
	return 'Main dummy page'


def wash_car():
	"""
	This is a dummy job that is scheduled to wash my car
	Note: objects in the mirror are closer than they appear
	"""
	global toggle
	toggle = not toggle
	if toggle:
		count = 50
		while count > 0:
			time.sleep(0.1)
			print("washing..\n")
			count -= 1
		print("The car was washed")
	else:
		time.sleep(1)
		raise Exception("car wash failed!")

def another_task():
	print("another_task")


@pytest.fixture
def client():
	with app.test_client() as c:
		yield c


def test_webservice(client):
	assert(client.get("/").status_code==200)

def test_blankpage(client):
	homepage = client.get("/{}".format(monitor._endpoint))
	assert(homepage.status_code==200)
	assert(homepage.data.decode().lower()=='nothing here')


def test_monitor_homepage(client):
	sched.every("day").at("8:00").do(another_task)
	sched.every(20).do(wash_car, do_parallel=True)
	sched.every(30).do(lambda: wash_car(), do_parallel=True)
	# CherryFlask(app, sched).run() # unused

	homepage = client.get("/{}".format(monitor._endpoint))
	assert(homepage.status_code==200)
	html_text = homepage.data.decode(errors='ignore').lower()
	assert("lambda" in html_text)
	assert("wash_car" in html_text)
	assert("another_task" in html_text)


def test_monitor_jobpage(client):
	jobpage = client.get("/{}/0".format(monitor._endpoint))
	assert(jobpage.status_code==200)
	html_text = jobpage.data.decode(errors='ignore').lower()
	assert("another_task" in html_text)
	assert("lambda" not in html_text)

	assert("logs" in html_text)
	assert("next run in" in html_text)

def test_monitor_rerun_btn(client):
	sched.every(30).do(another_task, do_parallel=True)
	res = client.post("/{}/rerun".format(monitor._endpoint), json={'job_idx':0})
	assert(res.status_code==200)
	assert("success" in res.data.decode(errors='ignore').lower())
