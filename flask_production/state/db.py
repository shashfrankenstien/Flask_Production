from datetime import datetime as dt

from .base import BaseStateHandler



class SQLAlchemyState(BaseStateHandler):

	def __init__(self, uri) -> None:
		super().__init__()
		self.uri = uri
		self.__tables_created = False

		try: # make sure required packages are installed
			import sqlalchemy
			import sqlalchemy_utils
		except ImportError:
			msg = f"Please install sqlalchemy and sqlalchemy-utils to use '{self.__class__.__name__}' class"
			print("=="*25)
			print(msg)
			print("=="*25)
			raise ImportError(msg)

	def _ensure_create_table(self):
		if self.__tables_created is True:
			return
		self.__tables_created = True

		from sqlalchemy import create_engine, MetaData
		from sqlalchemy import Table, Column, String, Text, DateTime, Boolean
		from sqlalchemy import select, insert, update
		from sqlalchemy_utils import database_exists, create_database

		self._engine = create_engine(self.uri)
		if not database_exists(self._engine.url):
			create_database(self._engine.url)
		self._meta = MetaData()

		# sqlalchemy table definitions
		self.fp_apps = Table(
			'fp_apps', self._meta,
			Column('app_id', String(50), primary_key=True),
			Column('app_unique_info', String(255)),
			Column('restart_dt', DateTime)
		)

		self.fp_state = Table(
			'fp_state', self._meta,
			Column('app_id', String(50), primary_key=True),
			Column('signature', String(50), primary_key=True),
			Column('readable', String(200)),
			Column('log', Text),
			Column('err', Text),
			Column('start_dt', DateTime),
			Column('end_dt', DateTime),
			Column('disabled', Boolean),
		)
		self._meta.create_all(self._engine)

		# update info to fp_apps table
		info_str = '\n'.join(self._cur_app_unique_info)
		restart_dt = dt.now()
		with self._engine.connect() as conn:
			app_row = conn.execute(select(self.fp_apps).where(self.fp_apps.c.app_id == self._cur_app_unique_info_hash)).all()
			if len(app_row) > 0:
				update(self.fp_apps).where(self.fp_apps.c.app_id == self._cur_app_unique_info_hash).values(restart_dt=restart_dt)
				if info_str != app_row[0].app_unique_info:
					print("=="*25)
					print(f"{self.__class__.__name__}: HASH COLLISION")
					print("=="*25)
			else:
				conn.execute(insert(self.fp_apps).values(app_id=self._cur_app_unique_info_hash, app_unique_info=info_str, restart_dt=restart_dt))
				conn.commit()


	def save_job_logs(self, job_obj):
		self._ensure_create_table()
		from sqlalchemy import select, insert, update
		signature = job_obj.signature_hash()
		logs = job_obj._logs_to_dict()

		with self._engine.connect() as conn:
			stmt = select(self.fp_state).where(self.fp_state.c.signature == signature, self.fp_state.c.app_id == self._cur_app_unique_info_hash)
			db_job = conn.execute(stmt).all()
			if len(db_job) == 1: # has to return only 1 element as we are querying on primary keys
				# print(db_job[0])
				update_stmt = update(self.fp_state).where(self.fp_state.c.signature == signature, self.fp_state.c.app_id == self._cur_app_unique_info_hash)

			else: # no state exists. insert!
				update_stmt = insert(self.fp_state)

			conn.execute(update_stmt.values(
				app_id=self._cur_app_unique_info_hash,
				signature=signature,
				readable=job_obj.func_signature(),
				log=logs.get('log'),
				err=logs.get('err'),
				start_dt=logs.get('start'),
				end_dt=logs.get('end'),
				disabled=job_obj.is_disabled
			))
			conn.commit()


	def restore_all_job_logs(self, jobs_list):
		self._ensure_create_table()
		from sqlalchemy import select, delete

		with self._engine.connect() as conn:
			db_states = conn.execute(select(self.fp_state).where(self.fp_state.c.app_id == self._cur_app_unique_info_hash)).all()

		states = {}
		for s in db_states:
			states[s.signature] = s

		found_states = []
		for j in jobs_list.copy(): # work on a shallow copy of this list - safer in case the list changes. TODO: maybe use locks instead?
			signature = j.signature_hash()
			if signature in states:
				st = states[signature]
				j._logs_from_dict({
					'log': st.log,
					'err': st.err,
					'start': st.start_dt,
					'end': st.end_dt,
				})
				if st.disabled:
					j.disable()
				found_states.append(signature)
				# print("restored", j)

		# clean up other states that did not match current jobs list (possibly stale)
		with self._engine.connect() as conn:
			for sig, st in states.items():
				if sig not in found_states:
					conn.execute(delete(self.fp_state).where(self.fp_state.c.signature == sig))
			conn.commit()
