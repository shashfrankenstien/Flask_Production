from threading import Event, Thread
from types import SimpleNamespace

import pytest

import flask_production.core as core_module
from flask_production.core import CherryFlask


class FakeEngine:
	def __init__(self):
		self.exit_calls = 0
		self.exit_callbacks = []
		self.exited = Event()

	def start(self):
		pass

	def subscribe(self, event, callback):
		if event == 'exit':
			self.exit_callbacks.append(callback)

	def exit(self):
		self.exit_calls += 1
		for callback in self.exit_callbacks:
			callback()
		self.exited.set()


class FakeServer:
	def subscribe(self):
		pass


def install_fake_cherrypy(monkeypatch, graft=None):
	engine = FakeEngine()
	fake_cherrypy = SimpleNamespace(
		config=SimpleNamespace(update=lambda config: None),
		tree=SimpleNamespace(graft=graft or (lambda app, path: None)),
		server=SimpleNamespace(unsubscribe=lambda: None),
		_cpserver=SimpleNamespace(Server=FakeServer),
		engine=engine,
	)
	monkeypatch.setattr(core_module, "cherrypy", fake_cherrypy)
	return engine


def make_app():
	return SimpleNamespace(wsgi_app=object(), after_request=lambda callback: callback)


def test_blocking_run_stops_engine_once_when_scheduler_returns(monkeypatch):
	engine = install_fake_cherrypy(monkeypatch)
	scheduler = SimpleNamespace(start=lambda: None, stop=lambda: None)
	server = CherryFlask(make_app(), scheduler=scheduler, silent=True)

	server.run()
	server.stop()

	assert engine.exit_calls == 1


def test_run_stops_engine_if_setup_raises(monkeypatch):
	engine = install_fake_cherrypy(
		monkeypatch,
		graft=lambda app, path: (_ for _ in ()).throw(RuntimeError("graft failed"))
	)
	server = CherryFlask(make_app(), silent=True, blocking=False)

	with pytest.raises(RuntimeError, match="graft failed"):
		server.run()

	assert engine.exit_calls == 0


def test_nonblocking_scheduler_failure_stops_engine_and_can_be_joined(monkeypatch):
	engine = install_fake_cherrypy(monkeypatch)
	failed = Event()

	class FailingScheduler:
		def start(self):
			try:
				raise RuntimeError("scheduler failed")
			finally:
				failed.set()

		def stop(self):
			pass

	server = CherryFlask(make_app(), scheduler=FailingScheduler(), silent=True, blocking=False)
	server.run()

	assert engine.exited.wait(timeout=2)
	assert failed.wait(timeout=2)
	server.stop()

	assert engine.exit_calls == 1
	assert server._scheduler_thread is not None
	assert not server._scheduler_thread.is_alive()


def test_stop_does_not_join_the_calling_worker_thread(monkeypatch):
	install_fake_cherrypy(monkeypatch)
	server = CherryFlask(make_app(), silent=True)
	worker = Thread(target=server.stop)
	server._scheduler_thread = worker

	worker.start()
	worker.join(timeout=2)

	assert not worker.is_alive()
