import socket
import subprocess
import re


_HOST_INFO = {} # cache

def get_host_info():
	'''called to get host and git info to show on task monitor and report errors'''
	global _HOST_INFO

	if _HOST_INFO:
		return _HOST_INFO

	_host_info = {
		'hostname':"hostname not found",
		'ip_addr': "IP addr not found",
		'git_url': 'Git URL not found'
	}
	try:
		_host_info['hostname'] =  socket.gethostname()
		_host_info['ip_addr'] = socket.gethostbyname(_host_info['hostname'])
	except Exception:
		pass

	try:
		git_remote = subprocess.run(['git', 'remote', 'get-url', 'origin'], capture_output=True, text=True, check=True)
		git_url = git_remote.stdout.strip()
		# Remove user and token from git URL (handles https://user:token@host/path format)
		# The pattern matches `http://` or `https://`, then all characters up to
		# the `@` separator; replacing it removes embedded credentials.
		git_url = re.sub(r'https?://[^@]*@', 'https://', git_url)
		_host_info['git_url'] = git_url

	except Exception:
		pass

	_HOST_INFO = _host_info # cache fields
	return _HOST_INFO
