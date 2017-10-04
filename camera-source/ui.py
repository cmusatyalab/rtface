#!/usr/bin/env python

from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import QThread, SIGNAL, pyqtSignal
from PyQt4.QtGui import QPixmap, QImage, QMessageBox, QVBoxLayout
import threading
import sys  # We need sys so that we can pass argv to QApplication

import design  # This file holds our MainWindow and all design related things
# it also keeps events etc that we defined in Qt Designer
import os  # For listing directory methods
from client import Controller
import numpy as np
import re
import pdb

class ControllerThread(QThread):
    sig_frame_available = pyqtSignal(object)
    sig_server_info_available = pyqtSignal(object)    
    
    def __init__(self):
        super(self.__class__, self).__init__()
        
        self.controller=Controller()
        self._stop = threading.Event()        

    def run(self):
        self.controller.recv(self.sig_frame_available, self.sig_server_info_available)

    def stop(self):
        self.Controller.alive=False
        self._stop.set()

controllerThread = ControllerThread()
class UI(QtGui.QMainWindow, design.Ui_MainWindow):
    def __init__(self):
        # Explaining super is out of the scope of this article
        # So please google it if you're not familar with it
        # Simple reason why we use it here is that it allows us to
        # access variables, methods etc in the design.py file
        super(self.__class__, self).__init__()
        self.setupUi(self)  # This is defined in design.py file automatically

        # It sets up layout and widgets that are defined
        self.button_blur.clicked.connect(self.generate_whitelist)
        self.button_delete.clicked.connect(self.delete)        
        self.button_train.setCheckable(True)
        self.button_train.clicked.connect(self.toggle_train)
        self.vbox_trainedpeople = QVBoxLayout()
        self.groupBox_trainedpeople.setFlat(True)
        self.groupBox_trainedpeople.setLayout(self.vbox_trainedpeople)
        self.name_list=[]
        
        # self.frame=None
        # self.timer = QtCore.QTimer()
        # self.timer.timeout.connect(self.nextFrameSlot)
        # self.timer.start(1000./1) # fps = 10
        
    # def nextFrameSlot(self):
    #    if self.frame != None:
    #        img = QImage(self.frame, self.frame.shape[1], self.frame.shape[0], QtGui.QImage.Format_RGB888)
    #        pix = QPixmap.fromImage(img)
    #        print 'frame {} image {} pix {}'.format(self.frame, img, pix)
    #        self.label_image.setPixmap(pix)           

    def only_char(self, strg, search=re.compile(r'[^a-zA-Z0-9.]').search):
        return not bool(search(strg))    

    def get_name(self):
        name=str(self.textEdit.toPlainText())
        if len(name)>0 and self.only_char(name):
            self.textEdit.clear()
            return name
        else:
            return None

    def add_name_to_ui(self,name):
        if name not in self.name_list:
            cb =  QtGui.QCheckBox(name)
            self.vbox_trainedpeople.addWidget(cb)
            self.name_list.append(name)
            
    def toggle_train(self):
        # if not in training
        print 'train clicked'
        if not controllerThread.controller.is_training:
            name=self.get_name()
            print 'add training {}'.format(name)
            if name != None:
                controllerThread.controller.start_train(name)
                self.button_train.setChecked(True)                
            else:
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Critical)
                msg.setText("Please Enter a valid name (only characters allowed)")
                msg.setWindowTitle("Error")
                msg.exec_()
                self.button_train.setChecked(False)                            
        else:
            added_name=controllerThread.controller.stop_train()
            print 'training stopped. add name: {}'.format(added_name)
            self.add_name_to_ui(added_name)
            self.button_train.setChecked(False)            
    
    def set_image(self, frame):
        img = QImage(frame, frame.shape[1], frame.shape[0], QtGui.QImage.Format_RGB888)
        pix = QPixmap.fromImage(img)
        self.label_image.setPixmap(pix)           

    def init_name_list(self, name_list):
        print 'name list {}'.format(name_list)
        for name in name_list:
            self.add_name_to_ui(str(name))
        
    def get_people_selected(self):
        cnt=self.vbox_trainedpeople.count()
        texts=[]
        items=[]
        for i in range(0,cnt):
            item=self.vbox_trainedpeople.itemAt(i)
            widget=item.widget()
            if widget.isChecked():
                items.append(item)
                texts.append(str(widget.text()))
        return items, texts
        
    def generate_whitelist(self):
        _, controllerThread.controller.whitelist=self.get_people_selected()
        controllerThread.controller.set_whitelist(controllerThread.controller.whitelist)
        print 'client new whitelist: {}'.format(controllerThread.controller.whitelist)

    def delete(self):
        rm_items,rm_list=self.get_people_selected()
        for item in rm_items:
            if item is not None:
                item.widget().close()
                self.vbox_trainedpeople.removeItem(item)

        for name in rm_list:
            self.name_list.remove(name)
            controllerThread.controller.remove_person(name)

        new_whitelist=set(controllerThread.controller.whitelist) - set(rm_list)
        controllerThread.controller.whitelist=list(new_whitelist)
        controllerThread.controller.set_whitelist(controllerThread.controller.whitelist)        
        
def main():
    global controllerThread
    app = QtGui.QApplication(sys.argv)
    ui = UI()        
    ui.show()
    controllerThread.sig_server_info_available.connect(ui.init_name_list)        
    controllerThread.sig_frame_available.connect(ui.set_image)
    controllerThread.finished.connect(app.exit)
    controllerThread.start()
    
    sys.exit(app.exec_())  # and execute the app

    
if __name__ == '__main__':  # if we're running file directly and not importing it
    main()  # run the main function
