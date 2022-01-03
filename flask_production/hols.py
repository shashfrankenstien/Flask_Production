import holidays
from datetime import date
from dateutil.relativedelta import relativedelta, MO, FR
from dateutil.easter import easter

class TradingHolidays(holidays.UnitedStates):
	def _populate(self, year):
		# Populate the holiday list with the default US holidays
		holidays.UnitedStates._populate(self, year)
		# Remove Columbus Day
		self.pop(date(year, 10, 1) + relativedelta(weekday=MO(+2)), None)
		# Remove Veterans Day
		self.pop(date(year, 11, 11), None)

		# # Add Good Friday # NOTE: removed this since Good Friday is not a bond market holiday - [04/01/2021]
		# self[easter(year) + relativedelta(weekday=FR(-1))] = "Good Friday"

		# 2021-12-31 is not a holiday apparently :( and windows version seems to think it is
		nye_2021 = date(2021, 12, 31)
		if nye_2021 in self:
			self.pop(nye_2021, None)
