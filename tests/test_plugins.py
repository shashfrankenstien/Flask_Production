from flask import Flask
from flask_production import TaskScheduler
from flask_production.plugins import TaskMonitor

import time
import json
import pytest

MONITOR_NAME = "Web Test"

app = Flask(__name__)
sched = TaskScheduler()
monitor = TaskMonitor(app, sched=sched, display_name=MONITOR_NAME)

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
	res = client.post("/{}/rerun".format(monitor._endpoint), json={'jobid':0}) # missing api_token causes call to be blocked
	assert(res.status_code==200)
	assert("blocked" in res.data.decode(errors='ignore').lower())
	time.sleep(1)
	res = client.post("/{}/rerun".format(monitor._endpoint), json={'jobid':0, 'api_token': monitor._api_protection_token})
	assert("success" in res.data.decode(errors='ignore').lower())


def test_monitor_disable_btn(client):
	sched.every(30).do(another_task, do_parallel=True)
	payload = {'jobid':0, 'api_token': monitor._api_protection_token, 'disable': True}
	res = client.post("/{}/enable_disable".format(monitor._endpoint), json=payload)
	assert(res.status_code==200)
	assert(sched.get_job_by_id(0).is_disabled==True)
	time.sleep(1)
	payload['disable'] = False
	res = client.post("/{}/enable_disable".format(monitor._endpoint), json=payload)
	assert("success" in res.data.decode(errors='ignore').lower())
	assert(sched.get_job_by_id(0).is_disabled==False)



def test_monitor_all_json(client):
	sched.every("day").at("8:00").do(another_task)

	resp = client.get("/{}/json/all".format(monitor._endpoint), content_type='application/json')
	respdict = json.loads(resp.data.decode('utf8'))
	assert('success' in respdict)
	assert(isinstance(respdict['success'], list))
	assert(isinstance(respdict['success'][0], dict))
	assert(isinstance(respdict['success'][0]['logs'], dict))


def test_monitor_one_json(client):
	sched.every("day").at("8:00").do(another_task)

	resp = client.get("/{}/json/0".format(monitor._endpoint), content_type='application/json')
	respdict = json.loads(resp.data.decode('utf8'))
	assert('success' in respdict)
	assert(isinstance(respdict['success'], dict))
	assert(respdict['success']['jobid']==0)


def test_monitor_summary(client):
	sched.every("day").at("8:00").do(another_task)

	all_resp = client.get("/{}/json/all".format(monitor._endpoint), content_type='application/json')
	all_respdict = json.loads(all_resp.data.decode('utf8'))

	resp = client.get("/{}/json/summary".format(monitor._endpoint), content_type='application/json')
	respdict = json.loads(resp.data.decode('utf8'))
	assert('success' in respdict)
	assert(respdict['success']['name']==MONITOR_NAME)
	assert(respdict['success']['summary']['count']==len(respdict['success']['details']))
	assert(respdict['success']['summary']['errors']==0)

	assert(len(all_respdict['success'])==len(respdict['success']['details']))
