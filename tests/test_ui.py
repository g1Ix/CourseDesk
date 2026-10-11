import copy
import json
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import tests_support
import course_data as data
from course_import import ocr_pages_to_rows
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication,QDialog,QLabel,QScrollArea
from PySide6.QtTest import QTest
from course_ui import MainWindow,CourseDialog,ScopeDialog,qdate

class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setStyle('Fusion')
        data.save_schedule(tests_support.fixture())
        cls.window=MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.window.exiting=True
        cls.window.close()
        cls.app.processEvents()

    def setUp(self):
        self.window.data=tests_support.fixture()
        self.window.prefs=copy.deepcopy(data.DEFAULT_PREFS)
        self.window.resize(1420,920)
        self.window.apply_theme();self.window.refresh()

    def test_creator_is_visible_in_about(self):
        labels=[w.text() for w in self.window.settings_page.findChildren(QLabel)]
        self.assertTrue(any('g1Ix' in value and '版权所有' in value for value in labels))

    def test_refresh_hides_previous_dashboard_immediately(self):
        old=self.window.home_heading
        self.window.refresh_dashboard()
        self.assertTrue(old.parentWidget().isHidden())
        self.assertIsNot(old,self.window.home_heading)

    def test_editor_date_and_mode_enabled(self):
        editor=CourseDialog(self.window,data.row_fields(self.window.data['weekly_rules'][0]),date(2026,12,8))
        self.assertTrue(editor.mode.isEnabled());self.assertTrue(editor.day.isEnabled())
        editor.day.setDate(qdate(date(2027,1,1)));self.assertEqual(editor.day.date(),qdate(date(2027,1,1)))
        editor.mode.setCurrentIndex(0);self.assertIn('weekday',editor.value())
        editor.mode.setCurrentIndex(1);self.assertNotIn('weekday',editor.value())
        editor.close()

    def test_handler_saves_destination_date(self):
        day=date(2026,12,8);row=data.classes_on(self.window.data,day)[0]
        def edit(dialog):
            dialog.mode.setCurrentIndex(1);dialog.day.setDate(qdate(date(2027,1,1)))
            return QDialog.Accepted
        with patch.object(ScopeDialog,'exec',lambda dialog:QDialog.Accepted),patch.object(CourseDialog,'exec',edit),patch.object(self.window,'commit') as commit:
            self.window.edit(day,row)
        candidate=commit.call_args.args[0]
        self.assertEqual(data.classes_on(candidate,day),[])
        self.assertEqual(len(data.classes_on(candidate,date(2027,1,1))),1)
        self.assertEqual(len(data.classes_on(candidate,date(2026,12,15))),1)

    def test_empty_json_import(self):
        empty=data.normalize({'term':self.window.data['term'],'weekly_rules':[],'exceptions':[]})
        path=Path(tests_support.PROFILE.name)/'empty-import.json';data.atomic_json(path,empty)
        page=self.window.import_page;page.paths=[str(path)]
        def run(work,done,fail):
            try:done(work())
            except Exception as exc:fail(str(exc))
        with patch.object(self.window,'run_job',run):page.start()
        self.assertEqual(page.read_rows(),[])
        with patch.object(self.window,'confirm',return_value=True),patch.object(self.window,'commit',return_value=True) as commit:page.apply()
        self.assertEqual(commit.call_args.args[0]['weekly_rules'],[])

    def test_cancellation_only_json_import(self):
        native=data.normalize({'term':self.window.data['term'],'weekly_rules':[],'exceptions':[{'date':'2026-12-08','mode':'cancel','classes':[]}]})
        page=self.window.import_page;page.native=native;page.table.setRowCount(0)
        with patch.object(self.window,'confirm',return_value=True),patch.object(self.window,'commit',return_value=True) as commit:page.apply()
        self.assertEqual(commit.call_args.args[0]['exceptions'][0]['mode'],'cancel')

    def test_csv_import(self):
        from course_ui import ImportPage
        path=Path(__file__).resolve().parents[1]/'examples/template.csv'
        rows=ImportPage.csv_rows(path,list(range(1,17)),0)
        self.assertEqual(len(rows),2);self.assertEqual(rows[0]['weekday'],0)

    def test_small_window_single_column(self):
        self.window.show();self.window.resize(900,600);self.app.processEvents()
        self.window.adapt_layout()
        self.assertEqual(self.window.course_columns,1)
        self.assertGreaterEqual(self.window.calendar.minimumWidth(),780)

    def test_themes_and_scroll_background(self):
        for mode in ['light','dark','system']:
            with self.subTest(mode=mode):
                self.window.prefs['theme']=mode;self.window.apply_theme();self.app.processEvents()
                for scroll in self.window.findChildren(QScrollArea):
                    self.assertEqual(scroll.viewport().palette().color(scroll.viewport().backgroundRole()).name(),self.window.theme['bg'].lower())

    def test_animation_reversal_preserves_hit_area(self):
        button=self.window.nav[0];geometry=button.geometry()
        button._hovered=True;button.animate();QTest.qWait(80)
        self.assertGreater(button.get_progress(),0)
        before=button.get_progress();button._hovered=False;button.animate()
        self.assertEqual(button.get_progress(),before)
        QTest.qWait(260)
        self.assertAlmostEqual(button.get_progress(),0,places=3)
        self.assertEqual(button.geometry(),geometry)

    def test_ocr_keeps_sunday_course(self):
        lines=[{'text':f'星期{x}','x':160+i*100,'y':30,'width':80,'height':20} for i,x in enumerate('一二三四五六日')]
        lines += [{'text':f'{i}节','x':10,'y':80+(i-1)*60,'width':30,'height':20} for i in range(1,9)]
        lines += [{'text':'示例实验·示例教师@A101','x':760,'y':100,'width':90,'height':20}]
        rows=ocr_pages_to_rows({'pages':[{'width':900,'height':650,'lines':lines}]},[1],False)
        self.assertTrue(any(row['weekday']==6 for row in rows))

if __name__=='__main__':unittest.main()
