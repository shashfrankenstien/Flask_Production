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
		# Add Good Friday
		self[easter(year) + relativedelta(weekday=FR(-1))] = "Good Friday"
