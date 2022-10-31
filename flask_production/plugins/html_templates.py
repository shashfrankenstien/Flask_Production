
def HTML(content, title):
	return '''
	<!DOCTYPE html>
	<html lang="en">
		<head>
			<meta charset="UTF-8">
			<meta name="viewport" content="width=device-width, initial-scale=1.0">
			<script src="https://cdnjs.cloudflare.com/ajax/libs/tablesort/5.2.1/tablesort.min.js"
				integrity="sha512-F/gIMdDfda6OD2rnzt/Iyp2V9JLHlFQ+EUyixDg9+rkwjqgW1snpkpx7FD5FV1+gG2fmFj7I3r6ReQDUidHelA=="
				crossorigin="anonymous"></script>
			<script src="https://cdnjs.cloudflare.com/ajax/libs/tablesort/5.2.1/sorts/tablesort.number.min.js"
				integrity="sha512-dRD755QRxlybm0h3LXXIGrFcjNakuxW3reZqnPtUkMv6YsSWoJf+slPjY5v4lZvx2ss+wBZQFegepmA7a2W9eA=="
				crossorigin="anonymous"></script>
			<link rel="stylesheet"
				href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.6.0/styles/monokai-sublime.min.css">
			<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.6.0/highlight.min.js"></script>
			<script src="https://cdn.jsdelivr.net/gh/TRSasasusu/highlightjs-highlight-lines.js@1.2.0/highlightjs-highlight-lines.min.js"></script>
			<script src="https://cdn.jsdelivr.net/gh/shashfrankenstien/lib-tablefilterjs@v0.0.5/lib-tablefilter.min.js"></script>
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

def _TAG(tag, content, css, attrs):
	attrs = ["{}='{}'".format(k,v) for k,v in attrs.items()]
	if not isinstance(css, (list,set,tuple)):
		css = [css]
	attrs.append("class='{}'".format(' '.join(css)))
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

def SCRIPT(s):
	return "<script>{}</script>".format(s)

def CODE(s, css=[]):
	if not isinstance(css, (list,set,tuple)):
		css = [css]
	return "<pre><code class='{}'>{}</code></pre>".format(' '.join(css), s)
