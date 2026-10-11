import copy
import json
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import tests_support
import course_data as data
from course_system import notification_text, reminder
from course_greetings import GREETINGS, GreetingDeck

class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.schedule = tests_support.fixture()
        self.day = date(2026,12,8)
        self.row = data.classes_on(self.schedule,self.day)[0]
        self.fields = data.row_fields(self.row)

    def test_fresh_profile_ignores_adjacent_timetable(self):
        # A stale development file must never become a new user's timetable.
        root=Path(tests_support.PROFILE.name)/'fresh';root.mkdir(exist_ok=True)
        (root/'timetable.json').write_text('{"private":"fictional canary"}',encoding='utf-8')
        with patch.object(data,'DATA_PATH',root/'schedule.json'),patch.object(data,'RESOURCE_DIR',root):
            loaded=data.load_schedule()
        self.assertEqual(loaded['weekly_rules'],[])
        self.assertEqual(loaded['exceptions'],[])
        self.assertEqual(loaded['term']['first_week'],1)

    def test_existing_profile_kept(self):
        root=Path(tests_support.PROFILE.name)/'existing';root.mkdir(exist_ok=True)
        data.atomic_json(root/'schedule.json',self.schedule)
        with patch.object(data,'DATA_PATH',root/'schedule.json'):
            self.assertEqual(data.load_schedule(),self.schedule)

    def test_cross_year_and_end_boundary(self):
        self.assertEqual(len(data.classes_on(self.schedule,date(2027,1,5))),1)
        self.assertEqual(data.classes_on(self.schedule,date(2027,1,18)),[])

    def test_empty_day(self):
        self.assertEqual(notification_text(self.schedule,data.DEFAULT_PREFS,date(2026,12,9))[2],[])

    def test_add_and_sort(self):
        changed=data.add_course(self.schedule,{**self.fields,'period_start':5,'period_end':6},self.day)
        self.assertEqual([r['period_start'] for r in data.classes_on(changed,self.day)],[1,5])

    def test_single_move_across_year(self):
        changed=data.add_course(self.schedule,self.fields,date(2026,12,31))
        row=data.classes_on(changed,date(2026,12,31))[0]
        moved=data.edit_course(changed,row,date(2026,12,31),self.fields,target_day=date(2027,1,1))
        self.assertEqual(data.classes_on(moved,date(2026,12,31)),[])
        self.assertEqual(len(data.classes_on(moved,date(2027,1,1))),1)

    def test_edit_one(self):
        changed=data.edit_course(self.schedule,self.row,self.day,{**self.fields,'course':'改名'},'one')
        self.assertEqual(data.classes_on(changed,self.day)[0]['course'],'改名')
        self.assertEqual(data.classes_on(changed,date(2026,12,15))[0]['course'],'虚构课程')

    def test_edit_future(self):
        day=date(2026,12,15);row=data.classes_on(self.schedule,day)[0]
        changed=data.edit_course(self.schedule,row,day,{**row,'course':'改名'},'future')
        self.assertEqual(data.classes_on(changed,self.day)[0]['course'],'虚构课程')
        self.assertEqual(data.classes_on(changed,date(2027,1,5))[0]['course'],'改名')

    def test_edit_all(self):
        changed=data.edit_course(self.schedule,self.row,self.day,{**self.row,'course':'改名'},'all')
        self.assertTrue(all(r['course']=='改名' for _,r in data.occurrences(changed)))

    def test_future_empty_raises_without_mutating_source(self):
        original=copy.deepcopy(self.schedule)
        with self.assertRaises(ValueError):
            data.edit_course(self.schedule,self.row,self.day,{**self.fields,'weekday':0,'weeks':[1]},'future')
        self.assertEqual(self.schedule,original)

    def test_delete_scopes(self):
        day=date(2026,12,15);row=data.classes_on(self.schedule,day)[0]
        for scope,count in [('one',5),('future',1),('all',0)]:
            with self.subTest(scope=scope):
                changed=data.edit_course(self.schedule,row,day,self.fields,scope,delete=True)
                self.assertEqual(len(list(data.occurrences(changed))),count)

    def test_repeat_to_single_scopes(self):
        day=date(2026,12,15);row=data.classes_on(self.schedule,day)[0]
        for scope,count in [('one',5),('future',1),('all',0)]:
            with self.subTest(scope=scope):
                changed=data.edit_course(self.schedule,row,day,self.fields,scope,target_day=date(2027,1,1))
                data.validate_schedule(changed)
                self.assertEqual(sum(r['_source']=='rule' for _,r in data.occurrences(changed)),count)
                self.assertEqual(len(data.classes_on(changed,date(2027,1,1))),1)

    def test_single_to_repeat(self):
        changed=data.add_course(self.schedule,self.fields,date(2026,12,31))
        row=data.classes_on(changed,date(2026,12,31))[0]
        converted=data.edit_course(changed,row,date(2026,12,31),{**self.fields,'weekday':4,'weeks':[4,5]},target_day=date(2026,12,31))
        self.assertEqual(data.classes_on(converted,date(2026,12,31)),[])
        self.assertEqual(len(data.classes_on(converted,date(2027,1,1))),1)

    def test_cancel_day(self):
        self.schedule['exceptions']=[{'date':str(self.day),'mode':'cancel','classes':[]}]
        self.assertEqual(data.classes_on(self.schedule,self.day),[])

    def test_replace_day(self):
        self.schedule['exceptions']=[{'date':str(self.day),'mode':'replace','classes':[{'id':'replacement',**self.fields,'course':'临时课'}]}]
        self.assertEqual([r['course'] for r in data.classes_on(self.schedule,self.day)],['临时课'])

    def test_cancellation_follows_future_rule(self):
        self.schedule['exceptions']=[{'date':'2026-12-22','mode':'add','classes':[],'cancel_rule_ids':['test-rule']}]
        changed=data.edit_course(self.schedule,self.row,self.day,self.row,'future')
        self.assertEqual(data.classes_on(changed,date(2026,12,22)),[])

    def test_sunday_filter_preserves_original(self):
        changed=data.add_course(self.schedule,{**self.fields,'course':'示例实验'},date(2026,12,13))
        before=copy.deepcopy(changed)
        self.assertEqual(data.classes_on(changed,date(2026,12,13),data.DEFAULT_PREFS),[])
        self.assertEqual(len(data.classes_on(changed,date(2026,12,13),{'exclude_sunday_labs':False})),1)
        self.assertEqual(changed,before)

    def test_migrate_legacy_preserves_sunday_data(self):
        legacy={'date_range':{'start':'2026-12-07','end':'2027-01-17'},'classes':[{'date':'2026-12-13',**self.fields,'course':'示例实验'}]}
        migrated=data.migrate_legacy(legacy)
        data.validate_schedule(migrated)
        self.assertEqual(len(data.classes_on(migrated,date(2026,12,13))),1)

    def test_validation_rejects_bad_records(self):
        for changes in [{'course':''},{'period_start':4,'period_end':2},{'weeks':[99]},{'weekday':8}]:
            with self.subTest(changes=changes):
                candidate=copy.deepcopy(self.schedule);candidate['weekly_rules'][0].update(changes)
                with self.assertRaises(ValueError):data.validate_schedule(candidate)

    def test_invalid_term(self):
        self.schedule['term']['end']='2026-01-01'
        with self.assertRaises(ValueError):data.validate_schedule(self.schedule)

    def test_duplicate_ids(self):
        self.schedule['weekly_rules'].append(copy.deepcopy(self.schedule['weekly_rules'][0]))
        with self.assertRaises(ValueError):data.validate_schedule(self.schedule)

    def test_conflicts(self):
        changed=data.add_course(self.schedule,self.fields,self.day)
        self.assertEqual(len(data.find_conflicts(changed)),1)

    def test_backup_and_restore(self):
        root=Path(tests_support.PROFILE.name)/'backup';root.mkdir(exist_ok=True)
        with patch.object(data,'DATA_PATH',root/'schedule.json'),patch.object(data,'BACKUP_DIR',root/'backups'):
            data.save_schedule(self.schedule)
            changed=data.edit_course(self.schedule,self.row,self.day,{**self.row,'course':'改名'},'all')
            data.save_schedule(changed)
            backup=next((root/'backups').glob('*.json'))
            self.assertEqual(data.restore_backup(backup),self.schedule)
            self.assertEqual(len(list((root/'backups').glob('*.json'))),2)

    def test_weeks_roundtrip(self):
        weeks=[1,2,3,5,8]
        self.assertEqual(data.parse_weeks(data.weeks_text(weeks,5),5),weeks)
        with self.assertRaises(ValueError):data.parse_weeks('5-1')

    def test_preference_validation(self):
        data.validate_prefs(data.DEFAULT_PREFS)
        with self.assertRaises(ValueError):data.validate_prefs({**data.DEFAULT_PREFS,'reminder_time':'25:00'})

    def test_notification_has_all_fields(self):
        title,body,rows=notification_text(self.schedule,data.DEFAULT_PREFS,self.day)
        self.assertIn('12月8日',title)
        for value in ['虚构课程','示例教师','教学楼 A101','第 1–2 节']:self.assertIn(value,body)

    def test_greeting_cycle_unique_and_persistent(self):
        deck=GreetingDeck();deck.remaining=[]
        values=[deck.next() for _ in range(len(GREETINGS))]
        self.assertEqual(len(set(values)),len(GREETINGS))
        reloaded=GreetingDeck()
        self.assertNotEqual(reloaded.next(),values[-1])

    def test_public_example_valid(self):
        example=Path(__file__).resolve().parents[1]/'examples/demo-schedule.json'
        data.validate_schedule(data.normalize(json.loads(example.read_text(encoding='utf-8'))))

if __name__=='__main__':unittest.main()
