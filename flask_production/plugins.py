
def HTML(content, title):
	return '''
	<!DOCTYPE html>
	<html lang="en">
		<head>
			<meta charset="UTF-8">
			<meta name="viewport" content="width=device-width, initial-scale=1.0">
			<link rel="stylesheet"
				href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/10.1.1/styles/monokai-sublime.min.css">
			<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/10.1.1/highlight.min.js"></script>
			<script src="https://cdn.jsdelivr.net/gh/TRSasasusu/highlightjs-highlight-lines.js@1.1.6/highlightjs-highlight-lines.min.js"></script>
			<script>
				hljs.configure({{languages: ['python', 'accesslog']}});
				hljs.initHighlightingOnLoad();
			</script>
			<title>{}</title>
		</head>
		<body>
			{}
		</body>
	</html>'''.format(title, str(content))

def H(index, content):
	return "<h{i}>{c}</h{i}>".format(c=content, i=index)

def DIV(content, css=[]):
	if not isinstance(css, (list,set,tuple)):
		css = [css]
	if css:
		return "<div class='{}'>{}</div>".format(' '.join(css), content)
	else:
		return "<div>{}</div>".format(content)

def TABLE(thead='', tbody='', css=[]):
	if not isinstance(css, (list,set,tuple)):
		css = [css]
	if css:
		return "<table class='{}'>{}{}</table>".format(' '.join(css), thead, tbody)
	else:
		return "<table>{}{}</table>".format(thead, tbody)

def THEAD(headers):
	th = ["<th>{}</th>".format(h) for h in headers]
	return "<thead>{}</thead>".format(''.join(th))

def TBODY(rows):
	return "<tbody>{}</tbody>".format(''.join(rows))

def TD(content, css=[], colspan=1, rowspan=1):
	if not isinstance(css, (list,set,tuple)):
		css = [css]
	return "<td class='{}' colspan={} rowspan={}>{}</td>".format(
		' '.join(css),
		colspan,
		rowspan,
		content if content is not None else "-"
	)

def TR(row):
	return "<tr>{}</tr>".format(''.join(row))

def SCRIPT(s):
	return "<script>{}</script>".format(s)

def CODE(s, css=[]):
	if not isinstance(css, (list,set,tuple)):
		css = [css]
	return "<pre><code class='{}'>{}</code></pre>".format(' '.join(css), s)



class ReadOnlyTaskMonitor(object):

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
			}
			*::-webkit-scrollbar {
				width: 11px;
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
			h2 { padding-top:10px;}
			table {
				border-spacing: 5px;
				border-collapse: collapse;
				border: 1px solid grey;
				width:85%;
				margin-top:20px;
			}
			td, th {
				border: 1px solid grey;
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
		</style>
		'''

	def __init__(self, app, sched, display_name=None, endpoint="@taskmonitor", homepage_refresh=30):
		self.app = app
		self.sched = sched
		self._endpoint = endpoint
		self._display_name = display_name or self.app.name
		self._homepage_refresh = homepage_refresh
		self.create_endpoints()

	def create_endpoints(self):
		self.app.add_url_rule("/{}".format(self._endpoint), view_func=self.__show_all, methods=['GET'])
		self.app.add_url_rule("/{}/<int:n>".format(self._endpoint), view_func=self.__show_one, methods=['GET'])

	def __html_wrap(self, *args):
		return HTML(''.join(args), title="{} Task Monitor".format(self._display_name))

	def __state(self, jdict):
		state = 'READY'
		if jdict['is_running']:
			state = "RUNNING"
		elif jdict['logs']['err'].strip()!='':
			state = "ERROR"
		elif jdict['logs']['end'] is not None and jdict['logs']['log'].strip()!='':
			state = "SUCCESS"
		return state

	def __state_css(self, state):
		css = []
		if state=="READY":
			css = 'grey'
		elif state=="RUNNING":
			css = 'yellow'
		elif state=="ERROR":
			css = 'red'
		elif state=="SUCCESS":
			css = 'green'
		return css

	def __duration(self, jdict):
		duration = None
		if jdict['logs']['start'] is not None and jdict['logs']['end'] is not None:
			seconds = (jdict['logs']['end']-jdict['logs']['start']).seconds
			if seconds >= 60:
				minutes = seconds // 60
				seconds = seconds % 60
				duration = "{}:{} minutes".format(minutes, seconds)
			elif seconds==1:
				duration = "{} second".format(seconds)
			else:
				duration = "{} seconds".format(seconds)
		return duration

	def __schedule_str(self, jdict):
		return "every {} seconds".format(jdict['every']) if isinstance(jdict['every'], int) else "every {} at {}".format(jdict['every'], jdict['at'])

	def __date_fmt(self, d):
		return d.strftime("%Y-%m-%d %H:%M:%S") if d is not None else '-'+('&nbsp;'*30)

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

	def __show_all(self):
		if len(self.sched.jobs)==0:
			return 'Nothing here'
		d = []
		for i,j in enumerate(self.sched.jobs):
			jd = j.to_dict()
			duration = self.__duration(jd)
			state = self.__state(jd)
			d.append({
				'Id': TD(i),
				'Name': TD(jd['func'].replace('<', '&lt;').replace('>', '&gt;')),
				'Schedule': TD(self.__schedule_str(jd)),
				'Description': self.__descrTD(jd['doc']),
				'State': TD(state, css=self.__state_css(state)),
				'Start': TD(self.__date_fmt(jd['logs']['start'])),
				'End': TD(self.__date_fmt(jd['logs']['end'])),
				'Time Taken': TD(duration),
				'Next Run': TD(jd['next_run']),
				'More':TD("<a href='/{}/{}'><button>show more</button><a>".format(self._endpoint, i))
			})
		rows = [TR(row.values()) for row in d]
		all_jobs_table = TABLE(thead=THEAD(d[0].keys()), tbody=TBODY(rows))

		auto_reload_script = '''
		window.addEventListener('load', (event) => {{
			setTimeout(()=>location.reload(), {}000)
		}})
		'''.format(self._homepage_refresh)
		return self.__html_wrap(
			self.STYLES,
			H(2, "{} - Task Monitor".format(self._display_name)),
			all_jobs_table,
			SCRIPT(auto_reload_script)
		)

	def __show_one(self, n):
		if n>=len(self.sched.jobs):
			return 'Nothing here'
		jobd = self.sched.jobs[n].to_dict()
		titleTD = lambda t: TD(t, 'title')
		state = self.__state(jobd)

		rows = [
			TR([ titleTD("Schedule"), TD(self.__schedule_str(jobd)), ]),
			TR([ titleTD("State"), TD(state, self.__state_css(state)) ]),
			TR([ titleTD("Start Time"), TD(self.__date_fmt(jobd['logs']['start'])) ]),
			TR([ titleTD("End Time"), TD(self.__date_fmt(jobd['logs']['end'])) ]),
			TR([ titleTD("Time Taken"), TD(self.__duration(jobd)) ]),
			TR([ titleTD("Next Run In"), "<td id='next-run-in'>-<td>" ]),
		]
		info_table = TABLE(tbody=TBODY(rows), css='info_table')
		description_div = DIV( CODE(jobd['src'], css='python'), css=['console-color ', 'console-div', 'brdr'])
		job_funcname = jobd['func'].replace('<', '&lt;').replace('>', '&gt;')
		monitor_div = DIV(
			H(2, job_funcname) + info_table + description_div,
			css="monitor"
		)

		logs_row = TR([
			TD( DIV( CODE(jobd['logs']['log'], css='accesslog'), css='console-div'), css="console-color"),
			TD( DIV( CODE(jobd['logs']['err'], css='accesslog'), css='console-div'), css="console-color"),
		])
		logs_table = TABLE(thead=THEAD(['Logs', 'Traceback']), tbody=TBODY(logs_row), css='log_table')
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
		let next_run = Date.parse("{next_run}")
		let err_line = {err_line}
		function countdown_str(seconds) {{
			let hours = Math.floor(seconds / (60*60))
			seconds -= hours * (60*60)
			let minutes = Math.floor(seconds / 60)
			seconds -= minutes * 60
			return `${{hours.pad()}}:${{minutes.pad()}}:${{Math.floor(seconds).pad()}}`
		}}
		window.addEventListener('load', (event) => {{
			//scroll to bottom
			document.getElementsByClassName("log_table")[0].querySelectorAll("div").forEach(d=>d.scrollTo(0,d.scrollHeight))
			if (running) {{
				setTimeout(()=>location.reload(), 3000)
			}} else if ( isNaN(next_run) ) {{
				document.getElementById("next-run-in").innerHTML = 'Never'
			}} else {{
				setInterval(()=>{{
					let ttr = next_run-Date.now()
					if (ttr<=0) {{
						location.reload()
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
			next_run=jobd['next_run'],
			err_line=self.__src_err_line(jobd)
		)

		return self.__html_wrap(
			self.STYLES,
			container,
			SCRIPT(auto_reload_script)
		)
