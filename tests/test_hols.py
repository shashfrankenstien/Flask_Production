from datetime import date
import time

from dateutil.easter import easter
from dateutil.parser import parse as date_parse
from dateutil.relativedelta import relativedelta, FR

from flask_production import TaskScheduler
from flask_production.hols import TradingHolidays


def job(x, y):
	time.sleep(0.1)
	print(x, y)


def test_holidays():
	s = TaskScheduler() # default holidays calendar
	s.every("businessday").at("10:00").do(job, x="hello", y="world")
	assert(s.jobs[0]._job_must_run_today(date_parse("2020-04-09"))==True)
	assert(s.jobs[0]._job_must_run_today(date_parse("2024-11-11"))==False) # Veterans Day is a US holiday

	s = TaskScheduler(holidays_calendar=TradingHolidays())
	s.every("businessday").at("10:00").do(job, x="hello", y="world")
	assert(s.jobs[0]._job_must_run_today(date_parse("2020-04-09"))==True)
	assert(s.jobs[0]._job_must_run_today(date_parse("2020-04-11"))==False) # saturday
	assert(s.jobs[0]._job_must_run_today(date_parse("2024-11-11"))==True) # test Custom financial calendar with Veterans Day removed

	s.every("trading-holiday").at("10:00").do(job, x="hello", y="world")
	assert(s.jobs[1]._job_must_run_today(date_parse("2020-01-01"))==True)
	assert(s.jobs[1]._job_must_run_today(date_parse("2020-01-02"))==False)

	# added [04/03/2026]
	good_friday_2025 = easter(2025) + relativedelta(weekday=FR(-1))
	good_friday_2026 = easter(2026) + relativedelta(weekday=FR(-1))
	assert(s.jobs[1]._job_must_run_today(good_friday_2025)==True) # 2025 good friday was a holiday
	assert(s.jobs[1]._job_must_run_today(good_friday_2026)==False) # 2026 good friday was NOT a holiday


def test_includes_default_us_holidays():
	holidays = TradingHolidays()

	assert date(2024, 1, 1) in holidays


def test_removes_columbus_day():
	holidays = TradingHolidays()

	assert date(2024, 10, 14) not in holidays


def test_removes_veterans_day():
	holidays = TradingHolidays()

	assert date(2024, 11, 11) not in holidays


def test_removes_observed_veterans_day_in_2023():
	holidays = TradingHolidays()

	assert date(2023, 11, 10) not in holidays
	assert date(2023, 11, 11) not in holidays


def test_adds_good_friday_when_it_is_not_the_first_friday_of_the_month():
	holidays = TradingHolidays()

	assert holidays.get(date(2025, 4, 18)) == "Good Friday"


def test_does_not_add_good_friday_when_it_is_the_first_friday_of_the_month():
	holidays = TradingHolidays()

	assert date(2026, 4, 3) not in holidays


def test_removes_new_years_eve_in_2021():
	holidays = TradingHolidays()

	assert date(2021, 12, 31) not in holidays
