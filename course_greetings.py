"""A persistent shuffled deck of short, original home-page greetings."""
import json
import random
from course_data import APP_DIR,atomic_json

GREETINGS=(
    '今天，也从容一点',
    '按自己的节奏，慢慢来',
    '先看课表，再慢慢开始',
    '把今天，安排得刚刚好',
    '新的安排，新的期待',
    '一步一步，走好今天',
    '忙里有序，心里有余',
    '让今天，有条不紊',
    '认真学习，也记得休息',
    '给每一天，留一点余地',
    '不用着急，按计划来',
    '今天的节奏，由你掌握',
    '准备好，再轻松出发',
    '把小事做好，把日子过好',
    '留一点时间，给喜欢的事',
    '每一点进步，都算数',
    '课表清楚，心里有数',
    '愿今天，顺顺利利',
    '学有所获，也有所乐',
    '把时间，留给值得的事',
)

class GreetingDeck:
    def __init__(self):
        self.path=APP_DIR/'ui-greetings.json'
        self.remaining=[];self.last=GREETINGS[0]
        try:
            state=json.loads(self.path.read_text(encoding='utf-8'))
            if isinstance(state,dict):
                if state.get('last') in GREETINGS:self.last=state['last']
                pending=state.get('remaining',[])
                if isinstance(pending,list):
                    self.remaining=list(dict.fromkeys(x for x in pending if isinstance(x,str) and x in GREETINGS and x!=self.last))
        except (OSError,ValueError):pass
    def next(self):
        if not self.remaining:
            self.remaining=list(GREETINGS);random.shuffle(self.remaining)
            if self.remaining[-1]==self.last:
                self.remaining[0],self.remaining[-1]=self.remaining[-1],self.remaining[0]
        self.last=self.remaining.pop()
        try:atomic_json(self.path,{'last':self.last,'remaining':self.remaining})
        except OSError:pass  # An unwritable UI state must not prevent using the timetable.
        return self.last
