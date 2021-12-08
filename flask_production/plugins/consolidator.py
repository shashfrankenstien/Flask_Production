import socket
import requests
# import json
import psutil

from .html_templates import * # pylint: disable=unused-wildcard-import


class LocalMonitors:
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
		ports=[],
		page_refresh=30):

		self.app = app
		self.machine = socket.gethostname()
		self.ports = set(ports)
		self.page_refresh = page_refresh
		self.app.add_url_rule("/", view_func=self._render_monitors, methods=['GET'])


	def scan(self, min_port=1000, max_port=10000, timeout=5):
		for conn in psutil.net_connections():
			if conn.status == "LISTEN" and conn.laddr.port >= min_port and conn.laddr.port <= max_port:
				print('>> scanning', conn.laddr.port)
				m = self._get_taskmonitor(conn.laddr.port, timeout=timeout)
				if m is not None:
					self.ports.add(conn.laddr.port)


	def _get_taskmonitor(self, port, timeout=5):
		try:
			monitor_url = f"http://127.0.0.1:{port}/@taskmonitor"
			res = requests.get(f"{monitor_url}/json/summary", timeout=timeout).json()
			# print(json.dumps(res, indent=4))
			res['port'] = port
			res['url'] = monitor_url
			return res
		except Exception:
			# print(e)
			return None


	def _iter_monitors(self):
		for port in self.ports:
			monitor = self._get_taskmonitor(port)
			if monitor is not None:
				yield monitor


	def _render_monitors(self):
		content = []
		for monitor in self._iter_monitors():
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
