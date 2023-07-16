import os, shutil
import time
import threading

from flask import Flask
import requests
from flask_production import CherryFlask, TaskScheduler, TaskMonitor
from flask_production.state import FileSystemState

CUR_APP_DATA_DIR_PATH = FileSystemState()._get_current_app_data_directory()

MONITOR_NAME = "Cherrypy Test"
TEST_PORT = 5555


def task():
	time.sleep(1)
	print("Done")


app = Flask(__name__)
sched = TaskScheduler()
monitor = TaskMonitor(app, sched=sched, display_name=MONITOR_NAME)

cherry = CherryFlask(app, sched)

thrd = threading.Thread(target=lambda: cherry.run(port=TEST_PORT))


@app.route("/", methods=['GET'])
def main():
	return 'Main dummy page'


def setup_module(module):
	thrd.start()
	time.sleep(1)


def teardown_module(module):
	cherry.stop()
	thrd.join()
	time.sleep(1)
	if os.path.isdir(CUR_APP_DATA_DIR_PATH):
		shutil.rmtree(CUR_APP_DATA_DIR_PATH)


def test_cherry_simple():
	res = requests.get(f"http://localhost:{TEST_PORT}/")
	assert(res.status_code==200)


def test_cherry_sched():
	res = requests.get(f"http://localhost:{TEST_PORT}/{monitor._endpoint}/json/summary")
	assert(res.status_code==200)
	assert('error' in res.json())

	sched.every(20).do(task)

	res = requests.get(f"http://localhost:{TEST_PORT}/{monitor._endpoint}/json/summary")
	assert(res.status_code==200)
	res_json = res.json()
	assert('success' in res_json)
	assert(res_json['success']['summary']['count']==1)
	assert(len(res_json['success']['details'])==1)
