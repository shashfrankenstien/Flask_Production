# Flask_Production
Cherrypy prod server for Flask + parallel scheduler plugin

![Python 3.6](https://img.shields.io/badge/python-3.6+-blue.svg)
![license](https://img.shields.io/github/license/shashfrankenstien/flask_production)
![pytest](https://github.com/shashfrankenstien/Flask_Production/workflows/pytest/badge.svg)


## Installation

```sh
pip install -U git+https://github.com/shashfrankenstien/Flask_Production.git
```


## Usage example

> Cherrypy Server
```py
from flask import Flask
from flask_production import CherryFlask

app = Flask(__name__)
cherry = CherryFlask(app)

cherry.run(host="0.0.0.0", port=8080, threads=5, debug=False)
```

> Cherrypy Server + TaskScheduler
```py
from flask import Flask
from flask_production import CherryFlask, TaskScheduler

app = Flask(__name__)

sched = TaskScheduler(check_interval=2)
sched.every(60).do(foo) # Runs every minute
sched.every("weekday").at("08:00").do(lambda:bar())
example_job = sched.every("weekday").at("09:00").do(lambda:failing()).catch(lambda e: print(e))

print(example_job.to_dict()) # access job information and status as dict
print(sched.jobs[-1].to_dict()) # same job

cherry = CherryFlask(app, scheduler=sched)
cherry.run(host="0.0.0.0", port=8080, threads=5, debug=False)
```

> Experimental Plugins

The TaskScheduler exposes a list of Job objects through  the `.jobs` attribute

Job information and logs from the last execution are available using the `.to_dict()` method

There is one example plugin ReadOnlyTaskMonitor

```py
from flask import Flask
from flask_production import CherryFlask, TaskScheduler
from flask_production.plugins import ReadOnlyTaskMonitor

app = Flask(__name__)
sched = TaskScheduler(check_interval=2)

monitor = ReadOnlyTaskMonitor(app, sched)
print(monitor._endpoint) # /@taskmonitor

sched.every(60).do(foo) # Runs every minute
cherry = CherryFlask(app, scheduler=sched)
cherry.run(host="0.0.0.0", port=8080)
# localhost:8080/@taskmonitor
```
[Example Gist here](https://gist.github.com/shashfrankenstien/5cfa8821d74c24fb0a01b979d434e5bb)
