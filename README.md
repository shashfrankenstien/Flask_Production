# Flask_Production
Cherrypy prod server for Flask + parallel scheduler plugin

![Python 3.6](https://img.shields.io/badge/python-3.6+-blue.svg)
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

print(example_job.info) # access job information as dict

cherry = CherryFlask(app, scheduler=sched)
cherry.run(host="0.0.0.0", port=8080, threads=5, debug=False)
```
