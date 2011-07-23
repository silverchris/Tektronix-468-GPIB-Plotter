#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import re
import struct
import matplotlib.pyplot as plt
import serial
import wx
f = open('putty1.log')
message = f.read()

def process(message):
	regex = re.compile('([\w\s/\.,:]+);WFMPRE WFID:([\w\s/|\"]+),NR.PT:(\d+),PT.FMT:(\w+),XINCR:(\d+),XZERO:(\d+),PT.OFF:(\d+),XUNIT:(\w+),YMULT:(\d+),YZERO:(\d+),YOFF:(\d+),YUNIT:(\w+),ENCDG:(\w+),BN.FMT:(\w+),BYT/NR:(\d+),BIT/NR:(\d+),%(.+)+')
	split =re.compile('.+')
	message = regex.findall(message)
	message = message[0]
	data = list(message[16])
	data_new = []
	for number in data:
		data_new.append((struct.unpack_from('B', number))[0])
	data = data_new
	del data[0]
	del data[0]
	del data[int(message[2])]
	x_values = []
	time_div = float(message[4])*500/(10)
	for i in range(len(data)):
		#x_values.append(int(message[5])+int(message[4])*(i-int(message[6])))
		x_values.append(((int(message[4])*i)/time_div))
	y_values = []
	for value in data:
		#y_values.append(int(message[9])+int(message[8])*(int(value)-int(message[10])))
		y_values.append((int(message[9])+int(message[8]))*(int(value)-int(message[10]))/1000.00)
	return {'ID':message[0],'WFID':message[1],'NR.POINTS':message[2],'PT.FMT':message[3],'XINCR':message[4],'XZERO':message[5],
		'PT.OFF':message[6],'XUNIT':message[7],'YMULT':message[8],'YZERO':message[9],'YOFF':message[10],'YUNIT':message[11],
		'ENCDG':message[12],'BN.FMT':message[13],'BYT/NR':message[14],'BIT/NR':message[15], 'TIME/DIV':time_div}

print process(message)
#print 'Scope Version:%s'%message[0]
#print 'Channel Info:%s'%message[1]
#print 'Number of Points:%s'%message[2]
#print 'Point Format:%s'%message[3]
#print 'X Increment:%s'%message[4]
#print 'X Origin:%s'%message[5]
#print 'Point Offset:%s'%message[6]
#print 'X Units:%s'%message[7]
#print 'Y Multiplier:%s'%message[8]
#print 'Y Origin:%s'%message[9]
#print 'Y Value Offset:%s'%message[10]
#print 'Y Units:%s'%message[11]
#print 'Data Encoding:%s'%message[12]
#print 'Binary Format:%s'%message[13]
#print 'Bytes Per Number:%s'%message[14]
#print 'Bits Per Number:%s'%message[15]
#print (25*int(message[8]))
#print int(message[4])*500/(10),message[7]
#plt.plot(x_values,y_values)
#plt.yticks([-5,-4,-3,-2,-1,0,1,2,3,4,5])
#plt.xticks([0,1,2,3,4,5,6,7,8,9,10])
#plt.grid(True)
#plt.axis([0,10,-5,5])
#plt.ylabel('Y Div')
#plt.xlabel('X Div')
#plt.text(-0,-5, '%s, %s%s/Div'%(message[1],time_div,message[7]))
#plt.show()