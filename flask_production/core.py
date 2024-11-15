from flask import request
import cherrypy
import traceback
from datetime import datetime as dt


class CherryFlask(object):

	__slots__ = ['app', 'sched', 'timeout']

	def __init__(self, app, scheduler=None, silent=False, timeout=60):
		self.app = app
		self.sched = scheduler
		self.timeout = timeout
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
		if not debug: cherrypy.config.update({'engine.autoreload.on' : False})

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


		try:
			cherrypy.engine.start()
			if self.sched is not None:
				cherrypy.engine.subscribe('exit', lambda:self.sched.stop())
				self.sched.start()
			else:
				cherrypy.engine.block()
		except Exception:
			traceback.print_exc()
		finally:
			self.stop()

	def stop(self):
		cherrypy.engine.exit()


