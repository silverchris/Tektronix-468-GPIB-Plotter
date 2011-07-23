#!/usr/bin/python
# -*- coding: utf-8 -*-
import wx
import os
import re
import struct
import serial
import cStringIO
import sys
import pickle
import threading
from wx.lib.floatcanvas import NavCanvas, FloatCanvas

import matplotlib
matplotlib.use('WXAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigCanvas, NavigationToolbar2WxAgg as NavigationToolbar
 
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
		'ENCDG':message[12],'BN.FMT':message[13],'BYT/NR':message[14],'BIT/NR':message[15], 'TIME/DIV':time_div, 'Y':y_values,'X':x_values}
 

try:
	configfile = open("config.ini", 'r')
	config = pickle.load(configfile)
	configfile.close()
	serialsettings = config
except:
	serialsettings = {}
	serialsettings['port'] = "COM1"
	serialsettings['speed'] = "9600"

serialports = []
if sys.platform == "win32":
	import serialprobewin32
	for order, port, desc, hwid in sorted(serialprobewin32.comports()):
		try:
			serial.Serial(port) # test open
		except serial.serialutil.SerialException:
			pass
		else:
			serialports.append(port)

elif sys.platform == "linux2":
	import glob
	"""scan for available ports. return a list of device names."""
	serialports = glob.glob('/dev/ttyS*') + glob.glob('/dev/ttyUSB*')


SERIALRX = wx.NewEventType()
# bind to serial data receive events
EVT_SERIALRX = wx.PyEventBinder(SERIALRX, 0)

class SerialRxEvent(wx.PyCommandEvent):
	eventType = SERIALRX
	def __init__(self, windowID, data):
		wx.PyCommandEvent.__init__(self, self.eventType, windowID)
		self.data = data

	def Clone(self):
		self.__class__(self.GetId(), self.data)

class config_dialog(wx.Dialog):
	def __init__(self, parent, id, title):
		wx.Dialog.__init__(self, parent, id, title, size=(280, 200))
		panel = wx.Panel(self, -1)
		self.parent = parent
		vbox = wx.BoxSizer(wx.VERTICAL)

		wx.StaticBox(panel, -1, 'Serial Port Configuration', (5, 5), (270, 120))
		wx.StaticText(panel, -1, 'Serial Port', (15, 30))
		self.port = wx.ComboBox(panel, -1, pos=(100, 30), size=(150, -1), choices=serialports, style=wx.CB_READONLY, value=serialsettings['port'])
		wx.StaticText(panel, -1, 'Speed', (15, 60))
		self.speed = wx.TextCtrl(panel, -1, serialsettings['speed'], (100, 60))

		hbox = wx.BoxSizer(wx.HORIZONTAL)
		okButton = wx.Button(self, 1, 'Ok', size=(70, 30))
		closeButton = wx.Button(self, 2, 'Cancel', size=(70, 30))
		hbox.Add(okButton, 1)
		hbox.Add(closeButton, 1, wx.LEFT, 5)

		vbox.Add(panel)
		vbox.Add(hbox, 1, wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, 10)

		self.SetSizer(vbox)
		self.Bind(wx.EVT_BUTTON,self.OnConfig, id=1)
		self.Bind(wx.EVT_BUTTON,self.OnQuit, id=2)

	def OnConfig(self,event):
		try:
			serial.Serial(str(self.port.GetValue())) # test open
		except serial.serialutil.SerialException:
			wx.MessageBox('Can Not Open Serial Port\nPlease Check the port and try again', 'Error')
		else:
			self.parent.serialport = str(self.port.GetValue())
			self.parent.serialspeed = self.speed.GetValue()
			serialsettings['port'] = self.parent.serialport 
			serialsettings['speed'] = self.parent.serialspeed
			self.parent.statusbar.SetStatusText("Port :%s Speed:%s"%(self.parent.serialport,self.parent.serialspeed),1)
			self.Close()

	def OnQuit(self, event):
		self.Close()

ID_CLEAR_BUTTON = wx.NewId()
ID_DELETE_BUTTON = wx.NewId()
ID_CHECKLISTBOX = wx.NewId()
ID_LEGEND_CHECKBOX = wx.NewId()
ID_TIME_DIV = wx.NewId()

class DrawFrame(wx.Frame):
	def __init__(self,parent, id,title,position,size):
		wx.Frame.__init__(self,parent, id,title,position, size)
		self.serialport = serialsettings['port']
		self.serialspeed = serialsettings['speed']
		self.thread = None
		self.alive = threading.Event()    
		menubar = wx.MenuBar()
		self.file = ""
		self.lines = []
		self.legend = 0
		file = wx.Menu()
		file.Append(1, '&Open', 'Open a Existing Plot')
		file.Append(2, '&Connect', 'Connect to GPIB')
		file.Append(3, '&Quit', 'Quit')
		menubar.Append(file, '&File')
		config = wx.Menu()
		config.Append(4, '&Configure', 'Configure Software Settings')
		menubar.Append(config, '&Configure')
		self.SetMenuBar(menubar)
		self.statusbar = self.CreateStatusBar()
		self.statusbar.SetFieldsCount(2)
		self.statusbar.SetStatusWidths([-3,-2])
		self.statusbar.SetStatusText("Port:%s Speed:%s"%(self.serialport,self.serialspeed),1)
		self.Bind(wx.EVT_TOOL, self.OnOpen, id=1)
		self.Bind(wx.EVT_TOOL, self.OnConnect, id=2)
		self.Bind(wx.EVT_TOOL, self.OnQuit, id=3)
		self.Bind(wx.EVT_TOOL, self.OnConfig, id=4)
		self.Bind(EVT_SERIALRX, self.OnSerialRead)
		self.create_main_panel()
		self.create_toolbar()
		self.Show(True)

	def create_main_panel(self):
		""" Creates the main panel with all the controls on it:
		* mpl canvas
		* mpl navigation toolbar
		* Control panel for interaction
		"""
		self.panel = wx.Panel(self)
		# Create the mpl Figure and FigCanvas objects.
		# 5x4 inches, 100 dots-per-inch

		self.dpi = 100
		self.fig = Figure((5.0, 5.0))
		self.canvas = FigCanvas(self.panel, -1, self.fig)
		
		# Since we have only one plot, we can use add_axes 
		# instead of add_subplot, but then the subplot
		# configuration tool in the navigation toolbar wouldn't
		# work.
		
		self.axes = self.fig.add_subplot(111,yticks=[-5,-4,-3,-2,-1,0,1,2,3,4,5],xticks=[0,1,2,3,4,5,6,7,8,9,10],xlim=[0,17],ylim=[-5,5])
		self.axes.axis([0,17,-5,5])
		self.axes.legend()
		self.axes.grid(1)
		self.canvas.draw()
		# Bind the 'pick' event for clicking on one of the bars
		
		self.canvas.mpl_connect('pick_event', self.on_pick)
		
		# Create the navigation toolbar, tied to the canvas
		#
		self.toolbar = NavigationToolbar(self.canvas)
		#
		# Layout with box sizers
		#
		
		self.vbox = wx.BoxSizer(wx.VERTICAL)
		self.vbox.Add(self.canvas, 1, wx.LEFT | wx.TOP | wx.GROW)
		self.vbox.Add(self.toolbar, 0, wx.EXPAND)
		#self.vbox.AddSpacer(10)
		
		
		self.panel.SetSizer(self.vbox)
		#self.vbox.Fit(self)

	def create_toolbar(self):
		self.tb = self.CreateToolBar(wx.NO_BORDER)
		#self.tb = wx.Panel(self)
		tb = self.tb
		tb.AddControl(wx.Button(tb, ID_CLEAR_BUTTON, "Clear",wx.DefaultPosition, wx.DefaultSize))
		wx.EVT_BUTTON(self, ID_CLEAR_BUTTON, self.clear_plot)
		tb.AddControl(wx.CheckListBox(self.tb, ID_CHECKLISTBOX,size=( 100, 100 ), choices = self.lines, style = wx.LB_HSCROLL ))
		wx.EVT_CHECKLISTBOX (tb, ID_CHECKLISTBOX , self.clickHandler )
		tb.AddControl(wx.Button(tb, ID_DELETE_BUTTON, "Delete Unchecked",wx.DefaultPosition, wx.DefaultSize))
		wx.EVT_BUTTON(self, ID_DELETE_BUTTON, self.delete_lines)
		tb.AddControl(wx.CheckBox(tb, ID_LEGEND_CHECKBOX, 'Legend On'))
		wx.EVT_CHECKBOX(self, ID_LEGEND_CHECKBOX, self.OnLegend)
		#tb.AddControl(wx.StaticText(tb, ID_TIME_DIV, 'Time/Div:', style=wx.ALIGN_LEFT))
		
		#self.vbox.Add(self.tb,1,wx.LEFT|wx.TOP)
		#self.tb.SetSizer(self.vbox)
		self.tb.Realize()
	
	def on_pick(self, event):
		# The event received here is of the type
		# matplotlib.backend_bases.PickEvent
		#
		# It carries lots of information, of which we're using
		# only a small amount here.
		# 
		box_points = event.artist.get_bbox().get_points()
		msg = "You've clicked on a bar with coords:\n %s" % box_points
		
		dlg = wx.MessageDialog(
		self, 
		msg, 
		"Click!",
		wx.OK | wx.ICON_INFORMATION)

		dlg.ShowModal() 
		dlg.Destroy()        

	def on_save_plot(self, event):
		file_choices = "PNG (*.png)|*.png"
		
		dlg = wx.FileDialog(self, message="Save plot as...",defaultDir=os.getcwd(),defaultFile="plot.png",wildcard=file_choices,style=wx.SAVE)
		
		if dlg.ShowModal() == wx.ID_OK:
			path = dlg.GetPath()
			self.canvas.print_figure(path, dpi=self.dpi)
			self.flash_status_message("Saved to %s" % path)
	
	def delete_lines(self,event):
		to_delete = range(self.FindWindowById(ID_CHECKLISTBOX).GetCount())
		print 'To Delete', to_delete
		for line in self.FindWindowById(ID_CHECKLISTBOX).GetChecked():
			print 'Removing Line From to_delete',line
			to_delete.remove(line)
		print 'To Delete',to_delete
		for line in to_delete:
			print 'Deleting Line',line
			del self.axes.lines[line]
		self.FindWindowById(ID_CHECKLISTBOX).Clear()
		print self.axes.lines
		for line in range(len(self.axes.lines)):
			print line
			self.FindWindowById(ID_CHECKLISTBOX).Append('Line %s'%(line+1))
			self.axes.lines[line].set_label('Line %s'%(line+1))
			self.FindWindowById(ID_CHECKLISTBOX).Check(len(self.axes.lines))
		self.OnLegend('event')
		self.canvas.draw()
	
	def clear_plot(self, event):
		self.fig.clear()
		self.axes = self.fig.add_subplot(111,yticks=[-5,-4,-3,-2,-1,0,1,2,3,4,5],xticks=[0,1,2,3,4,5,6,7,8,9,10],xlim=[0,17],ylim=[-5,5])
		self.axes.axis([0,17,-5,5])
		self.axes.grid(1)
		self.FindWindowById(ID_CHECKLISTBOX).Clear()
		self.canvas.draw()
		
	def OnOpen(self, event):
		self.statusbar.SetStatusText('Open .plt file to Cut')
		dlg = wx.FileDialog(self, "Choose a file", os.getcwd(), "", "*", wx.OPEN)
		if dlg.ShowModal() == wx.ID_OK:
			path = dlg.GetPath()
			self.SetStatusText("You selected: %s" % path)
			self.file = path
		dlg.Destroy()
		f = open(path)
		message = f.read()
		self.draw(message)
	
	def OnLegend(self,event):
		self.legend = self.FindWindowById(ID_LEGEND_CHECKBOX).GetValue()
		if self.legend == True:
			self.axes.legend()
			print 'Legend On'
		if self.legend == False:
			print 'Legend Off'
			self.axes.legend_ = None
		self.canvas.draw()
	
	def clickHandler ( self, event ):
		if self.FindWindowById(ID_CHECKLISTBOX).IsChecked(event.GetSelection()) == True:
			self.axes.lines[event.GetSelection()].set_visible(True)
		if self.FindWindowById(ID_CHECKLISTBOX).IsChecked(event.GetSelection()) == False:
			self.axes.lines[event.GetSelection()].set_visible(False)
		self.canvas.draw()
	
	def draw(self,message):
		message = process(message)
		""" Redraws the figure"""
		print message
		self.FindWindowById(ID_CHECKLISTBOX).Append('Line %s'%((len(self.axes.lines)+1)))
		self.FindWindowById(ID_CHECKLISTBOX).Check(len(self.axes.lines))
		self.axes.grid(1)
		self.axes.plot(message['X'],message['Y'],label='%s:%s,%s/DIV, /DIV'%(len(self.axes.lines)+1,message['WFID'],message['TIME/DIV']))
		#self.axes.ylabel('Y Div')
		#self.axes.xlabel('X Div')
		self.axes.axis([0,17,-5,5])

		print 
		self.OnLegend('event')
		self.canvas.draw()
	
	def StartThread(self):
		"""Start the receiver thread"""        
		self.thread = threading.Thread(target=self.ComPortThread)
		self.thread.setDaemon(1)
		self.alive.set()
		self.thread.start()
	
	def OnConnect(self, event):
		self.serial = serial.Serial(self.serialport, int(self.serialspeed), rtscts=0)
		try:
			self.serial.open()
		except serial.SerialException, e:
			dlg = wx.MessageDialog(None, str(e), "Serial Port Error", wx.OK | wx.ICON_ERROR)
			dlg.ShowModal()
			dlg.Destroy()
		else:
			self.StartThread()
	def OnSerialRead(self, event):
		"""Handle input from the serial port."""
		text = event.data
		print text
	
	def OnQuit(self, event):
		self.Close()
    
	def OnConfig(self,event):
		configure = config_dialog(self, -1, 'Configuration')
		configure.ShowModal()
		configure.Destroy()
	

class DemoApp(wx.App):

    def OnInit(self):
        frame = DrawFrame(None, wx.ID_ANY, "Tektronix 468 GBIP Plotter",wx.DefaultPosition,wx.Size(1024,600))

        self.SetTopWindow(frame)

        return True
            
    
if __name__ == "__main__":

    app = DemoApp(0)
    app.MainLoop()
    
try:
	configfile = open("config.ini", 'w')
	config = pickle.dump(serialsettings, configfile)
	configfile.close()
except:
	pass

