from datetime import datetime, timedelta

import pytest

from flask_production.state import SQLAlchemyState
from .state_test_helpers import JobState


def make_state(tmp_path, hist_limit=30, db_name="state.db"):
	db_path = tmp_path / db_name
	return SQLAlchemyState(f"sqlite:///{db_path}", hist_limit=hist_limit)


def test_sqlalchemy_state_archives_previous_job_state(tmp_path):
	state = make_state(tmp_path)
	started = datetime(2026, 1, 1, 10)
	ended = started + timedelta(minutes=5)
	try:
		state.save_job_logs(JobState(
			"job-1", "first", disabled=True, err="old error", start=started, end=ended
		))
		with state._engine.connect() as conn:
			assert conn.execute(state.fp_state_hist.select()).all() == []

		state.save_job_logs(JobState("job-1", "second"))

		with state._engine.connect() as conn:
			history = conn.execute(state.fp_state_hist.select()).one()
			current = conn.execute(state.fp_state.select()).one()

		assert history.log == "first"
		assert history.err == "old error"
		assert history.start_dt == started
		assert history.end_dt == ended
		assert history.disabled is True
		assert history.archived_at is not None
		assert current.log == "second"
		assert state._hist_limit == 30
	finally:
		state._engine.dispose()


def test_sqlalchemy_state_limits_history_per_app_and_job(tmp_path):
	state = make_state(tmp_path, hist_limit=2)
	other_app_state = make_state(tmp_path, hist_limit=2)
	other_app_state._cur_app_unique_info_hash = "other-app"
	try:
		for value in ("first", "second", "third", "fourth"):
			state.save_job_logs(JobState("job-1", value))
		for value in ("other-job-first", "other-job-second"):
			state.save_job_logs(JobState("job-2", value))
		other_app_state.save_job_logs(JobState("job-1", "other-app-first"))
		other_app_state.save_job_logs(JobState("job-1", "other-app-second"))

		with state._engine.connect() as conn:
			rows = conn.execute(state.fp_state_hist.select().where(
					state.fp_state_hist.c.app_id == state._cur_app_unique_info_hash,
					state.fp_state_hist.c.signature == "job-1"
				).order_by(state.fp_state_hist.c.id)).all()
			other_job_rows = conn.execute(state.fp_state_hist.select().where(
				state.fp_state_hist.c.app_id == state._cur_app_unique_info_hash,
				state.fp_state_hist.c.signature == "job-2"
			)).all()
			other_app_rows = conn.execute(state.fp_state_hist.select().where(
				state.fp_state_hist.c.app_id == "other-app"
			)).all()

		assert [row.log for row in rows] == ["second", "third"]
		assert [row.log for row in other_job_rows] == ["other-job-first"]
		assert [row.log for row in other_app_rows] == ["other-app-first"]
	finally:
		state._engine.dispose()
		other_app_state._engine.dispose()


def test_sqlalchemy_state_restore_removes_history_for_removed_jobs(tmp_path):
	state = make_state(tmp_path)
	other_app_state = make_state(tmp_path)
	other_app_state._cur_app_unique_info_hash = "other-app"
	try:
		state.save_job_logs(JobState("kept-job", "kept-previous"))
		state.save_job_logs(JobState("kept-job", "kept-current", disabled=True))
		state.save_job_logs(JobState("removed-job", "removed-previous"))
		state.save_job_logs(JobState("removed-job", "removed-current"))
		other_app_state.save_job_logs(JobState("removed-job", "other-app-previous"))
		other_app_state.save_job_logs(JobState("removed-job", "other-app-current"))

		restored_job = JobState("kept-job", "new")
		state.restore_all_job_logs([restored_job])

		with state._engine.connect() as conn:
			rows = conn.execute(state.fp_state_hist.select().where(
				state.fp_state_hist.c.app_id == state._cur_app_unique_info_hash
			)).all()
			current_rows = conn.execute(state.fp_state.select().where(
				state.fp_state.c.app_id == state._cur_app_unique_info_hash
			)).all()
			other_app_history = conn.execute(state.fp_state_hist.select().where(
				state.fp_state_hist.c.app_id == other_app_state._cur_app_unique_info_hash
			)).all()
			other_app_current = conn.execute(state.fp_state.select().where(
				state.fp_state.c.app_id == other_app_state._cur_app_unique_info_hash
			)).all()

		assert [row.signature for row in rows] == ["kept-job"]
		assert [row.signature for row in current_rows] == ["kept-job"]
		assert restored_job.restored_logs['log'] == "kept-current"
		assert restored_job.is_disabled is True
		assert [row.log for row in other_app_history] == ["other-app-previous"]
		assert [row.log for row in other_app_current] == ["other-app-current"]
	finally:
		state._engine.dispose()
		other_app_state._engine.dispose()


def test_sqlalchemy_state_zero_history_limit(tmp_path):
	state = make_state(tmp_path, hist_limit=0)
	try:
		state.save_job_logs(JobState("job-1", "first"))
		state.save_job_logs(JobState("job-1", "second"))

		with state._engine.connect() as conn:
			history = conn.execute(state.fp_state_hist.select()).all()

		assert history == []
	finally:
		state._engine.dispose()


@pytest.mark.parametrize("hist_limit", [-1, 1.5, "2", True])
def test_sqlalchemy_state_rejects_invalid_history_limits(tmp_path, hist_limit):
	with pytest.raises(ValueError, match="hist_limit must be a non-negative integer"):
		make_state(tmp_path, hist_limit=hist_limit)


def test_sqlalchemy_state_restore_cleans_history_for_empty_job_list(tmp_path):
	state = make_state(tmp_path)
	try:
		state.save_job_logs(JobState("job-1", "first"))
		state.save_job_logs(JobState("job-1", "second"))

		state.restore_all_job_logs([])

		with state._engine.connect() as conn:
			history = conn.execute(state.fp_state_hist.select()).all()
			current = conn.execute(state.fp_state.select()).all()

		assert history == []
		assert current == []
	finally:
		state._engine.dispose()


def test_sqlalchemy_state_rolls_back_history_when_current_save_fails(tmp_path):
	state = make_state(tmp_path)

	class InvalidJobState(JobState):
		def func_signature(self):
			raise RuntimeError("failed to build job signature")

	try:
		state.save_job_logs(JobState("job-1", "original"))
		with pytest.raises(RuntimeError, match="failed to build job signature"):
			state.save_job_logs(InvalidJobState("job-1", "replacement"))

		with state._engine.connect() as conn:
			history = conn.execute(state.fp_state_hist.select()).all()
			current = conn.execute(state.fp_state.select()).one()

		assert history == []
		assert current.log == "original"
	finally:
		state._engine.dispose()


def test_sqlalchemy_state_creates_history_table_in_existing_database(tmp_path):
	from sqlalchemy import create_engine, inspect

	db_path = tmp_path / "legacy.db"
	legacy_engine = create_engine(f"sqlite:///{db_path}")
	try:
		with legacy_engine.begin() as conn:
			conn.exec_driver_sql(
				"CREATE TABLE fp_state ("
				"app_id VARCHAR(50) NOT NULL, "
				"signature VARCHAR(50) NOT NULL, "
				"readable VARCHAR(200), "
				"log TEXT, err TEXT, start_dt DATETIME, end_dt DATETIME, "
				"disabled BOOLEAN, PRIMARY KEY (app_id, signature))"
			)
			conn.exec_driver_sql(
				"INSERT INTO fp_state (app_id, signature, log) VALUES "
				"('legacy-app', 'legacy-job', 'preserved')"
			)

		state = SQLAlchemyState(f"sqlite:///{db_path}")
		try:
			state._ensure_create_table()
			table_names = inspect(state._engine).get_table_names()
			with state._engine.connect() as conn:
				legacy_row = conn.exec_driver_sql(
					"SELECT log FROM fp_state WHERE app_id = 'legacy-app' "
					"AND signature = 'legacy-job'"
				).one()

			assert "fp_state_hist" in table_names
			assert legacy_row.log == "preserved"
		finally:
			state._engine.dispose()
	finally:
		legacy_engine.dispose()
