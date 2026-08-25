import os,sys,subprocess,shutil,webbrowser,time,sqlite3
from pathlib import Path
ROOT=Path(__file__).parent; DATA=ROOT/'data'
def ensure():
    [ (DATA/x).mkdir(parents=True,exist_ok=True) for x in ['accounts','screenshots','logs','exports','database'] ]
def doctor():
    ensure(); checks=[('Python',sys.version_info>=(3,11)),('Node/npm',shutil.which('npm') is not None),('SQLite',True),('Data directories',all((DATA/x).exists() for x in ['accounts','database'])),('Disk space',shutil.disk_usage(ROOT).free>1_000_000_000)]
    for n,ok in checks: print(('✓ PASS ' if ok else '✕ FAIL ')+n)
    return 0 if all(ok for _,ok in checks) else 1
def main():
    if len(sys.argv)>1 and sys.argv[1]=='doctor': raise SystemExit(doctor())
    ensure(); env=os.environ.copy(); env.setdefault('MOCK_MODE','false')
    be=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000'],cwd=ROOT/'backend',env=env)
    fe=subprocess.Popen(['npm','run','dev'],cwd=ROOT/'frontend',shell=os.name=='nt')
    time.sleep(2); webbrowser.open('http://127.0.0.1:5173/dashboard')
    try: be.wait()
    finally: fe.terminate()
if __name__=='__main__': main()
