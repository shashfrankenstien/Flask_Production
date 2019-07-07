from setuptools import setup

setup(
	name='cherry_flask',
	version='0.1.0',
	author='Shashank Gopikrishna',
	author_email='shashank.gopikrishna@gmail.com',
	packages=['cherry_flask'],
	install_requires=['cherrypy', 'monthdelta', 'holidays'],
	description='cherrypy prod server for Flask + parallel scheduler plugin',
)