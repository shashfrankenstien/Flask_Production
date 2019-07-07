import cherrypy
import time
import traceback
from datetime import datetime as dt


class CherryFlask(object):

	def __init__(self, app, request_environ=None, scheduler=None):
		self.app = app
		self.sched = scheduler
		if request_environ is not None:
			@app.after_request
			def teardown(response): # pylint: disable=unused-variable
				adr = request_environ.get('HTTP_X_REAL_IP', request_environ.get('REMOTE_ADDR'))
				mth = request_environ.get('REQUEST_METHOD')
				pth = request_environ.get('PATH_INFO')
				print(f'''{adr} - [{dt.now().strftime('%d/%b/%Y %H:%M:%S')}] - "{mth} {pth}" - {response.status_code}''')
				return response

	def run(self, host='0.0.0.0', port=8080, threads=5, debug=False):
		if not debug: cherrypy.config.update({'engine.autoreload.on' : False})

		cherrypy.tree.graft(self.app.wsgi_app, '/')
		cherrypy.server.unsubscribe()
		server = cherrypy._cpserver.Server()

		server.socket_host = host
		server.socket_port = port
		server.thread_pool = threads
		server.subscribe()

		if hasattr(cherrypy.engine, "signal_handler"):
			cherrypy.engine.signal_handler.subscribe()
		if hasattr(cherrypy.engine, "console_control_handler"):
			cherrypy.engine.console_control_handler.subscribe()
		
		try:
			cherrypy.engine.start()
			if self.sched is not None:
				self.sched.start()
			else:
				cherrypy.engine.block()
		except Exception:
			traceback.print_exc()
			self.stop()
			

	def stop(self):
		cherrypy.engine.exit()
