import os
import holidays
from datetime import date
from dateutil.relativedelta import relativedelta, MO, FR
from dateutil.easter import easter


class TradingHolidays(holidays.countries.UnitedStates):
	def _populate(self, year):
		# Populate the holiday list with the default US holidays
		holidays.UnitedStates._populate(self, year)
		# Remove Columbus Day
		# Edit: in holidays==0.61, Columbus day was removed as a US countrywide holiday
		# 	- https://github.com/vacanza/holidays/pull/2106
		columbus_day = date(year, 10, 1) + relativedelta(weekday=MO(+2))
		if columbus_day in self:
			self.pop(columbus_day, None)

		# Remove Veterans Day
		self.pop(date(year, 11, 11), None)
		if year==2023:
			self.pop(date(year, 11, 10), None)

		# # Add Good Friday  [04/03/2026]
		# Good Friday is a holiday usually unless it's the first Friday of a month
		# Employment numbers come out on first Friday of every month. So market is open for a few hours even on Good Friday
		good_friday = easter(year) + relativedelta(weekday=FR(-1))
		if good_friday.month == (good_friday - relativedelta(days=7)).month: # check if previous Friday is same month
			self[good_friday] = "Good Friday"

		# 2021-12-31 is not a holiday apparently :( and windows version seems to think it is
		if year == 2021:
			nye_2021 = date(2021, 12, 31)
			if nye_2021 in self:
				self.pop(nye_2021, None)
