import os
import holidays
from datetime import date
from dateutil.relativedelta import relativedelta, MO, FR
from dateutil.easter import easter


GOOD_FRIDAY_TRADING_HOLIDAY = str(os.environ.get('GOOD_FRIDAY_TRADING_HOLIDAY')).strip() == '1'


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

		# # Add Good Friday
		# NOTE: removed this since Good Friday is not a bond market holiday - [04/01/2021]
		# new NOTE: this is back to being a holiday now. So making it env variable - [4/17/2025]
		if GOOD_FRIDAY_TRADING_HOLIDAY:
			self[easter(year) + relativedelta(weekday=FR(-1))] = "Good Friday"

		# 2021-12-31 is not a holiday apparently :( and windows version seems to think it is
		nye_2021 = date(2021, 12, 31)
		if nye_2021 in self:
			self.pop(nye_2021, None)
