import os
ROOT = os.path.dirname(os.path.realpath(__file__))
WEB_FOLDER = os.path.join(ROOT, 'web')

# expose package version to templates
try:
	from flask_production import __version__ as PACKAGE_VERSION
except Exception:
	PACKAGE_VERSION = ''


def _readTemplate(fileName, **kwargs):
	with open(fileName, 'r') as f:
		templateText = f.read()
	for arg in kwargs:
		templateText = templateText.replace("{{ "+arg+" }}", str(kwargs[arg]))
	return templateText

def html_escape(text):
	'''replace < and > with &lt; and &gt;'''
	return text.replace("<", "&lt;").replace(">", "&gt;")


def HTML(title:str, stylesheets:list, body:list, body_css:list=None):
	body_css = body_css or []
	if not isinstance(body_css, (list,set,tuple)):
		body_css = [body_css]
	return _readTemplate(os.path.join(WEB_FOLDER, 'index.html'),
		title=title,
		stylesheets='\n'.join(stylesheets),
		body='\n'.join(body),
		body_css=' '.join(body_css),
		version=f"fp v{PACKAGE_VERSION}"
	)

def _TAG(tag, content, css:list, attrs:dict):
	css = css or []
	attrs = attrs or {}
	attrs = ['''{}="{}"'''.format(k,v) for k,v in attrs.items()]
	if not isinstance(css, (list,set,tuple)):
		css = [css]
	if css:
		attrs.append('''class="{}"'''.format(' '.join(css)))
	return "<{t} {a}>{c}</{t}>".format(t=tag, a=' '.join(attrs), c=content)

def A(content, css:list=None, attrs:dict=None):
	return _TAG('a', content, css, attrs)

def H(index, content, css:list=None, attrs:dict=None):
	return _TAG('h{i}'.format(i=index), content, css, attrs)

def B(content, css:list=None, attrs:dict=None):
	return _TAG('b', content, css, attrs)

def I(content, css:list=None, attrs:dict=None):
	return _TAG('i', content, css, attrs)

def SMALL(content, css:list=None, attrs:dict=None):
	return _TAG('small', content, css, attrs)

def SPAN(content, css:list=None, attrs:dict=None):
	return _TAG('span', content, css, attrs)

def DIV(content, css:list=None, attrs:dict=None):
	return _TAG('div', content, css, attrs)

def TABLE(thead='', tbody='', elem_id='', css:list=None, attrs:dict=None):
	if elem_id:
		attrs = attrs or {}
		attrs['id'] = elem_id
	return _TAG('table', '{}{}'.format(thead, tbody), css, attrs)

def TH(h, default_sort=False):
	return "<th {}>{}</th>".format("data-sort-default" if default_sort else "", h)

def THEAD(th, css:list=None, attrs:dict=None):
	return _TAG('thead', ''.join(th), css, attrs)

def TBODY(rows, css:list=None, attrs:dict=None):
	return _TAG('tbody', ''.join(rows), css, attrs)

def TD(content, colspan=1, rowspan=1, css:list=None, attrs:dict=None):
	attrs = attrs or {}
	attrs['colspan'] = colspan
	attrs['rowspan'] = rowspan
	return _TAG('td', content if content is not None else "-", css, attrs)

def TR(row, css:list=None, attrs:dict=None):
	return _TAG('tr', ''.join(row), css, attrs)

def INPUT(css:list=None, attrs:dict=None):
	return _TAG('input', content="", css=css, attrs=attrs)

def TEXTAREA(content, css:list=None, attrs:dict=None):
	return _TAG('textarea', content, css=css, attrs=attrs)

def BUTTON(content, css:list=None, attrs:dict=None):
	return _TAG('button', content, css, attrs)

def OPTION(content, css:list=None, attrs:dict=None):
	return _TAG('option', content, css, attrs)

def SELECT(options, css:list=None, attrs:dict=None):
	return _TAG('select', ''.join(options), css, attrs)

def CODE(s, css:list=None):
	css = css or []
	if not isinstance(css, (list,set,tuple)):
		css = [css]
	return '''<pre><code class="{}">{}</code></pre>'''.format(' '.join(css), s)

def SCRIPT(s):
	return "<script>{}</script>".format(s)


def SCRIPT_SRC(url):
	return '<script src="{}"></script>'.format(url)

def STYLESHEET(url):
	return '<link rel="stylesheet" href="{}">'.format(url)
