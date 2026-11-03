class JobState:
	def __init__(self, signature, log, disabled=False, err=None, start=None, end=None):
		self.signature = signature
		self.log = log
		self.is_disabled = disabled
		self.err = err
		self.start = start
		self.end = end
		self.restored_logs = None
		self.restored_history = None

	def signature_hash(self):
		return self.signature

	def func_signature(self):
		return self.signature

	def _logs_to_dict(self):
		return {
			'log': self.log,
			'err': self.err,
			'start': self.start,
			'end': self.end,
		}

	def _logs_from_dict(self, logs):
		self.restored_logs = logs

	def _logs_hist_from_list(self, logs_hist):
		self.restored_history = logs_hist

	def disable(self):
		self.is_disabled = True
