import os, sys, subprocess, time
from selenium import webdriver



conf_path = '/mnt/ad_keeper/test_udp.ovpn'
auth_path = '/mnt/ad_keeper/vpn/pass.txt'
wait = 15

def make_vpn():
	x = subprocess.Popen(['sudo', 'openvpn', 
			'--config', conf_path,
			'--user','pi',
			'--auth-user-pass', auth_path], stdout=subprocess.PIPE) #, capture_output=True)

	while True:
		if 'Initialization Sequence Completed' in str(x.stdout.readline()):
			print('Link established')
			return(0)





driver = webdriver.Chrome()

driver.get('https://whatismyipaddress.com/')

print('closing')

def stop_vpn():
	k = subprocess.Popen(['sudo', 'killall', 'openvpn'])


	while x.poll() != 0:
		time.sleep(1)

