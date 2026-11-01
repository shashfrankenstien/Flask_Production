from flask import request
import cherrypy
import traceback
from datetime import datetime as dt
import threading


class CherryFlask(object):

	def __init__(self, app, scheduler=None, silent=False, timeout=60, blocking=True):
		self.app = app
		self.sched = scheduler
		self.timeout = timeout
		self.blocking = blocking

		self._scheduler_thread = None
		self._shutdown_lock = threading.Lock()
		self._engine_exited = False

		if not silent:
			@app.after_request
			def _teardown(response): # pylint: disable=unused-variable
				pth = request.environ.get('PATH_INFO')
				if "@" not in pth and 'favicon' not in pth: # disable logging of endpoints like @taskmonitor, favicon.ico
					adr = request.environ.get('HTTP_X_REAL_IP', request.environ.get('REMOTE_ADDR'))
					mth = request.environ.get('REQUEST_METHOD')
					print(f'''{adr} - [{dt.now().strftime('%m/%d/%Y %H:%M:%S')}] - "{mth} {pth}" - {response.status_code}''')
				return response


	def run(self, host='0.0.0.0', port=8080, threads=5, debug=False):
		if not debug:
			cherrypy.config.update({'engine.autoreload.on' : False})

		cherrypy.tree.graft(self.app.wsgi_app, '/')
		cherrypy.server.unsubscribe()
		server = cherrypy._cpserver.Server()

		server.socket_host = host
		server.socket_port = port
		server.thread_pool = threads
		server.socket_timeout = self.timeout
		server.subscribe()

		if hasattr(cherrypy.engine, "signal_handler"):
			cherrypy.engine.signal_handler.subscribe()
		if hasattr(cherrypy.engine, "console_control_handler"):
			cherrypy.engine.console_control_handler.subscribe()

		self._engine_exited = False
		engine_started = False
		try:
			cherrypy.engine.start()
			engine_started = True
			if self.sched is not None:
				cherrypy.engine.subscribe('exit', lambda:self.sched.stop())
				if self.blocking:
					self.sched.start()
				else:
					def _sched_start():
						try:
							self.sched.start()
						except Exception:
							traceback.print_exc()
							self.stop()

					self._scheduler_thread = threading.Thread(target=_sched_start)
					self._scheduler_thread.daemon = True
					self._scheduler_thread.start()

			else:
				if self.blocking:
					cherrypy.engine.block()

		except Exception:
			if engine_started:
				self.stop()
			raise

		else:
			# if we reach here in blocking execution, it means server has finished running
			# and no errors occurred
			if self.blocking:
				self.stop()


	def stop(self):
		# locking here as this may get called from within the scheduler thread in non-blocking config
		with self._shutdown_lock:
			if not self._engine_exited:
				cherrypy.engine.exit()
				self._engine_exited = True

		if self._scheduler_thread is not None and self._scheduler_thread != threading.current_thread():
			self._scheduler_thread.join()

