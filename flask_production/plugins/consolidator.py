import socket
import requests
import json

from .html_templates import * # pylint: disable=unused-wildcard-import

EXCLUDE_PORTS = [22]


class MonitorConsolidator:
	'''Automatically scan ports and consolidate many TaskMonitors'''

	STYLES = '''
		<style>
			body {
				width:100%;
				height:100%;
				margin: 0;
				display:flex;
				flex-direction:column;
				align-items:center;
			}
			.wrapper {
				margin: 50px;
				display: grid;
				grid-template-columns: repeat(3, 1fr);
				gap: 30px;
			}
			.monitor-block {
				padding: 20px;
				width: 250px;
				height: 70px;
				border: thin solid lightgrey;
				border-radius: 5px;
				box-shadow: 5px 5px 5px #888888;
				display:flex;
				flex-direction:column;
				justify-content: space-around;
				align-items:center;
				cursor:pointer;
			}
			.monitor-block:hover {
				box-shadow: 2px 2px 4px #888888;
			}
			.error-border {
				border: 2px solid red;
			}
		</style>
	'''

	def __init__(self,
		app,
		scan_host='127.0.0.1',
		known_ports=[],
		page_refresh=30):

		self.app = app
		self.machine = socket.gethostname()
		self.scan_host = scan_host
		self.known_ports = known_ports
		self.page_refresh = page_refresh
		self.app.add_url_rule("/", view_func=self._render_monitors, methods=['GET'])


	def _check_taskmonitor(self, port):
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		result = sock.connect_ex((self.scan_host, port))
		if result == 0:
			print ("Port is open -",port)
			try:
				monitor_url = f"http://{self.scan_host}:{port}/@taskmonitor"
				res = requests.get(f"{monitor_url}/json/summary").json()
				# print(json.dumps(res, indent=4))
				res['port'] = port
				res['url'] = monitor_url
				return res
			except Exception as e:
				print(e)
		sock.close()

	def _find_monitors(self, port_start=1000, port_end=10000):
		for p in self.known_ports:
			if p in EXCLUDE_PORTS: continue
			monitor = self._check_taskmonitor(p)
			if monitor is not None:
				yield monitor
		for p in range(port_start, port_end):
			if p in EXCLUDE_PORTS: continue
			if p in self.known_ports: continue
			monitor = self._check_taskmonitor(p)
			if monitor is not None:
				yield monitor


	def _render_monitors(self):
		content = []
		for monitor in self._find_monitors():
			css = ['monitor-block']
			attrs = {}
			elem = ""
			if 'error' in monitor:
				elem = H(5, monitor['error']) + SPAN(str(monitor['port']))
				css.append('error-border')
			else:
				mon = monitor['success']
				msg = f"tasks: {mon['summary']['count']}  errors: {mon['summary']['errors']}"
				elem = SPAN(B(mon['name'])) + SPAN(msg)
				if mon['summary']['errors'] > 0:
					css.append('error-border')
				url = monitor['url']
				attrs['onclick'] = f'window.open("{url}")'
				attrs['title'] = url
			content.append(DIV(elem, css=css, attrs=attrs))

		wrapper = DIV(''.join(content), css='wrapper')
		header_txt = f"Task Monitors on {self.machine}"
		header = H(2, header_txt)
		rerun_txt = SMALL(f"Auto-refresh in {SPAN(self.page_refresh, attrs={'id': 'refresh-msg'})} seconds")

		auto_reload = SCRIPT('''
		let COUNT_DOWN = {page_refresh}
		window.addEventListener('load', (event) => {{
			setInterval(()=>{{
				if (COUNT_DOWN > 0) {{
					COUNT_DOWN --
					document.getElementById('refresh-msg').innerText = COUNT_DOWN
				}} else {{
					location.reload()
				}}
			}}, 1000)
		}})
		'''.format(page_refresh=self.page_refresh))
		return HTML(''.join([
			self.STYLES,
			header,
			rerun_txt,
			wrapper,
			auto_reload
		]), title=header_txt)
