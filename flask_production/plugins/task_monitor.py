from datetime import datetime as dt
from dateutil import tz
from collections import OrderedDict
from flask import request
import json

from .html_templates import * # pylint: disable=unused-wildcard-import


STYLES = '''
<style>
	html {
		--console-bg: #333333;
		--thumb-bg: grey;
	}
	body {
		width:100%;
		height:100%;
		margin: 0;
		display:flex;
		flex-direction:column;
		align-items:center;
		font-family: sans-serif;
		font-size: 14px;
	}
	*::-webkit-scrollbar {
		width: 14px !important;
		height: 14px !important;
	}
	* {
		scrollbar-width: thin;
		scrollbar-color: var(--thumb-bg) var(--console-bg);
	}
	*::-webkit-scrollbar-track {
		background: var(--console-bg);
	}
	*::-webkit-scrollbar-thumb {
		background-color: var(--thumb-bg) ;
		border-radius: 6px;
		border: 3px solid var(--console-bg);
	}
	*::-webkit-scrollbar-corner {
		background-color: var(--console-bg) ;
	}
	th[role=columnheader]:not(.no-sort) { /*tablesort.css*/
		cursor: pointer;
	}
	th[role=columnheader]:not(.no-sort):after { /*tablesort.css*/
		content: '';
		float: right;
		margin-top: 7px;
		border-width: 4px 4px 0;
		border-style: solid;
		border-color: #e3e3e3 transparent;
		visibility: hidden;
		-ms-user-select: none;
		-webkit-user-select: none;
		-moz-user-select: none;
		user-select: none;
	}
	th[aria-sort=ascending]:not(.no-sort):after { /*tablesort.css*/
		border-width: 0 4px 4px;
	}
	th[aria-sort]:not(.no-sort):after { /*tablesort.css*/
		visibility: visible;
	}
	small, h2 { padding-top:10px;}
	table {
		border-spacing: 5px;
		border-collapse: collapse;
		border: 1px solid #c2c2c2;
		width:85%;
		margin-top:20px;
		margin-bottom:40px;
	}
	tr:hover { background-color: #ededed; }
	td, th {
		border: 1px solid #d1d1d1;
		padding: 5px;
	}
	th {
		height:2vh;
		background-color:var(--console-bg);
		color:white;
	}
	td.grey {color:#c2c2c2;}
	td.yellow {background-color:yellow;}
	td.green {
		background-color:#d2ffcc;
		color:green;
	}
	td.red {
		background-color:red;
		color:white;
		font-weight:bold;
	}
	tr.row-hidden { display:none; }
	a > button {
		width:100%;
		height:100%;
		cursor:pointer;
	}
	.container {
		width:100%;
		height:100%;
		display:flex;
		flex-direction:row;
	}
	.center {
		justify-content:center;
		align-items:center;
	}
	.rerun-btn {
		cursor: pointer;
	}
	.rerun-btn:disabled,.rerun-btn[disabled] {
		cursor: not-allowed;
	}
	.monitor {
		width: 30vw;
		height: 100vh;
		display:flex;
		flex-flow: column;
		align-items:center;
	}
	.monitor > div {
		flex: 1 1 auto;
		width:100%;
		overflow-wrap: break-word;
	}
	.info_table {
		border:none;
		margin-bottom:30px;
		width:100%;
	}
	.info_table td {
		border:none;
		width:50%;
		text-align:left;
	}
	td.title {
		font-weight:bold;
		text-align:right !important;
		padding-right:20px;
	}
	.logs_div {
		width: 70vw;
		height: 100vh;
		display:flex;
		align-items:center;
		justify-content:center;
	}
	.log_table {
		table-layout:fixed;
		width:100%;
		height:100%;
		margin-top:0px;
		margin-bottom:0px;
		overflow:hidden;
	}
	.log_table td, .log_table th {
		border:none;
		border-left: 1px solid grey;
		vertical-align: top;
		overflow:hidden;
	}
	.console-div {
		width:100%;
		top:0px;
		bottom:0px;
		height:95vh;
		overflow:scroll;
		white-space: nowrap;
		list-style-type: none;
		font-size: 13px;
		padding-left: 5px;
	}
	.console-color {
		background-color:var(--console-bg);
		color:white;
	}
	.brdr {border: 1px solid grey;}
	pre, code {
		background-color:transparent !important;
		overflow:visible !important;
	}
	input[type=text] {
		width: 250px;
		padding: 6px 15px;
		margin: 8px 0;
		border: 1px solid #999;
		border-radius: 3px;
		outline: none;
	}
</style>
'''

class TaskMonitor(object):

	def __init__(self, app, sched, display_name=None, endpoint="@taskmonitor", homepage_refresh=30, taskpage_refresh=5):
		self.tzname = sched._tz_default
		self._init_dt = dt.now(tz.gettz(self.tzname)).strftime("%m/%d/%Y %I:%M %p %Z") # preformatted start time
		self.app = app
		self.sched = sched
		self._endpoint = endpoint
		self._display_name = display_name or self.app.name
		self._homepage_refresh = homepage_refresh
		self._taskpage_refresh = taskpage_refresh
		self.app.add_url_rule("/{}".format(self._endpoint), view_func=self.__show_all, methods=['GET'])
		self.app.add_url_rule("/{}/<int:n>".format(self._endpoint), view_func=self.__show_one, methods=['GET'])
		self.app.add_url_rule("/{}/rerun".format(self._endpoint), view_func=self.__rerun_job, methods=['POST'])
		self.app.add_url_rule("/{}/json/all".format(self._endpoint), view_func=self.__get_all_json, methods=['GET'])
		self.app.add_url_rule("/{}/json/summary".format(self._endpoint), view_func=self.__get_summary_json, methods=['GET'])
		self.app.add_url_rule("/{}/json/<int:n>".format(self._endpoint), view_func=self.__get_one_json, methods=['GET'])

	def __html_wrap(self, *args):
		return HTML(''.join(args), title="{} Task Monitor".format(self._display_name))

	def __state(self, jdict):
		state = {'state':'READY', 'css': 'grey', 'title': '' }
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

	def __schedule_str(self, jdict):
		if isinstance(jdict['every'], int): # jdict['type']=='RepeatJob'
			out = "every {} seconds".format(jdict['every'])
		elif jdict['type']=='OneTimeJob':
			out = "on {} at {}".format(jdict['every'], jdict['at'])
		elif jdict['type']=='NeverJob':
			out = 'on-demand'
		elif isinstance(jdict['at'], (list,set,tuple)):
			out = "every {} at {}".format(jdict['every'], ', '.join(jdict['at']))
		else:
			out = "every {} at {}".format(jdict['every'], jdict['at'])

		if isinstance(jdict['tzname'], str):
			out += " " + dt.now(tz.gettz(jdict['tzname'])).strftime("[%Z]")
		return out

	def __date_fmt(self, d, fallback=None):
		fallback = fallback or '-'+('&nbsp;'*30) # a hiphen and some html spaces
		return d.strftime("%Y-%m-%d %H:%M:%S %Z") if d is not None else fallback

	def __date_sort_attr(self, d):
		return {'data-sort': d.timestamp() if d is not None else 0}

	def __descrTD(self, d):
		if d is None: return TD('-')
		d = d.strip()
		short_d = d[:30] + "..."
		return '<td title="{}">{}</td>'.format(
			d,
			short_d if len(d)>30 else d
		)

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
			summary = {'count': 0, 'errors': 0}
			for j in self.sched.jobs:
				jd = j.to_dict()
				state = self.__state(jd)
				summary['count'] += 1
				if state['state'] == "ERROR":
					summary['errors'] += 1
				details.append({
					'id': jd['jobid'],
					'state': state['state'],
					'signature': jd['signature']
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
		table_id = 'all-jobs'
		for j in self.sched.jobs:
			jd = j.to_dict()
			duration = self.__duration(jd)
			state = self.__state(jd)
			start_dt = jd['logs']['start']
			end_dt = jd['logs']['end']
			next_dt = jd['next_run']
			d.append(OrderedDict({
				'Id': TD(jd['jobid']),
				'Name': TD(jd['func'].replace('<', '&lt;').replace('>', '&gt;'), attrs={'title':j.func_signature()}),
				'Schedule': TD(self.__schedule_str(jd)),
				'Description': self.__descrTD(jd['doc']),
				'State': TD(state['state'], css=state['css'], attrs={'title': state['title']}),
				'Start': TD(self.__date_fmt(start_dt), attrs=self.__date_sort_attr(start_dt)),
				'End': TD(self.__date_fmt(end_dt), attrs=self.__date_sort_attr(end_dt)),
				'Time Taken': TD(duration),
				'Next Run': TD(self.__date_fmt(next_dt, "Never"), attrs=self.__date_sort_attr(next_dt)),
				'More':TD("<a href='/{}/{}'><button>show more</button><a>".format(self._endpoint, jd['jobid']))
			}))
		rows = [TR(row.values()) for row in d]
		head = [TH(th, default_sort=(th=="Next Run") ) for th in d[0].keys()]	# apply sorting to 'next run'
		all_jobs_table = TABLE(thead=THEAD(head), tbody=TBODY(rows), elem_id=table_id)
		rerun_txt = SMALL(f"Auto-refresh in {SPAN(self._homepage_refresh, attrs={'id': 'refresh-msg'})} seconds")
		filter_input = INPUT("", attrs={'type':'text', 'placeholder':'Filter', 'id': 'filter-box'})

		js_auto_reload_variables = '''
		new Tablesort(document.getElementById('{}'));
		let COUNT_DOWN = {};
		'''.format(table_id, self._homepage_refresh)

		js_functions = '''
		const table = document.getElementById("all-jobs")
		const filter_box = document.getElementById("filter-box");
		const tf = new TableFilter(table, filter_box)

		window.addEventListener('load', (event) => {
			const timer = setInterval(()=>{
				if (COUNT_DOWN > 0) {
					COUNT_DOWN --
					document.getElementById('refresh-msg').innerText = COUNT_DOWN
				} else {
					clearInterval(timer)
					location.reload()
				}
			}, 1000)
		})
		'''

		return self.__html_wrap(
			STYLES,
			H(2, "{} - Task Monitor".format(self._display_name)),
			SPAN("Running since {}".format(self._init_dt)),
			rerun_txt,
			filter_input,
			all_jobs_table,
			SCRIPT(js_auto_reload_variables + js_functions),
		)

	def __show_one(self, n):
		j = self.sched.get_job_by_id(n)
		if j is None:
			return 'Not found'
		jobd = j.to_dict()
		titleTD = lambda t: TD(t, css='title')
		state = self.__state(jobd)
		job_funcname = jobd['func'].replace('<', '&lt;').replace('>', '&gt;')

		rerun_btn = '''<button class="rerun-btn" onclick="{}" {}>Rerun</button>'''.format(
			'''rerun_trigger('{}', {})'''.format(job_funcname, n),
			"disabled" if state['state']=="RUNNING" else ""
		)
		rows = [
			TR([ titleTD("Schedule"), TD(self.__schedule_str(jobd)), ]),
			TR([ titleTD("State"), TD(state['state'], css=state['css']) ]),
			TR([ titleTD("Start Time"), TD(self.__date_fmt(jobd['logs']['start'])) ]),
			TR([ titleTD("End Time"), TD(self.__date_fmt(jobd['logs']['end'])) ]),
			TR([ titleTD("Time Taken"), TD(self.__duration(jobd)) ]),
			TR([ titleTD("Next Run In"), "<td id='next-run-in'>-<td>" ]),
			TR([ TD(rerun_btn, colspan=2, attrs={'style':'text-align:center'}) ])
		]

		info_table = TABLE(tbody=TBODY(rows), css='info_table')
		description_div = DIV( CODE(jobd['src'], css='python'), css=['console-color ', 'console-div', 'brdr'])
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
		auto_reload_script = '''
		Number.prototype.pad = function(size) {{
			let s = String(this);
			while (s.length < (size || 2)) {{s = "0" + s;}}
			return s;
		}}
		let running = {is_running}
		let next_run = {next_run_ts} * 1000 //ms
		let err_line = {err_line}
		function countdown_str(seconds) {{
			let hours = Math.floor(seconds / (60*60))
			seconds -= hours * (60*60)
			let minutes = Math.floor(seconds / 60)
			seconds -= minutes * 60
			return `${{hours.pad()}}:${{minutes.pad()}}:${{Math.floor(seconds).pad()}}`
		}}
		function rerun_trigger(job_name, jobid) {{
			let input_txt = prompt("Please type in the job name to confirm rerun", "");
			console.log(jobid)
			if (input_txt===job_name) {{
				fetch('./rerun', {{method: 'POST', body: JSON.stringify({{jobid}})}}).then(resp => {{
					return resp.json();
				}}).then(j=>{{
					if (j.success)
						window.location.reload()
					else if (j.error)
						throw Error(j.error)
					else
						throw Error("Rerun failed")
				}}).catch(e=>alert(e))
			}} else {{
				alert("Rerun aborted")
			}}
		}}
		window.addEventListener('load', (event) => {{
			//scroll to bottom
			document.getElementsByClassName("log_table")[0].querySelectorAll("div").forEach(d=>d.scrollTo(0,d.scrollHeight))
			if (running) {{
				setTimeout(()=>location.reload(), {taskpage_refresh}000)
			}} else if ( isNaN(next_run) ) {{ // if not number
				document.getElementById("next-run-in").innerHTML = next_run
			}} else {{
				const timer = setInterval(()=>{{
					let ttr = next_run-Date.now()
					if (ttr<=0) {{
						clearInterval(timer)
						setTimeout(()=>location.reload(), 1000) // small timeout to avoid too many reloads
					}} else {{
						document.getElementById("next-run-in").innerHTML = countdown_str(ttr/1000)
					}}
				}}, 1000)
			}}
			//highlight error line
			if (err_line>=0) {{
				hljs.initHighlightLinesOnLoad([
					[{{start: err_line, end: err_line, color: 'rgba(255, 0, 0, 0.4)'}}], // Highlight some lines in the first code block.
				]);
			}}
		}});
		'''.format(
			is_running=int(jobd['is_running']),
			next_run_ts=jobd['next_run'].timestamp() if jobd['next_run'] else '"Never"',
			err_line=self.__src_err_line(jobd),
			taskpage_refresh=self._taskpage_refresh
		)

		return self.__html_wrap(
			STYLES,
			container,
			SCRIPT(auto_reload_script)
		)


	def __rerun_job(self):
		error = None
		data = json.loads(request.data)
		if 'jobid' not in data or not isinstance(data['jobid'], int):
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
