from datetime import date
def update_date():
	today = date.today()
	return today.strftime("%d_%m_%Y")