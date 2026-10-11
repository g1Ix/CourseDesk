import os,subprocess,sys,json,logging
from datetime import date,datetime,timedelta
from pathlib import Path
from course_data import APP_DIR,RESOURCE_DIR,load_schedule,load_prefs,classes_on,class_time,WEEKDAYS

def powershell():return str(Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe')
def hidden_options():return {'creationflags':getattr(subprocess,'CREATE_NO_WINDOW',0)}
def update_task(prefs):
    if os.environ.get('COURSEDESK_NO_OS_ACTIONS')=='1':return '设置已保存'
    if getattr(sys,'frozen',False):exe=sys.executable;args='--notify-tomorrow'
    else:
        exe=str(Path(sys.executable).with_name('pythonw.exe'));args=f'"{RESOURCE_DIR / "course_assistant.py"}" --notify-tomorrow'
    result=subprocess.run([powershell(),'-NoProfile','-ExecutionPolicy','Bypass','-File',str(RESOURCE_DIR/'register_reminder.ps1'),'-Executable',exe,'-Arguments',args,'-Time',prefs['reminder_time'],'-Enabled',str(bool(prefs['reminder_enabled'])).lower()],capture_output=True,timeout=30,**hidden_options())
    if result.returncode:
        error=(result.stderr or result.stdout).decode('utf-8',errors='replace').strip()
        raise RuntimeError('Windows 未能更新提醒。请重试，或运行应用文件夹中的“安装每日提醒”脚本。\n'+error[-350:])
    return '每日提醒已更新'

def show_notification(title,body):
    if os.environ.get('COURSEDESK_NO_OS_ACTIONS')=='1':return
    result=subprocess.run([powershell(),'-NoProfile','-STA','-ExecutionPolicy','Bypass','-File',str(RESOURCE_DIR/'toast_notification.ps1'),'-Title',title,'-Body',body],capture_output=True,timeout=25,**hidden_options())
    if result.returncode:raise RuntimeError('Windows 没有发送通知，请检查系统通知设置。')

def notification_text(data,prefs,day):
    rows=classes_on(data,day,prefs)
    title=f"{day.month}月{day.day}日 · 星期{WEEKDAYS[day.weekday()]}的课程"
    body='\n'.join(f"{class_time(r,prefs)}  {r['course']}\n{r.get('teacher') or '教师未填写'} · {r.get('room') or '教室未填写'}" for r in rows)
    return title,body,rows

def reminder(target=None,dry_run=False):
    APP_DIR.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=APP_DIR/'reminder.log',level=logging.INFO,encoding='utf-8',format='%(asctime)s %(levelname)s %(message)s')
    try:
        data,prefs=load_schedule(),load_prefs();day=target or date.today()+timedelta(days=1)
        title,body,rows=notification_text(data,prefs,day)
        if dry_run:
            result={'date':str(day),'title':title,'body':body,'classes':rows,'reminder_enabled':prefs['reminder_enabled']}
            (APP_DIR/'last-preview.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            if sys.stdout:print(title+'\n'+(body or '没有课程'))
        elif prefs['reminder_enabled'] and rows:
            show_notification('明天 · '+title,body);logging.info('Notified %s: %s classes',day,len(rows))
        else:logging.info('Silent: %s (%s classes)',day,len(rows))
        return 0
    except Exception:
        logging.exception('Reminder failed');return 1
