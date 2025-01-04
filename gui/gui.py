import matplotlib
import matplotlib.ticker as ticker

matplotlib.use('Qt5Agg')

from PyQt5 import QtWidgets, uic

from PyQt5.QtCore import (
    QSettings,
    Qt,
    QSize,
    QPoint,
    QTimer,
    QTime,
)

from PyQt5.QtWidgets import (
    QVBoxLayout,
)

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT as NavigationToolbar

from matplotlib.figure import Figure
from datetime import time, datetime

from instruments.instrument import Instrument
from gui.swcccv import SwCCCV
from gui.internal_r import InternalR
from gui.log_control import LogControl
from sys import argv


class MplCanvas(FigureCanvasQTAgg):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super(MplCanvas, self).__init__(self.fig)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)

        uic.loadUi('gui/main.ui', self)
        self.load_settings()

        self.plot_placeholder.setLayout(self.plot_layout())
        self.map_controls()
        self.programmaticalStateChange = False
        self.tab2 = uic.loadUi("gui/settings.ui")
        self.logControl = LogControl()
        self.swCCCV = SwCCCV()
        self.internal_r = InternalR()
        self.controlsLayout.insertWidget(3, self.internal_r)
        self.tab2.layout().addWidget(self.logControl, 0, 0)
        self.tab2.layout().addWidget(self.swCCCV, 1, 0)
        self.tabs.addTab(self.tab2, "Settings")
        self.show()

    def plot_layout(self):
        self.canvas = MplCanvas(self, width=8, height=4, dpi=100)

        self.ax = self.canvas.axes
        self.ax.tick_params(axis='y', colors='blue')

        self.twinaxCurrent = self.ax.twinx()
        self.twinaxCurrent.tick_params(axis='y', colors='red')

        self.twinaxPower = self.ax.twinx()
        self.twinaxPower.tick_params(axis='y', colors='green')
        
        self.twinaxTemp = self.ax.twinx()
        self.twinaxTemp.tick_params(axis='y', colors='grey')
        self.twinaxTemp.yaxis.tick_left()

        toolbar = NavigationToolbar(self.canvas, self)
        layout = QVBoxLayout()
        layout.addWidget(toolbar)
        layout.addWidget(self.canvas)
        return layout

    def map_controls(self):
        self.en_checkbox.stateChanged.connect(self.enabled_changed)
        self.set_voltage.valueChanged.connect(self.voltage_changed)
        self.set_current.valueChanged.connect(self.current_changed)
        self.set_timer.timeChanged.connect(self.timer_changed)
        self.resetButton.clicked.connect(self.reset_dev)

        self.set_voltage_timer = QTimer(singleShot=True,
                                        timeout=self.voltage_set)
        self.set_current_timer = QTimer(singleShot=True,
                                        timeout=self.current_set)
        self.set_timer_timer = QTimer(singleShot=True, timeout=self.timer_set)

    def data_row(self, data, row):
        if data:
            set_voltage = data.lastval('set_voltage')
            if not self.set_voltage.hasFocus():
                self.set_voltage.setValue(set_voltage)

            set_current = data.lastval('set_current')
            if not self.set_current.hasFocus():
                self.set_current.setValue(set_current)

            is_on = data.lastval('is_on')
            if is_on:
                if not self.en_checkbox.isChecked():
                    self.programmaticalStateChange = True
                    self.en_checkbox.setCheckState(Qt.Checked)
            else:
                if self.en_checkbox.isChecked():
                    self.programmaticalStateChange = True
                    self.en_checkbox.setCheckState(Qt.Unchecked)

            voltage = data.lastval('voltage')
            current = data.lastval('current')
            power = round(voltage * current, 3)
            data.setlastval('power', power)
            self.setWindowTitle("Battery tester {:4.2f}V {:4.2f}A ".format(
                voltage, current))
            self.readVoltage.setText("<pre>{:5.3f} V</pre>".format(voltage))
            self.readCurrent.setText("<pre>{:5.3f} A</pre>".format(current))
            self.readCapAH.setText("<pre>{:5.3f} Ah</pre>".format(data.lastval('cap_ah')))
            self.readCapWH.setText("<pre>{:5.3f} Wh</pre>".format(data.lastval('cap_wh')))
            self.readTemp.setText("<pre>" + str(int(data.lastval('temp'))) + "°C / " + str(int(data.lastval('temp') * 1.8 + 32)) + "°F</pre>")
            self.Wattage.setText("<pre>{:5.3f} W</pre>".format(power))
            self.readTime.setText("<pre>" + data.lastval('time').strftime("%H:%M:%S") + "</pre>")
            # print("TIMER:"+data.lastval('set_timer').strftime("%H:%M:%S")+" Type:" +str(type(data.lastval('set_timer'))))
            # Hour and minutes are not correct assigned in data.lastval('set_timer') Hour = Minute, Minute = second. Fix it here.
            if not self.set_timer.hasFocus():
                ReadHours=int(data.lastval('set_timer').seconds / 3600)
                # (All Seconds - Hours in seconds) / 60
                ReadMinutes=int((data.lastval('set_timer').seconds - (ReadHours*3600)) /60)
                # print("TYPE:" +  str(type(data.lastval('set_timer')))+ " ATTR:" + str(dir(data.lastval('set_timer'))) + "HOURS:" + str(ReadHours) +  " MINUTES:" +str(ReadMinutes) )                
                self.set_timer.setTime(QTime(ReadHours,ReadMinutes,0))
            xlim = (time(0), max([time(0, 1, 0), data.lastval('time')]))
            # clear axes
            self.ax.cla()
            self.twinaxCurrent.cla()
            self.twinaxPower.cla()
            self.twinaxTemp.cla()
            # print cell label as graph title
            self.ax.set_title(self.cellLabel.text() + " (" + datetime.today().strftime('%Y-%m-%d') + ")")
            
            # left Y-axis (voltage)
            data.plot(ax=self.ax, x='time', y=['voltage'], color='blue', xlim=xlim)
            #self.ax.set_ylabel('Voltage, V')
            self.ax.set_ylim(bottom=set_voltage)
            # add units to y axes
            self.ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('%.1fV'))

            # right Y-axis 1 (current)
            data.plot(ax=self.twinaxCurrent, x='time', y=['current'], style='r')
            self.twinaxCurrent.set_ylim(bottom=0)
            self.twinaxCurrent.get_legend().remove()
            self.twinaxCurrent.yaxis.set_major_formatter(ticker.FormatStrFormatter('%.1fA'))

            # right Y-axis 2 (power)
            if self.checkbox_p.isChecked():
                self.twinaxPower.spines.right.set_position(("axes", 1.1))
                data.plot(ax=self.twinaxPower, x='time', y=['power'], color='green')
                self.twinaxPower.set_ylim(bottom=0)
                self.twinaxPower.get_legend().remove()
                self.twinaxPower.yaxis.set_major_formatter(ticker.FormatStrFormatter('%.1f W'))
            else:
                self.twinaxPower.get_yaxis().set_visible(False)

            # left Y-axis 2 (temperature)
            if self.checkbox_t.isChecked():
                self.twinaxTemp.spines.left.set_position(("axes", -0.1))
                data.plot(ax=self.twinaxTemp, x='time', y=['temp'], color='grey')
                self.twinaxTemp.set_ylim(bottom=20)
                self.twinaxTemp.get_legend().remove()
                self.twinaxTemp.yaxis.set_major_formatter(ticker.FormatStrFormatter('%.0f°'))
            else:
                self.twinaxTemp.get_yaxis().set_visible(False)

            # legend
            lines1, labels1 = self.ax.get_legend_handles_labels()
            lines2, labels2 = self.twinaxCurrent.get_legend_handles_labels()
            lines3, labels3 = self.twinaxPower.get_legend_handles_labels()
            lines4, labels4 = self.twinaxTemp.get_legend_handles_labels()
            self.ax.legend(lines1 + lines2 + lines3 + lines4, labels1 + labels2 + labels3 + labels4, loc='lower left')

            #self.canvas.fig.subplots_adjust(right=1)
            self.canvas.fig.tight_layout()  # fit graph/canvas/figure into available space nicely
            
            self.canvas.draw()

    def status_update(self, status):
        self.statusBar().showMessage(status)

    def set_backend(self, backend):
        self.backend = backend
        backend.subscribe(self)
        self.swCCCV.set_backend(backend)
        self.internal_r.set_backend(backend)

    def closeEvent(self, event):
        self.logControl.save_settings()
        self.swCCCV.save_settings()
        self.internal_r.save_settings()
        self.save_settings()
        self.write_logs()

        self.backend.at_exit()
        event.accept()

    def enabled_changed(self):
        if not self.programmaticalStateChange: 
            value = self.en_checkbox.isChecked()
            self.en_checkbox.clearFocus()
            self.backend.send_command({Instrument.COMMAND_ENABLE: value})
        else:
            self.programmaticalStateChange = False


    def voltage_changed(self):
        if self.set_voltage.hasFocus():
            self.set_voltage_timer.start(1000)

    def voltage_set(self):
        value = round(self.set_voltage.value(), 2)
        self.set_voltage.clearFocus()
        self.backend.send_command({Instrument.COMMAND_SET_VOLTAGE: value})

    def current_changed(self):
        if self.set_current.hasFocus():
            self.set_current_timer.start(1000)

    def current_set(self):
        value = round(self.set_current.value(), 2)
        self.set_current.clearFocus()
        self.backend.send_command({Instrument.COMMAND_SET_CURRENT: value})

    def timer_changed(self):
        if self.set_timer.hasFocus():
            self.set_timer_timer.start(1000)

    def timer_set(self):
        set_time = self.set_timer.time()
        value = time(set_time.hour(), set_time.minute(), set_time.second())
        self.set_timer.clearFocus()
        self.backend.send_command({Instrument.COMMAND_SET_TIMER: value})


    def reset_dev(self, s):
        self.resetButton.clearFocus()
        self.write_logs()
        self.swCCCV.reset()
        self.internal_r.reset()
        self.backend.datastore.reset()
        self.backend.send_command({Instrument.COMMAND_RESET: 0.0})

    def load_settings(self):
        settings = QSettings()

        self.resize(settings.value("MainWindow/size", QSize(1024, 600)))
        self.move(settings.value("MainWindow/pos", QPoint(0, 0)))
        self.cellLabel.setText(settings.value("MainWindow/cellLabel", 'Cell x'))
        self.checkbox_t.setCheckState(Qt.Checked if settings.value("MainWindow/checkbox_t", True) == 'true'  else Qt.Unchecked)
        self.checkbox_p.setCheckState(Qt.Checked if settings.value("MainWindow/checkbox_p", True) == 'true'  else Qt.Unchecked)


    def write_logs(self):
        if self.logControl.isChecked():
            self.internal_r.write(self.logControl.full_path,
                                  self.cellLabel.text())
            self.backend.datastore.write(self.logControl.full_path,
                                         self.cellLabel.text())

    def save_settings(self):
        settings = QSettings()

        settings.setValue("MainWindow/size", self.size())
        settings.setValue("MainWindow/pos", self.pos())
        settings.setValue("MainWindow/cellLabel", self.cellLabel.text())
        settings.setValue("MainWindow/checkbox_t", self.checkbox_t.isChecked())
        settings.setValue("MainWindow/checkbox_p", self.checkbox_p.isChecked())
        settings.sync()


class GUI:
    def __init__(self, backend):
        app = QtWidgets.QApplication(argv)
        self.window = MainWindow()
        self.window.set_backend(backend)
        app.exec_()
