flask-production
================

Cherrypy-based server for Flask, plus a scheduler and task monitor.

|Python 3.8| |license| |pytest|

Features
--------

- Run a Flask application with CherryPy via ``CherryFlask``
- Schedule one-off, recurring, monthly, and on-demand jobs
- Run jobs in parallel with ``do_parallel()``
- Expose a web-based task monitor with rerun and disable actions
- Persist scheduler state across restarts with filesystem or SQLAlchemy backends
- Support custom holidays calendars and timezones


Installation
------------

.. code:: sh

   pip install flask_production


Quick start
-----------

.. code:: python

   from flask import Flask
   from flask_production import CherryFlask, TaskScheduler

   def send_report():
       print("sending report")

   app = Flask(__name__)
   sched = TaskScheduler(check_interval=2)
   sched.every("day").at("08:00").do(send_report)

   cherry = CherryFlask(app, scheduler=sched)
   cherry.run(host="0.0.0.0", port=8080, threads=5, debug=False)

When used with ``CherryFlask``, the scheduler runs alongside the Flask app and is stopped cleanly when the server exits.



CherryFlask
-----------

``CherryFlask`` wraps a Flask app with a CherryPy server.

.. code:: python

   CherryFlask(app, scheduler=None, silent=False, timeout=60)

Parameters:

- **app** *(Flask)*: Flask application instance
- **scheduler** *(TaskScheduler)*: optional scheduler to run alongside the app
- **silent** *(bool)*: suppress request logging
- **timeout** *(int)*: CherryPy socket timeout in seconds

.. code:: python

   from flask import Flask
   from flask_production import CherryFlask

   app = Flask(__name__)
   cherry = CherryFlask(app)
   cherry.run(host="0.0.0.0", port=8080, threads=5, debug=False)



TaskScheduler
-------------

``TaskScheduler`` is the main class for defining and managing jobs.

.. code:: python

   TaskScheduler(
       check_interval=5,
       holidays_calendar=None,
       tzname=None,
       on_job_error=None,
       log_filepath=None,
       log_maxsize=5 * 1024 * 1024,
       log_backups=1,
       startup_grace_mins=0,
       persist_states=True,
       state_handler=None,
   )

Parameters:

- **check_interval** *(int)*: how often to check for pending jobs in seconds
      - default 5
- **holidays_calendar** *(holidays.HolidayBase)*: calendar for schedules such as ``businessday``
      - default US holidays
- **tzname** *(str)*: timezone name used by default
      - default local timezone
- **on_job_error** *(callable)*: callback invoked when a job fails
      - default None
- **log_filepath** *(str)*: optional file path for rotating logs
      - default None
- **log_maxsize** *(int)*: maximum size in bytes for the rotating log file
      - default 5 * 1024 * 1024
- **log_backups** *(int)*: number of log backups to retain
      - default 1
- **startup_grace_mins** *(int)*: grace period for jobs after a restart
      - default 0
- **persist_states** *(bool)*: restore job logs and disabled state after restart
      - default True
- **state_handler** *(BaseStateHandler)*: custom state backend
      - default ``FileSystemState()``


Common scheduling patterns:

.. code:: python

   from flask_production import TaskScheduler

   sched = TaskScheduler(check_interval=2)

   # Run every minute
   sched.every(60).do(my_job)

   # Run once per day at a specific time
   sched.every("day").at("08:00").do(my_job)

   # Run every weekday at 08:00 in a specific timezone
   sched.every("weekday").at("08:00").timezone("Europe/London").do(my_job)

   # Run on the 31st of each month (strict_date=False allows the last day of shorter months)
   sched.every("31st").strict_date(False).at("08:00").do(my_job)

   # Run multiple times in a day
   sched.every("day").at(["09:00", "17:00"]).do(my_job)

   # Run a job in a separate thread
   sched.every(30).do_parallel(my_job)

   # Run a script from disk
   sched.run_script("/path/to/scripts", "report.py", ["--daily"])

   # Start the scheduler loop (blocking)
   sched.start()

For standalone use, call ``sched.start()``. When running with ``CherryFlask``, pass the scheduler to ``CherryFlask(app, scheduler=sched)`` and let the app start it.



TaskMonitor
-----------

``TaskMonitor`` adds a web interface for inspecting jobs, viewing logs, rerunning tasks, and disabling or enabling them.


.. code:: python

   TaskMonitor(
      app,
      sched,
      display_name=None,
      endpoint="@taskmonitor",
      homepage_refresh=30,
      taskpage_refresh=5,
      can_rerun=True,
      can_disable=True,
      enhanced_rerun=True
   )

Parameters:

- **app** *(Flask)*: Flask application instance
- **sched** *(TaskScheduler)*: task scheduler with task definitions
- **display_name** *(str)*: name of the application to be displayed
      - default ``app.name``
- **endpoint** *(str)*: URL endpoint where the monitor can be viewed
      - default ``"@taskmonitor"``
- **homepage_refresh** *(int)*: home page auto-refresh interval in seconds
      - default 30
- **taskpage_refresh** *(int)*: task detail page auto-refresh interval in seconds
      - default 5
- **can_rerun** *(bool)*: enable the rerun action on job pages
      - default True
- **can_disable** *(bool)*: enable the disable/enable action on job pages
      - default True
- **enhanced_rerun** *(bool)*: allow editing job arguments before rerunning
      - default True




.. code:: python

   from flask import Flask
   from flask_production import CherryFlask, TaskScheduler
   from flask_production.plugins import TaskMonitor

   app = Flask(__name__)
   sched = TaskScheduler(check_interval=2)

   monitor = TaskMonitor(app, sched, display_name="My App")

   sched.every("day").at("08:00").do(my_job)

   cherry = CherryFlask(app, scheduler=sched)
   cherry.run(host="0.0.0.0", port=8080)

The monitor is available at ``/@taskmonitor`` by default, or at the endpoint you pass to ``TaskMonitor``.



State persistence
-----------------

By default, scheduler state is persisted to a filesystem-backed state directory. You can also use a SQLAlchemy-backed store.

.. code:: python

   from flask_production import TaskScheduler
   from flask_production.state import FileSystemState, SQLAlchemyState

   sched = TaskScheduler(persist_states=True)
   sched = TaskScheduler(persist_states=True, state_handler=FileSystemState())
   sched = TaskScheduler(persist_states=True, state_handler=SQLAlchemyState("sqlite:///app_state.db"))

The SQLAlchemy backend requires ``sqlalchemy`` and ``sqlalchemy-utils`` to be installed.



Custom holidays and timezones
-----------------------------

.. code:: python

   from flask_production import TaskScheduler
   from flask_production.hols import TradingHolidays

   holidays = TradingHolidays()
   sched = TaskScheduler(holidays_calendar=holidays)
   sched.every("businessday").at("10:00").do(my_job)



Examples and references
-----------------------

- The package includes tests covering scheduler behavior, plugin monitoring, and state persistence in the ``tests`` directory.
- The monitor exposes JSON endpoints for the full job list, a single job, and a summary view.


`Example Gist
here <https://gist.github.com/shashfrankenstien/5cfa8821d74c24fb0a01b979d434e5bb>`__


.. |Python 3.8| image:: https://img.shields.io/badge/python-3.8+-blue.svg
.. |license| image:: https://img.shields.io/github/license/shashfrankenstien/flask_production
.. |pytest| image:: https://github.com/shashfrankenstien/Flask_Production/workflows/pytest/badge.svg
