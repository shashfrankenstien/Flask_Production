from setuptools import setup

setup(
	name='flask_production',
	version='2.2.1',
	author='Shashank Gopikrishna',
	author_email='shashank.gopikrishna@gmail.com',
	packages=['flask_production'],
	install_requires=['cherrypy', 'monthdelta', 'holidays', 'python_dateutil'],
	description='cherrypy prod server for Flask + parallel scheduler plugin',
)
