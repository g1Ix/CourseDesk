from PySide6.QtCore import Qt, QRectF, QSize, Signal,Property,QPropertyAnimation,QEasingCurve,QEvent
from PySide6.QtGui import QColor,QPainter,QPixmap,QIcon,QFont,QPen,QFontMetricsF
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QAbstractButton,QPushButton
from math import ceil

LIGHT={'bg':'#F5F7F7','panel':'#FFFFFF','sidebar':'#FBFCFC','ink':'#172E2D','muted':'#7B8B8A','line':'#E5EBE9','accent':'#177D72','soft':'#E9F4EF','hover':'#F0F5F3','danger':'#C7524D'}
DARK={'bg':'#121C1E','panel':'#1C292B','sidebar':'#172325','ink':'#E4EEEC','muted':'#91AAA5','line':'#304244','accent':'#6FC8B0','soft':'#24423C','hover':'#273A3B','danger':'#F39386'}
COLORS=[('#236DAD','#E9F2FB'),('#218574','#E8F5EE'),('#B88029','#FCF3DF'),('#8B64AF','#F1ECF8'),('#A96068','#FAEBEF'),('#348A9E','#E7F4F7')]
PATHS={
 'home':'<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z"/>',
 'calendar':'<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M16 3v4M8 3v4M3 11h18M8 15h2M14 15h2M8 18h2"/>',
 'book':'<path d="M12 6v15M12 6C9 3 6 3 3 4v15c3-1 6-1 9 2 3-3 6-3 9-2V4c-3-1-6-1-9 2z"/>',
 'upload':'<path d="M12 16V3m-5 5 5-5 5 5M4 15v5a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-5"/>',
 'settings':'<path d="m9 3-1 3-3 1-2 3 2 2-1 3 3 3 3-1 2 2 3-2 2 1 3-3-1-3 2-2-2-3-3-1-1-3z"/><circle cx="12" cy="12" r="3"/>',
 'plus':'<path d="M12 5v14M5 12h14"/>',
 'left':'<path d="m15 5-7 7 7 7"/>','right':'<path d="m9 5 7 7-7 7"/>',
 'bell':'<path d="M5 17h14l-2-3V9a5 5 0 0 0-10 0v5zm5 3h4"/>',
 'search':'<circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/>',
 'minimize':'<path d="M5 12h14"/>','maximize':'<rect x="5" y="5" width="14" height="14" rx="1.5"/>','window_restore':'<path d="M8 8V5h11v11h-3M5 9h11v11H5z"/>','window_close':'<path d="m6 6 12 12M18 6 6 18"/>',
 'sun':'<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1 1M18 18l1 1M5 19l1-1M18 6l1-1"/>',
 'moon':'<path d="M20 14A9 9 0 0 1 10 4a9 9 0 1 0 10 10z"/>',
 'download':'<path d="M12 3v13m-5-5 5 5 5-5M4 16v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/>',
 'restore':'<path d="M3 10a9 9 0 1 1 2 8M3 4v6h6M12 7v5l3 2"/>',
 'map':'<path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0z"/><circle cx="12" cy="10" r="2.5"/>',
 'user':'<circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>',
 'clock':'<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',
 'check':'<path d="m5 12 4 4L19 6"/>','trash':'<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/>',
 'close':'<path d="m6 6 12 12M6 18 18 6"/>','folder':'<path d="M3 7V4h6l3 3h9v13H3z"/>',
 'image':'<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1"/><path d="m3 17 6-6 5 5 3-3 4 4"/>',
 'file':'<path d="M14 3H5v18h14V8zM14 3v5h5M8 12h8M8 16h8"/>',
 'spark':'<path d="m12 3 2 6 6 3-6 2-2 7-3-7-6-2 6-3z"/>',
 'external':'<path d="M14 3h7v7M21 3l-11 11M10 3H3v18h18v-7"/>',
 'info':'<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7v1"/>',
 'edit':'<path d="m16 3 5 5-12 12-6 1 1-6zM13 6l5 5"/>',
 'dots':'<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
}
def icon(name,color='#177D72',size=24):
    path=PATHS.get(name,PATHS['calendar'])
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{path}</svg>'
    pix=QPixmap(size*2,size*2);pix.fill(Qt.transparent)
    p=QPainter(pix);QSvgRenderer(svg.encode()).render(p);p.end();pix.setDevicePixelRatio(2)
    return QIcon(pix)

_BUTTON_PIXMAPS={}

def button_pixmap(glyph,color,dpr):
    """Fixed-size, shared raster assets; generated before hover starts."""
    key=(glyph,color,dpr)
    if key not in _BUTTON_PIXMAPS:
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{PATHS.get(glyph,PATHS["dots"])}</svg>'
        pix=QPixmap(round(18*dpr),round(18*dpr));pix.fill(Qt.transparent)
        p=QPainter(pix);QSvgRenderer(svg.encode()).render(p);p.end();pix.setDevicePixelRatio(dpr)
        _BUTTON_PIXMAPS[key]=pix
    return _BUTTON_PIXMAPS[key]

class AnimatedButton(QPushButton):
    """Stable hit area, circle-to-pill transition, label with right-hand icon."""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self._progress=0.0;self._hovered=False;self._keyboard_focus=False
        self._goal=0.0;self._assets={};self._asset_key=None;self._label_key=None
        self._animation=QPropertyAnimation(self,b'progress',self)
        self._animation.setDuration(240)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover)
        self.setAutoDefault(False)
    def get_progress(self):return self._progress
    def set_progress(self,value):self._progress=float(value);self.update()
    progress=Property(float,get_progress,set_progress)
    def animate(self):
        goal=1.0 if self.isEnabled() and (self._hovered or self._keyboard_focus) else 0.0
        if goal==self._goal:return
        self.prepare_assets();self._goal=goal
        self._animation.stop();self._animation.setStartValue(self._progress)
        self._animation.setDuration(max(40,round(240*abs(goal-self._progress))))
        self._animation.setEndValue(goal)
        self._animation.start()
    def enterEvent(self,event):self._hovered=True;self.animate();super().enterEvent(event)
    def leaveEvent(self,event):self._hovered=False;self.animate();super().leaveEvent(event)
    def focusInEvent(self,event):
        super().focusInEvent(event)
        self._keyboard_focus=event.reason() in (Qt.TabFocusReason,Qt.BacktabFocusReason,Qt.ShortcutFocusReason)
        self.animate()
    def focusOutEvent(self,event):super().focusOutEvent(event);self._keyboard_focus=False;self.animate()
    def showEvent(self,event):self.prepare_assets();super().showEvent(event)
    def hideEvent(self,event):
        self._animation.stop();self._hovered=False;self._keyboard_focus=False;self._goal=0.0;self._progress=0.0;super().hideEvent(event)
    def changeEvent(self,event):
        super().changeEvent(event)
        if event.type()==QEvent.EnabledChange:
            self._animation.stop();self._goal=0.0;self._progress=0.0;self.update()
    def sizeHint(self):
        hint=super().sizeHint()
        label=self.text().strip()
        measured=QFont(self.font());measured.setPixelSize(13);measured.setBold(self.objectName() in ('Primary','Nav'))
        width=40 if not label or label.isdigit() else ceil(QFontMetricsF(measured).horizontalAdvance(label))+64
        return QSize(max(hint.width(),width),max(hint.height(),40))
    def minimumSizeHint(self):return self.sizeHint()
    def theme(self):
        owner=self.parentWidget()
        while owner:
            theme=getattr(owner,'theme',None)
            if isinstance(theme,dict) and 'ink' in theme:return theme
            owner=owner.parentWidget()
        return LIGHT
    def prepare_assets(self):
        t=self.theme();dpr=max(2.0,self.devicePixelRatioF())
        glyph=self.property('motionGlyph') or self.property('glyph') or 'dots'
        key=(glyph,t['ink'],t['muted'],t['accent'],dpr)
        if key!=self._asset_key:
            self._assets={color:button_pixmap(glyph,color,dpr) for color in ('#FFFFFF',t['ink'],t['muted'],t['accent'])}
            if glyph=='maximize':
                self._restore_assets={color:button_pixmap('window_restore',color,dpr) for color in self._assets}
            self._asset_key=key
    def draw_icon(self,p,glyph,color,rect):
        assets=self._restore_assets if glyph=='window_restore' and hasattr(self,'_restore_assets') else self._assets
        pix=assets[color]
        p.drawPixmap(rect,pix,QRectF(pix.rect()))
    def paintEvent(self,event):
        # Normally warmed on show/theme changes. This also handles DPI migration.
        self.prepare_assets()
        t=self.theme();v=1.0 if self.property('alwaysExpanded') else self._progress;name=self.objectName()
        control=name in ('WindowControl','WindowClose')
        icon_only=not self.text().strip()
        label=self.text().strip() or self.accessibleName() or self.toolTip()
        numeric=label.isdigit();selected=self.isCheckable() and self.isChecked()
        danger=name in ('Danger','WindowClose') or self.property('motionDanger')
        nav=name=='Nav'
        hovered=QColor('#DC4F5C' if danger else '#177D72')
        base=QColor(t['accent'] if selected else '#141414')
        if nav:
            base=QColor(t['soft'] if selected else t['sidebar']);hovered=QColor(t['soft'] if selected else t['hover'])
        elif control:
            base=QColor(t['bg']);hovered=QColor('#DC4F5C' if danger else t['hover'])
        color=QColor.fromRgbF(*(base.getRgbF()[i]+(hovered.getRgbF()[i]-base.getRgbF()[i])*v for i in range(4)))
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.setRenderHint(QPainter.SmoothPixmapTransform)
        if not self.isEnabled():color=QColor(t['line'])
        available=QRectF(self.rect()).adjusted(2,2,-2,-2)
        h=min(40.0,available.height());diameter=h
        width=diameter+(available.width()-diameter)*v
        if numeric or control or icon_only or nav:width=available.width()
        x=available.center().x()-width/2
        rect=QRectF(x,available.center().y()-h/2,width,h)
        if self.isDown():
            rect.adjust(1,1,-1,-1);color=color.darker(115)
        p.setPen(Qt.NoPen)
        if not nav and not control:
            p.setBrush(QColor(0,0,0,12));p.drawRoundedRect(rect.translated(0,1.5),h/2,h/2)
        p.setBrush(color);p.drawRoundedRect(rect,h/2,h/2)
        if self._keyboard_focus:
            p.setBrush(Qt.NoBrush);p.setPen(QPen(QColor(t['accent']),1.5));p.drawRoundedRect(rect.adjusted(-1,-1,1,1),h/2,h/2)
        p.setClipRect(rect)
        foreground='#FFFFFF' if self.isEnabled() else t['muted']
        if nav:foreground=t['accent'] if selected else t['ink']
        elif control:foreground='#FFFFFF' if danger and v>.5 else t['ink']
        glyph=self.property('motionGlyph') or self.property('glyph') or 'dots'
        if control:
            glyph=('window_restore' if self.window().isMaximized() else 'maximize') if glyph=='maximize' else glyph
        if numeric:
            p.setPen(QColor(foreground));p.drawText(rect,Qt.AlignCenter,label)
        elif control or icon_only:
            self.draw_icon(p,glyph,foreground,QRectF(rect.center().x()-9,rect.center().y()-9,18,18))
        else:
            key=(label,round(available.width()),name,self.font().toString())
            if key!=self._label_key:
                self._label_font=QFont(self.font());self._label_font.setPixelSize(13);self._label_font.setBold(name in ('Primary','Nav'))
                fm=QFontMetricsF(self._label_font)
                self._shown=fm.elidedText(label,Qt.ElideRight,max(1,int(available.width()-54)))
                self._text_width=fm.horizontalAdvance(self._shown);self._label_key=key
            group_width=self._text_width+8+18
            target_x=available.left()+16 if nav else available.center().x()-group_width/2
            target_icon=available.right()-34 if nav else target_x+self._text_width+8
            icon_x=target_icon if nav else available.center().x()-9+(target_icon-(available.center().x()-9))*v
            self.draw_icon(p,glyph,foreground,QRectF(icon_x,rect.center().y()-9,18,18))
            p.setOpacity(1.0 if nav else v)
            p.setFont(self._label_font);p.setPen(QColor(foreground))
            p.drawText(QRectF(target_x-(0 if nav else (1-v)*8),rect.top(),self._text_width+1,rect.height()),Qt.AlignVCenter|Qt.AlignLeft,self._shown)
        p.end()

class Switch(QAbstractButton):
    def __init__(self,checked=False,parent=None):
        super().__init__(parent);self.setCheckable(True);self.setChecked(checked);self.setFixedSize(44,26);self.setCursor(Qt.PointingHandCursor)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen);p.setBrush(QColor('#177D72' if self.isChecked() else '#B9C6C2'))
        p.drawRoundedRect(QRectF(0,1,44,24),12,12);p.setBrush(QColor('white'))
        p.drawEllipse(QRectF(24 if self.isChecked() else 3,4,18,18));p.end()

def stylesheet(t):
    return f'''
    QWidget {{font-family:"Microsoft YaHei UI"; font-size:13px; color:{t['ink']};}}
    QMainWindow, QDialog {{background:{t['bg']};}}
    QWidget#Page,QWidget#DialogContent {{background:{t['bg']};}}
    QWidget[scrollContent="true"],QWidget#ScrollViewport {{background:{t['bg']};}}
    QFrame#Sidebar {{background:{t['sidebar']};border-right:1px solid {t['line']};}}
    QFrame#TitleBar {{background:{t['bg']};border:0;}}
    QFrame#TitleBar QLabel {{color:{t['ink']};background:transparent;}}
    QLabel#WindowTitle {{font-size:13px;font-weight:600;}}
    QLabel#TitleBarHint {{color:{t['muted']};font-size:11px;}}
    QPushButton#WindowControl {{background:transparent;border:0;border-radius:8px;padding:0;min-width:0;min-height:0;}}
    QPushButton#WindowControl:hover {{background:{t['hover']};}}
    QPushButton#WindowControl:pressed {{background:{t['soft']};}}
    QPushButton#WindowClose {{background:transparent;border:0;border-radius:8px;padding:0;min-width:0;min-height:0;}}
    QPushButton#WindowClose:hover {{background:#D94D5B;}}
    QPushButton#WindowClose:pressed {{background:#B93848;}}
    QFrame#Card {{background:{t['panel']};border:1px solid {t['line']};border-radius:16px;}}
    QLabel {{background:transparent;}}
    QLabel#Heading {{font-size:26px;font-weight:700;}}
    QLabel#Brand {{font-size:23px;font-weight:700;}}
    QLabel#Section {{font-size:17px;font-weight:600;}}
    QLabel#Muted {{color:{t['muted']};font-size:12px;}}
    QLabel#Caption {{color:{t['muted']};font-size:11px;}}
    QLabel#BigNumber {{font-size:30px;font-weight:600;}}
    QLabel#Error {{color:{t['danger']};font-size:12px;}}
    QLabel#Badge {{background:{t['soft']};color:{t['accent']};border-radius:7px;padding:4px 8px;font-size:11px;}}
    QLabel#Toast {{background:{t['ink']};color:{t['panel']};border-radius:10px;padding:12px 20px;}}
    QPushButton {{background:{t['panel']};border:1px solid {t['line']};border-radius:9px;padding:9px 15px;min-height:18px;}}
    QPushButton:hover {{background:{t['hover']};border-color:#9BC8B7;}}
    QPushButton:pressed {{background:{t['soft']};}}
    QPushButton:disabled {{color:{t['muted']};background:{t['hover']};}}
    QPushButton#Primary {{background:#177D72;color:white;border:1px solid #177D72;font-weight:600;}}
    QPushButton#Primary:hover {{background:#116B61;}}
    QPushButton#Danger {{background:{t['panel']};color:{t['danger']};border:1px solid {t['line']};}}
    QPushButton#Ghost {{background:transparent;border:0;color:{t['muted']};padding:7px;}}
    QPushButton#Nav {{background:transparent;border:0;text-align:left;padding:12px 18px;border-radius:10px;color:{t['muted']};font-size:14px;}}
    QPushButton#Nav:checked {{background:{t['soft']};color:{t['accent']};font-weight:600;}}
    QPushButton#Nav:hover {{background:{t['hover']};}}
    QLineEdit,QSpinBox,QComboBox,QDateEdit,QTimeEdit,QTextEdit {{background:{t['panel']};border:1px solid {t['line']};border-radius:8px;padding:7px 10px;min-height:20px;selection-background-color:{t['soft']};}}
    QLineEdit:focus,QSpinBox:focus,QComboBox:focus,QDateEdit:focus,QTimeEdit:focus,QTextEdit:focus {{border:1px solid {t['accent']};}}
    QComboBox::drop-down,QDateEdit::drop-down,QTimeEdit::drop-down {{border:0;width:24px;}}
    QComboBox::down-arrow,QDateEdit::down-arrow {{image:url(__ASSET_DIR__/down.svg);width:12px;height:12px;}}
    QSpinBox::up-button,QTimeEdit::up-button {{subcontrol-origin:border;subcontrol-position:top right;width:20px;border:0;background:transparent;}}
    QSpinBox::down-button,QTimeEdit::down-button {{subcontrol-origin:border;subcontrol-position:bottom right;width:20px;border:0;background:transparent;}}
    QSpinBox::up-arrow,QTimeEdit::up-arrow {{image:url(__ASSET_DIR__/up.svg);width:10px;height:10px;}}
    QSpinBox::down-arrow,QTimeEdit::down-arrow {{image:url(__ASSET_DIR__/down.svg);width:10px;height:10px;}}
    QComboBox QAbstractItemView {{background:{t['panel']};selection-background-color:{t['soft']};border:1px solid {t['line']};padding:6px;}}
    QCheckBox {{spacing:9px;}}
    QCheckBox::indicator {{width:17px;height:17px;border:1px solid #AEBFBA;border-radius:5px;background:{t['panel']};}}
    QCheckBox::indicator:checked {{background:#177D72; border-color:#177D72;image:url(__CHECK_SVG__);}}
    QTableWidget {{background:{t['panel']};alternate-background-color:{t['hover']};border:0;gridline-color:{t['line']};selection-background-color:{t['soft']};selection-color:{t['ink']};}}
    QTableWidget::item {{padding:8px;}}
    QHeaderView::section {{background:{t['hover']};color:{t['muted']};border:0;border-bottom:1px solid {t['line']};padding:12px 8px;font-weight:500;}}
    QScrollArea {{border:0;background:{t['bg']};}}
    QScrollBar:vertical {{background:transparent;width:7px;margin:3px;}}
    QScrollBar::handle:vertical {{background:#BECBC7;border-radius:3px;min-height:30px;}}
    QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{height:0;}}
    QScrollBar:horizontal {{background:transparent;height:7px;margin:3px;}}
    QScrollBar::handle:horizontal {{background:#BECBC7;border-radius:3px;min-width:30px;}}
    QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal {{width:0;}}
    QProgressBar {{background:{t['hover']};border:0;border-radius:4px;min-height:6px;max-height:6px;}}
    QProgressBar::chunk {{background:{t['accent']};border-radius:4px;}}
    QMenu {{background:{t['panel']};border:1px solid {t['line']};padding:5px;border-radius:10px;}}
    QMenu::item {{padding:9px 24px;border-radius:5px;}}
    QMenu::item:selected {{background:{t['soft']};}}
    QToolTip {{background:{t['panel']};color:{t['ink']};border:1px solid {t['line']};padding:9px;}}
    QCalendarWidget QWidget {{background:{t['panel']};}}
    QCalendarWidget QToolButton {{color:{t['ink']};background:{t['hover']};padding:6px;}}
    QTabBar::tab {{padding:9px 16px;background:{t['panel']};color:{t['muted']};border-bottom:2px solid transparent;}}
    QTabBar::tab:selected {{border-bottom:2px solid {t['accent']};color:{t['accent']};}}
    '''
