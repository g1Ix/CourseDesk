"""Windows entry point shared by interactive UI and the scheduled reminder."""
import argparse,hashlib,logging,sys
from datetime import date
from course_data import APP_DIR,RESOURCE_DIR

def main():
    parser=argparse.ArgumentParser(description='课序 · 课程助手')
    parser.add_argument('--notify-tomorrow',action='store_true')
    parser.add_argument('--date',type=date.fromisoformat)
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    if args.notify_tomorrow or args.dry_run:
        from course_system import reminder
        return reminder(args.date,args.dry_run)
    from PySide6.QtCore import Qt,QTimer
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication
    from PySide6.QtNetwork import QLocalServer,QLocalSocket
    if sys.platform=='win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Codex.ClassReminder')
    app=QApplication(sys.argv);app.setStyle('Fusion');app.setApplicationName('CourseDesk');app.setOrganizationName('CourseDesk');app.setWindowIcon(QIcon(str(RESOURCE_DIR/'assets/app.ico')))
    APP_DIR.mkdir(parents=True,exist_ok=True);logging.basicConfig(filename=APP_DIR/'desktop.log',level=logging.INFO,encoding='utf-8',format='%(asctime)s %(levelname)s %(message)s')
    name='CourseDesk-'+hashlib.sha256(str(APP_DIR.resolve()).lower().encode()).hexdigest()[:20]
    socket=QLocalSocket();socket.connectToServer(name)
    if socket.waitForConnected(500):socket.write(b'open');socket.flush();socket.waitForBytesWritten(500);return 0
    server=QLocalServer()
    if not server.listen(name):
        QLocalServer.removeServer(name)
        if not server.listen(name):return 1
    from course_ui import MainWindow,NoticeDialog
    try:window=MainWindow()
    except Exception as exc:
        logging.exception('Startup failed');NoticeDialog(None,'课表暂时无法打开',str(exc)+'\n你的数据未被修改。请从数据文件夹的 backups 中恢复有效课表。').exec();return 1
    def incoming():
        client=server.nextPendingConnection()
        if client:client.disconnectFromServer();client.deleteLater()
        window.bring_to_front()
    server.newConnection.connect(incoming)
    def report(exc_type,value,tb):
        logging.error('UI error',exc_info=(exc_type,value,tb));QTimer.singleShot(0,lambda:window.notice('操作未完成',str(value)))
    sys.excepthook=report
    app.styleHints().colorSchemeChanged.connect(lambda _:window.apply_theme() if window.prefs['theme']=='system' else None)
    window.show();return app.exec()

if __name__=='__main__':raise SystemExit(main())
