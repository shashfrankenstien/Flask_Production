Flask_Production
================

Cherrypy prod server for Flask + parallel task scheduler

|Python 3.6| |license| |pytest|

Installation
---------------------

.. code:: sh

   pip install flask_production

Usage example
-------------

Cherrypy Server
~~~~~~~~~~~~~~~
.. code-block:: python

   from flask import Flask
   from flask_production import CherryFlask

   app = Flask(__name__)
   cherry = CherryFlask(app)

   cherry.run(host="0.0.0.0", port=8080, threads=5, debug=False)

|


Cherrypy Server + TaskScheduler
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. code-block:: python

   from flask import Flask
   from flask_production import CherryFlask, TaskScheduler

   app = Flask(__name__)

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

   cherry = CherryFlask(app, scheduler=sched)
   cherry.run(host="0.0.0.0", port=8080, threads=5, debug=False)

..

|

TaskMonitor Plugin
~~~~~~~~~~~~~~~~~~~
| The TaskScheduler exposes a list of Job objects through the ``.jobs`` attribute
| Job information and logs from the last execution are available using the ``.to_dict()`` method
| TaskMonitor uses these features to provide a web interface to view and rerun tasks

.. code-block:: python

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
