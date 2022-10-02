from datetime import datetime

def write_log(log, datestr):
	ctime = datetime.now()
	time_string = ctime.strftime("[%H:%M:%S] ")

	with open(datestr+".log", "a+") as file:
		file.seek(0)
		contents = file.read(100)
		if len(contents) > 0:
			file.write("\n")
		file.write(time_string+log)
		print(time_string+log)