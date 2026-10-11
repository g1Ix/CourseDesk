"""Shared Windows frame: native resize/snap, integrated Qt title controls."""
import ctypes
from ctypes import wintypes as wt
import sys
from PySide6.QtCore import Qt,QEvent,QSize,QTimer
from PySide6.QtGui import QIcon,QPixmap
from PySide6.QtWidgets import QApplication,QMainWindow,QDialog,QFrame,QLabel,QPushButton,QHBoxLayout,QVBoxLayout,QWidget,QScrollArea
from course_data import RESOURCE_DIR
from course_style import icon,AnimatedButton

if sys.platform=='win32':
    user32=ctypes.WinDLL('user32',use_last_error=True)
    user32.GetWindowLongPtrW.argtypes=[wt.HWND,ctypes.c_int];user32.GetWindowLongPtrW.restype=ctypes.c_ssize_t
    user32.SetWindowLongPtrW.argtypes=[wt.HWND,ctypes.c_int,ctypes.c_ssize_t];user32.SetWindowLongPtrW.restype=ctypes.c_ssize_t
    user32.SetWindowPos.argtypes=[wt.HWND,wt.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wt.UINT]
    user32.GetWindowRect.argtypes=[wt.HWND,ctypes.POINTER(wt.RECT)]
    user32.ClientToScreen.argtypes=[wt.HWND,ctypes.POINTER(wt.POINT)]
    user32.IsZoomed.argtypes=[wt.HWND]
    user32.ShowWindow.argtypes=[wt.HWND,ctypes.c_int]
    user32.MonitorFromWindow.argtypes=[wt.HWND,wt.DWORD];user32.MonitorFromWindow.restype=wt.HANDLE
    class MonitorInfo(ctypes.Structure):
        _fields_=[('size',wt.DWORD),('monitor',wt.RECT),('work',wt.RECT),('flags',wt.DWORD)]
    user32.GetMonitorInfoW.argtypes=[wt.HANDLE,ctypes.POINTER(MonitorInfo)]
    class MinMaxInfo(ctypes.Structure):
        _fields_=[('reserved',wt.POINT),('max_size',wt.POINT),('max_position',wt.POINT),('min_track',wt.POINT),('max_track',wt.POINT)]

class WindowTitleBar(QFrame):
    def __init__(self,owner,dialog=False):
        super().__init__(owner);self.owner=owner;self.setObjectName('TitleBar');self.setFixedHeight(46)
        layout=QHBoxLayout(self);layout.setContentsMargins(15,0,9,0);layout.setSpacing(8)
        brand=QLabel();brand.setPixmap(QPixmap(str(RESOURCE_DIR/'assets/app.png')).scaled(25,25,Qt.KeepAspectRatio,Qt.SmoothTransformation));layout.addWidget(brand)
        self.title=QLabel(owner.windowTitle());self.title.setObjectName('WindowTitle');layout.addWidget(self.title);owner.windowTitleChanged.connect(self.title.setText)
        self.hint=QLabel('  把每一天，安排得清清楚楚');self.hint.setObjectName('TitleBarHint');self.hint.setVisible(not dialog);layout.addWidget(self.hint);layout.addStretch()
        self.minimize=self.control('minimize','最小化',owner.showMinimized);self.maximize=self.control('maximize','最大化',owner.toggle_maximized)
        self.close_button=self.control('window_close','关闭',owner.close,True)
        if not dialog:layout.addWidget(self.minimize);layout.addWidget(self.maximize)
        else:self.minimize.hide();self.maximize.hide()
        layout.addWidget(self.close_button);self.refresh_controls()
    def control(self,glyph,title,callback,close=False):
        button=AnimatedButton(self);button.setObjectName('WindowClose' if close else 'WindowControl');button.setProperty('glyph',glyph);button.setIconSize(QSize(16,16));button.setFixedSize(43,34);button.setToolTip(title);button.setAccessibleName(title);button.clicked.connect(callback);return button
    def refresh_controls(self):
        theme=getattr(self.owner,'theme',None) or getattr(self.owner.parentWidget(),'theme',{'ink':'#172E2D'})
        for button in (self.minimize,self.maximize,self.close_button):
            glyph=('window_restore' if self.owner.isMaximized() else 'maximize') if button==self.maximize else button.property('glyph')
            button.setIcon(icon(glyph,theme['ink'],16))
            button.prepare_assets()
        self.maximize.setToolTip('还原' if self.owner.isMaximized() else '最大化')
        self.maximize.setAccessibleName(self.maximize.toolTip())

class WindowFrame:
    def init_frame(self):
        self.setWindowFlag(Qt.FramelessWindowHint,True)
        self.setWindowIcon(QIcon(str(RESOURCE_DIR/'assets/app.ico')));self._native_ready=False
    def showEvent(self,event):
        super().showEvent(event)
        if sys.platform=='win32' and not self._native_ready and self.windowHandle() and self.windowHandle().screen():
            # Offscreen previews have no real HWND; never call user32 on them.
            from PySide6.QtGui import QGuiApplication
            if QGuiApplication.platformName()=='windows':self.configure_native()
        if hasattr(self,'titlebar'):self.titlebar.refresh_controls()
    def configure_native(self):
        handle=wt.HWND(int(self.winId()));style=user32.GetWindowLongPtrW(handle,-16)
        resizable=self.minimumWidth()<self.maximumWidth() or self.minimumHeight()<self.maximumHeight()
        style=(style|0x80000)&~0xC00000
        if resizable:style|=0x40000
        if isinstance(self,QMainWindow):style|=0x30000
        user32.SetWindowLongPtrW(handle,-16,style);self._native_ready=True
        user32.SetWindowPos(handle,None,0,0,0,0,0x0027)
        try:
            dwm=ctypes.WinDLL('dwmapi');dwm.DwmSetWindowAttribute.argtypes=[wt.HWND,wt.DWORD,ctypes.c_void_p,wt.DWORD]
            corner=ctypes.c_int(2);dwm.DwmSetWindowAttribute(handle,33,ctypes.byref(corner),4)
            border=ctypes.c_uint(0xFFFFFFFE);dwm.DwmSetWindowAttribute(handle,34,ctypes.byref(border),4)
        except OSError:pass
    def toggle_maximized(self):
        if sys.platform=='win32' and self._native_ready:
            user32.ShowWindow(wt.HWND(int(self.winId())),9 if self.isMaximized() or user32.IsZoomed(wt.HWND(int(self.winId()))) else 3)
        else:self.showNormal() if self.isMaximized() else self.showMaximized()
    def changeEvent(self,event):
        super().changeEvent(event)
        if event.type()==QEvent.WindowStateChange:
            if hasattr(self,'titlebar'):self.titlebar.refresh_controls()
            # Qt can rewrite native styles while restoring a frameless window.
            if sys.platform=='win32' and getattr(self,'_native_ready',False):QTimer.singleShot(0,self.configure_native)
    def nativeEvent(self,event_type,message):
        if sys.platform=='win32' and getattr(self,'_native_ready',False):
            msg=wt.MSG.from_address(int(message));handle=msg.hWnd
            if msg.message==0x83 and getattr(self,'_native_ready',False):
                # First RECT also heads NCCALCSIZE_PARAMS. Constrain maximized client
                # bounds to the work area, including non-primary/negative monitors.
                if user32.IsZoomed(handle) or self.isMaximized():
                    monitor=MonitorInfo();monitor.size=ctypes.sizeof(monitor)
                    if user32.GetMonitorInfoW(user32.MonitorFromWindow(handle,2),ctypes.byref(monitor)):
                        rect=wt.RECT.from_address(msg.lParam)
                        rect.left,rect.top,rect.right,rect.bottom=monitor.work.left,monitor.work.top,monitor.work.right,monitor.work.bottom
                return True,0
            if msg.message==0x24:
                monitor=MonitorInfo();monitor.size=ctypes.sizeof(monitor)
                if user32.GetMonitorInfoW(user32.MonitorFromWindow(handle,2),ctypes.byref(monitor)):
                    info=MinMaxInfo.from_address(msg.lParam);work=monitor.work;bounds=monitor.monitor
                    info.max_position.x=work.left-bounds.left;info.max_position.y=work.top-bounds.top
                    info.max_size.x=work.right-work.left;info.max_size.y=work.bottom-work.top
                    scale=self.devicePixelRatioF();info.min_track.x=round(self.minimumWidth()*scale);info.min_track.y=round(self.minimumHeight()*scale)
                    info.max_track.x=max(info.min_track.x,min(round(self.maximumWidth()*scale),bounds.right-bounds.left+16))
                    info.max_track.y=max(info.min_track.y,min(round(self.maximumHeight()*scale),bounds.bottom-bounds.top+16))
                    return True,0
            if msg.message==0x84:
                rect=wt.RECT();user32.GetWindowRect(handle,ctypes.byref(rect))
                x=ctypes.c_short(msg.lParam&0xffff).value;y=ctypes.c_short((msg.lParam>>16)&0xffff).value
                scale=self.devicePixelRatioF();edge=round(8*scale)
                left,right=x<rect.left+edge,x>=rect.right-edge;top,bottom=y<rect.top+edge,y>=rect.bottom-edge
                horizontal=self.minimumWidth()<self.maximumWidth();vertical=self.minimumHeight()<self.maximumHeight()
                if not (user32.IsZoomed(handle) or self.isMaximized()):
                    left,right=left and horizontal,right and horizontal;top,bottom=top and vertical,bottom and vertical
                    if (top or bottom) and (left or right):return True,{(True,True):13,(True,False):14,(False,True):16,(False,False):17}[(top,left)]
                    if top:return True,12
                    if bottom:return True,15
                    if left:return True,10
                    if right:return True,11
                # Convert native physical coordinates relative to HWND; never multiply
                # global Qt coordinates (which fails on mixed-DPI monitors).
                titlebar=getattr(self,'titlebar',None)
                if titlebar:
                    client_origin=wt.POINT();user32.ClientToScreen(handle,ctypes.byref(client_origin))
                    pos=titlebar.mapTo(self,titlebar.rect().topLeft())
                    if pos.y()*scale<=y-client_origin.y<(pos.y()+titlebar.height())*scale:
                        for button in (titlebar.minimize,titlebar.maximize,titlebar.close_button):
                            if not button.isVisible():continue
                            p=button.mapTo(self,button.rect().topLeft());bx,by=client_origin.x+p.x()*scale,client_origin.y+p.y()*scale
                            if bx<=x<bx+button.width()*scale and by<=y<by+button.height()*scale:return True,1
                        return True,2
        return super().nativeEvent(event_type,message)

class FramelessMainWindow(WindowFrame,QMainWindow):
    def __init__(self,parent=None):super().__init__(parent);self.init_frame()

class FramelessDialog(WindowFrame,QDialog):
    def __init__(self,parent=None):
        super().__init__(parent);self.init_frame();self.setMinimumHeight(100)
        outer=QVBoxLayout(self);outer.setContentsMargins(0,0,0,0);outer.setSpacing(0)
        self.titlebar=WindowTitleBar(self,True);outer.addWidget(self.titlebar)
        self.content=QWidget();self.content.setObjectName('DialogContent')
        self.body_scroll=QScrollArea();self.body_scroll.setFrameShape(QFrame.NoFrame);self.body_scroll.setWidgetResizable(True);self.body_scroll.viewport().setObjectName('ScrollViewport');self.body_scroll.setWidget(self.content);outer.addWidget(self.body_scroll,1)
        self._sized=False
    def showEvent(self,event):
        if not self._sized:
            self._sized=True;available=(self.parentWidget().screen() if self.parentWidget() else QApplication.primaryScreen()).availableGeometry()
            if type(self).__name__ in ('NoticeDialog','ScopeDialog','DayArrangement','CourseDialog') or type(self)==FramelessDialog:
                hint=self.content.sizeHint();self.resize(max(self.minimumWidth(),hint.width(),440),min(available.height()-80,hint.height()+46))
        super().showEvent(event)
