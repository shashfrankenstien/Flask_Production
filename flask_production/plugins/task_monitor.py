from datetime import datetime as dt, date
from collections import OrderedDict
from enum import Enum
import json
import random
import string
import inspect

from dateutil import tz
from flask import Flask, Blueprint, request, send_file, redirect


from .html_templates import * # pylint: disable=unused-wildcard-import
from ..sched import TaskScheduler
from ..script_func import ScriptFunc


class TaskMonitor:
	'''
	Web interface to monitor and manage tasks

	- app (`Flask`): Flask application object
	- sched (`TaskScheduler`): task scheduler with task definitions
	- display_name (`str`): name of the application to be displayed
		- default app.name
	- endpoint (`str`): URL endpoint where the taskmonitor can be viewed
		- default "@taskmonitor"
	- homepage_refresh (`int`): home page auto refresh interval (in seconds)
		- default 30
	- taskpage_refresh (`int`): task page auto refresh interval (in seconds)
		- default 5
	- can_rerun (`bool`): if True adds `rerun` button to job page
		- default True
	- can_disable (`bool`): if True adds `disable` button to job page
		- default True
	- enhanced_rerun (`bool`): if True enables enhanced rerun feature with ability to edit function arguments
		- default False
	'''
	def __init__(self,
		app:Flask,
		sched:TaskScheduler,
		display_name=None,
		endpoint="@taskmonitor",
		homepage_refresh=30,
		taskpage_refresh=5,
		can_rerun=True, # adds rerun button to job page
		can_disable=True, # adds disable button to job page
		enhanced_rerun=True, # set False to disable enhanced rerun feature with ability to edit function arguments
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
		self._enhanced_rerun = enhanced_rerun

		bp = Blueprint('taskmonitor_bp', __name__, url_prefix=f"/{self._endpoint}")

		bp.add_url_rule("", view_func=lambda: redirect(request.path+"/", code=301) , methods=['GET']) # redirect to "/" because we need the browser to treat this endpoint as a folder
		bp.add_url_rule("/", view_func=self.__show_all, methods=['GET'])
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

	@property
	def title(self):
		return "{} Task Monitor".format(self._display_name)

	def __js_src_wrap(self, filename):
		return SCRIPT_SRC(f'./static/js/{filename}') # use relating url

	def __css_src_wrap(self, filename):
		return STYLESHEET(f'./static/css/{filename}') # use relating url

	def __serve_file(self, type, filename):
		if 'max_age' in inspect.getfullargspec(send_file).args:
			return send_file(os.path.join(WEB_FOLDER, type, filename), max_age=86400)
		else:
			return send_file(os.path.join(WEB_FOLDER, type, filename), cache_timeout=86400)


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

	def __duration_sort_attr(self, jdict):
		if jdict['logs']['start'] is not None and jdict['logs']['end'] is not None:
			# Calculate total seconds for the data-sort attribute
			delta = (jdict['logs']['end'] - jdict['logs']['start']).total_seconds()
			return {'data-sort': delta}
		return {'data-sort': 0}

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
				'Time Taken': TD(duration, attrs=self.__duration_sort_attr(jd)),
				'Next Run': TD(next_dt_str, attrs=self.__date_sort_attr(next_dt)),
				'More':TD("<a href='./{}'><button>show more</button><a>".format(jd['jobid'])) # use relating url
			}))
		rows = [TR(row.values()) for row in d]
		head = [TH(th, default_sort=(th=="Next Run") ) for th in d[0].keys()]	# apply sorting to 'next run'
		all_jobs_table = TABLE(thead=THEAD(head), tbody=TBODY(rows), elem_id='all-jobs', css='all-jobs')
		refresh_text = SMALL(f"Auto-refresh in {SPAN(self._homepage_refresh, attrs={'id': 'refresh-msg'})} seconds")
		filter_input = INPUT(attrs={'type':'text', 'placeholder':'Filter', 'id': 'filter-box'})

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

		return HTML(
			title=self.title,
			stylesheets=[
				self.__css_src_wrap('dark_theme.css'),
				self.__css_src_wrap('taskmonitor.css'),
			],
			body=[
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

		# should we use BUTTON template function? Maybe raw string is easier here
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
		# should we use BUTTON template function? Maybe raw string is easier here
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
			TD( DIV( CODE(html_escape(jobd['logs']['log']), css='accesslog'), css='console-div'), css="console-color"),
			TD( DIV( CODE(html_escape(jobd['logs']['err']), css='accesslog'), css='console-div'), css="console-color"),
		])
		logs_table = TABLE(thead=THEAD([TH('Logs'), TH('Traceback')]), tbody=TBODY(logs_row), css='log_table')
		logs_div = DIV( logs_table, css="logs_div" )

		container = DIV(
			monitor_div + logs_div + self._create_rerun_popup_html(j.func, j.kwargs),
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
		let SCHED_HAS_CHECKED = {'true' if self.sched.has_checked() else 'false'};
		'''

		return HTML(
			title=self.title,
			stylesheets=[
				self.__css_src_wrap('dark_theme.css'),
				self.__css_src_wrap('taskmonitor.css'),
				self.__css_src_wrap('rerun_popup.css'),
			],
			body=[
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

		elif 'jobid' not in data or not isinstance(data['jobid'], int) or (_job := self.sched.get_job_by_id(data['jobid'])) is None:
			error = 'Invalid job'
		else:
			kwargs = data.get('kwargs') or {}
			types = data.get('types') or {}
			# Convert kwargs based on types
			for k, v in kwargs.items():
				typ = types.get(k)
				try:
					if typ == 'none':
						kwargs[k] = None
					elif typ == 'bool':
						kwargs[k] = v.lower() == 'true'
					elif typ == 'int':
						kwargs[k] = int(v)
					elif typ == 'float':
						kwargs[k] = float(v)
					elif typ == 'datetime':
						kwargs[k] = dt.fromisoformat(v)
					elif typ == 'date':
						kwargs[k] = date.fromisoformat(v)

					elif str(typ).endswith('<enum>'):
						# for custom enum types, we need to get the enum class either from function annotation or kwarg value
						# j = self.sched.get_job_by_id(data['jobid'])
						argspec = inspect.getfullargspec(_job.func)
						_class = argspec.annotations.get(k)
						if not _class:
							val = _job.kwargs.get(k)
							if issubclass(type(val), Enum):
								_class = type(val)
						if not _class:
							total_args = len(argspec.args)
							total_with_defaults = len(argspec.defaults) if argspec.defaults else 0
							i = argspec.args.index(k)
							if i >= total_args - total_with_defaults:
								default = argspec.defaults[i - (total_args - total_with_defaults)]
								if issubclass(type(default), Enum):
									_class = type(default)
						if not _class:
							raise ValueError(f"Bad type for {k}")

						kwargs[k] = _class[v]
					# else keep as string
				except Exception as e:
					error = f"DataType error {k} ({typ}) - {str(e)}"

			if error is None:
				try:
					self.sched.rerun(data['jobid'], kwargs=kwargs)
				except Exception as e:
					error = f"Task rerun error - {str(e)}"

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

		elif 'jobid' not in data or not isinstance(data['jobid'], int):
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



	#

	def _create_rerun_popup_html(self, func:object, input_kwargs:dict) -> str:
		'''
		This function will check types and create appropriate HTML input fields to allow for accurate changes
		- we assign current values to 'data-key' and 'data-value' to the input container.
			these are checked js to flag that an argument has changed
		- None value arguments are handled by checkbox
		- see __rerun_job() where types are converted back to python
		'''

		header = H(3, "Rerun task")
		body_section = ''

		if self._enhanced_rerun:
			argspec = inspect.getfullargspec(func)
			total_args = len(argspec.args)
			total_with_defaults = len(argspec.defaults) if argspec.defaults else 0

			kwargs_options = '' # default value

			for i, name in enumerate(argspec.args):
				if name == 'self' and isinstance(func, ScriptFunc):
					continue # ScriptFunc is a callable class. __call__ function takes 'self' as argument which we don't care about here

				annot = argspec.annotations.get(name)
				value_exists = False
				value = None
				default_exists = False
				default = None
				if name in input_kwargs:
					value = input_kwargs[name]
					value_exists = True

				if i >= total_args - total_with_defaults:
					default = argspec.defaults[i - (total_args - total_with_defaults)]
					default_exists = True
					if not value_exists:
						value = default

				def _value_isinstance(type_or_tuple):
					'''
					check both type of value and default value
					- in cases where annotations is not provided and input value is set to None,
						we try to get the type info from default value in func definition when default_exists is True
					'''
					return isinstance(value, type_or_tuple) or (default_exists and isinstance(default, type_or_tuple))

				inp_attrs = {
					'type': 'text',
					'title': str(name),
					'value': str(value),
				}
				orig_kwarg_attr = {
					'data-key': name,
					'data-value': value
				}

				bool_select = None
				if annot==str or _value_isinstance(str):
					inp_attrs['type'] = 'text'
					orig_kwarg_attr['data-type'] = 'str'

				elif annot==dt or _value_isinstance(dt): # check datetime before date as true datetime objects will wrongly match date
					inp_attrs['type'] = 'datetime-local'
					inp_attrs['value'] = value.isoformat(timespec="seconds") if value is not None else ''
					orig_kwarg_attr['data-value'] = value.isoformat(timespec="seconds") if value is not None else '' # maintain the same formatting
					orig_kwarg_attr['data-type'] = 'datetime'

				elif annot==date or _value_isinstance(date):
					inp_attrs['type'] = 'date'
					inp_attrs['value'] = value.strftime("%Y-%m-%d") if value is not None else ''
					orig_kwarg_attr['data-value'] = value.strftime("%Y-%m-%d") if value is not None else '' # maintain the same formatting
					orig_kwarg_attr['data-type'] = 'date'

				elif annot==bool or _value_isinstance(bool): # check bool before int as boolean objects will wrongly match int
					true_option_attrs = {'value': 'true'}
					false_option_attrs = {'value': 'false'}
					none_option_attrs = {'value': '', 'disabled': 'disabled', 'hidden':'hidden'}
					if value is True:
						true_option_attrs['selected'] = 'selected'
						orig_kwarg_attr['data-value'] = 'true'
					elif value is False:
						false_option_attrs['selected'] = 'selected'
						orig_kwarg_attr['data-value'] = 'false'
					else:
						none_option_attrs['selected'] = 'selected'
						orig_kwarg_attr['data-value'] = 'none'
					bool_options = [
						OPTION('', attrs=none_option_attrs),
						OPTION('True', attrs=true_option_attrs),
						OPTION('False', attrs=false_option_attrs),
					]
					bool_select = SELECT(bool_options, css=['rerun-bool-select'], attrs={'title': f"{name} (bool)"})
					orig_kwarg_attr['data-type'] = 'bool'

				# we will force int type only if explicitly annotated as int.
				# else numbers will be treated as float for convenience of datatype inference
				elif annot == int:
					# inp_attrs['type'] = 'text' # default
					inp_attrs["inputmode"] = "numeric"
					inp_attrs["pattern"] = "[0-9]*"
					inp_attrs["oninput"] = r"this.value = this.value.replace(/[^0-9]/g, '');"
					orig_kwarg_attr['data-type'] = 'int'

				elif annot == float or _value_isinstance((int,float)):
					# inp_attrs['type'] = 'text' # default
					inp_attrs["inputmode"] = "decimal"
					inp_attrs["oninput"] = r"this.value = this.value.replace(/[^0-9.]/g, '').replace(/(\..*)\./g, '$1');"
					orig_kwarg_attr['data-type'] = 'float'

				elif annot and issubclass(annot, Enum) or _value_isinstance(Enum):
					if annot and issubclass(annot, Enum):
						enum_cls = annot
					else:
						enum_cls = type(default) if default_exists else type(value)

					options = [OPTION('', attrs={'value': '', 'disabled': 'disabled', 'selected': 'selected', 'hidden':'hidden'})]
					for k,v in enum_cls.__members__.items():
						attrs = {'value': v.name}
						if v == value:
							attrs['selected'] = 'selected'
						options.append(OPTION(k, attrs=attrs))

					bool_select = SELECT(options, css=['rerun-bool-select'], attrs={'title': f"{name} ({enum_cls})"})
					orig_kwarg_attr['data-type'] = f"{enum_cls.__name__}<enum>"
					orig_kwarg_attr['data-value'] = value.name if value is not None else None

				else:
					inp_attrs['disabled'] = 'disabled'

				if 'data-type' in orig_kwarg_attr:
					inp_attrs['title'] += f" ({orig_kwarg_attr['data-type']})"
				else:
					inp_attrs['title'] += f" (not editable)"

				none_attr = {'title': "Set value to python 'None'"}
				if value is None:
					none_attr['data-none'] = '1'
					none_attr['data-orig-none'] = '1'

				input_field = bool_select if bool_select else INPUT(attrs=inp_attrs)

				opt = DIV(
					content=SPAN(name) + input_field + BUTTON("None", css=['btn', 'none-btn'], attrs=none_attr),
					css=['rerun-kwarg'],
					attrs=orig_kwarg_attr
				)
				kwargs_options += opt


			if not kwargs_options:
				kwargs_options = 'This job takes no arguments' # fallback value

			body_section = DIV(
				kwargs_options,
				css=['rerun-kwargs-set']
			)

			header += '<p>Update arguments (optional) and confirm rerun by typing the job name</p>'


		header_section = DIV(
			content=header,
			css=[]
		)

		job_name_input = INPUT(attrs={
			'id': 'popup-rerun-prompt',
			'type':"text",
			'placeholder': 'Please type in the job name to confirm rerun'
		})

		rerun_btn = BUTTON("Rerun", css=['btn'], attrs={'id': 'popup-rerun-btn'}) # action will be assigned by js
		cancel_btn = BUTTON("Cancel", css=['btn'], attrs={'id': 'popup-cancel-btn'}) # action will be assigned by js

		rerun_section = DIV(
			job_name_input + rerun_btn + cancel_btn,
			css=['rerun-exec']
		)

		return DIV(
			content=header_section + body_section + rerun_section,
			css=['console-color', 'rerun-popup'],
			attrs={'id': "rerun-popup", 'style': 'display: none; width: 100%; height: 100%;'},
		)
