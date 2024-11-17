import socket
import requests
# import json
import psutil
from flask import send_file

from .html_templates import * # pylint: disable=unused-wildcard-import




class ControlPanel:
	'''Automatically scan ports and consolidate many TaskMonitors'''

	def __init__(self,
		app,
		ports=[],
		external_addrs=[],
		page_refresh=60):

		self.app = app
		self.machine = socket.gethostname()
		self.local_ip = socket.gethostbyname(self.machine)
		self.ports = set(ports)
		self.external_addrs = set(external_addrs)
		self.page_refresh = page_refresh
		self.app.add_url_rule("/", view_func=self._render_monitors, methods=['GET'])
		self.app.add_url_rule("/static/<type>/<filename>", view_func=self.__serve_file, methods=['GET'])


	def __serve_file(self, type, filename):
		return send_file(os.path.join(WEB_FOLDER, type, filename))


	def scan(self, min_port=1000, max_port=10000, timeout=5):
		for conn in psutil.net_connections():
			if conn.status == "LISTEN" and conn.laddr.port >= min_port and conn.laddr.port <= max_port:
				m = self._get_taskmonitor(self.local_ip, conn.laddr.port, timeout=timeout)
				if m is not None:
					self.ports.add(conn.laddr.port)
				print('>> scanned', conn.laddr.port, "- found" if m is not None else "")


	def _get_taskmonitor(self, host, port, timeout=5):
		try:
			if port == 80:
				monitor_url = f"http://{host}/@taskmonitor" # need to add option to change this endpoint since task monitor has that option
			elif port == 443:
				monitor_url = f"https://{host}/@taskmonitor" # need to add option to change this endpoint since task monitor has that option
			else:
				monitor_url = f"http://{host}:{port}/@taskmonitor" # need to add option to change this endpoint since task monitor has that option

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
			monitor = self._get_taskmonitor(self.local_ip, port)
			if monitor is not None:
				yield monitor
		for host, port in self.external_addrs:
			monitor = self._get_taskmonitor(host, port)
			if monitor is not None:
				yield monitor


	def _render_monitors(self):
		content = []
		tot_jobs = 0
		for monitor in self._iter_monitors():
			css = ['monitor-block']
			attrs = {}
			elem = ""
			if 'error' in monitor:
				elem = H(5, monitor['error']) + SPAN(str(monitor['url']))
				css.append('error-border')
				css.append('no-page')
				attrs['title'] = monitor['error']
			else:
				mon = monitor['success']
				# for backward compatibility, apply defaults
				if 'errors' not in mon['summary']:
					mon['summary']['errors'] = 0
				if 'running' not in mon['summary']:
					mon['summary']['running'] = 0

				err_msg_css = []
				running_msg_css = []
				if mon['summary']['errors'] > 0:
					css.append('error-border')
					err_msg_css = ['red']
				if mon['summary']['running'] > 0:
					running_msg_css = ['yellow']

				task_msg = f"tasks: {DIV(mon['summary']['count'])}"
				running_msg = f"running: {DIV(mon['summary']['running'], css=running_msg_css)}"
				error_msg = f"errors: {DIV(mon['summary']['errors'], css=err_msg_css)}"

				msg = f"{task_msg}  {running_msg}  {error_msg}"
				elem = SPAN(B(mon['name']), css=['block-title']) + SPAN(msg, css=['block-msg'])
				attrs['data-url'] = monitor['url']
				attrs['title'] = f"{mon['name']}\n{monitor['url']}"
			content.append(DIV(elem, css=css, attrs=attrs))
			tot_jobs += mon['summary']['count']

		wrapper = DIV(''.join(content), css='wrapper')
		header_txt = f"Control Panel"
		header = DIV(H(2, header_txt), css=['header-bar'])
		summary_txt = SMALL(f"Monitoring {tot_jobs} jobs")
		rerun_txt = SMALL(f"Auto-refresh in {SPAN(self.page_refresh, attrs={'id': 'refresh-msg'})} seconds")

		return HTML(''.join([
			STYLE_LINK('/static/css/dark_theme.css'),
			STYLE_LINK('/static/css/ctrl_panel.css'),
			header,
			summary_txt,
			rerun_txt,
			wrapper,
			SCRIPT(f'''let COUNT_DOWN = {self.page_refresh}'''),
			SCRIPT_SRC('/static/js/ctrl_panel.js')
		]), title=header_txt)
