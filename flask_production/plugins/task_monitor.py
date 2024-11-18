from datetime import datetime as dt
from collections import OrderedDict
import json
import random
import string

from dateutil import tz
from flask import Flask, Blueprint, request, send_file


from .html_templates import * # pylint: disable=unused-wildcard-import



class TaskMonitor(object):
	'''
	Web interface to monitor and manage tasks

	Args:
	- app (int): ``Flask`` application
	- sched (TaskScheduler): task scheduler with task definitions
	- display_name (str): name of the application to be displayed
		- default app.name

	- endpoint (str): URL endpoint where the taskmonitor can be viewed
		- default "@taskmonitor"
	- homepage_refresh (int): home page auto refresh interval (in seconds)
		- default 30
	- taskpage_refresh (int): task page auto refresh interval (in seconds)
		- default 5
	- can_rerun (bool): if True adds `rerun` button to job page
		- default True
	- can_disable (bool): if True adds `disable` button to job page
		- default True
	'''
	def __init__(self, app:Flask, sched, display_name=None, endpoint="@taskmonitor", homepage_refresh=30, taskpage_refresh=5,
		can_rerun=True, # adds rerun button to job page
		can_disable=True, # adds disable button to job page
		):
		self.tzname = sched._tz_default
		self._init_dt = dt.now(tz.gettz(self.tzname)).strftime("%m/%d/%Y %I:%M %p %Z") # preformatted start time
		self.app = app
		self.sched = sched
		self._endpoint = endpoint
		self._display_name = display_name or self.app.name
		self._homepage_refresh = homepage_refresh
		self._taskpage_refresh = taskpage_refresh
		self._api_protection_token = ''.join(random.choices(string.ascii_letters, k=20)) # protect job reruns external API calls. makes sure endpoint can only be called by TaskMonitor

		self._can_rerun = can_rerun
		self._can_disable = can_disable

		bp = Blueprint('taskmonitor_bp', __name__, url_prefix=f"/{self._endpoint}")

		bp.add_url_rule("", view_func=self.__show_all, methods=['GET'])
		bp.add_url_rule("/<int:n>", view_func=self.__show_one, methods=['GET'])
		bp.add_url_rule("/rerun", view_func=self.__rerun_job, methods=['POST'])
		bp.add_url_rule("/enable_disable", view_func=self.__enable_disable_job, methods=['POST'])
		bp.add_url_rule("/json/all", view_func=self.__get_all_json, methods=['GET'])
		bp.add_url_rule("/json/summary", view_func=self.__get_summary_json, methods=['GET'])
		bp.add_url_rule("/json/<int:n>", view_func=self.__get_one_json, methods=['GET'])

		bp.add_url_rule("/static/<type>/<filename>", view_func=self.__serve_file, methods=['GET'])
		self.app.register_blueprint(bp)

		_favicon_is_set = False
		for rule in self.app.url_map.iter_rules():
			if 'favicon.ico' in str(rule):
				_favicon_is_set = True

		if not _favicon_is_set:
			self.app.add_url_rule("/favicon.ico", view_func=lambda: self.__serve_file('ico', 'flask_boiler.ico'), methods=['GET'])


	def __html_wrap(self, elems, css=[]):
		return HTML(''.join(elems), title="{} Task Monitor".format(self._display_name), css=css)

	def __js_src_wrap(self, filename):
		return SCRIPT_SRC(f'/{self._endpoint}/static/js/{filename}')

	def __css_src_wrap(self, filename):
		return STYLE_LINK(f'/{self._endpoint}/static/css/{filename}')

	def __serve_file(self, type, filename):
		return send_file(os.path.join(WEB_FOLDER, type, filename), max_age=86400)

	def __state(self, jdict):
		state = {'state':'READY', 'css': 'grey', 'title': '' }
		if jdict['is_disabled']:
			state['state'] = "DISABLED"
			state['css'] = "blue"
			return state # no need to check status if disabled

		if jdict['is_running']:
			state['state'] = "RUNNING"
			state['css'] = "yellow"
		elif jdict['logs']['err'].strip()!='':
			state['state'] = "ERROR"
			state['css'] = "red"
			state['title'] = jdict['logs']['err'].strip().split("\n")[-1]
		elif jdict['logs']['end'] is not None and jdict['logs']['log'].strip()!='':
			state['state'] = "SUCCESS"
			state['css'] = "green"
		return state

	def __duration(self, jdict):
		duration = None
		if jdict['logs']['start'] is not None and jdict['logs']['end'] is not None:
			seconds = (jdict['logs']['end']-jdict['logs']['start']).seconds
			if seconds >= 60:
				minutes = seconds // 60
				seconds = seconds % 60
				duration = "{}:{} minutes".format(minutes, str(seconds).zfill(2))
			elif seconds==1:
				duration = "{} second".format(seconds)
			else:
				duration = "{} seconds".format(seconds)
		return duration

	def __timestr_to_12hr(self, tstr):
		d = dt.strptime(dt.now().strftime("%Y-%m-%d "+ str(tstr)), "%Y-%m-%d %H:%M")
		return d.strftime("%I:%M%p")


	def __scheduleTD(self, jdict):
		tz_str = ''
		if isinstance(jdict['tzname'], str):
			tz_str = dt.now(tz.gettz(jdict['tzname'])).strftime("[%Z]")

		if isinstance(jdict['every'], int): # jdict['type']=='RepeatJob'
			out = "every {} seconds {}".format(jdict['every'], tz_str)
			return TD(out.strip())

		elif jdict['type']=='OneTimeJob':
			out = "on {} at {} {}".format(jdict['every'], jdict['at'], tz_str)
			return TD(out.strip())

		elif jdict['type']=='NeverJob':
			out = 'on-demand'
			return TD(out)

		elif isinstance(jdict['at'], (list,set,tuple)):
			full_str = "every {} at {} {}".format(jdict['every'], ', '.join(jdict['at']), tz_str)

			if len(jdict['at']) >= 5:
				at_str = ', '.join(jdict['at'][:3]) + ', ...' + jdict['at'][-1]
				out = "every {} at {} {}".format(jdict['every'], at_str, tz_str)
				return TD(out.strip(), attrs={'title': full_str.strip()})
			else:
				return TD(full_str.strip())
		else:
			out = "every {} at {} {}".format(jdict['every'], jdict['at'], tz_str)
			return TD(out.strip())


	def __date_fmt(self, d):
		fallback = '-'+('&nbsp;'*30) # a hiphen and some html spaces
		return d.strftime("%Y-%m-%d %H:%M:%S %Z") if d is not None else fallback

	def __date_sort_attr(self, d):
		return {'data-sort': d.timestamp() if d is not None else 0}

	def __descrTD(self, d):
		if d is None: return TD('-')
		d = d.strip()
		short_d = d[:30] + "..."
		return TD(short_d if len(d)>30 else d, attrs={'title': d})

	def __src_err_line(self, j):
		if j['logs']['err'].strip()!='':
			for l in j['logs']['err'].strip().split("\n"):
				if l.strip():
					idx = j['src'].find(l.strip())
					if idx>=0:
						return j['src'][:idx].count("\n")
		return -1

	def __get_all_json(self):
		if len(self.sched.jobs)==0:
			return json.dumps({'error':'Nothing here'})
		else:
			return json.dumps({'success': [j.to_dict() for j in self.sched.jobs]}, default=str)

	def __get_summary_json(self):
		if len(self.sched.jobs)==0:
			return json.dumps({'error':'Nothing here'})
		else:
			details = []
			summary = {'count': 0, 'running': 0, 'errors': 0}
			for j in self.sched.jobs:
				jd = j.to_dict()
				state = self.__state(jd)
				summary['count'] += 1
				if state['state'] == "ERROR":
					summary['errors'] += 1
				elif state['state'] == 'RUNNING':
					summary['running'] += 1
				details.append({
					'id': jd['jobid'],
					'state': state['state'],
					'signature': jd['signature'],
					'prev_run': jd['logs']['start'],
					'next_run': jd['next_run'],
				})
			out = {'name': self._display_name, 'summary': summary, 'details': details}
			return json.dumps({'success': out}, default=str)

	def __get_one_json(self, n):
		j = self.sched.get_job_by_id(n)
		if j is None:
			return json.dumps({'error':'Invalid job id'})
		return json.dumps({'success': j.to_dict()}, default=str)

	def __show_all(self):
		if len(self.sched.jobs)==0:
			return 'Nothing here'
		d = []
		for j in self.sched.jobs:
			jd = j.to_dict()
			duration = self.__duration(jd)
			state = self.__state(jd)
			start_dt = jd['logs']['start']
			end_dt = jd['logs']['end']
			next_dt = jd['next_run']
			next_dt_str = ''
			if next_dt is None:
				if jd['is_disabled']:
					next_dt_str = 'Disabled'
				else:
					next_dt_str = 'Never'
			else:
				next_dt_str = self.__date_fmt(next_dt)

			d.append(OrderedDict({
				'Id': TD(jd['jobid']),
				'Name': TD(jd['func'].replace('<', '&lt;').replace('>', '&gt;'), attrs={'title':j.func_signature()}),
				'Schedule': self.__scheduleTD(jd),
				'Description': self.__descrTD(jd['doc']),
				'State': TD(state['state'], css=state['css'], attrs={'title': state['title']}),
				'Start': TD(self.__date_fmt(start_dt), attrs=self.__date_sort_attr(start_dt)),
				'End': TD(self.__date_fmt(end_dt), attrs=self.__date_sort_attr(end_dt)),
				'Time Taken': TD(duration),
				'Next Run': TD(next_dt_str, attrs=self.__date_sort_attr(next_dt)),
				'More':TD("<a href='/{}/{}'><button>show more</button><a>".format(self._endpoint, jd['jobid']))
			}))
		rows = [TR(row.values()) for row in d]
		head = [TH(th, default_sort=(th=="Next Run") ) for th in d[0].keys()]	# apply sorting to 'next run'
		all_jobs_table = TABLE(thead=THEAD(head), tbody=TBODY(rows), elem_id='all-jobs', css='all-jobs')
		refresh_text = SMALL(f"Auto-refresh in {SPAN(self._homepage_refresh, attrs={'id': 'refresh-msg'})} seconds")
		filter_input = INPUT("", attrs={'type':'text', 'placeholder':'Filter', 'id': 'filter-box'})

		js_auto_reload_variables = '''let COUNT_DOWN = {};'''.format(self._homepage_refresh)

		container = DIV(
			'\n'.join([
				H(2, "{} - Task Monitor".format(self._display_name)),
				SPAN("Running since {}".format(self._init_dt)),
				refresh_text,
				filter_input,
				all_jobs_table,
			]),
			css=["container", "container-vertical", 'center']
		)

		return self.__html_wrap(
			[
				self.__css_src_wrap('dark_theme.css'),
				self.__css_src_wrap('taskmonitor.css'),
				container,
				SCRIPT(js_auto_reload_variables),
				self.__js_src_wrap('taskmonitor.js')
			]
		)

	def __show_one(self, n):
		j = self.sched.get_job_by_id(n)
		if j is None:
			return 'Not found'
		jobd = j.to_dict()
		titleTD = lambda t: TD(t, css='title')
		state = self.__state(jobd)
		job_funcname = jobd['func'].replace('<', '&lt;').replace('>', '&gt;')

		enable_disable_btn = '''<button class="btn enable-disable-btn"
									onclick="enable_disable('{name}', {jobid}, {job_disable})"
									{btn_disabled}>
								{btn_name}
								</button>'''.format(
			name=job_funcname, jobid=n,
			job_disable="true" if not jobd['is_disabled'] else "false",
			btn_disabled="disabled" if state['state']=="RUNNING" else "",
			btn_name="Disable" if not jobd['is_disabled'] else "Enable",
		)
		rerun_btn = '''<button class="btn rerun-btn"
							onclick="rerun_trigger('{name}', {jobid})"
							{btn_disabled}>
						Rerun
						</button>'''.format(
			name=job_funcname, jobid=n, # rerun_trigger params
			btn_disabled="disabled" if state['state']=="RUNNING" or jobd['is_disabled'] else ""
		)
		rows = [
			TR([ titleTD("Schedule"), self.__scheduleTD(jobd), ]),
			TR([ titleTD("State"), TD(state['state'], css=state['css']) ]),
			TR([ titleTD("Start Time"), TD(self.__date_fmt(jobd['logs']['start'])) ]),
			TR([ titleTD("End Time"), TD(self.__date_fmt(jobd['logs']['end'])) ]),
			TR([ titleTD("Time Taken"), TD(self.__duration(jobd)) ]),
			TR([ titleTD("Next Run In"), TD("-", attrs={'id':'next-run-in'}) ]),
			TR([ TD(enable_disable_btn, colspan=2, css=['monitor-btn']) ]) if self._can_disable else '',
			TR([ TD(rerun_btn, colspan=2, css=['monitor-btn']) ]) if self._can_rerun else ''
		]

		info_table = TABLE(tbody=TBODY(rows), css='info_table')
		description_div = DIV( CODE(jobd['src'], css='python'), css=['console-color', 'console-div', 'brdr', 'monitor-code'])
		title = H(2, job_funcname, attrs={'title': j.func_signature()})
		monitor_div = DIV(
			title + info_table + description_div,
			css="monitor"
		)

		logs_row = TR([
			TD( DIV( CODE(jobd['logs']['log'], css='accesslog'), css='console-div'), css="console-color"),
			TD( DIV( CODE(jobd['logs']['err'], css='accesslog'), css='console-div'), css="console-color"),
		])
		logs_table = TABLE(thead=THEAD([TH('Logs'), TH('Traceback')]), tbody=TBODY(logs_row), css='log_table')
		logs_div = DIV( logs_table, css="logs_div" )

		container = DIV(
			monitor_div + logs_div,
			css="container"
		)

		next_run_ts = '"Never"'
		if jobd['is_disabled']:
			next_run_ts = '"Disabled"'
		elif jobd['next_run']:
			next_run_ts = jobd['next_run'].timestamp()

		variables_script = f'''
		let RUNNING = {int(jobd['is_running'])};
		let NEXT_RUN = {next_run_ts};
		let ERR_LINE = {self.__src_err_line(jobd)};
		let TASKPAGE_REFRESH = {self._taskpage_refresh};
		let API_TOKEN = '{self._api_protection_token}';
		'''

		return self.__html_wrap(
			[
				self.__css_src_wrap('dark_theme.css'),
				self.__css_src_wrap('taskmonitor.css'),
				container,
				SCRIPT(variables_script),
				self.__js_src_wrap('task.js')
			]
		)


	def __rerun_job(self):
		error = None
		data = json.loads(request.data)
		print("> rerun", data)
		if 'api_token' not in data or data['api_token']!=self._api_protection_token:
			error = 'Invalid token. Rerun blocked. Please reload the page and try again'

		elif 'jobid' not in data or not isinstance(data['jobid'], int):
			error = 'Invalid input'
		else:
			try:
				self.sched.rerun(data['jobid'])
			except Exception as e:
				error = str(e)

		if error is not None:
			return json.dumps({'error': error})
		else:
			return json.dumps({'success': True})


	def __enable_disable_job(self):
		error = None
		data = json.loads(request.data)
		print("> enable_disable", data)
		if 'api_token' not in data or data['api_token']!=self._api_protection_token:
			error = 'Action blocked'

		if 'jobid' not in data or not isinstance(data['jobid'], int):
			error = 'Invalid input'
		else:
			try:
				j = self.sched.get_job_by_id(data['jobid'])
				if j is None:
					raise ValueError("Job not found")
				if data['disable']==True:
					j.disable()
				else:
					j.enable()
			except Exception as e:
				error = str(e)

		if error is not None:
			return json.dumps({'error': error})
		else:
			return json.dumps({'success': True})
