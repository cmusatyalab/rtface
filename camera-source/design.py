# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'design.ui'
#
# Created: Sun Jun 12 17:49:00 2016
#      by: PyQt4 UI code generator 4.10.4
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

try:
    _encoding = QtGui.QApplication.UnicodeUTF8
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName(_fromUtf8("MainWindow"))
        MainWindow.resize(1026, 675)
        self.centralwidget = QtGui.QWidget(MainWindow)
        self.centralwidget.setObjectName(_fromUtf8("centralwidget"))
        self.horizontalLayout = QtGui.QHBoxLayout(self.centralwidget)
        self.horizontalLayout.setObjectName(_fromUtf8("horizontalLayout"))
        self.label_image = QtGui.QLabel(self.centralwidget)
        self.label_image.setObjectName(_fromUtf8("label_image"))
        self.horizontalLayout.addWidget(self.label_image)
        self.verticalLayout = QtGui.QVBoxLayout()
        self.verticalLayout.setContentsMargins(-1, -1, -1, 20)
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
        self.label = QtGui.QLabel(self.centralwidget)
        self.label.setObjectName(_fromUtf8("label"))
        self.verticalLayout.addWidget(self.label)
        self.textEdit = QtGui.QTextEdit(self.centralwidget)
        self.textEdit.setObjectName(_fromUtf8("textEdit"))
        self.verticalLayout.addWidget(self.textEdit)
        self.button_train = QtGui.QPushButton(self.centralwidget)
        self.button_train.setObjectName(_fromUtf8("button_train"))
        self.verticalLayout.addWidget(self.button_train)
        self.label_trainedpeople = QtGui.QLabel(self.centralwidget)
        self.label_trainedpeople.setObjectName(_fromUtf8("label_trainedpeople"))
        self.verticalLayout.addWidget(self.label_trainedpeople)
        self.groupBox_trainedpeople = QtGui.QGroupBox(self.centralwidget)
        self.groupBox_trainedpeople.setMinimumSize(QtCore.QSize(0, 400))
        self.groupBox_trainedpeople.setTitle(_fromUtf8(""))
        self.groupBox_trainedpeople.setObjectName(_fromUtf8("groupBox_trainedpeople"))
        self.verticalLayout.addWidget(self.groupBox_trainedpeople)
        self.button_blur = QtGui.QPushButton(self.centralwidget)
        self.button_blur.setObjectName(_fromUtf8("button_blur"))
        self.verticalLayout.addWidget(self.button_blur)
        self.button_delete = QtGui.QPushButton(self.centralwidget)
        self.button_delete.setObjectName(_fromUtf8("button_delete"))
        self.verticalLayout.addWidget(self.button_delete)
        self.horizontalLayout.addLayout(self.verticalLayout)
        MainWindow.setCentralWidget(self.centralwidget)
        self.statusbar = QtGui.QStatusBar(MainWindow)
        self.statusbar.setObjectName(_fromUtf8("statusbar"))
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(_translate("MainWindow", "MainWindow", None))
        self.label_image.setText(_translate("MainWindow", "Image", None))
        self.label.setText(_translate("MainWindow", "Please Enter a Name", None))
        self.button_train.setText(_translate("MainWindow", "Train", None))
        self.label_trainedpeople.setText(_translate("MainWindow", "Trained People", None))
        self.button_blur.setText(_translate("MainWindow", "Whitelist", None))
        self.button_delete.setText(_translate("MainWindow", "Delete", None))

