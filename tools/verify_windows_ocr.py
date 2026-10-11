"""Real Windows OCR smoke test using generated, fictional PNG and PDF files."""
import json
import os
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ['COURSEDESK_NO_OS_ACTIONS']='1'
from PySide6.QtCore import Qt,QRectF,QSizeF
from PySide6.QtGui import QImage,QPainter,QFont,QPdfWriter,QPageSize
from PySide6.QtWidgets import QApplication
from course_system import powershell,hidden_options
from course_import import ocr_pages_to_rows

app=QApplication([])
dest=ROOT/'build/ocr-smoke';dest.mkdir(parents=True,exist_ok=True)
image=QImage(1600,1200,QImage.Format_RGB32);image.fill(Qt.white)
p=QPainter(image);p.setPen(Qt.black)
font=QFont('Microsoft YaHei');font.setPixelSize(28);p.setFont(font)
p.drawText(20,40,'第1周')
for i,x in enumerate('一二三四五六日'):p.drawText(180+i*200,95,'星期'+x)
for i in range(1,9):p.drawText(18,165+(i-1)*110,f'{i}节')
p.drawText(185,190,'示例数学');p.drawText(185,225,'示例教师');p.drawText(185,260,'@A101')
p.drawText(585,410,'示例编程');p.drawText(585,445,'示例教师');p.drawText(585,480,'@B202')
p.end();image.save(str(dest/'fictional-timetable.png'))
writer=QPdfWriter(str(dest/'fictional-timetable.pdf'));writer.setResolution(96)
writer.setPageSize(QPageSize(QSizeF(1600,1200),QPageSize.Point))
p=QPainter(writer)
for i in range(2):
    if i:writer.newPage()
    p.drawImage(QRectF(0,0,writer.width(),writer.height()),image)
p.end()
summary=[]
for name,expected in [('fictional-timetable.png',1),('fictional-timetable.pdf',2)]:
    result=subprocess.run([powershell(),'-NoProfile','-STA','-ExecutionPolicy','Bypass','-File',str(ROOT/'windows_ocr.ps1'),'-Path',str(dest/name)],capture_output=True,timeout=150,**hidden_options())
    if result.returncode:raise RuntimeError(result.stderr.decode('utf-8',errors='replace'))
    payload=json.loads(result.stdout.decode('utf-8-sig'))
    assert len(payload['pages'])==expected,(name,'page count')
    assert all(page['lines'] for page in payload['pages']),(name,'OCR lines')
    rows=ocr_pages_to_rows(payload,[1,2],True)
    assert rows,(name,'editable rows')
    assert any('示例' in row['course'] for row in rows),(name,'Chinese recognition')
    summary.append({'format':Path(name).suffix,'pages':expected,'rows':len(rows),'language':payload['language']})
print(json.dumps({'passed':True,'checks':summary},ensure_ascii=False))
