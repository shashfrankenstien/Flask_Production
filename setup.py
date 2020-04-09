from setuptools import setup

setup(
	name='flask_production',
	version='1.1.0',
	author='Shashank Gopikrishna',
	author_email='shashank.gopikrishna@gmail.com',
	packages=['flask_production'],
	install_requires=['cherrypy', 'monthdelta', 'holidays', 'dateutil'],
	description='cherrypy prod server for Flask + parallel scheduler plugin',
)
