import os,sys,json,time,threading,traceback,ctypes
from pathlib import Path
from ctypes import wintypes as wt
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
os.environ['COURSEDESK_DATA_DIR']=str(root/'build/v22-native-data');os.environ['COURSEDESK_NO_OS_ACTIONS']='1'
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from course_ui import MainWindow,CourseDetails
from course_data import occurrences,course_key,save_schedule
save_schedule(json.loads((root/'examples/demo-schedule.json').read_text(encoding='utf-8')))
from course_window import user32,MonitorInfo
app=QApplication([]);app.setStyle('Fusion');w=MainWindow();w.resize(900 if w.devicePixelRatioF()>=1.5 else 1100,600 if w.devicePixelRatioF()>=1.5 else 760);w.move(80,50);w.navigate(2);w.show()
report={'scale':w.devicePixelRatioF(),'checks':[]};done=threading.Event();handle=wt.HWND(int(w.winId()))
user32.SetForegroundWindow.argtypes=[wt.HWND];user32.SetCursorPos.argtypes=[ctypes.c_int,ctypes.c_int]
user32.SendMessageW.argtypes=[wt.HWND,wt.UINT,wt.WPARAM,wt.LPARAM];user32.SendMessageW.restype=ctypes.c_ssize_t
user32.WindowFromPoint.argtypes=[wt.POINT];user32.WindowFromPoint.restype=wt.HWND
def rect():
 r=wt.RECT();assert user32.GetWindowRect(handle,ctypes.byref(r));return (r.left,r.top,r.right,r.bottom)
def drag(x,y,dx,dy):
 user32.SetCursorPos(x,y);time.sleep(.3);user32.mouse_event(2,0,0,0,0);time.sleep(.2)
 for i in range(1,9):user32.SetCursorPos(x+dx*i//8,y+dy*i//8);time.sleep(.06)
 user32.mouse_event(4,0,0,0,0);time.sleep(.5)
def run():
 point=wt.POINT();user32.GetCursorPos(ctypes.byref(point))
 try:
  user32.SetWindowPos(handle,wt.HWND(-1),0,0,0,0,3);user32.SetForegroundWindow(handle);time.sleep(.4)
  origin=rect();l,t,r,b=origin;width=r-l;height=b-t
  user32.SetCursorPos(l+260,t+24);time.sleep(.2);user32.mouse_event(2,0,0,0,0);time.sleep(.12);user32.mouse_event(4,0,0,0,0);time.sleep(.7)
  positions={'left':(l+2,(t+b)//2,-25,0),'right':(r-2,(t+b)//2,25,0),'top':((l+r)//2,t+2,0,-20),'bottom':((l+r)//2,b-2,0,20),'top-left':(l+2,t+2,-20,-20),'top-right':(r-2,t+2,20,-20),'bottom-left':(l+2,b-2,-20,20),'bottom-right':(r-2,b-2,20,20)}
  for name,(x,y,dx,dy) in positions.items():
   user32.SetWindowPos(handle,None,l,t,width,height,0x0004);time.sleep(.3);before=rect()
   # Native normal-frame position may be adjusted while Qt synchronizes margins.
   x=before[0]+2 if 'left' in name else before[2]-2 if 'right' in name else (before[0]+before[2])//2
   y=before[1]+2 if 'top' in name else before[3]-2 if 'bottom' in name else (before[1]+before[3])//2
   report['last_hit']=user32.SendMessageW(handle,0x84,0,(y<<16)|(x&0xffff));report['style']=hex(user32.GetWindowLongPtrW(handle,-16));report['point_window']=user32.WindowFromPoint(wt.POINT(x,y));report['handle']=handle.value;drag(x,y,dx,dy);after=rect()
   if (after[2]-after[0],after[3]-after[1])==(before[2]-before[0],before[3]-before[1]):drag(x,y,dx,dy);after=rect()
   assert (after[2]-after[0],after[3]-after[1])!=(before[2]-before[0],before[3]-before[1]),(name,before,after)
   report['checks'].append({'edge':name,'before':before,'after':after})
  user32.SetWindowPos(handle,None,l,t,width,height,0x0004);time.sleep(.2);drag(l+260,t+24,35,25);assert rect()[:2]!=(l,t);report['checks'].append('caption mouse drag')
  # Real double click on caption; native WM_NCLBUTTONDBLCLK must maximize.
  l,t,r,b=rect();user32.SetCursorPos(l+260,t+24)
  for _ in range(2):user32.mouse_event(2,0,0,0,0);user32.mouse_event(4,0,0,0,0);time.sleep(.08)
  time.sleep(.5);assert user32.IsZoomed(handle),'caption double click did not maximize'
  monitor=MonitorInfo();monitor.size=ctypes.sizeof(monitor);user32.GetMonitorInfoW(user32.MonitorFromWindow(handle,2),ctypes.byref(monitor))
  maxrect=rect();work=(monitor.work.left,monitor.work.top,monitor.work.right,monitor.work.bottom)
  client=wt.RECT();originpoint=wt.POINT();user32.GetClientRect(handle,ctypes.byref(client));user32.ClientToScreen(handle,ctypes.byref(originpoint));client_bounds=(originpoint.x,originpoint.y,originpoint.x+client.right,originpoint.y+client.bottom)
  assert client_bounds==work,(client_bounds,work);report['checks'].append('double click maximize client within work area')
  user32.SendMessageW(handle,0x112,0xF120,0);time.sleep(.3);user32.SetWindowPos(handle,wt.HWND(-1),0,0,0,0,3);user32.SetForegroundWindow(handle);assert not user32.IsZoomed(handle);report['checks'].append('restore')
  user32.SendMessageW(handle,0x112,0xF020,0);time.sleep(.2);assert user32.IsIconic(handle);user32.SendMessageW(handle,0x112,0xF120,0);time.sleep(.2);report['checks'].append('minimize and restore')
  # Click the real title control.
  user32.SetWindowPos(handle,wt.HWND(-1),0,0,0,0,3);user32.SetForegroundWindow(handle);time.sleep(.2)
  l,t,r,b=rect();cx,cy=report['button_center'];x,y=l+round(cx*report['scale']),t+round(cy*report['scale']);report['button_hit']=user32.SendMessageW(handle,0x84,0,(y<<16)|(x&0xffff));user32.SetCursorPos(x,y);time.sleep(.15);user32.mouse_event(2,0,0,0,0);time.sleep(.12);user32.mouse_event(4,0,0,0,0);time.sleep(.5)
  assert user32.IsZoomed(handle),'maximize button did not receive mouse click';report['checks'].append('real maximize button click')
  user32.SendMessageW(handle,0x112,0xF120,0);time.sleep(.2)
  if report['scale']==1:
   l,t,r,b=rect();report['style_before_snap']=hex(user32.GetWindowLongPtrW(handle,-16));report['caption_hit']=user32.SendMessageW(handle,0x84,0,((t+24)<<16)|(l+260));drag(l+260,t+24,work[2]-2-(l+260),(work[1]+work[3])//2-(t+24));time.sleep(.5);snapped=rect()
   assert snapped[2]==work[2] and snapped[3]==work[3],('snap',snapped,work);report['checks'].append('mouse drag snap to screen edge')
  user32.SetWindowPos(handle,None,80,50,min(round(1420*report['scale']),work[2]-work[0]-160),min(round(880*report['scale']),work[3]-work[1]-100),0x0004)
  report['success']=True
 except Exception:report['error']=traceback.format_exc();report['success']=False
 finally:user32.SetCursorPos(point.x,point.y);done.set()
def finish():
 point=w.titlebar.maximize.mapTo(w,w.titlebar.maximize.rect().center());report['button_center']=(point.x(),point.y())
 if not done.is_set():return
 timer.stop();w.grab().save(str(root/'build/courses-native.png'))
 report['qt_geometry']={'size':(w.width(),w.height()),'minimum':(w.minimumWidth(),w.minimumHeight()),'maximum':(w.maximumWidth(),w.maximumHeight()),'maximized':w.isMaximized()}
 d=CourseDetails(w,course_key(next(occurrences(w.data))[1]));d.show();app.processEvents();d.grab().save(str(root/'build/details-native.png'));d.close()
 path=root/f"build/native-v22-scale-{os.environ.get('QT_SCALE_FACTOR','1')}.json";path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 w.exiting=True;w.close();app.quit()
timer=QTimer();timer.timeout.connect(finish);timer.start(200)
QTimer.singleShot(3000,lambda:threading.Thread(target=run,daemon=True).start())
QTimer.singleShot(60000,app.quit)
app.exec()
print(json.dumps({'success':report.get('success',False),'scale':report['scale'],'checks':len(report['checks']),'error':report.get('error')},ensure_ascii=False))
raise SystemExit(0 if report.get('success') else 1)
