import os
import pickle
from datetime import datetime, timedelta

import pytest

from flask_production.state import FileSystemState
import flask_production.state.fs as fs_module
from .state_test_helpers import JobState


def make_state(tmp_path, hist_limit=30):
	state_dir = tmp_path / "states"
	return FileSystemState(str(state_dir), hist_limit=hist_limit)


def read_pickle(path):
	with open(path, 'rb') as state_file:
		return pickle.load(state_file)


def use_increasing_timestamps(monkeypatch):
	timestamp = datetime(2026, 1, 1)

	class FakeDateTime:
		@staticmethod
		def now():
			nonlocal timestamp
			current = timestamp
			timestamp += timedelta(seconds=1)
			return current

	monkeypatch.setattr(fs_module, "dt", FakeDateTime)


def test_filesystem_state_creates_state_and_history_directories(tmp_path):
	state = make_state(tmp_path)

	assert os.path.isdir(state._job_state_dir)
	assert os.path.isdir(state._job_hist_dir)
	assert state._hist_limit == 30


@pytest.mark.parametrize("disabled", [False, True])
def test_filesystem_state_saves_and_restores_current_job_state(tmp_path, disabled):
	state = make_state(tmp_path)
	job = JobState("job-1", "saved log", disabled=disabled)

	state.save_job_logs(job)

	state_file = os.path.join(state._job_state_dir, "job-1.pickle")
	stored_state = read_pickle(state_file)
	assert stored_state['logs'] == job._logs_to_dict()
	assert stored_state['disabled'] is disabled
	assert isinstance(stored_state['timestamp'], datetime)

	restored_job = JobState("job-1", "initial")
	state.restore_all_job_logs([restored_job])

	assert restored_job.restored_logs == job._logs_to_dict()
	assert restored_job.is_disabled is disabled


def test_filesystem_state_restores_legacy_state_without_timestamp(tmp_path):
	state = make_state(tmp_path)
	legacy_logs = {'log': 'legacy log', 'err': None, 'start': None, 'end': None}
	state_file = os.path.join(state._job_state_dir, "job-1.pickle")
	with open(state_file, 'wb') as file:
		pickle.dump({'logs': legacy_logs, 'disabled': True}, file)

	job = JobState("job-1", "initial")
	state.restore_all_job_logs([job])

	assert job.restored_logs == legacy_logs
	assert job.is_disabled is True


def test_filesystem_state_removes_current_state_for_unregistered_jobs(tmp_path):
	state = make_state(tmp_path)
	state.save_job_logs(JobState("registered-job", "registered"))
	state.save_job_logs(JobState("stale-job", "stale"))

	state.restore_all_job_logs([JobState("registered-job", "initial")])

	assert os.listdir(state._job_state_dir) == ["registered-job.pickle"]


def test_filesystem_state_archives_previous_state_with_unique_names(tmp_path, monkeypatch):
	state = make_state(tmp_path)
	use_increasing_timestamps(monkeypatch)
	job = JobState("job-1", "first")

	for log in ("first", "second", "third"):
		job.log = log
		state.save_job_logs(job)

	history_files = sorted(os.listdir(state._job_hist_dir))
	assert len(history_files) == 2
	assert len(set(history_files)) == 2
	assert [read_pickle(os.path.join(state._job_hist_dir, name))['logs']['log']
			for name in history_files] == ["first", "second"]
	assert read_pickle(os.path.join(state._job_state_dir, "job-1.pickle"))['logs']['log'] == "third"


def test_filesystem_state_retains_newest_history_up_to_limit(tmp_path, monkeypatch):
	state = make_state(tmp_path, hist_limit=2)
	use_increasing_timestamps(monkeypatch)
	job = JobState("job-1", "first")
	for log in ("first", "second", "third", "fourth"):
		job.log = log
		state.save_job_logs(job)

	history = [
		read_pickle(os.path.join(state._job_hist_dir, name))['logs']['log']
		for name in sorted(os.listdir(state._job_hist_dir))
	]
	assert history == ["second", "third"]


def test_filesystem_state_zero_history_limit_disables_archiving(tmp_path):
	state = make_state(tmp_path, hist_limit=0)
	job = JobState("job-1", "first")
	state.save_job_logs(job)
	job.log = "second"
	state.save_job_logs(job)

	assert os.listdir(state._job_hist_dir) == []
	assert read_pickle(os.path.join(state._job_state_dir, "job-1.pickle"))['logs']['log'] == "second"


def test_filesystem_state_cleanup_removes_history_for_unregistered_jobs(tmp_path):
	state = make_state(tmp_path)
	for signature in ("registered-job", "stale-job"):
		state.save_job_logs(JobState(signature, "first"))
		state.save_job_logs(JobState(signature, "second"))

	state.restore_all_job_logs([JobState("registered-job", "initial")])

	assert len(os.listdir(state._job_hist_dir)) == 1
	assert os.listdir(state._job_hist_dir)[0].startswith("registered-job_")


@pytest.mark.parametrize("hist_limit", [-1, 1.5, "2"])
def test_filesystem_state_rejects_invalid_history_limits(tmp_path, hist_limit):
	with pytest.raises(ValueError, match="hist_limit must be a non-negative integer"):
		FileSystemState(str(tmp_path / "states"), hist_limit=hist_limit)
