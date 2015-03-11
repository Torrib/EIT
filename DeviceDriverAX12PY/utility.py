#!/usr/bin/env python2.6
import os
import dynamixel
import sys
import subprocess
import optparse
import yaml
import socket
import json
import time

class Car_configuration:
	def __init__(self, left_actuator_cluster, right_actuator_cluster, net):
		self.right_actuator_cluster = right_actuator_cluster
		self.left_actuator_cluster = left_actuator_cluster
		self.speed_scale = 6
		self.net = net

	def reset_speed(self):
		for actuator_id in self.left_actuator_cluster:
			self.net[actuator_id].moving_speed = 0

		for actuator_id in self.right_actuator_cluster:
			self.net[actuator_id].moving_speed = 1024

	def add_move_forward(self, speed):
		if speed > 100:
			setspeed = 100
		elif speed < 0:
			setspeed = 0
		else:
			setspeed = speed

		for actuator_id in self.left_actuator_cluster:
			self.net[actuator_id].moving_speed += (self.speed_scale*setspeed)
			if self.net[actuator_id].moving_speed > 2048:
				self.net[actuator_id].moving_speed = 2048

		for actuator_id in self.right_actuator_cluster:
			self.net[actuator_id].moving_speed += (self.speed_scale*setspeed)
			if self.net[actuator_id].moving_speed > 2048:
				self.net[actuator_id].moving_speed = 2048


	def add_move_backward(self, speed):
		if speed > 100:
			setspeed = 100
		elif speed < 0:
			setspeed = 0
		else:
			setspeed = speed

		for actuator_id in self.left_actuator_cluster:
			self.net[actuator_id].moving_speed += (1024 + self.speed_scale*setspeed)
			if self.net[actuator_id].moving_speed > 2048:
				self.net[actuator_id].moving_speed = 2048

		for actuator_id in self.right_actuator_cluster:
			self.net[actuator_id].moving_speed -= (1000 - self.speed_scale*setspeed) 
			if self.net[actuator_id].moving_speed < 0:
				self.net[actuator_id].moving_speed = 0

	def add_turn_left(self, turn):
		if turn > 100:
			setturn = 100
		elif turn < 0:
			setturn = 0
		else:
			setturn = turn

		#TODO::TAKE CARE OF SPECIAL CASES TO WORK PROPERLY
		for actuator_id in self.left_actuator_cluster:
			self.net[actuator_id].moving_speed -= (10 - self.speed_scale)*setturn
			if self.net[actuator_id].moving_speed < 0:
				self.net[actuator_id].moving_speed = 0

		for actuator_id in self.right_actuator_cluster:
			self.net[actuator_id].moving_speed += (10 - self.speed_scale)*setturn
			if self.net[actuator_id].moving_speed > 2048:
				self.net[actuator_id].moving_speed = 2048

	def add_turn_right(self, turn):
		if turn > 100:
			setturn = 100
		elif turn < 0:
			setturn = 0
		else:
			setturn = turn

		for actuator_id in self.left_actuator_cluster:
			self.net[actuator_id].moving_speed += (10 - self.speed_scale)*setturn
			if self.net[actuator_id].moving_speed > 2048:
				self.net[actuator_id].moving_speed = 2048

		for actuator_id in self.right_actuator_cluster:
			self.net[actuator_id].moving_speed -= (10 - self.speed_scale)*setturn
			if self.net[actuator_id].moving_speed < 1024:
				self.net[actuator_id].moving_speed = 1024
		


class ErrorLogger:
	def __init__(self, logfile):
		try:
			self.errorlog = open(logfile, 'a')
			print("Date: " + time.strftime("%d/%m/%Y") + 
				"\nTime: " + time.strftime("%H:%M:%S") + 
				"\nErrorlog initialized\n")
		except:
			print("Date: " + time.strftime("%d/%m/%Y") + 
				"\nTime: " + time.strftime("%H:%M:%S") + 
				"\nFailed to open errorlog!\n")
			self.errorlog = 0

	def write(self, string):
		if self.errorlog:
			self.errorlog.write("Date: " + time.strftime("%d/%m/%Y") + 
			"\nTime: " + time.strftime("%H:%M:%S") + 
			"\n" + string + "\n" + "\n")
		else:
			return 0
	def close_log(self):
		if self.errorlog:
			self.errorlog.close()

	

class DeviceController:
	def __init__(self, settings, errorlog):
		try:
			self.name = settings['name']
		except:
			self.name = "RULS_DEFAULT"
		self.clientsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.connected = False
		self.configurations = {}
		self.configuration_ids = []

		# Establish a serial connection to the dynamixel network.
		# This usually requires a USB2Dynamixel
		self.serial = dynamixel.SerialStream(port=settings['port'],
										baudrate=settings['baudRate'],
										timeout=1)
		# Instantiate our network object
		self.net = dynamixel.DynamixelNetwork(self.serial)

		self.create_car_configuration(0, settings['servoIds'])


		# Populate our network with dynamixel objects
		for servoId in settings['servoIds']:
			newDynamixel = dynamixel.Dynamixel(servoId, self.net)
			self.net._dynamixel_map[servoId] = newDynamixel
		
		# Get all the dynamixels in the network
		if not self.net.get_dynamixels():
			errorlog.write("ERROR: No Dynamixels Found!\n")
			printdt("No Dynamixels Found!")
			sys.exit(0)
		else:
			printdt("Dynamixels found, network initialized")

		for actuator in self.net.get_dynamixels():
			actuator._set_to_wheel_mode()
			actuator.moving_speed = 1024
			actuator.torque_enable = False
			actuator.torque_limit = 900
			actuator.max_torque = 900
			actuator.goal_position = 512
			
		self.net.synchronize()

	def create_car_configuration(self, conf_id, servo_ids):
		right_actuator_cluster = []
		left_actuator_cluster = []

		self.configuration_ids.append(conf_id)

		#CW for forward
		for i in range(len(servo_ids)/2):
			right_actuator_cluster.append(servo_ids[i])

		#CCW for forward
		for i in range(len(servo_ids)/2, len(servo_ids)):
			left_actuator_cluster.append(servo_ids[i])

		self.configurations[conf_id] = Car_configuration(left_actuator_cluster, right_actuator_cluster, self.net)

	def move_configuration(self, speed, turn, conf_id):
		self.configurations[conf_id].reset_speed()
		if(speed > 0):
			self.configurations[conf_id].add_move_forward(speed)
		elif(speed < 0):
			self.configurations[conf_id].add_move_backward(abs(speed))

		if(turn > 0):
			self.configurations[conf_id].add_turn_right(turn)
		elif (turn < 0):
			self.configurations[conf_id].add_turn_left(abs(turn))

		self.net.synchronize()

	def restart_program(self):
		python = sys.executable
		os.execl(python, python, * sys.argv)

	def return_name_packet(self):
		name_packet={}
		name_packet["name"] = self.name
		return name_packet

	def establish_connection(self,errorlog, server_conn, num_conn_attempts, conn_attempt_delay):
		if num_conn_attempts <= 0:
			while (not self.connected):
				try:
					self.clientsocket.connect(server_conn)
					self.clientsocket.send(json.dumps(self.return_name_packet()))
					self.connected = True
				except:
					errorlog.write("ERROR: Failed to connect to remote server, retrying")
					printdt("ERROR: Failed to connect to remote server, retrying")
				time.sleep(conn_attempt_delay)
		else:
			for i in range(num_conn_attempts):
				try:
					self.clientsocket.connect(server_conn)
					self.clientsocket.send(json.dumps(self.return_name_packet()))
					self.connected = True
					break;
				except:
					errorlog.write("ERROR: Failed to connect to remote server, retrying")
					printdt("ERROR: Failed to connect to remote server, retrying")
				time.sleep(conn_attempt_delay)

	def send_reply_message(self, status, message):
		status_packet={}
		status_packet["status"] = status
		status_packet["message"] = message
		self.clientsocket.send(json.dumps(status_packet))

def printdt(string):
		print ("Date: " + time.strftime("%d/%m/%Y") + 
			"\nTime: " + time.strftime("%H:%M:%S") + 
			"\n" + string + "\n")