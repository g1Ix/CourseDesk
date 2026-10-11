from __future__ import annotations
import ctypes,ctypes.wintypes
import copy,csv,json,os,re,subprocess,sys,traceback
from collections import defaultdict
from datetime import date,datetime,timedelta
from pathlib import Path
from PySide6.QtCore import Qt,QDate,QTime,QSize,QRectF,QPointF,QTimer,QThread,Signal,QUrl,QEvent
from PySide6.QtGui import QColor,QPainter,QPen,QFont,QFontDatabase,QPalette,QLinearGradient,QPixmap,QIcon,QDesktopServices,QAction,QKeySequence,QShortcut,QPolygonF
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QFrame,QLabel,QPushButton,QHBoxLayout,QVBoxLayout,QGridLayout,QFormLayout,QLineEdit,QTextEdit,QSpinBox,QComboBox,QDateEdit,QTimeEdit,QCheckBox,QRadioButton,QButtonGroup,QScrollArea,QStackedWidget,QDialog,QFileDialog,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QProgressBar,QMenu,QSystemTrayIcon)
from course_data import *
from course_style import LIGHT,DARK,COLORS,icon,Switch,stylesheet,AnimatedButton
from course_system import update_task,show_notification,notification_text,powershell,hidden_options
from course_import import ocr_pages_to_rows
from course_window import FramelessMainWindow,FramelessDialog,WindowTitleBar
from course_greetings import GreetingDeck

def text(value,name=None,wrap=False):
    w=QLabel(str(value));w.setWordWrap(wrap)
    if name:w.setObjectName(name)
    return w
def btn(title,kind=None,glyph=None,callback=None):
    w=AnimatedButton(title);w.setCursor(Qt.PointingHandCursor)
    inferred=next((g for word,g in [('删除','trash'),('保存','check'),('确认','check'),('添加','plus'),('新增','plus'),('导出','download'),('下载','download'),('导入','upload'),('编辑','edit'),('设置','settings'),('关闭','close'),('取消','close'),('返回','left'),('清空','trash'),('识别','spark'),('本周','calendar'),('全部','calendar'),('单周','calendar'),('双周','calendar'),('课表','calendar'),('查看','book')] if word in title),'dots')
    w.setProperty('motionGlyph',glyph or inferred);w.setProperty('motionDanger',any(word in title for word in ('删除','清空')))
    accessible=title.strip() or {'left':'上一周','right':'下一周'}.get(glyph,'操作')
    w.setToolTip(accessible);w.setAccessibleName(accessible)
    if kind:w.setObjectName(kind)
    if glyph:w.setIcon(icon(glyph,'#FFFFFF' if kind=='Primary' else '#667F78',18));w.setIconSize(QSize(18,18))
    if callback:w.clicked.connect(callback)
    return w
def vlayout(w=None,margins=(0,0,0,0),spacing=12):
    l=QVBoxLayout(w.content if isinstance(w,FramelessDialog) else w);l.setContentsMargins(*margins);l.setSpacing(spacing);return l
def hlayout(w=None,margins=(0,0,0,0),spacing=10):
    l=QHBoxLayout(w);l.setContentsMargins(*margins);l.setSpacing(spacing);return l
def card():
    w=QFrame();w.setObjectName('Card');return w
def clear_layout(layout):
    while layout.count():
        item=layout.takeAt(0)
        if item.widget():item.widget().hide();item.widget().deleteLater()
        elif item.layout():clear_layout(item.layout())
def qdate(day):return QDate(day.year,day.month,day.day)
def pydate(q):return date(q.year(),q.month(),q.day())
def page_header(title,subtitle):
    w=QWidget();l=vlayout(w,spacing=5);l.addWidget(text(title,'Heading'));l.addWidget(text(subtitle,'Muted'));return w
def make_scroll(content):
    scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QFrame.NoFrame);scroll.setObjectName('PageScroll');scroll.viewport().setObjectName('ScrollViewport');content.setProperty('scrollContent',True);scroll.setWidget(content);return scroll
def font(size,bold=False):
    f=QFont('Microsoft YaHei UI');f.setPixelSize(size);f.setBold(bold);return f

class Job(QThread):
    done=Signal(object);failed=Signal(str)
    def __init__(self,work,parent):super().__init__(parent);self.work=work
    def run(self):
        try:self.done.emit(self.work())
        except Exception as exc:self.failed.emit(str(exc))

class NoticeDialog(FramelessDialog):
    def __init__(self,parent,title,body,action='知道了',confirm=False,danger=False):
        super().__init__(parent);self.setWindowTitle(title);self.setFixedWidth(440)
        l=vlayout(self,(28,24,28,24),18)
        glyph=text('');glyph.setPixmap(icon('trash' if danger else 'info', '#C7524D' if danger else '#177D72',36).pixmap(36,36));l.addWidget(glyph)
        l.addWidget(text(title,'Section'));l.addWidget(text(body,'Muted',True));l.addSpacing(4)
        row=hlayout();row.addStretch()
        if confirm:row.addWidget(btn('取消',callback=self.reject))
        row.addWidget(btn(action,'Danger' if danger else 'Primary',callback=self.accept));l.addLayout(row)

class ScopeDialog(FramelessDialog):
    def __init__(self,parent,delete=False):
        super().__init__(parent);self.setWindowTitle('删除范围' if delete else '修改范围');self.setFixedWidth(470)
        self.scope='one';l=vlayout(self,(28,24,28,24),14)
        l.addWidget(text('这次调整，应用到哪里？','Section'));l.addWidget(text('这是一门重复课程，请选择需要调整的安排。','Muted'))
        self.group=QButtonGroup(self)
        for i,(key,title,sub) in enumerate([('one','仅本次课程','其他日期的安排保持当前状态'),('future','从这一天起','应用到所选日期及之后的同一课程'),('all','全部上课周次','应用到这条课程安排的所有周次')]):
            c=card();cl=vlayout(c,(15,12,15,12),5);r=QRadioButton(title);r.setChecked(i==0);self.group.addButton(r,i);cl.addWidget(r);cl.addWidget(text(sub,'Muted'));l.addWidget(c)
        row=hlayout();row.addStretch();row.addWidget(btn('取消',callback=self.reject));row.addWidget(btn('确认删除' if delete else '应用修改','Danger' if delete else 'Primary',callback=self.accept));l.addLayout(row)
    def accept(self):self.scope=['one','future','all'][self.group.checkedId()];super().accept()

class CourseDialog(FramelessDialog):
    def __init__(self,app,record=None,day=None,period=1):
        super().__init__(app);self.owner=app;self.record=record;self.setWindowTitle('编辑课程' if record else '添加课程');self.setMinimumWidth(590)
        self.delete_requested=False;day=day or date.today();r=record or {};self.setModal(True)
        l=vlayout(self,(28,24,28,24),16)
        l.addWidget(text('编辑课程' if record else '添加一门课程','Heading'));l.addWidget(text('填写课程信息，让课表与提醒一起更新。','Muted'))
        grid=QGridLayout();grid.setHorizontalSpacing(16);grid.setVerticalSpacing(6)
        self.name=QLineEdit(r.get('course',''));self.name.setPlaceholderText('例如：数据结构')
        self.teacher=QLineEdit(r.get('teacher',''));self.teacher.setPlaceholderText('授课教师（选填）')
        self.room=QLineEdit(r.get('room',''));self.room.setPlaceholderText('教学楼 / 教室（选填）')
        for i,(title,w) in enumerate([('课程名称',self.name),('教师',self.teacher),('教室',self.room)]):
            grid.addWidget(text(title,'Muted'),i*2,0,1,2);grid.addWidget(w,i*2+1,0,1,2)
        self.begin=QSpinBox();self.begin.setRange(1,14);self.begin.setValue(int(r.get('period_start',period)))
        self.end=QSpinBox();self.end.setRange(1,14);self.end.setValue(int(r.get('period_end',min(14,period+1))))
        grid.addWidget(text('开始节次','Muted'),6,0);grid.addWidget(text('结束节次','Muted'),6,1);grid.addWidget(self.begin,7,0);grid.addWidget(self.end,7,1);l.addLayout(grid)
        self.mode=QComboBox();self.mode.addItems(['每周重复','单次 / 临时课程']);self.mode.setCurrentIndex(0 if not record or 'weekday' in record else 1)
        line=hlayout();line.addWidget(text('安排方式','Muted'));line.addStretch();line.addWidget(self.mode);l.addLayout(line)
        self.options=QStackedWidget();self.repeat=QWidget();rl=vlayout(self.repeat,spacing=10)
        self.weekday=QComboBox();self.weekday.addItems([f'星期{x}' for x in WEEKDAYS]);self.weekday.setCurrentIndex(int(r.get('weekday',day.weekday())))
        rl.addWidget(self.weekday);wr=hlayout();wr.addWidget(text('上课周次','Muted'));wr.addStretch()
        for title,mode in [('全部','all'),('单周','odd'),('双周','even')]:wr.addWidget(btn(title,'Ghost',callback=lambda _=False,m=mode:self.select_weeks(m)))
        rl.addLayout(wr);self.week_buttons=[];wg=QGridLayout();wg.setSpacing(7)
        for i in range(1,total_weeks(app.data)+1):
            actual=displayed_week(app.data,i);b=btn(str(actual));b.setCheckable(True);b.setFixedSize(44,34)
            b.setStyleSheet('QPushButton:checked{background:#177D72;color:white;border-color:#177D72;}')
            default_weeks=[week_number(parse_date(app.data['term']['start']),day)] if record else list(range(1,total_weeks(app.data)+1))
            b.setChecked(i in r.get('weeks',default_weeks));b.setProperty('week',i);self.week_buttons.append(b);wg.addWidget(b,(i-1)//9,(i-1)%9)
        week_panel=QWidget();week_panel.setLayout(wg);week_scroll=make_scroll(week_panel);week_scroll.setMaximumHeight(170);week_scroll.setMinimumHeight(min(170,((total_weeks(app.data)+8)//9)*44));rl.addWidget(week_scroll);rl.addWidget(text('数字为课表中的实际周次，可选择不连续的上课周。','Caption',True))
        self.once=QWidget();ol=vlayout(self.once,spacing=6);ol.addWidget(text('上课日期','Muted'));self.day=QDateEdit(qdate(day));self.day.setCalendarPopup(True);self.day.setDisplayFormat('yyyy-MM-dd');self.day.setDateRange(qdate(parse_date(app.data['term']['start'])),qdate(parse_date(app.data['term']['end'])));ol.addWidget(self.day)
        self.options.addWidget(self.repeat);self.options.addWidget(self.once);self.options.setCurrentIndex(self.mode.currentIndex());self.mode.currentIndexChanged.connect(self.options.setCurrentIndex);l.addWidget(self.options)
        self.notes=QLineEdit(r.get('notes',''));self.notes.setPlaceholderText('备注：带实验报告、提前到教室等（选填）');l.addWidget(self.notes)
        self.error=text('','Error',True);l.addWidget(self.error)
        row=hlayout()
        if record:row.addWidget(btn('删除课程','Danger','trash',self.delete))
        row.addStretch();row.addWidget(btn('取消',callback=self.reject));row.addWidget(btn('保存课程','Primary','check',self.accept));l.addLayout(row)
        self.name.setFocus()
    def select_weeks(self,mode):
        for b in self.week_buttons:
            actual=displayed_week(self.owner.data,b.property('week'));b.setChecked(mode=='all' or actual%2==(1 if mode=='odd' else 0))
    def value(self):
        r={'course':self.name.text().strip(),'teacher':self.teacher.text().strip(),'room':self.room.text().strip(),'notes':self.notes.text().strip(),'period_start':self.begin.value(),'period_end':self.end.value()}
        if self.mode.currentIndex()==0:r.update(weekday=self.weekday.currentIndex(),weeks=[b.property('week') for b in self.week_buttons if b.isChecked()])
        return r
    def accept(self):
        r=self.value()
        if not r['course'] or r['course']=='待校对课程':self.error.setText('请填写课程名称。');return
        if r['period_end']<r['period_start']:self.error.setText('结束节次不能早于开始节次。');return
        if 'weeks' in r and not r['weeks']:self.error.setText('请选择至少一个上课周次。');return
        super().accept()
    def delete(self):self.delete_requested=True;self.reject()

class CalendarCanvas(QWidget):
    edit=Signal(object,object);add=Signal(object,int)
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.data=owner.data;self.prefs=owner.prefs;self.week=monday(date.today());self.setMouseTracking(True);self.hits=[];self.hover=None;self.rowheight=72;self.header=82
    def set_calendar(self,data,prefs,week):
        self.data=data;self.prefs=prefs;self.week=week;self.count=max(int(prefs['period_count']),max((r['period_end'] for _,r in occurrences(data)),default=8));self.setMinimumHeight(self.header+self.count*self.rowheight+18);self.update()
    def colors(self,row):
        fg,bg=COLORS[color_index(row)]
        if self.owner.dark:bg=QColor(fg).darker(245).name();fg=QColor(fg).lighter(175).name()
        return fg,bg
    def paintEvent(self,event):
        t=self.owner.theme;p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.fillRect(self.rect(),QColor(t['panel']));days=7 if self.prefs['show_weekends'] else 5
        gutter=62;cw=(self.width()-gutter-10)/days;self.hits=[]
        p.setPen(QColor(t['muted']));p.setFont(font(11));p.drawText(QRectF(8,15,46,52),Qt.AlignCenter,'节次')
        for j in range(days):
            day=self.week+timedelta(days=j);x=gutter+j*cw
            if day==date.today():p.setPen(Qt.NoPen);p.setBrush(QColor(t['soft']));p.drawRoundedRect(QRectF(x+6,8,cw-12,self.header-16),12,12)
            p.setPen(QColor(t['accent'] if day==date.today() else t['muted']));p.setFont(font(11));p.drawText(QRectF(x,17,cw,19),Qt.AlignCenter,f'星期{WEEKDAYS[j]}')
            p.setFont(font(21,True));p.setPen(QColor(t['accent'] if day==date.today() else t['ink']));p.drawText(QRectF(x,39,cw,27),Qt.AlignCenter,f'{day.month:02d}.{day.day:02d}')
        pen=QPen(QColor(t['line']));pen.setWidthF(1);p.setPen(pen)
        for j in range(days+1):p.drawLine(QPointF(gutter+j*cw,self.header),QPointF(gutter+j*cw,self.header+self.count*self.rowheight))
        for i in range(self.count+1):p.drawLine(QPointF(gutter,self.header+i*self.rowheight),QPointF(self.width()-10,self.header+i*self.rowheight))
        for i in range(self.count):
            y=self.header+i*self.rowheight;p.setFont(font(13));p.setPen(QColor(t['muted']));p.drawText(QRectF(0,y+10,56,22),Qt.AlignCenter,f'{i+1:02d}')
            times=self.prefs.get('period_times',[])
            if i<len(times) and times[i].get('start'):
                p.setFont(font(9));p.drawText(QRectF(0,y+35,56,30),Qt.AlignCenter,times[i]['start']+'\n'+times[i]['end'])
        for j in range(days):
            day=self.week+timedelta(days=j);rows=classes_on(self.data,day,self.prefs)
            lanes=[];placements=[]
            for row in rows:
                lane=next((i for i,end in enumerate(lanes) if row['period_start']>end),len(lanes))
                if lane==len(lanes):lanes.append(row['period_end'])
                else:lanes[lane]=row['period_end']
                placements.append((lane,row))
            lane_count=max(1,len(lanes))
            for lane,row in placements:
                x=gutter+j*cw+7+lane*(cw-14)/lane_count;y=self.header+(row['period_start']-1)*self.rowheight+6
                rect=QRectF(x,y,(cw-14)/lane_count-3,(row['period_end']-row['period_start']+1)*self.rowheight-12)
                fg,bg=self.colors(row);p.setBrush(QColor(bg));p.setPen(QPen(QColor(fg if self.hover==row['id'] else bg),1.2));p.drawRoundedRect(rect,10,10)
                p.setPen(Qt.NoPen);p.setBrush(QColor(fg));p.drawRoundedRect(QRectF(x,y+12,3,rect.height()-24),1.5,1.5)
                p.setPen(QColor(fg));p.setFont(font(13,True));p.drawText(QRectF(x+12,y+12,rect.width()-24,min(44,rect.height()-20)),Qt.TextWordWrap|Qt.AlignTop,row['course'])
                if rect.height()>=90:
                    p.setFont(font(11));p.drawText(QRectF(x+12,y+61,rect.width()-24,18),Qt.AlignLeft,row.get('teacher') or '教师未填写')
                    p.setFont(font(10));p.drawText(QRectF(x+12,y+84,rect.width()-24,18),Qt.AlignLeft,row.get('room') or '教室未填写')
                    if rect.height()>120:p.drawText(QRectF(x+12,rect.bottom()-27,rect.width()-24,18),Qt.AlignLeft,period_text(row))
                self.hits.append((rect,day,row))
        p.end()
    def mouseMoveEvent(self,event):
        hit=next((r for rect,d,r in self.hits if rect.contains(event.position())),None);value=hit['id'] if hit else None
        if value!=self.hover:self.hover=value;self.setCursor(Qt.PointingHandCursor if hit else Qt.ArrowCursor);self.update()
        self.setToolTip((hit['course']+'\n'+period_text(hit)+' · '+(hit.get('teacher') or '')+' · '+(hit.get('room') or '')+'\n'+hit.get('notes','')) if hit else '双击空白时段添加课程')
    def leaveEvent(self,event):self.hover=None;self.update()
    def mousePressEvent(self,event):
        if event.button()!=Qt.LeftButton:return
        for rect,day,row in self.hits:
            if rect.contains(event.position()):self.edit.emit(day,row);return
    def mouseDoubleClickEvent(self,event):
        if any(rect.contains(event.position()) for rect,_,_ in self.hits):return
        days=7 if self.prefs['show_weekends'] else 5;cw=(self.width()-72)/days;x,y=event.position().x(),event.position().y()
        if x>=62 and y>=self.header:
            day=self.week+timedelta(days=max(0,min(days-1,int((x-62)/cw))));period=max(1,min(self.count,int((y-self.header)/self.rowheight)+1));self.add.emit(day,period)

class HeroArt(QWidget):
    def __init__(self):super().__init__();self.setFixedSize(210,170)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.setPen(Qt.NoPen)
        p.setBrush(QColor(255,255,255,24));p.drawEllipse(QRectF(25,-10,180,180));p.drawEllipse(QRectF(70,55,125,125))
        p.save();p.translate(110,84);p.rotate(10);p.setBrush(QColor(255,255,255,35));p.drawRoundedRect(QRectF(-62,-55,124,120),14,14);p.restore()
        p.save();p.translate(101,86);p.rotate(-7);p.setBrush(QColor('#F6FBF4'));p.drawRoundedRect(QRectF(-60,-57,120,118),13,13)
        p.setBrush(QColor('#BBDFCE'));p.drawRoundedRect(QRectF(-60,-57,120,26),13,13);p.drawRect(QRectF(-60,-43,120,13))
        p.setPen(QPen(QColor('#177D72'),3));p.drawLine(-30,-62,-30,-50);p.drawLine(30,-62,30,-50)
        p.setPen(Qt.NoPen)
        for r in range(3):
            for c in range(4):p.setBrush(QColor('#DDEAE1'));p.drawRoundedRect(QRectF(-41+c*24,-16+r*22,14,13),3,3)
        p.setBrush(QColor('#177D72'));p.drawRoundedRect(QRectF(7,6,14,13),3,3);p.restore()
        p.setBrush(QColor('#D8EFAD'));p.drawEllipse(QRectF(151,114,31,31));p.setPen(QPen(QColor('#177D72'),2.5));p.drawPolyline(QPolygonF([QPointF(159,130),QPointF(165,135),QPointF(175,124)]));p.end()

class CourseRow(QWidget):
    def __init__(self,owner,day,row,compact=False):
        super().__init__();self.setCursor(Qt.PointingHandCursor);self.owner=owner;self.day=day;self.row=row
        l=hlayout(self,(0,10,0,10),14);fg,bg=COLORS[color_index(row)]
        number=text(f"{row['period_start']:02d}");number.setFixedSize(40,40);number.setAlignment(Qt.AlignCenter);number.setStyleSheet(f'background:{bg};color:{fg};border-radius:12px;font-size:15px;font-weight:600;');l.addWidget(number)
        info=vlayout(spacing=5);info.addWidget(text(row['course'],'Section' if not compact else None));info.addWidget(text((row.get('teacher') or '教师未填写')+'  ·  '+(row.get('room') or '教室未填写'),'Muted'));l.addLayout(info,1)
        l.addWidget(text(class_time(row,owner.prefs),'Caption'))
    def mousePressEvent(self,e):
        if e.button()==Qt.LeftButton:self.owner.edit(self.day,self.row)

class CourseDetails(FramelessDialog):
    def __init__(self,owner,key):
        super().__init__(owner);self.setWindowTitle('课程详情');self.resize(680,640)
        l=vlayout(self,(28,24,28,24),16);rows=[(d,r) for d,r in occurrences(owner.data,prefs=owner.prefs) if course_key(r)==key]
        r=rows[0][1];l.addWidget(text(r['course'],'Heading'));l.addWidget(text(f"{r.get('teacher') or '教师未填写'} · 共 {len(rows)} 次安排",'Muted'))
        content=QWidget();cl=vlayout(content,spacing=8)
        for day,row in rows:
            c=card();cc=hlayout(c,(14,10,14,10));cc.addWidget(text(f'{day:%m月%d日}  星期{WEEKDAYS[day.weekday()]}'));cc.addWidget(text(period_text(row)+' · '+(row.get('room') or '教室未填写'),'Muted'),1)
            b=btn('编辑','Ghost','edit');b.clicked.connect(lambda _=False,d=day,r=row:(self.accept(),owner.edit(d,r)));cc.addWidget(b);cl.addWidget(c)
        cl.addStretch();l.addWidget(make_scroll(content),1);l.addWidget(btn('关闭',callback=self.accept),alignment=Qt.AlignRight)

class BackupDialog(FramelessDialog):
    def __init__(self,owner):
        super().__init__(owner);self.owner=owner;self.setWindowTitle('备份与恢复');self.resize(650,480)
        l=vlayout(self,(28,24,28,24),16);l.addWidget(text('找回之前的课表','Heading'));l.addWidget(text('每次保存前自动备份，保留最近 30 份。恢复前也会备份当前课表。','Muted',True))
        self.paths=sorted(BACKUP_DIR.glob('schedule-*.json'),reverse=True);self.table=QTableWidget(len(self.paths),2);self.table.setHorizontalHeaderLabels(['保存时间','文件大小']);self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch);self.table.verticalHeader().hide();self.table.setSelectionBehavior(QAbstractItemView.SelectRows);self.table.setSelectionMode(QAbstractItemView.SingleSelection);self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        for i,p in enumerate(self.paths):
            stamp=datetime.fromtimestamp(p.stat().st_mtime);self.table.setItem(i,0,QTableWidgetItem(f'{stamp:%Y-%m-%d  %H:%M:%S}'));self.table.setItem(i,1,QTableWidgetItem(f'{p.stat().st_size/1024:.1f} KB'))
        l.addWidget(self.table,1)
        if not self.paths:l.addWidget(text('还没有历史备份；下一次修改课表后会出现在这里。','Muted',True))
        row=hlayout();row.addStretch();row.addWidget(btn('关闭',callback=self.reject));self.restore=btn('恢复所选备份','Primary','restore',self.apply);self.restore.setEnabled(bool(self.paths));row.addWidget(self.restore);l.addLayout(row)
    def apply(self):
        i=self.table.currentRow()
        if i<0:self.owner.notice('先选择备份','点击需要恢复的备份记录。');return
        if not self.owner.confirm('恢复这份课表？','当前课表会先备份，随后替换为所选历史版本。','恢复课表'):return
        try:self.owner.data=restore_backup(self.paths[i]);self.owner.refresh();self.owner.toast('课表已恢复');self.accept()
        except Exception as e:self.owner.notice('恢复失败',str(e))

class DayArrangement(FramelessDialog):
    def __init__(self,owner,day):
        super().__init__(owner);self.owner=owner;self.setWindowTitle('调整当天');self.setFixedWidth(490)
        l=vlayout(self,(28,24,28,24),16);l.addWidget(text('调整某一天的安排','Section'));l.addWidget(text('适用于放假、停课，以及恢复原来的每周安排。','Muted',True))
        self.day=QDateEdit(qdate(day));self.day.setCalendarPopup(True);self.day.setDisplayFormat('yyyy-MM-dd');self.day.setDateRange(qdate(parse_date(owner.data['term']['start'])),qdate(parse_date(owner.data['term']['end'])));l.addWidget(self.day)
        self.choice=QComboBox();self.choice.addItems(['当天全部停课','清除当天调整，恢复每周课表']);l.addWidget(self.choice);l.addWidget(text('临时增课请使用“添加课程”，并选择单次课程。','Caption',True))
        row=hlayout();row.addStretch();row.addWidget(btn('取消',callback=self.reject));row.addWidget(btn('应用调整','Primary',callback=self.apply));l.addLayout(row)
    def apply(self):
        day=pydate(self.day.date());candidate=copy.deepcopy(self.owner.data);candidate['exceptions']=[e for e in candidate['exceptions'] if e['date']!=str(day)]
        if self.choice.currentIndex()==0:candidate['exceptions'].append({'date':str(day),'mode':'cancel','classes':[],'cancel_rule_ids':[]})
        if self.owner.confirm('确认调整当天？',f'{day:%Y年%m月%d日}：{self.choice.currentText()}。当前课表会自动备份。','应用调整') and self.owner.commit(candidate):self.accept()

class SettingsPage(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.setObjectName('Page');l=vlayout(self,(0,0,0,20),20);l.addWidget(page_header('设置','按你的节奏安排课表、提醒与界面。'))
        c=card();cl=vlayout(c,(24,22,24,22),18);cl.addWidget(text('每日课程提醒','Section'));row=hlayout();info=vlayout(spacing=4);info.addWidget(text('提前知道明天的课程'));info.addWidget(text('没有课程时保持安静，关闭软件后仍可提醒。','Muted'));row.addLayout(info,1);self.enabled=Switch();row.addWidget(self.enabled);cl.addLayout(row)
        row=hlayout();row.addWidget(text('提醒时间'));self.time=QTimeEdit();self.time.setDisplayFormat('HH:mm');self.time.setFixedWidth(110);row.addWidget(self.time);row.addStretch();row.addWidget(btn('发送示例通知',glyph='bell',callback=owner.test_notification));cl.addLayout(row)
        row=hlayout();row.addWidget(text('过滤周日实验课'));row.addStretch();self.sunday=Switch();row.addWidget(self.sunday);cl.addLayout(row);cl.addWidget(text('电脑需已登录桌面。错过提醒时间后，Windows 会在可运行时补执行。','Caption',True));l.addWidget(c)
        c=card();cl=vlayout(c,(24,22,24,22),18);cl.addWidget(text('界面与使用习惯','Section'));row=hlayout();row.addWidget(text('界面主题'));row.addStretch();self.theme=QComboBox();self.theme.addItems(['浅色 · 清晨','深色 · 夜读','跟随 Windows']);self.theme.setFixedWidth(190);row.addWidget(self.theme);cl.addLayout(row)
        for title,attr,sub in [('显示周末','weekends','周视图同时显示周六和周日'),('关闭窗口后留在托盘','tray','可从右下角托盘重新打开；每日提醒始终独立运行')]:
            row=hlayout();info=vlayout(spacing=4);info.addWidget(text(title));info.addWidget(text(sub,'Muted'));row.addLayout(info,1);w=Switch();setattr(self,attr,w);row.addWidget(w);cl.addLayout(row)
        l.addWidget(c)
        c=card();cl=vlayout(c,(24,22,24,22),16);cl.addWidget(text('学期信息','Section'));g=QGridLayout();g.setSpacing(12);self.term_name=QLineEdit();g.addWidget(text('学期名称','Muted'),0,0,1,3);g.addWidget(self.term_name,1,0,1,3)
        self.start=QDateEdit();self.end=QDateEdit();self.first=QSpinBox();self.first.setRange(1,100)
        for w in [self.start,self.end]:w.setCalendarPopup(True);w.setDisplayFormat('yyyy-MM-dd')
        for j,(label,w) in enumerate([('起始日期',self.start),('结束日期',self.end),('起始周次',self.first)]):g.addWidget(text(label,'Muted'),2,j);g.addWidget(w,3,j)
        cl.addLayout(g);cl.addWidget(text('起始周次决定界面显示的周数。调整日期时，已录入课程会按原日期保留。','Caption',True));l.addWidget(c)
        c=card();cl=vlayout(c,(24,22,24,22),14);row=hlayout();row.addWidget(text('节次与上课时间','Section'));row.addStretch();row.addWidget(text('每天节数','Muted'));self.count=QSpinBox();self.count.setRange(1,14);self.count.setFixedWidth(80);row.addWidget(self.count);cl.addLayout(row);cl.addWidget(text('时间可留空，课表与通知将按节次展示。填写格式：08:00。','Muted',True))
        self.times=QTableWidget(8,3);self.times.setHorizontalHeaderLabels(['节次','开始时间','结束时间']);self.times.verticalHeader().hide();self.times.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);self.times.setFixedHeight(315);self.times.setAlternatingRowColors(True);cl.addWidget(self.times);self.count.valueChanged.connect(self.resize_times);l.addWidget(c)
        c=card();cl=vlayout(c,(24,22,24,22),16);cl.addWidget(text('数据与备份','Section'));cl.addWidget(text('所有课表保存在这台电脑，导入识别也在本地完成。每次保存前自动创建备份。','Muted',True));path=text(str(APP_DIR),'Caption',True);path.setTextInteractionFlags(Qt.TextSelectableByMouse);cl.addWidget(path)
        row=hlayout();row.addWidget(btn('备份与恢复',glyph='restore',callback=lambda:BackupDialog(owner).exec()));row.addWidget(btn('导出课表',glyph='download',callback=owner.export_json));row.addWidget(btn('打开数据文件夹',glyph='folder',callback=lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(APP_DIR)))));row.addStretch();cl.addLayout(row);l.addWidget(c)
        c=card();cl=hlayout(c,(24,22,24,22));col=vlayout(spacing=6);col.addWidget(text('课序 · 课程助手','Section'));col.addWidget(text(f'版本 {VERSION}  /  Windows 桌面版','Muted'));col.addWidget(text('创作者：g1Ix  ·  版权所有 © 2026 g1Ix','Muted',True));col.addWidget(text('把每一天，安排得清清楚楚。','Caption'));cl.addLayout(col,1);cl.addWidget(btn('打开 Windows 通知设置',glyph='external',callback=lambda:QDesktopServices.openUrl(QUrl('ms-settings:notifications'))));l.addWidget(c)
        self.footer=QWidget();footer=vlayout(self.footer,spacing=7);self.error=text('','Error',True);footer.addWidget(self.error);row=hlayout();row.addWidget(text('修改后点击保存，立即应用。','Muted'));row.addStretch();row.addWidget(btn('放弃修改',callback=self.reset));self.save_button=btn('保存设置','Primary','check',self.save);row.addWidget(self.save_button);footer.addLayout(row);self.reset()
    def resize_times(self,n):
        self.times.setRowCount(n)
        for i in range(n):
            label=QTableWidgetItem(f'第 {i+1} 节');label.setFlags(Qt.ItemIsEnabled);self.times.setItem(i,0,label)
            for j in (1,2):
                if self.times.item(i,j) is None:self.times.setItem(i,j,QTableWidgetItem(''))
            self.times.setRowHeight(i,35)
    def reset(self):
        p=self.owner.prefs;t=self.owner.data['term'];self.enabled.setChecked(p['reminder_enabled']);self.time.setTime(QTime.fromString(p['reminder_time'],'HH:mm'));self.sunday.setChecked(p['exclude_sunday_labs']);self.theme.setCurrentIndex(['light','dark','system'].index(p['theme']));self.weekends.setChecked(p['show_weekends']);self.tray.setChecked(p['close_to_tray']);self.term_name.setText(t['name']);self.start.setDate(qdate(parse_date(t['start'])));self.end.setDate(qdate(parse_date(t['end'])));self.first.setValue(t['first_week']);self.count.setValue(p['period_count']);self.resize_times(p['period_count'])
        for i in range(p['period_count']):
            t=p['period_times'][i] if i<len(p['period_times']) else {}
            for j,key in [(1,'start'),(2,'end')]:self.times.item(i,j).setText(t.get(key,''))
        self.error.clear()
    def save(self):
        try:
            p=copy.deepcopy(self.owner.prefs);p.update(reminder_enabled=self.enabled.isChecked(),reminder_time=self.time.time().toString('HH:mm'),exclude_sunday_labs=self.sunday.isChecked(),theme=['light','dark','system'][self.theme.currentIndex()],show_weekends=self.weekends.isChecked(),close_to_tray=self.tray.isChecked(),period_count=self.count.value(),period_times=[{'start':self.times.item(i,1).text().strip(),'end':self.times.item(i,2).text().strip()} for i in range(self.count.value())]);validate_prefs(p)
            candidate=copy.deepcopy(self.owner.data);newstart=pydate(self.start.date());newend=pydate(self.end.date());oldstart=parse_date(candidate['term']['start']);shift=(monday(oldstart)-monday(newstart)).days//7
            candidate['term']={'name':self.term_name.text().strip() or '我的学期','start':str(newstart),'end':str(newend),'first_week':self.first.value()}
            for r in candidate['weekly_rules']:r['weeks']=[w+shift for w in r['weeks']]
            validate_schedule(candidate)
        except Exception as e:self.error.setText(str(e));return
        self.save_button.setEnabled(False);self.save_button.setText('正在保存…');self.error.clear();self.owner.setEnabled(False)
        def done(_):
            try:
                if candidate!=self.owner.data:save_schedule(candidate)
                save_prefs(p);self.owner.data=candidate;self.owner.prefs=p;self.owner.apply_theme();self.owner.refresh();self.owner.setup_tray();self.owner.toast('设置已保存')
            except Exception as e:self.error.setText(str(e))
            self.owner.setEnabled(True);self.save_button.setEnabled(True);self.save_button.setText('保存设置')
        def fail(message):self.error.setText(message);self.owner.setEnabled(True);self.save_button.setEnabled(True);self.save_button.setText('保存设置')
        self.owner.run_job(lambda:update_task(p),done,fail)

class DropZone(QFrame):
    files=Signal(object)
    def __init__(self):
        super().__init__();self.setAcceptDrops(True);self.setObjectName('DropZone');self.setMinimumHeight(220)
        self.setStyleSheet('QFrame#DropZone{border:2px dashed #B9CEC5;border-radius:18px;background:transparent;}')
        l=vlayout(self,(28,28,28,28),10);pic=text('');pic.setPixmap(icon('upload','#177D72',42).pixmap(42,42));pic.setAlignment(Qt.AlignCenter);l.addWidget(pic);l.addWidget(text('把你的课表拖到这里','Section'),alignment=Qt.AlignCenter);l.addWidget(text('支持 PNG、JPG、BMP、TIFF、多页 PDF、JSON 和 CSV','Muted'),alignment=Qt.AlignCenter);self.choose=btn('选择课表文件','Primary','folder');l.addWidget(self.choose,alignment=Qt.AlignCenter)
    def dragEnterEvent(self,e):
        if e.mimeData().hasUrls():e.acceptProposedAction()
    def dropEvent(self,e):self.files.emit([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]);e.acceptProposedAction()

class ImportPage(QWidget):
    HEADERS=['录入','安排','星期 / 日期','开始','结束','课程名称','教师','教室','上课周次']
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.paths=[];self.native=None;self.busy=False;self.setObjectName('Page');l=vlayout(self,(0,0,0,20),18);l.addWidget(page_header('导入课表','本地识别，认真校对，确认后再加入你的课表。'))
        steps=hlayout();self.steps=[]
        for i,title in enumerate(['选择文件','校对课程','完成导入']):
            w=text(f'0{i+1}   {title}','Badge' if i==0 else 'Muted');self.steps.append(w);steps.addWidget(w)
            if i<2:steps.addWidget(text('—','Muted'))
        steps.addStretch();l.addLayout(steps);self.stack=QStackedWidget();l.addWidget(self.stack,1)
        first=QWidget();fl=vlayout(first,spacing=18);self.drop=DropZone();self.drop.files.connect(self.set_files);self.drop.choose.clicked.connect(self.choose);fl.addWidget(self.drop)
        self.file_card=card();fc=vlayout(self.file_card,(22,18,22,18),10);r=hlayout();r.addWidget(text('已选择文件','Section'));r.addStretch();r.addWidget(btn('清空','Ghost',callback=lambda:self.set_files([])));fc.addLayout(r);self.file_labels=vlayout(spacing=6);fc.addLayout(self.file_labels);fl.addWidget(self.file_card);self.file_card.hide()
        c=card();cl=vlayout(c,(22,20,22,20),14);cl.addWidget(text('识别方式','Section'));self.mode=QComboBox();self.mode.addItems(['按每页标注的日期 / 周次识别','作为每周重复的课表识别']);cl.addWidget(self.mode);r=hlayout();r.addWidget(text('重复课表的上课周次','Muted'));self.weeks=QLineEdit(weeks_text(range(1,total_weeks(owner.data)+1),owner.data['term']['first_week']-1));self.weeks.setPlaceholderText('例如：6–18');r.addWidget(self.weeks,1);cl.addLayout(r);cl.addWidget(text('课表样式各不相同，识别后的日期、周次、课程名及节次都可修改。截图中的临时增减课将按日期保留。','Muted',True));fl.addWidget(c)
        tip=card();tl=hlayout(tip,(20,16,20,16));tl.addWidget(text('也可以用标准表格导入，省去识别校对。','Muted'),1);tl.addWidget(btn('下载 CSV 模板','Ghost','download',self.template));fl.addWidget(tip)
        self.status=text('','Muted',True);self.progress=QProgressBar();self.progress.setRange(0,0);self.progress.hide();fl.addWidget(self.status);fl.addWidget(self.progress);self.error=text('','Error',True);fl.addWidget(self.error);r=hlayout();r.addStretch();self.start_button=btn('开始识别','Primary','spark',self.start);self.start_button.setEnabled(False);r.addWidget(self.start_button);fl.addLayout(r);fl.addStretch();self.stack.addWidget(first)
        preview=QWidget();pl=vlayout(preview,spacing=16);r=hlayout();self.summary=text('识别结果','Section');r.addWidget(self.summary);r.addStretch();self.source=btn('查看原课表',glyph='image',callback=self.show_source);r.addWidget(self.source);r.addWidget(btn('新增一行',glyph='plus',callback=lambda:self.append_row({})));r.addWidget(btn('删除所选行',glyph='trash',callback=self.remove_row));pl.addLayout(r)
        pl.addWidget(text('点击单元格直接修改。取消“录入”可跳过某行；周次使用实际数字，单次课程填写具体日期。','Muted',True));self.native_hint=text('','Caption',True);pl.addWidget(self.native_hint)
        c=card();cl=vlayout(c,(8,8,8,8),0);self.table=QTableWidget(0,9);self.table.setHorizontalHeaderLabels(self.HEADERS);self.table.verticalHeader().hide();self.table.setAlternatingRowColors(True);self.table.setSelectionBehavior(QAbstractItemView.SelectRows);self.table.setMinimumHeight(335);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        for i,w in enumerate([52,108,154,67,67,215,105,132,135]):self.table.setColumnWidth(i,w)
        cl.addWidget(self.table);pl.addWidget(c,1);self.preview_error=text('','Error',True);pl.addWidget(self.preview_error);r=hlayout();self.replace=QComboBox();self.replace.addItems(['合并到现有课表','替换整个课表（先自动备份）']);r.addWidget(self.replace);r.addStretch();r.addWidget(btn('返回选择',callback=lambda:self.go(0)));self.apply_button=btn('确认导入','Primary','check',self.apply);r.addWidget(self.apply_button);pl.addLayout(r);self.stack.addWidget(preview)
        finish=QWidget();ll=vlayout(finish,(50,60,50,60),20);mark=text('');mark.setPixmap(icon('check','#177D72',64).pixmap(64,64));ll.addWidget(mark,alignment=Qt.AlignCenter);ll.addWidget(text('新的安排，准备好了','Heading'),alignment=Qt.AlignCenter);self.finish_text=text('课程已保存，明天的提醒也会一起更新。','Muted',True);self.finish_text.setAlignment(Qt.AlignCenter);ll.addWidget(self.finish_text);r=hlayout();r.addStretch();r.addWidget(btn('继续导入',callback=self.reset));r.addWidget(btn('查看我的课表','Primary','calendar',lambda:owner.navigate(1)));r.addStretch();ll.addLayout(r);ll.addStretch();self.stack.addWidget(finish)
    def go(self,i):
        self.stack.setCurrentIndex(i)
        for j,w in enumerate(self.steps):w.setObjectName('Badge' if j==i else 'Muted');w.style().unpolish(w);w.style().polish(w)
    def reset(self):self.set_files([]);self.go(0)
    def choose(self):
        paths,_=QFileDialog.getOpenFileNames(self,'选择课表文件',str(Path.home()/'Desktop'),'课表文件 (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.pdf *.json *.csv)')
        if paths:self.set_files(paths)
    def set_files(self,paths):
        if self.busy:return
        self.paths=list(dict.fromkeys(paths));clear_layout(self.file_labels);self.error.clear()
        for p in self.paths:self.file_labels.addWidget(text(Path(p).name+'  ·  '+(f'{Path(p).stat().st_size/1024:.0f} KB' if Path(p).is_file() else '文件不存在'),'Muted'))
        self.file_card.setVisible(bool(paths));self.start_button.setEnabled(bool(paths));self.status.clear()
    def template(self):
        path,_=QFileDialog.getSaveFileName(self,'保存导入模板','课表导入模板.csv','CSV (*.csv)')
        if path:
            try:
                with open(path,'w',newline='',encoding='utf-8-sig') as f:
                    w=csv.writer(f);w.writerow(['安排','星期','日期','开始节次','结束节次','课程名称','教师','教室','周次']);w.writerow(['每周','星期一','',1,2,'示例：数据结构','张老师','教学楼 101',weeks_text(range(1,total_weeks(self.owner.data)+1),self.owner.data['term']['first_week']-1)]);w.writerow(['单次','',self.owner.data['term']['start'],3,4,'示例：临时讲座','','报告厅',''])
                self.owner.toast('CSV 模板已保存')
            except Exception as e:self.owner.notice('保存失败',str(e))
    @staticmethod
    def csv_rows(path,default_weeks,offset):
        rows=[]
        with open(path,encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f)
            if not reader.fieldnames or not {'开始节次','结束节次','课程名称'}.issubset(reader.fieldnames):raise ValueError('CSV 缺少标准表头。请使用“下载 CSV 模板”中的格式。')
            for raw in reader:
                if not any(raw.values()):continue
                r={'course':raw.get('课程名称',''),'teacher':raw.get('教师',''),'room':raw.get('教室',''),'period_start':int(raw['开始节次']),'period_end':int(raw['结束节次'])}
                if raw.get('日期'):r['date']=raw['日期']
                else:
                    dow=raw.get('星期','').replace('星期','').replace('周','').replace('天','日');r['weekday']=WEEKDAYS.index(dow) if dow in WEEKDAYS and dow else int(dow)-1;r['weeks']=parse_weeks(raw.get('周次',''),offset) or default_weeks
                rows.append(r)
        return rows
    def start(self):
        try:
            weeks=parse_weeks(self.weeks.text(),self.owner.data['term']['first_week']-1)
            if not weeks or any(not 1<=w<=total_weeks(self.owner.data) for w in weeks):raise ValueError('请填写学期范围内的上课周次。')
            for p in self.paths:
                if not Path(p).is_file():raise ValueError(f'文件不存在：{Path(p).name}')
                if Path(p).stat().st_size>100*1024*1024:raise ValueError('单个文件不能超过 100 MB。可先拆分 PDF 或缩小图片。')
            if len(self.paths)>1 and any(Path(p).suffix.lower() in ('.json','.csv') for p in self.paths):raise ValueError('JSON 或 CSV 请单独导入；图片与 PDF 可以一起选择。')
        except Exception as e:self.error.setText(str(e));return
        paths=self.paths[:];per_week=self.mode.currentIndex()==0;first_week=self.owner.data['term']['first_week'];self.import_term=copy.deepcopy(self.owner.data['term']);term_start=self.import_term['start'];self.busy=True;self.start_button.setEnabled(False);self.drop.setEnabled(False);self.progress.show();self.status.setText('正在本地识别，请稍候…');self.error.clear()
        def work():
            if Path(paths[0]).suffix.lower()=='.json':
                try:
                    raw=json.loads(Path(paths[0]).read_text(encoding='utf-8-sig'));data=migrate_legacy(raw) if 'date_range' in raw else normalize(raw);validate_schedule(data)
                except Exception as e:raise ValueError('这个 JSON 不是有效的课表文件。请使用本软件导出的课表数据。\n'+str(e)) from e
                rows=[]
                for r in data['weekly_rules']:rows.append(copy.deepcopy(r))
                for ex in data['exceptions']:
                    for r in ex['classes']:rows.append({**copy.deepcopy(r),'date':ex['date']})
                return rows,data,None
            if Path(paths[0]).suffix.lower()=='.csv':return self.csv_rows(paths[0],weeks,first_week-1),None,None
            pages=[]
            for p in paths:
                result=subprocess.run([powershell(),'-NoProfile','-STA','-ExecutionPolicy','Bypass','-File',str(RESOURCE_DIR/'windows_ocr.ps1'),'-Path',p],capture_output=True,timeout=150,**hidden_options())
                if result.returncode:
                    detail=result.stderr.decode('utf-8',errors='replace')
                    if 'language' in detail.lower() or '语言' in detail:raise ValueError('Windows 中文识别语言不可用。请在系统“语言和区域”中安装简体中文语言及 OCR 功能，或使用 CSV / 手动添加课程。')
                    raise ValueError(f'无法识别 {Path(p).name}。请检查文件是否损坏、受密码保护或不受支持。\n'+detail[-300:])
                payload=json.loads(result.stdout.decode('utf-8-sig'));pages.extend(payload.get('pages',[]))
            payload={'pages':pages};return ocr_pages_to_rows(payload,weeks,per_week,first_week,term_start),None,payload
        def done(value):
            self.stop_busy();rows,self.native,self.ocr_payload=value
            if not rows and self.native is None:self.error.setText('没有识别到可用课程。可以尝试更清晰的完整课表截图，或使用 CSV / 手动添加。');return
            self.table.setRowCount(0)
            if self.native:
                self.replace.setCurrentIndex(1);self.replace.setEnabled(False);self.native_hint.setText('此文件包含完整课表；临时停课与覆盖安排将完整保留。表格中可校正课程信息，确认后替换并备份当前课表。')
            else:self.replace.setEnabled(True);self.native_hint.setText('识别结果尚未保存。请特别检查标红的内容、节次和上课周次。')
            for r in rows:self.append_row(r)
            self.summary.setText(f'{len(rows)} 条课程安排待确认');self.preview_error.clear();self.source.setEnabled(Path(paths[0]).suffix.lower() not in ('.json','.csv'));self.go(1)
        self.owner.run_job(work,done,lambda e:(self.stop_busy(),self.error.setText(e)))
    def stop_busy(self):self.busy=False;self.start_button.setEnabled(bool(self.paths));self.drop.setEnabled(True);self.progress.hide();self.status.clear()
    def append_row(self,row):
        i=self.table.rowCount();self.table.insertRow(i);self.table.setRowHeight(i,47);self.table.setItem(i,0,QTableWidgetItem());self.table.item(i,0).setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable);self.table.item(i,0).setCheckState(Qt.Checked);self.table.item(i,0).setData(Qt.UserRole,row.get('id'));self.table.item(i,0).setData(Qt.UserRole+1,row.get('notes',''))
        mode=QComboBox();mode.addItems(['每周重复','单次课程']);mode.setCurrentIndex(1 if 'date' in row else 0);self.table.setCellWidget(i,1,mode)
        slot=QStackedWidget();dow=QComboBox();dow.addItems([f'星期{x}' for x in WEEKDAYS]);dow.setCurrentIndex(row.get('weekday',0));dt=QDateEdit(qdate(parse_date(row.get('date',self.owner.data['term']['start']))));dt.setCalendarPopup(True);dt.setDisplayFormat('yyyy-MM-dd');slot.addWidget(dow);slot.addWidget(dt);slot.setCurrentIndex(mode.currentIndex());mode.currentIndexChanged.connect(slot.setCurrentIndex);self.table.setCellWidget(i,2,slot)
        for j,key in [(3,'period_start'),(4,'period_end')]:w=QSpinBox();w.setRange(1,14);w.setValue(int(row.get(key,1 if j==3 else 2)));self.table.setCellWidget(i,j,w)
        for j,key in [(5,'course'),(6,'teacher'),(7,'room')]:
            item=QTableWidgetItem(row.get(key,''));self.table.setItem(i,j,item)
            if j==5 and (not item.text() or item.text()=='待校对课程'):item.setBackground(QColor('#FBE5E2'));item.setForeground(QColor('#A2413C'))
        source_data=self.native or self.owner.data;offset=source_data['term']['first_week']-1;self.table.setItem(i,8,QTableWidgetItem(weeks_text(row.get('weeks',range(1,total_weeks(source_data)+1)),offset)))
        if self.native:
            mode.setEnabled(False);slot.setEnabled(False)
        self.table.scrollToBottom()
    def remove_row(self):
        indices=sorted({index.row() for index in self.table.selectedIndexes()},reverse=True)
        for i in indices:self.table.removeRow(i)
    def read_rows(self):
        rows=[];source=self.native or self.owner.data;offset=source['term']['first_week']-1
        for i in range(self.table.rowCount()):
            if self.table.item(i,0).checkState()!=Qt.Checked:continue
            r={'course':self.table.item(i,5).text().strip(),'teacher':self.table.item(i,6).text().strip(),'room':self.table.item(i,7).text().strip(),'notes':self.table.item(i,0).data(Qt.UserRole+1) or '','period_start':self.table.cellWidget(i,3).value(),'period_end':self.table.cellWidget(i,4).value(),'id':self.table.item(i,0).data(Qt.UserRole) or uid()}
            if not r['course'] or r['course']=='待校对课程':raise ValueError(f'第 {i+1} 行的课程名称需要校对。')
            slot=self.table.cellWidget(i,2)
            if self.table.cellWidget(i,1).currentIndex()==0:r.update(weekday=slot.widget(0).currentIndex(),weeks=parse_weeks(self.table.item(i,8).text(),offset))
            else:r['date']=str(pydate(slot.widget(1).date()))
            rows.append(r)
        if not rows and self.native is None:raise ValueError('请保留至少一条需要录入的课程。')
        return rows
    def apply(self):
        try:
            if not self.native and getattr(self,'import_term',self.owner.data['term'])!=self.owner.data['term']:raise ValueError('学期信息在识别后发生变化。请返回选择文件，按新的学期重新识别。')
            rows=self.read_rows()
            if self.native:
                candidate=copy.deepcopy(self.native);by_id={r['id']:r for r in rows};candidate['weekly_rules']=[{**r,**row_fields(by_id[r['id']]),'weeks':by_id[r['id']]['weeks']} for r in candidate['weekly_rules'] if r['id'] in by_id]
                for ex in candidate['exceptions']:ex['classes']=[{**r,**row_fields(by_id[r['id']])} for r in ex['classes'] if r['id'] in by_id]
                for r in rows:
                    if not any(r['id']==x['id'] for x in self.native['weekly_rules']) and not any(r['id']==x['id'] for e in self.native['exceptions'] for x in e['classes']):
                        if 'weekday' in r:candidate['weekly_rules'].append({k:v for k,v in r.items() if k!='date'})
                        else:exception_for(candidate,parse_date(r['date']))['classes'].append({k:v for k,v in r.items() if k!='date'})
            else:
                candidate=copy.deepcopy(self.owner.data)
                if self.replace.currentIndex()==1:candidate['weekly_rules']=[];candidate['exceptions']=[]
                for r in rows:
                    if 'weekday' in r:
                        existing=next((x for x in candidate['weekly_rules'] if all(x.get(k)==r.get(k) for k in ['weekday','period_start','period_end','course','teacher','room'])),None)
                        if existing:existing['weeks']=sorted(set(existing['weeks']+r['weeks']))
                        else:candidate['weekly_rules'].append(r)
                    else:
                        ex=exception_for(candidate,parse_date(r.pop('date')))
                        if ex['mode']=='cancel':ex['mode']='replace'
                        if not any(all(x.get(k)==r.get(k) for k in ['period_start','period_end','course','teacher','room']) for x in ex['classes']):ex['classes'].append(r)
            validate_schedule(candidate)
        except Exception as e:self.preview_error.setText(str(e));return
        if self.native and not rows and not self.owner.confirm('导入空课表？','该文件没有课程安排，当前课程将被替换。保存前会备份现有课表。','替换课表'):return
        if self.owner.commit(candidate):self.finish_text.setText(f'已导入 {len(rows)} 条课程安排。课表与每日提醒已同步更新。');self.go(2)
    def show_source(self):
        dialog=FramelessDialog(self.owner);dialog.setWindowTitle('原课表 · 对照校对');dialog.resize(1030,730);l=vlayout(dialog,(18,18,18,18),12);picker=QComboBox();pages=[]
        for p in self.paths:
            if Path(p).suffix.lower()=='.pdf':
                try:
                    from PySide6.QtPdf import QPdfDocument
                    doc=QPdfDocument(dialog)
                    if doc.load(p)!=QPdfDocument.Error.None_:raise ValueError('PDF 无法打开')
                    for n in range(doc.pageCount()):pages.append((p,n,doc));picker.addItem(f'{Path(p).name} · 第 {n+1} 页')
                except Exception as e:self.owner.notice('无法预览 PDF',str(e));return
            else:pages.append((p,None,None));picker.addItem(Path(p).name)
        l.addWidget(picker);pic=text('');pic.setAlignment(Qt.AlignCenter);l.addWidget(make_scroll(pic),1)
        def load(i):
            p,n,doc=pages[i];pix=QPixmap(p) if n is None else QPixmap.fromImage(doc.render(n,QSize(1800,1300)));pic.setPixmap(pix.scaledToWidth(950,Qt.SmoothTransformation));pic.adjustSize()
        picker.currentIndexChanged.connect(load);load(0);l.addWidget(btn('关闭',callback=dialog.accept),alignment=Qt.AlignRight);dialog.exec()

class MainWindow(FramelessMainWindow):
    def __init__(self):
        self.greeting_deck=GreetingDeck();self.greeting='今天，也从容一点'
        super().__init__();self.data=load_schedule();self.prefs=load_prefs();self.dark=False;self.theme=LIGHT;self.jobs=[];self.tray=None;self.exiting=False;self.selected_week=monday(max(parse_date(self.data['term']['start']),min(date.today(),parse_date(self.data['term']['end']))));self.last_day=date.today()
        self.setWindowTitle('课序 · 课程助手');self.setWindowIcon(QIcon(str(RESOURCE_DIR/'assets/app.ico')));self.setMinimumSize(900,600);available=QApplication.primaryScreen().availableGeometry();self.resize(min(1420,max(900,available.width()-40)),min(920,max(600,available.height()-60)))
        root=QWidget();root.setObjectName('Page');self.setCentralWidget(root);root_layout=vlayout(root,margins=(0,0,0,0),spacing=0);self.titlebar=WindowTitleBar(self);root_layout.addWidget(self.titlebar);rl=hlayout(spacing=0)
        self.sidebar=QFrame();self.sidebar.setObjectName('Sidebar');self.sidebar.setFixedWidth(196);sl=vlayout(self.sidebar,(14,22,14,18),8)
        brand=hlayout(spacing=10);logo=text('');logo.setPixmap(QPixmap(str(RESOURCE_DIR/'assets/app.png')).scaled(34,34,Qt.KeepAspectRatio,Qt.SmoothTransformation));brand.addWidget(logo);col=vlayout(spacing=1);col.addWidget(text('课序','Brand'));col.addWidget(text('C O U R S E D E S K','Caption'));brand.addLayout(col);brand.addStretch();sl.addLayout(brand);sl.addSpacing(12);sl.addWidget(text('学习空间','Caption'));self.nav=[];self.nav_icons=['home','calendar','book','upload','settings']
        for i,title in enumerate(['今日安排','我的课表','课程管理','导入课表','设置']):
            b=btn(title,'Nav',self.nav_icons[i],lambda _=False,n=i:self.navigate(n));b.setCheckable(True);b.setFixedHeight(44);self.nav.append(b);sl.addWidget(b)
        sl.addSpacing(12);self.next_card=card();nc=vlayout(self.next_card,(14,14,14,14),8)
        nc.addWidget(text('下一次课程','Caption'));self.next_date=text('','Caption',True);self.next_name=text('','Section',True);self.next_room=text('','Muted',True)
        nc.addWidget(self.next_date);nc.addWidget(self.next_name);nc.addWidget(self.next_room)
        self.next_button=btn('查看所在周','Ghost','right',self.open_next_course);self.next_button.setProperty('alwaysExpanded',True);nc.addWidget(self.next_button);sl.addWidget(self.next_card)
        sl.addStretch();c=card();cl=vlayout(c,(14,14,14,14),7);self.term_label=text('','Caption',True);self.term_week=text('','Section');self.term_progress=QProgressBar();self.term_progress.setRange(0,100);self.term_progress.setTextVisible(False);cl.addWidget(self.term_label);cl.addWidget(self.term_week);cl.addWidget(self.term_progress);self.sidebar_reminder=text('','Caption',True);cl.addWidget(self.sidebar_reminder);sl.addWidget(c);sl.addSpacing(4);sl.addWidget(text('●  数据仅保存在本机','Caption'),alignment=Qt.AlignCenter);rl.addWidget(self.sidebar)
        main=QWidget();ml=vlayout(main,(32,24,32,22),24);top=hlayout(spacing=14);self.search=QLineEdit();self.search.setPlaceholderText('搜索课程、教师或教室   Ctrl+F');self.search.addAction(icon('search'),QLineEdit.LeadingPosition);self.search.setFixedWidth(330);self.search.textEdited.connect(lambda:self.navigate(2));self.search.textChanged.connect(self.refresh_courses);top.addWidget(self.search);top.addStretch();self.today_label=text('','Muted');top.addWidget(self.today_label);top.addWidget(btn('添加课程','Primary','plus',self.add));ml.addLayout(top);self.pages=QStackedWidget();ml.addWidget(self.pages,1)
        self.dashboard=QWidget();self.dashboard.setObjectName('Page');self.dashboard_l=vlayout(self.dashboard,spacing=20);self.pages.addWidget(make_scroll(self.dashboard))
        self.schedule_page=QWidget();self.schedule_page.setObjectName('Page');sc=vlayout(self.schedule_page,spacing=18);sc.addWidget(page_header('我的课表','每一周的安排，都清晰可见。点击课程编辑，双击空白时段添加。'));bar=hlayout();self.week_title=text('','Section');bar.addWidget(self.week_title);self.week_picker=QComboBox();self.week_picker.setFixedWidth(110);self.week_picker.currentIndexChanged.connect(self.pick_week);bar.addWidget(self.week_picker);bar.addStretch();self.prev_button=btn('','Ghost','left',lambda:self.shift_week(-1));self.next_button=btn('','Ghost','right',lambda:self.shift_week(1));bar.addWidget(self.prev_button);bar.addWidget(btn('本周',callback=self.current_week));bar.addWidget(self.next_button);jump=btn('跳转日期','Ghost','calendar',self.jump_date);bar.addWidget(jump);sc.addLayout(bar)
        self.calendar=CalendarCanvas(self);self.calendar.setMinimumWidth(780);self.calendar.edit.connect(self.edit);self.calendar.add.connect(self.add);sc.addWidget(make_scroll(self.calendar),1);bottom=hlayout();self.week_info=text('','Muted');bottom.addWidget(self.week_info,1);bottom.addWidget(btn('调整当天','Ghost','edit',lambda:DayArrangement(self,self.selected_week).exec()));bottom.addWidget(btn('导出图片','Ghost','image',self.export_image));bottom.addWidget(btn('导出 CSV','Ghost','download',self.export_csv));sc.addLayout(bottom);self.pages.addWidget(self.schedule_page)
        self.courses_page=QWidget();self.courses_page.setObjectName('Page');cp=vlayout(self.courses_page,spacing=20);cp.addWidget(page_header('课程管理','课程信息、上课地点与每次安排，集中在这里。'));r=hlayout();self.course_count=text('','Muted');r.addWidget(self.course_count);r.addStretch();r.addWidget(btn('清空搜索','Ghost',callback=lambda:self.search.clear()));r.addWidget(btn('导出完整课表',glyph='download',callback=self.export_json));cp.addLayout(r);self.course_body=QWidget();self.course_grid=QGridLayout(self.course_body);self.course_grid.setContentsMargins(0,0,0,0);self.course_grid.setSpacing(16);cp.addWidget(make_scroll(self.course_body),1);self.pages.addWidget(self.courses_page)
        self.import_page=ImportPage(self);self.pages.addWidget(make_scroll(self.import_page));self.settings_page=SettingsPage(self);self.pages.addWidget(make_scroll(self.settings_page));ml.addWidget(self.settings_page.footer);rl.addWidget(main,1);root_layout.addLayout(rl,1)
        self.toast_label=text('','Toast');self.toast_label.setParent(self);self.toast_label.hide();self.toast_timer=QTimer(self);self.toast_timer.setSingleShot(True);self.toast_timer.timeout.connect(self.toast_label.hide)
        self.course_columns=2;self.apply_theme();self.refresh();self.navigate(0);self.setup_tray();self.tick_timer=QTimer(self);self.tick_timer.timeout.connect(self.tick);self.tick_timer.start(30000)
        for keys,callback in [('Ctrl+N',self.add),('Ctrl+I',lambda:self.navigate(3)),('Ctrl+F',self.search.setFocus)]:QShortcut(QKeySequence(keys),self,activated=callback)
        self.titlebar.refresh_controls();self.course_columns=2;self.adapt_layout()
    def toggle_maximized(self):
        super().toggle_maximized();self.titlebar.refresh_controls()
    def changeEvent(self,event):
        super().changeEvent(event)
        if event.type()==QEvent.WindowStateChange and hasattr(self,'titlebar'):self.titlebar.refresh_controls()
    def apply_theme(self):
        mode=self.prefs['theme'];self.dark=mode=='dark' or (mode=='system' and QApplication.styleHints().colorScheme()==Qt.ColorScheme.Dark);self.theme=DARK if self.dark else LIGHT
        palette=QPalette()
        for role,key in [(QPalette.Window,'bg'),(QPalette.Base,'panel'),(QPalette.AlternateBase,'hover'),(QPalette.WindowText,'ink'),(QPalette.Text,'ink'),(QPalette.Button,'panel'),(QPalette.ButtonText,'ink'),(QPalette.Highlight,'accent'),(QPalette.HighlightedText,'panel')]:palette.setColor(role,QColor(self.theme[key]))
        QApplication.instance().setPalette(palette)
        QApplication.instance().setStyleSheet(stylesheet(self.theme).replace('__CHECK_SVG__',str(RESOURCE_DIR/'assets/check.svg').replace('\\','/')).replace('__ASSET_DIR__',str(RESOURCE_DIR/'assets').replace('\\','/')))
        for i,b in enumerate(self.nav):b.setIcon(icon(self.nav_icons[i],self.theme['accent'] if b.isChecked() else self.theme['muted'],20))
        for window in QApplication.topLevelWidgets():
            if hasattr(window,'titlebar'):window.titlebar.refresh_controls()
        for button in self.findChildren(AnimatedButton):button.prepare_assets();button.update()
        if hasattr(self,'calendar'):self.calendar.update()
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'course_columns'):self.adapt_layout()
    def adapt_layout(self):
        compact=self.width()<1150;self.titlebar.hint.setVisible(not compact)
        self.sidebar.setFixedWidth(190 if compact else 196)
        self.next_card.setVisible(self.height()>=760)
        self.search.setFixedWidth(220 if compact else 330);self.today_label.setVisible(not compact)
        columns=1 if self.width()<1150 else 2
        if columns!=self.course_columns:
            self.course_columns=columns
            # Rebuild the grid so obsolete column/row stretch factors cannot persist.
            clear_layout(self.course_grid)
            for i in range(self.course_grid.columnCount()):self.course_grid.setColumnStretch(i,0);self.course_grid.setColumnMinimumWidth(i,0)
            self.refresh_courses()
        for i in range(columns):self.course_grid.setColumnStretch(i,1)
    def navigate(self,i):
        if i==0:self.rotate_greeting()
        self.pages.setCurrentIndex(i)
        self.settings_page.footer.setVisible(i==4)
        for j,b in enumerate(self.nav):b.setChecked(j==i);b.setIcon(icon(self.nav_icons[j],self.theme['accent'] if j==i else self.theme['muted'],20))
        if i==2:self.refresh_courses()
    def rotate_greeting(self):
        self.greeting=self.greeting_deck.next()
        if hasattr(self,'home_heading'):self.home_heading.setText(self.greeting)
    def refresh(self):
        self.refresh_sidebar()
        self.today_label.setText(f'{date.today():%Y年%m月%d日}  星期{WEEKDAYS[date.today().weekday()]}');self.term_label.setText(self.data['term']['name']);n=week_number(parse_date(self.data['term']['start']),date.today());total=total_weeks(self.data);self.term_week.setText('学期尚未开始' if n<1 else ('学期已结束' if n>total else f'第 {displayed_week(self.data,n)} 周'));self.term_progress.setValue(max(0,min(100,round((date.today()-parse_date(self.data['term']['start'])).days/max(1,(parse_date(self.data['term']['end'])-parse_date(self.data['term']['start'])).days)*100))))
        self.selected_week=max(monday(parse_date(self.data['term']['start'])),min(self.selected_week,monday(parse_date(self.data['term']['end']))));self.week_picker.blockSignals(True);self.week_picker.clear()
        for w in range(1,total+1):self.week_picker.addItem(f'第 {displayed_week(self.data,w)} 周',w)
        self.week_picker.blockSignals(False);self.refresh_schedule();self.refresh_dashboard();self.refresh_courses()
    def refresh_sidebar(self):
        self.next_item=next(occurrences(self.data,date.today(),prefs=self.prefs),None)
        if self.next_item:
            day,row=self.next_item
            self.next_date.setText(f'{day:%m月%d日} · 星期{WEEKDAYS[day.weekday()]}\n{class_time(row,self.prefs)}')
            self.next_name.setText(row['course']);self.next_room.setText(row.get('room') or '教室未填写')
            self.next_button.setText('查看所在周')
        else:
            self.next_date.setText('当前学期');self.next_name.setText('暂无后续课程');self.next_room.setText('添加或导入新的课表')
            self.next_button.setText('导入新课表')
        self.sidebar_reminder.setText(f"每日提醒 · {self.prefs['reminder_time']}" if self.prefs['reminder_enabled'] else '每日提醒 · 已关闭')
    def open_next_course(self):
        if self.next_item:
            self.selected_week=monday(self.next_item[0]);self.refresh_schedule();self.navigate(1)
        else:self.navigate(3)
    def refresh_schedule(self):
        n=week_number(parse_date(self.data['term']['start']),self.selected_week);end=self.selected_week+timedelta(days=6);self.week_title.setText(f'{self.selected_week:%Y.%m.%d} — {end:%m.%d}');self.week_picker.blockSignals(True);self.week_picker.setCurrentIndex(n-1);self.week_picker.blockSignals(False);self.prev_button.setEnabled(n>1);self.next_button.setEnabled(n<total_weeks(self.data));self.calendar.set_calendar(self.data,self.prefs,self.selected_week);rows=list(occurrences(self.data,self.selected_week,end,self.prefs));self.week_info.setText(f'本周 {len(rows)} 次课程  ·  '+('已隐藏周末' if not self.prefs['show_weekends'] else '含周末安排'))
    def pick_week(self,i):
        if i<0:return
        self.selected_week=monday(parse_date(self.data['term']['start']))+timedelta(weeks=i);self.refresh_schedule()
    def shift_week(self,d):self.selected_week+=timedelta(weeks=d);self.refresh_schedule()
    def current_week(self):self.selected_week=monday(max(parse_date(self.data['term']['start']),min(date.today(),parse_date(self.data['term']['end']))));self.refresh_schedule()
    def jump_date(self):
        d=FramelessDialog(self);d.setWindowTitle('跳转日期');l=vlayout(d,(24,24,24,24));l.addWidget(text('查看哪一天？','Section'));w=QDateEdit(qdate(self.selected_week));w.setCalendarPopup(True);w.setDisplayFormat('yyyy-MM-dd');w.setDateRange(qdate(parse_date(self.data['term']['start'])),qdate(parse_date(self.data['term']['end'])));l.addWidget(w);l.addWidget(btn('查看课表','Primary',callback=d.accept))
        if d.exec()==QDialog.Accepted:self.selected_week=monday(pydate(w.date()));self.refresh_schedule()
    def refresh_dashboard(self):
        clear_layout(self.dashboard_l);today=date.today();tomorrow=today+timedelta(days=1);today_rows=classes_on(self.data,today,self.prefs);tomorrow_rows=classes_on(self.data,tomorrow,self.prefs);next_item=next(occurrences(self.data,tomorrow,prefs=self.prefs),None)
        heading=page_header(self.greeting,'一眼看清接下来的安排，把注意力留给学习。');self.home_heading=heading.findChild(QLabel,'Heading');self.dashboard_l.addWidget(heading)
        hero=QFrame();hero.setObjectName('Hero');hero.setStyleSheet('QFrame#Hero{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #125F59,stop:1 #208578);border-radius:20px;} QFrame#Hero QLabel{color:#FFFFFF;}');hl=hlayout(hero,(28,22,22,22),18);info=vlayout(spacing=13)
        badge=text('明日预告' if tomorrow_rows else '接下来的安排');badge.setStyleSheet('color:#D2EDE1;font-size:12px;');info.addWidget(badge)
        if tomorrow_rows:title=f'明天有 {len(tomorrow_rows)} 门课，提前准备好。';sub=f"第一门：{tomorrow_rows[0]['course']}\n{class_time(tomorrow_rows[0],self.prefs)} · {tomorrow_rows[0].get('room') or '教室未填写'}"
        elif next_item:
            day,row=next_item;title='明天没有课，留一点时间给自己。';sub=f"下一次课程：{day:%m月%d日} · {row['course']}"
        else:title='接下来的时间，由你安排。';sub='目前没有接下来的课程，可以添加或导入新的课表。'
        title_label=text(title,wrap=True);title_label.setStyleSheet('font-size:23px;font-weight:600;color:white;');info.addWidget(title_label);sub_label=text(sub,wrap=True);sub_label.setStyleSheet('font-size:12px;color:#D2EDE1;');info.addWidget(sub_label);link=btn('查看完整课表  →',callback=lambda:self.navigate(1));link.setStyleSheet('background:rgba(255,255,255,25);color:white;border:1px solid rgba(255,255,255,35);border-radius:8px;padding:8px 14px;');info.addWidget(link,alignment=Qt.AlignLeft);hl.addLayout(info,1);hl.addWidget(HeroArt());self.dashboard_l.addWidget(hero)
        metrics=hlayout(spacing=16);weekly=list(occurrences(self.data,monday(today),monday(today)+timedelta(days=6),self.prefs));unique=len({course_key(r) for _,r in occurrences(self.data,prefs=self.prefs)})
        for value,label,glyph,small in [(str(len(today_rows)),'今日课程','calendar','按节次排列'),(str(len(weekly)),'本周安排','book',f'共 {unique} 门课程'),(self.prefs['reminder_time'] if self.prefs['reminder_enabled'] else '已关闭','每日提醒','bell','明天无课时保持安静')]:
            c=card();cl=vlayout(c,(22,18,22,18),8);r=hlayout();r.addWidget(text(label,'Muted'));r.addStretch();im=text('');im.setPixmap(icon(glyph,self.theme['accent'],20).pixmap(20,20));r.addWidget(im);cl.addLayout(r);cl.addWidget(text(value,'BigNumber'));cl.addWidget(text(small,'Caption'));metrics.addWidget(c,1)
        self.dashboard_l.addLayout(metrics);two=hlayout(spacing=18)
        for day,rows,title in [(today,today_rows,'今日安排'),(tomorrow,tomorrow_rows,'明天的课程')]:
            c=card();cl=vlayout(c,(22,20,22,20),12);r=hlayout();r.addWidget(text(title,'Section'));r.addStretch();r.addWidget(text(f'{day:%m月%d日}  星期{WEEKDAYS[day.weekday()]}','Caption'));cl.addLayout(r)
            if rows:
                for row in rows:cl.addWidget(CourseRow(self,day,row,True))
            else:
                empty=vlayout(margins=(0,30,0,30),spacing=10);pic=text('');pic.setPixmap(icon('sun',self.theme['muted'],34).pixmap(34,34));empty.addWidget(pic,alignment=Qt.AlignCenter);empty.addWidget(text('这一天没有课程','Muted'),alignment=Qt.AlignCenter);empty.addWidget(text('休息、复习，或做一些喜欢的事。','Caption'),alignment=Qt.AlignCenter);cl.addLayout(empty)
            cl.addStretch();two.addWidget(c,1)
        self.dashboard_l.addLayout(two);self.dashboard_l.addStretch()
    def refresh_courses(self):
        if not hasattr(self,'course_grid'):return
        clear_layout(self.course_grid);groups=defaultdict(list);needle=self.search.text().strip().lower()
        for i in range(self.course_grid.rowCount()):self.course_grid.setRowStretch(i,0)
        for day,row in occurrences(self.data,prefs=self.prefs):
            if needle and not any(needle in str(row.get(k,'')).lower() for k in ['course','teacher','room']):continue
            groups[course_key(row)].append((day,row))
        self.course_count.setText(f'共 {len(groups)} 门课程 · {sum(map(len,groups.values()))} 次安排'+(' · 搜索结果' if needle else ''))
        for i,(key,items) in enumerate(sorted(groups.items())):
            r=items[0][1];c=card();c.setMinimumHeight(215);cl=vlayout(c,(22,20,22,18),12);fg,bg=COLORS[color_index(r)];head=hlayout();badge=text('COURSE');badge.setStyleSheet(f'color:{fg};font-size:10px;letter-spacing:2px;');head.addWidget(badge);head.addStretch();head.addWidget(text(f'{len(items)} 次','Badge'));cl.addLayout(head);name=text(r['course'],'Section',True);cl.addWidget(name);cl.addWidget(text((r.get('teacher') or '教师未填写')+'  ·  '+' / '.join(sorted({x.get('room') or '教室未填写' for _,x in items})),'Muted',True));remaining=sum(d>=date.today() for d,_ in items);days='、'.join('周'+WEEKDAYS[n] for n in sorted({d.weekday() for d,_ in items}));cl.addWidget(text(f'{days}  ·  还有 {remaining} 次安排','Caption',True));cl.addStretch();cl.addWidget(btn('查看与编辑  →','Ghost',callback=lambda _=False,k=key:CourseDetails(self,k).exec()),alignment=Qt.AlignLeft);self.course_grid.addWidget(c,i//self.course_columns,i%self.course_columns)
        if not groups:
            c=card();cl=vlayout(c,(40,70,40,70));cl.addWidget(text('没有找到课程','Section'),alignment=Qt.AlignCenter);cl.addWidget(text('尝试其他关键词，或导入、添加新的课程。','Muted'),alignment=Qt.AlignCenter);cl.addWidget(btn('导入课表','Primary','upload',lambda:self.navigate(3)),alignment=Qt.AlignCenter);self.course_grid.addWidget(c,0,0,1,self.course_columns)
        self.course_grid.setRowStretch((len(groups)+self.course_columns-1)//self.course_columns,1)
    def add(self,day=None,period=1):
        if isinstance(day,bool):day=None
        day=day if isinstance(day,date) else max(parse_date(self.data['term']['start']),min(date.today(),parse_date(self.data['term']['end'])));dialog=CourseDialog(self,day=day,period=period)
        if dialog.exec()==QDialog.Accepted:
            row=dialog.value();candidate=add_course(self.data,row,pydate(dialog.day.date()));self.commit(candidate)
    def edit(self,day,row):
        record=copy.deepcopy(row);scope='one'
        if row.get('_source')=='rule':
            choice=ScopeDialog(self)
            if choice.exec()!=QDialog.Accepted:return
            scope=choice.scope
            if scope=='one':record.pop('weekday',None);record.pop('weeks',None)
            elif scope=='future':record['weeks']=[w for w in record['weeks'] if w>=week_number(parse_date(self.data['term']['start']),day)]
        dialog=CourseDialog(self,record,day)
        if dialog.exec()==QDialog.Accepted:
            value=dialog.value()
            if row.get('_source')=='rule' and scope!='one' and 'weekday' not in value:
                extent='从所选日期起的重复安排' if scope=='future' else '这条课程的全部重复安排'
                if not self.confirm('改为单次课程',f'{extent}将替换为 {pydate(dialog.day.date())} 的一节单次课程。是否保存？','保存修改'):return
            self.commit(edit_course(self.data,row,day,value,scope,target_day=pydate(dialog.day.date())))
        elif dialog.delete_requested:
            if self.confirm('删除课程？',f"{row['course']}\n"+{'one':'仅删除这一次安排。','future':'删除这一天及之后的安排。','all':'删除这条安排的所有周次。'}[scope],'删除课程',True):self.commit(edit_course(self.data,row,day,record,scope,True))
    def commit(self,candidate):
        try:
            validate_schedule(candidate);new_conflicts={(str(d),a['id'],b['id']) for d,a,b in find_conflicts(candidate)};existing={(str(d),a['id'],b['id']) for d,a,b in find_conflicts(self.data)}
            if new_conflicts-existing and not self.confirm('有课程时段重叠',f'发现 {len(new_conflicts-existing)} 次重叠安排。仍然保存？重叠课程会并排显示。','仍然保存'):return False
            save_schedule(candidate);self.data=normalize(candidate);self.refresh();self.toast('课表已保存，提醒同步更新');return True
        except Exception as e:self.notice('无法保存课表',str(e));return False
    def export_json(self):
        path,_=QFileDialog.getSaveFileName(self,'导出完整课表','我的课表.json','课表数据 (*.json)')
        if path:
            try:atomic_json(Path(path),self.data);self.toast('完整课表已导出')
            except Exception as e:self.notice('导出失败',str(e))
    def export_csv(self):
        path,_=QFileDialog.getSaveFileName(self,'导出课程列表','我的课表.csv','CSV (*.csv)')
        if path:
            try:
                with open(path,'w',encoding='utf-8-sig',newline='') as f:
                    w=csv.writer(f);w.writerow(['安排','星期','日期','开始节次','结束节次','课程名称','教师','教室','周次'])
                    for day,r in occurrences(self.data,prefs=self.prefs):w.writerow(['单次','',str(day),r['period_start'],r['period_end'],r['course'],r.get('teacher',''),r.get('room',''),''])
                self.toast('课程列表已导出')
            except Exception as e:self.notice('导出失败',str(e))
    def export_image(self):
        path,_=QFileDialog.getSaveFileName(self,'保存本周课表',f'课表-{self.selected_week}.png','图片 (*.png)')
        if path:
            if self.calendar.grab().save(path):self.toast('本周课表图片已保存')
            else:self.notice('保存失败','无法写入图片，请选择其他文件夹。')
    def run_job(self,work,done,failed=None):
        job=Job(work,self);self.jobs.append(job);job.done.connect(done);job.failed.connect(failed or (lambda e:self.notice('操作未完成',e)))
        def finish():self.jobs.remove(job);job.deleteLater()
        job.finished.connect(finish);job.start()
    def test_notification(self):
        item=next(occurrences(self.data,date.today()+timedelta(days=1),prefs=self.prefs),None)
        if item:day,_=item;title,body,_=notification_text(self.data,self.prefs,day)
        else:title='课程助手 · 示例通知';body='明天 · 第 1–2 节  数据结构\n张老师 · 教学楼 101\n这是一条示例通知。'
        self.run_job(lambda:show_notification('课程助手 · '+title,body),lambda _:self.toast('示例通知已发送，请查看 Windows 通知中心'))
    def notice(self,title,body):NoticeDialog(self,title,body).exec()
    def confirm(self,title,body,action='确认',danger=False):return NoticeDialog(self,title,body,action,True,danger).exec()==QDialog.Accepted
    def toast(self,message):
        self.toast_label.setText(message);self.toast_label.adjustSize();self.toast_label.move((self.width()-self.toast_label.width())//2,self.height()-self.toast_label.height()-25);self.toast_label.show();self.toast_label.raise_();self.toast_timer.start(3500)
    def setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():return
        if not self.tray:
            self.tray=QSystemTrayIcon(self.windowIcon(),self);self.tray.setToolTip('课序 · 课程助手');menu=QMenu(self);menu.addAction('打开课程助手',self.bring_to_front);menu.addAction('退出',self.quit);self.tray.setContextMenu(menu);self.tray.activated.connect(lambda reason:self.bring_to_front() if reason==QSystemTrayIcon.DoubleClick else None)
        self.tray.setVisible(self.prefs['close_to_tray'])
    def bring_to_front(self):
        if self.pages.currentIndex()==0:self.rotate_greeting()
        self.showNormal();self.raise_();self.activateWindow()
    def quit(self):self.exiting=True;self.close()
    def closeEvent(self,event):
        if any(j.isRunning() for j in self.jobs):self.notice('正在处理','请等待当前识别或设置保存完成后再关闭。');event.ignore();return
        if self.prefs['close_to_tray'] and self.tray and not self.exiting:self.hide();event.ignore();return
        if self.tray:self.tray.hide()
        event.accept()
    def tick(self):
        if self.last_day!=date.today():self.last_day=date.today();self.refresh()
