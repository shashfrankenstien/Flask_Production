import os
ROOT = os.path.dirname(os.path.realpath(__file__))
WEB_FOLDER = os.path.join(ROOT, 'web')


def _readTemplate(fileName, **kwargs):
	with open(fileName, 'r') as f:
		templateText = f.read()
	for arg in kwargs:
		templateText = templateText.replace("{{ "+arg+" }}", str(kwargs[arg]))
	return templateText


def HTML(content, title, css=[]):
	if not isinstance(css, (list,set,tuple)):
		css = [css]
	return _readTemplate(os.path.join(WEB_FOLDER, 'index.html'), title=title, body=str(content), body_css=' '.join(css))

def _TAG(tag, content, css, attrs):
	attrs = ['''{}="{}"'''.format(k,v) for k,v in attrs.items()]
	if not isinstance(css, (list,set,tuple)):
		css = [css]
	attrs.append('''class="{}"'''.format(' '.join(css)))
	return "<{t} {a}>{c}</{t}>".format(t=tag, a=' '.join(attrs), c=content)

def H(index, content, css=[], attrs={}):
	return _TAG('h{i}'.format(i=index), content, css, attrs)

def B(content, css=[], attrs={}):
	return _TAG('b', content, css, attrs)

def I(content, css=[], attrs={}):
	return _TAG('i', content, css, attrs)

def SMALL(content, css=[], attrs={}):
	return _TAG('small', content, css, attrs)

def SPAN(content, css=[], attrs={}):
	return _TAG('span', content, css, attrs)

def DIV(content, css=[], attrs={}):
	return _TAG('div', content, css, attrs)

def TABLE(thead='', tbody='', elem_id='', css=[], attrs={}):
	attrs['id'] = elem_id
	return _TAG('table', '{}{}'.format(thead, tbody), css, attrs)

def TH(h, default_sort=False):
	return "<th {}>{}</th>".format("data-sort-default" if default_sort else "", h)

def THEAD(th, css=[], attrs={}):
	return _TAG('thead', ''.join(th), css, attrs)

def TBODY(rows, css=[], attrs={}):
	return _TAG('tbody', ''.join(rows), css, attrs)

def TD(content, colspan=1, rowspan=1, css=[], attrs={}):
	attrs['colspan'] = colspan
	attrs['rowspan'] = rowspan
	return _TAG('td', content if content is not None else "-", css, attrs)

def TR(row, css=[], attrs={}):
	return _TAG('tr', ''.join(row), css, attrs)

def INPUT(content, css=[], attrs={}):
	return _TAG('input', content, css, attrs)

def CODE(s, css=[]):
	if not isinstance(css, (list,set,tuple)):
		css = [css]
	return '''<pre><code class="{}">{}</code></pre>'''.format(' '.join(css), s)

def SCRIPT(s):
	return "<script>{}</script>".format(s)


def SCRIPT_SRC(url):
	return '<script src="{}"></script>'.format(url)

def STYLE_LINK(url):
	return '<link rel="stylesheet" href="{}">'.format(url)
