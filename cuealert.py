import os 
import subprocess as sub
import platform

from lib import (
	get_user_config,
)

from const import (
    queue_file_name,
)


def play_sound(filename):
	if 'linux' in platform.system().lower():
		p = sub.Popen(['aplay', os.path.join(os.getcwd(), filename)],stdout=sub.PIPE,stderr=sub.PIPE)
	else:
		p = sub.Popen(['afplay', os.path.join(os.getcwd(), filename)],stdout=sub.PIPE,stderr=sub.PIPE)
	(output, err) = p.communicate()

if __name__ == '__main__':
	queue_file_path = os.path.join(get_user_config()["result_files_dir"], queue_file_name)
	if os.path.isfile(queue_file_path):
		queue_text = open(queue_file_path).read().strip()
		if len(queue_text) > 0:
			play_sound('finealert.wav')
		else:
			print("Queue is empty")
	else:
		print("Queue is empty")
