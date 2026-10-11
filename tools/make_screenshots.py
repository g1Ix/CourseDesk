"""Create project screenshots from fictional data in an isolated profile."""
import json
import os
import sys
from datetime import date,timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
profile=ROOT/'build/screenshot-profile'
os.environ['COURSEDESK_DATA_DIR']=str(profile)
os.environ['COURSEDESK_NO_OS_ACTIONS']='1'
from course_data import save_schedule,save_prefs,DEFAULT_PREFS,monday
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QLabel
from course_ui import MainWindow

example=json.loads((ROOT/'examples/demo-schedule.json').read_text(encoding='utf-8'))
save_schedule(example);save_prefs(DEFAULT_PREFS)
app=QApplication([]);app.setStyle('Fusion')
if sys.platform=='win32':QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
window=MainWindow();window.resize(1420,920);window.show()
dest=ROOT/'docs/screenshots';dest.mkdir(parents=True,exist_ok=True)

def capture_home():
    window.prefs['theme']='light';window.apply_theme();window.refresh();window.navigate(0)
    app.processEvents();window.grab().save(str(dest/'home-light.png'))
    window.prefs['theme']='dark';window.apply_theme();window.selected_week=monday(date.today()+timedelta(days=1));window.refresh();window.navigate(1)
    QTimer.singleShot(400,capture_week)

def capture_week():
    window.grab().save(str(dest/'week-dark.png'))
    window.prefs['theme']='light';window.apply_theme();window.navigate(4)
    scroll=window.pages.widget(4);scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
    QTimer.singleShot(300,capture_about)

def capture_about():
    for label in window.settings_page.findChildren(QLabel):
        if label.text()==str(profile):label.setText('%LOCALAPPDATA%\\CourseDesk（独立演示数据目录）')
    window.grab().save(str(dest/'about.png'))
    window.exiting=True;window.close();app.quit()

QTimer.singleShot(500,capture_home)
raise SystemExit(app.exec())
