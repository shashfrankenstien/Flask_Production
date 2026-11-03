from flask_production.print_logger import _PrintLogger


def test_print_logger_get_history_returns_completed_runs():
	logger = _PrintLogger()

	with logger.start_capture(silently=True):
		print("completed run")

	history = logger.get_history()

	assert len(history) == 1
	logs = next(iter(history.values()))
	assert logs['log'].strip() == "completed run"
	assert logs['start'] is not None
	assert logs['end'] is not None


def test_print_logger_stores_completed_runs_in_history():
	logger = _PrintLogger()

	with logger.start_capture(silently=True):
		print("first run")

	with logger.start_capture(silently=True):
		print("second run")

	history = logger.get_history()

	assert len(history) == 2
	assert [logs['log'].strip() for logs in history.values()] == [
		"first run",
		"second run",
	]
	assert all(logs['start'] is not None for logs in history.values())
	assert all(logs['end'] is not None for logs in history.values())


def test_print_logger_restores_history():
	source = _PrintLogger()
	logs = [
		{'log': 'first', 'err': '', 'start': 1, 'end': 2},
		{'log': 'second', 'err': 'error', 'start': 3, 'end': 4},
	]
	source.restore_hist(logs)

	assert source.get_history() == {2: logs[0], 4: logs[1]} # keyed by 'end' value
