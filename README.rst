flask-production
================

Cherrypy prod server for Flask + parallel task scheduler

|Python 3.6| |license| |pytest|

Installation
---------------------

.. code:: sh

   pip install flask_production

Usage example
-------------

CherryFlask
~~~~~~~~~~~~~~~
``Cherrypy`` server on top of ``Flask`` app

.. code:: python

   CherryFlask(app, scheduler=None, silent=False)


Parameters:

- **app** *(Flask)*: ``Flask`` application

- **scheduler** *(TaskScheduler)*: task scheduler to run in parallel with ``Flask`` app

- **silent** *(bool)*: don't print logs
      - default False



.. code:: python

   from flask import Flask
   from flask_production import CherryFlask

   app = Flask(__name__)
   ...

   cherry = CherryFlask(app)
   cherry.run(host="0.0.0.0", port=8080, threads=5, debug=False)

|


TaskScheduler
~~~~~~~~~~~~~~~
| Main class to setup, run and manage jobs


.. code:: python

   TaskScheduler(check_interval=5,
      holidays_calendar=None,
      on_job_error=None,
      log_filepath=None,
      log_maxsize=5*1024*1024, # 5 MB
      log_backups=1)


Parameters:

- **check_interval** *(int)*: how often to check for pending jobs
      - default 5 seconds

- **holidays_calendar** *(holidays.HolidayBase)*: calendar to use for intervals like ``businessday``
      - default US holidays

- **on_job_error** *(func(e))*: function to call if any job fails
- **log_filepath** *(path)*: file to write logs to
- **log_maxsize** *(int)*: byte limit per log file
      - default 5 mb (only effective if log_filepath is provided)
- **log_backups** *(int)*: number of backups of logs to retain
      - default 1 (only effective if log_filepath is provided)



.. code:: python

   from flask_production import TaskScheduler

   sched = TaskScheduler(check_interval=2)

   # Run every minute
   sched.every(60).do(foo)

   # Run on end of every month (with strict_date False)
   sched.every("31st").strict_date(False).at("08:00").do(foo)

   # Run every weekday
   sched.every("weekday").at("08:00").do(lambda:bar())

   # catch() will run on job error
   example_job = sched.every("weekday").at("09:00").do(lambda:failing()).catch(lambda e: print(e))

   # access job information and status as dict
   print(example_job.to_dict())
   print(sched.jobs[-1].to_dict()) # same job

   sched.start() # starts the task scheduler and blocks
..


Instead of ``sched.start()``, TaskScheduler can be run in parallel with a Flask application using ``CherryFlask``

.. code:: python

   from flask import Flask
   from flask_production import TaskScheduler, CherryFlask

   app = Flask(__name__)
   ...

   sched = TaskScheduler()
   ...

   cherry = CherryFlask(app, scheduler=sched)
   cherry.run(host="0.0.0.0", port=8080, threads=5, debug=False)

..


|

TaskMonitor
~~~~~~~~~~~~~~

| The TaskScheduler exposes a list of Job objects through the ``.jobs`` attribute
| Job information and logs from the last execution are available using the ``.to_dict()`` method
| TaskMonitor uses these features to provide a web interface to view and rerun tasks



.. code:: python

   TaskMonitor(
      app,
      sched,
      display_name=None,
      endpoint="@taskmonitor",
      homepage_refresh=30,
      taskpage_refresh=5)

Parameters:

- **app** *(int)*: ``Flask`` application
- **sched** *(TaskScheduler)*: task scheduler with task definitions
- **display_name** *(str)*: name of the application to be displayed
      - default app.name

- **endpoint** *(str)*: URL endpoint where the taskmonitor can be viewed
      - default "@taskmonitor"
- **homepage_refresh** *(int)*: home page auto refresh interval (in seconds)
      - default 30
- **taskpage_refresh** *(int)*: task page auto refresh interval (in seconds)
      - default 5



.. code:: python

   from flask import Flask
   from flask_production import CherryFlask, TaskScheduler
   from flask_production.plugins import TaskMonitor

   app = Flask(__name__)
   sched = TaskScheduler(check_interval=2)

   monitor = TaskMonitor(app, sched)
   print(monitor._endpoint) # /@taskmonitor

   # Run every minute
   sched.every(60).do(foo)

   cherry = CherryFlask(app, scheduler=sched)
   cherry.run(host="0.0.0.0", port=8080) # localhost:8080/@taskmonitor

`Example Gist
here <https://gist.github.com/shashfrankenstien/5cfa8821d74c24fb0a01b979d434e5bb>`__


.. |Python 3.6| image:: https://img.shields.io/badge/python-3.6+-blue.svg
.. |license| image:: https://img.shields.io/github/license/shashfrankenstien/flask_production
.. |pytest| image:: https://github.com/shashfrankenstien/Flask_Production/workflows/pytest/badge.svg
