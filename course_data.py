"""CourseDesk persistence and calendar operations. All edits use detached candidates."""
from __future__ import annotations
import copy
import hashlib
import json
import os
import re
import shutil
import sys
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

VERSION = '1.0.0'
WEEKDAYS = '一二三四五六日'
RESOURCE_DIR = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
APP_DIR = Path(os.environ.get('COURSEDESK_DATA_DIR') or (Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'CourseDesk'))
DATA_PATH = APP_DIR / 'schedule.json'
PREFS_PATH = APP_DIR / 'preferences.json'
BACKUP_DIR = APP_DIR / 'backups'
DEFAULT_PREFS = {'theme': 'light', 'reminder_enabled': True, 'reminder_time': '23:55',
                 'show_weekends': True, 'close_to_tray': False, 'exclude_sunday_labs': True,
                 'period_count': 8, 'period_times': [], 'backup_limit': 30}

def uid(): return uuid.uuid4().hex[:16]
def parse_date(value): return date.fromisoformat(str(value))
def monday(day): return day - timedelta(days=day.weekday())
def week_number(start, day): return (monday(day) - monday(start)).days // 7 + 1
def total_weeks(data): return week_number(parse_date(data['term']['start']), parse_date(data['term']['end']))
def displayed_week(data, internal): return int(data['term'].get('first_week', 1)) + internal - 1
def period_text(row):
    a,b=int(row['period_start']),int(row['period_end'])
    return f'第 {a} 节' if a == b else f'第 {a}–{b} 节'
def weeks_text(weeks, offset=0):
    nums=sorted({int(w)+offset for w in weeks})
    result=[]
    for n in nums:
        if not result or n != result[-1][-1]+1: result.append([n])
        else: result[-1].append(n)
    return '、'.join(str(r[0]) if len(r)==1 else f'{r[0]}–{r[-1]}' for r in result)
def parse_weeks(text, offset=0):
    result=set()
    for part in re.split(r'[;；,，、\s]+', str(text).replace('周','').strip()):
        if not part: continue
        match=re.fullmatch(r'(\d+)\s*[-–—~至]\s*(\d+)',part)
        if match:
            a,b=map(int,match.groups())
            if b<a: raise ValueError('周次范围的结束不能早于开始。')
            result.update(range(a-offset,b-offset+1))
        elif part.isdigit(): result.add(int(part)-offset)
        else: raise ValueError('周次请填写数字或范围，例如 6–18 或 6;8;10。')
    return sorted(result)
def course_key(row): return str(row['course']) + '|' + str(row.get('teacher',''))
def color_index(row): return int(hashlib.sha256(course_key(row).encode()).hexdigest()[:6],16)%6
def row_fields(row):
    return {k:copy.deepcopy(row.get(k,'')) for k in ('course','teacher','room','period_start','period_end','notes')}

def migrate_legacy(data):
    start,end=map(parse_date,(data['date_range']['start'],data['date_range']['end']))
    grouped=defaultdict(list)
    for r in data.get('classes',[]):
        day=parse_date(r['date'])
        key=(day.weekday(),int(r['period_start']),int(r['period_end']),r['course'],r.get('teacher',''),r.get('room',''))
        grouped[key].append(r)
    rules=[]; exceptions=[]
    for key,rows in grouped.items():
        dow,a,b,course,teacher,room=key
        record={'id':uid(),'period_start':a,'period_end':b,'course':course,'teacher':teacher,'room':room}
        if len(rows)>1:
            rules.append({**record,'weekday':dow,'weeks':sorted({week_number(start,parse_date(r['date'])) for r in rows})})
        else: exceptions.append({'date':rows[0]['date'],'mode':'add','classes':[record]})
    return normalize({'schema_version':2,'term':{'start':start.isoformat(),'end':end.isoformat()},'weekly_rules':rules,'exceptions':exceptions})

def normalize(data):
    out=copy.deepcopy(data)
    out.setdefault('schema_version',2)
    t=out['term']
    t.setdefault('name',f"{parse_date(t['start']).year}–{parse_date(t['start']).year+1} 秋季学期")
    t.setdefault('first_week',1)
    out.setdefault('weekly_rules',[]);out.setdefault('exceptions',[])
    for r in out['weekly_rules']:
        r['weeks']=sorted({int(w) for w in r['weeks']})
        r.setdefault('notes','')
    for ex in out['exceptions']:
        ex.setdefault('classes',[]);ex.setdefault('cancel_rule_ids',[])
        for r in ex['classes']: r.setdefault('id',uid());r.setdefault('notes','')
    return out

def validate_schedule(data):
    start,end=map(parse_date,(data['term']['start'],data['term']['end']))
    if end < start: raise ValueError('学期结束日期不能早于开始日期。')
    if (end-start).days>730: raise ValueError('单个学期最多支持两年的日期范围。')
    if not 1<=int(data['term'].get('first_week',1))<=100: raise ValueError('起始周次应在 1–100 之间。')
    count=total_weeks(data); ids=set(); days=set()
    def validate_row(r):
        if not str(r.get('course','')).strip() or r['course']=='待校对课程': raise ValueError('请填写完整的课程名称，识别不清的课程需要先校对。')
        if not 1<=int(r['period_start'])<=int(r['period_end'])<=14: raise ValueError('节次应在 1–14 之间，结束节次不能早于开始。')
        if not r.get('id'): raise ValueError('课程缺少编号。')
        if r['id'] in ids: raise ValueError('课程编号重复。')
        ids.add(r['id'])
    for r in data['weekly_rules']:
        validate_row(r)
        if not 0<=int(r['weekday'])<=6: raise ValueError('请选择有效的星期。')
        if not r.get('weeks') or any(not 1<=int(w)<=count for w in r['weeks']):
            raise ValueError(f"{r['course']} 的周次超出学期范围，请检查上课周次。")
    for ex in data['exceptions']:
        day=parse_date(ex['date'])
        if not start<=day<=end: raise ValueError(f'{day} 的临时安排超出学期日期，请先调整学期范围。')
        if day in days: raise ValueError('同一天的临时安排需要合并保存。')
        days.add(day)
        if ex.get('mode') not in ('add','replace','cancel'): raise ValueError('临时安排类型无效。')
        for r in ex['classes']: validate_row(r)

def atomic_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    try:
        with temp.open('w',encoding='utf-8') as f:
            json.dump(data,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
        temp.replace(path)
    finally:
        if temp.exists():temp.unlink()

def load_schedule():
    if DATA_PATH.exists(): data=json.loads(DATA_PATH.read_text(encoding='utf-8-sig'))
    else:
        start=monday(date.today())
        data=normalize({'term':{'start':str(start),'end':str(start+timedelta(days=125))},'weekly_rules':[],'exceptions':[]})
        save_schedule(data)
    data=normalize(data);validate_schedule(data);return data

def save_schedule(data):
    candidate=normalize(data);validate_schedule(candidate)
    if DATA_PATH.exists():
        BACKUP_DIR.mkdir(parents=True,exist_ok=True)
        shutil.copy2(DATA_PATH,BACKUP_DIR/f"schedule-{datetime.now():%Y%m%d-%H%M%S-%f}.json")
    atomic_json(DATA_PATH,candidate)
    backups=sorted(BACKUP_DIR.glob('schedule-*.json'),reverse=True)
    for old in backups[30:]: old.unlink()

def load_prefs():
    result=copy.deepcopy(DEFAULT_PREFS)
    if PREFS_PATH.exists(): result.update(json.loads(PREFS_PATH.read_text(encoding='utf-8-sig')))
    return result
def validate_prefs(p):
    if p['theme'] not in ('light','dark','system'):raise ValueError('请选择有效的界面主题。')
    if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',p['reminder_time']):raise ValueError('提醒时间格式无效。')
    if not 1<=int(p['period_count'])<=14:raise ValueError('每天的节次数应在 1–14 之间。')
    for t in p.get('period_times',[]):
        a,b=t.get('start','').strip(),t.get('end','').strip()
        if bool(a)!=bool(b):raise ValueError('每节课的开始和结束时间需要一起填写。')
        if a and (not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',a) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',b) or b<=a):
            raise ValueError('上课时间应填写 HH:mm，结束时间需要晚于开始时间。')
def save_prefs(p):validate_prefs(p);atomic_json(PREFS_PATH,p)

def classes_on(data,day,prefs=None):
    start,end=map(parse_date,(data['term']['start'],data['term']['end']))
    if not start<=day<=end:return []
    week=week_number(start,day)
    rows=[{**copy.deepcopy(r),'_source':'rule','_date':str(day)} for r in data['weekly_rules'] if r['weekday']==day.weekday() and week in r['weeks']]
    for ex in data['exceptions']:
        if ex['date']!=str(day):continue
        if ex['mode'] in ('replace','cancel'):rows=[]
        else:rows=[r for r in rows if r['id'] not in ex.get('cancel_rule_ids',[])]
        if ex['mode']!='cancel':rows.extend({**copy.deepcopy(r),'_source':'exception','_date':str(day)} for r in ex['classes'])
    if prefs and prefs.get('exclude_sunday_labs') and day.weekday()==6:
        rows=[r for r in rows if '实验' not in r['course'] and '實驗' not in r['course']]
    return sorted(rows,key=lambda r:(r['period_start'],r['period_end'],r['course']))

def occurrences(data,start=None,end=None,prefs=None):
    lo=max(start or parse_date(data['term']['start']),parse_date(data['term']['start']))
    hi=min(end or parse_date(data['term']['end']),parse_date(data['term']['end']))
    while lo<=hi:
        for row in classes_on(data,lo,prefs): yield lo,row
        lo+=timedelta(days=1)

def find_conflicts(data):
    result=[]
    lo,hi=map(parse_date,(data['term']['start'],data['term']['end']))
    while lo<=hi:
        rows=classes_on(data,lo)
        for i,a in enumerate(rows):
            for b in rows[i+1:]:
                if a['period_start']<=b['period_end'] and b['period_start']<=a['period_end']:result.append((lo,a,b))
        lo+=timedelta(days=1)
    return result

def exception_for(data,day):
    ex=next((e for e in data['exceptions'] if e['date']==str(day)),None)
    if ex is None:
        ex={'date':str(day),'mode':'add','cancel_rule_ids':[],'classes':[]};data['exceptions'].append(ex)
    return ex

def add_course(data,record,day=None):
    out=copy.deepcopy(data);row=copy.deepcopy(record);row['id']=uid()
    if 'weekday' in row:out['weekly_rules'].append(row)
    else:
        ex=exception_for(out,day)
        if ex['mode']=='cancel':ex['mode']='replace'
        ex['classes'].append(row)
    return out

def edit_course(data,occurrence,day,record,scope='one',delete=False,target_day=None):
    # Explicit target dates enable rescheduling and mode conversion in the editor.
    # Existing callers without a target retain their original scope semantics.
    if target_day is not None and not delete:
        is_rule=any(r['id']==occurrence['id'] for r in data['weekly_rules'])
        if not is_rule or scope=='one' or 'weekday' not in record:
            out=edit_course(data,occurrence,day,record,scope,delete=True)
            return add_course(out,record,target_day)
    out=copy.deepcopy(data)
    original=next((r for r in out['weekly_rules'] if r['id']==occurrence['id']),None)
    if original is not None:
        if scope=='one':
            ex=exception_for(out,day)
            ex['cancel_rule_ids']=list(set(ex.get('cancel_rule_ids',[])+[original['id']]))
            if not delete:ex['classes'].append({'id':uid(),**row_fields(record)})
        elif scope=='future':
            split_week=week_number(parse_date(out['term']['start']),day)
            old=original['weeks'][:]
            original['weeks']=[w for w in old if w<split_week]
            new_weeks=[w for w in (record.get('weeks',old) if not delete else []) if w>=split_week]
            new_weekday=record.get('weekday',original['weekday'])
            origin=monday(parse_date(out['term']['start']))
            new_weeks=[w for w in new_weeks if origin+timedelta(weeks=w-1,days=new_weekday)>=day]
            if not delete and not new_weeks:
                raise ValueError('修改后没有这一天及之后的上课日期。请调整星期或周次。')
            if new_weeks:
                new_id=uid()
                out['weekly_rules'].append({'id':new_id,'weekday':new_weekday,'weeks':new_weeks,**row_fields(record)})
                # Existing date exceptions should continue to refer to the same future occurrence.
                for ex in out['exceptions']:
                    if parse_date(ex['date'])>=day and original['id'] in ex.get('cancel_rule_ids',[]):
                        ex['cancel_rule_ids']=[new_id if i==original['id'] else i for i in ex['cancel_rule_ids']]
            if not original['weeks']:out['weekly_rules'].remove(original)
        elif scope=='all':
            if delete:out['weekly_rules'].remove(original)
            else:
                original.update(row_fields(record));original['weekday']=record.get('weekday',original['weekday']);original['weeks']=record.get('weeks',original['weeks'])
        else:raise ValueError('未知的修改范围。')
    else:
        ex=exception_for(out,day)
        ex['classes']=[r for r in ex['classes'] if r['id']!=occurrence['id']]
        if not delete:ex['classes'].append({'id':uid(),**row_fields(record)})
    out['exceptions']=[e for e in out['exceptions'] if e['classes'] or e.get('cancel_rule_ids') or e['mode'] in ('cancel','replace')]
    return out

def restore_backup(path):
    data=normalize(json.loads(Path(path).read_text(encoding='utf-8-sig')));validate_schedule(data);save_schedule(data);return data

def class_time(row,prefs):
    times=prefs.get('period_times',[]);a,b=row['period_start']-1,row['period_end']-1
    if a<len(times) and b<len(times) and times[a].get('start') and times[b].get('end'):
        return f"{times[a]['start']}–{times[b]['end']}"
    return period_text(row)
