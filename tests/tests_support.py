"""A disposable profile and fictional fixture shared by public tests."""
import os
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
(ROOT/'build').mkdir(exist_ok=True)
PROFILE = tempfile.TemporaryDirectory(prefix='coursedesk-tests-',dir=ROOT/'build')
os.environ['COURSEDESK_DATA_DIR'] = PROFILE.name
os.environ['COURSEDESK_NO_OS_ACTIONS'] = '1'
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from course_data import normalize

def fixture():
    return normalize({
        'term': {'name': '测试学期', 'start': '2026-12-07', 'end': '2027-01-17', 'first_week': 1},
        'weekly_rules': [{'id': 'test-rule', 'course': '虚构课程', 'teacher': '示例教师',
                          'room': '教学楼 A101', 'period_start': 1, 'period_end': 2,
                          'weekday': 1, 'weeks': [1,2,3,4,5,6]}],
        'exceptions': []})
