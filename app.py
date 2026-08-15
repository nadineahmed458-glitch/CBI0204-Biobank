import sqlite3, os, json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from datetime import date, datetime

BASE=os.path.dirname(os.path.abspath(__file__))
DB=os.path.join(BASE,'biobank.db')
PORT=int(os.environ.get('PORT', '8000'))
HOST=os.environ.get('HOST', '0.0.0.0')

SCHEMA='''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS donor(donor_id INTEGER PRIMARY KEY AUTOINCREMENT, donor_code TEXT UNIQUE NOT NULL, first_name TEXT NOT NULL,last_name TEXT NOT NULL,date_of_birth TEXT NOT NULL,sex TEXT NOT NULL,email TEXT,phone TEXT,registration_date TEXT,status TEXT DEFAULT 'Active');
CREATE TABLE IF NOT EXISTS consent(consent_id INTEGER PRIMARY KEY AUTOINCREMENT, donor_id INTEGER NOT NULL,consent_type TEXT NOT NULL,consent_date TEXT NOT NULL,expiry_date TEXT,status TEXT NOT NULL,version_no TEXT NOT NULL,UNIQUE(donor_id,consent_type,version_no),FOREIGN KEY(donor_id) REFERENCES donor(donor_id));
CREATE TABLE IF NOT EXISTS sample_type(sample_type_id INTEGER PRIMARY KEY AUTOINCREMENT,type_name TEXT UNIQUE NOT NULL,description TEXT);
CREATE TABLE IF NOT EXISTS collection_event(collection_event_id INTEGER PRIMARY KEY AUTOINCREMENT,donor_id INTEGER NOT NULL,collection_date TEXT NOT NULL,collection_site TEXT NOT NULL,collector_name TEXT NOT NULL,protocol_code TEXT NOT NULL,notes TEXT,FOREIGN KEY(donor_id) REFERENCES donor(donor_id));
CREATE TABLE IF NOT EXISTS biospecimen(sample_id INTEGER PRIMARY KEY AUTOINCREMENT,sample_code TEXT UNIQUE NOT NULL,collection_event_id INTEGER NOT NULL,sample_type_id INTEGER NOT NULL,volume_ml REAL,collection_time TEXT NOT NULL,quality_status TEXT DEFAULT 'Pending',current_status TEXT DEFAULT 'Available',FOREIGN KEY(collection_event_id) REFERENCES collection_event(collection_event_id),FOREIGN KEY(sample_type_id) REFERENCES sample_type(sample_type_id));
CREATE TABLE IF NOT EXISTS storage_location(location_id INTEGER PRIMARY KEY AUTOINCREMENT,facility TEXT NOT NULL,room_code TEXT NOT NULL,freezer_code TEXT NOT NULL,shelf_no INTEGER NOT NULL,box_code TEXT NOT NULL,position_no INTEGER NOT NULL,temperature_c REAL NOT NULL);
CREATE TABLE IF NOT EXISTS aliquot(aliquot_id INTEGER PRIMARY KEY AUTOINCREMENT,sample_id INTEGER NOT NULL,aliquot_code TEXT UNIQUE NOT NULL,volume_ml REAL NOT NULL,location_id INTEGER,status TEXT DEFAULT 'Stored',created_at TEXT NOT NULL,FOREIGN KEY(sample_id) REFERENCES biospecimen(sample_id),FOREIGN KEY(location_id) REFERENCES storage_location(location_id));
CREATE TABLE IF NOT EXISTS researcher(researcher_id INTEGER PRIMARY KEY AUTOINCREMENT,researcher_code TEXT UNIQUE NOT NULL,full_name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,department TEXT NOT NULL,active_flag INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS test_request(test_request_id INTEGER PRIMARY KEY AUTOINCREMENT,researcher_id INTEGER NOT NULL,request_date TEXT NOT NULL,purpose TEXT NOT NULL,priority TEXT DEFAULT 'Routine',status TEXT DEFAULT 'Requested',FOREIGN KEY(researcher_id) REFERENCES researcher(researcher_id));
CREATE TABLE IF NOT EXISTS sample_usage(usage_id INTEGER PRIMARY KEY AUTOINCREMENT,test_request_id INTEGER NOT NULL,aliquot_id INTEGER NOT NULL,usage_date TEXT NOT NULL,quantity_used_ml REAL NOT NULL,result_summary TEXT,UNIQUE(test_request_id,aliquot_id),FOREIGN KEY(test_request_id) REFERENCES test_request(test_request_id),FOREIGN KEY(aliquot_id) REFERENCES aliquot(aliquot_id));
CREATE TABLE IF NOT EXISTS sample_test(sample_test_id INTEGER PRIMARY KEY AUTOINCREMENT,test_request_id INTEGER NOT NULL,sample_id INTEGER NOT NULL,test_name TEXT NOT NULL,test_date TEXT,result_value TEXT,result_unit TEXT,result_status TEXT,UNIQUE(test_request_id,sample_id,test_name),FOREIGN KEY(test_request_id) REFERENCES test_request(test_request_id),FOREIGN KEY(sample_id) REFERENCES biospecimen(sample_id));
'''

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c

def seed():
    c=db(); c.executescript(SCHEMA)
    if c.execute('SELECT COUNT(*) n FROM donor').fetchone()['n']:
        c.close(); return
    donors=[('D001','Ahmed','Hassan','1988-03-14','M','ahmed.hassan@example.org','01000000001'),('D002','Mona','Ali','1991-07-22','F','mona.ali@example.org','01000000002'),('D003','Omar','Khaled','1985-11-09','M','omar.khaled@example.org','01000000003'),('D004','Sara','Nabil','1994-02-18','F','sara.nabil@example.org','01000000004'),('D005','Youssef','Adel','1989-09-30','M','youssef.adel@example.org','01000000005'),('D006','Nour','Samir','1996-05-11','F','nour.samir@example.org','01000000006'),('D007','Karim','Fathy','1982-12-03','M','karim.fathy@example.org','01000000007'),('D008','Hana','Mostafa','1990-06-27','F','hana.mostafa@example.org','01000000008'),('D009','Tarek','Mahmoud','1987-01-16','M','tarek.mahmoud@example.org','01000000009'),('D010','Laila','Said','1993-10-05','F','laila.said@example.org','01000000010')]
    c.executemany('INSERT INTO donor(donor_code,first_name,last_name,date_of_birth,sex,email,phone,registration_date) VALUES(?,?,?,?,?,?,?,?)',[x+('2026-01-05',) if x[0]=='D001' else x+('2026-01-06',) for x in donors])
    types=[('Whole Blood','Whole blood specimen'),('Plasma','Plasma isolated from blood'),('Serum','Serum specimen'),('Urine','Urine specimen'),('Saliva','Saliva specimen'),('Tissue','Biological tissue'),('DNA','Extracted genomic DNA'),('RNA','Extracted RNA'),('PBMC','Peripheral blood mononuclear cells'),('CSF','Cerebrospinal fluid')]
    c.executemany('INSERT INTO sample_type(type_name,description) VALUES(?,?)',types)
    for i in range(1,11):
        c.execute('INSERT INTO consent(donor_id,consent_type,consent_date,status,version_no) VALUES(?,?,?,?,?)',(i,'Research Use',f'2026-01-{4+i:02d}','Active','v1'))
        c.execute('INSERT INTO collection_event(donor_id,collection_date,collection_site,collector_name,protocol_code,notes) VALUES(?,?,?,?,?,?)',(i,f'2026-02-{i:02d} 09:00','Alexandria Site A' if i%2 else 'Alexandria Site B','Dr. A. Farid' if i%3 else 'Dr. M. Salem','COL-01' if i%2 else 'COL-02','Routine collection'))
    vols=[8,7,10,6,9,5,4,6,8,5]
    for i,v in enumerate(vols,1):
        c.execute('INSERT INTO biospecimen(sample_code,collection_event_id,sample_type_id,volume_ml,collection_time,quality_status,current_status) VALUES(?,?,?,?,?,?,?)',(f'S{i:03d}',i,(i-1)%10+1,v,f'2026-02-{i:02d} 09:00','Accepted','Available'))
        c.execute('INSERT INTO storage_location(facility,room_code,freezer_code,shelf_no,box_code,position_no,temperature_c) VALUES(?,?,?,?,?,?,?)',('Alexandria Biobank',f'R0{(i%3)+1}',f'FZ-0{(i%3)+1}',(i%3)+1,f'B{(i%5)+1:02d}',i,-80 if i%2 else -20))
        loc=c.execute('SELECT last_insert_rowid() id').fetchone()['id']
        q=round(v/2,2)
        c.execute('INSERT INTO aliquot(sample_id,aliquot_code,volume_ml,location_id,status,created_at) VALUES(?,?,?,?,?,?)',(i,f'A{i:03d}',q,loc,'Stored',f'2026-02-{i:02d} 10:00'))
    for i in range(1,11):
        c.execute('INSERT INTO researcher(researcher_code,full_name,email,department) VALUES(?,?,?,?)',(f'R{i:03d}',f'Dr. Researcher {i}',f'researcher{i}@example.org',['Molecular Biology','Genomics','Immunology'][i%3]))
        c.execute('INSERT INTO test_request(researcher_id,request_date,purpose,priority,status) VALUES(?,?,?,?,?)',(i,f'2026-02-{11+i:02d}', ['Protein biomarker screening','Targeted sequencing','Immune marker analysis'][i%3], ['Routine','High','Urgent'][i%3], ['Approved','Completed','In Progress'][i%3]))
    c.commit(); c.close()

seed()

def q(sql,args=()):
    c=db(); rows=c.execute(sql,args).fetchall(); c.close(); return rows

def one(sql,args=()):
    c=db(); r=c.execute(sql,args).fetchone(); c.close(); return r

def esc(s):
    return ('' if s is None else str(s)).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')

def page(title,body,active='dashboard'):
    nav=[('dashboard','Dashboard','/'),('donors','Donors','/donors'),('samples','Samples','/samples'),('aliquots','Aliquots','/aliquots'),('requests','Test Requests','/requests'),('usage','Sample Usage','/usage'),('tests','Test Results','/tests'),('inventory','Inventory','/inventory')]
    links=''.join(f'<a class="nav {"active" if active==k else ""}" href="{u}">{lab}</a>' for k,lab,u in nav)
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} · CBIO204 Biobank</title><style>
    *{{box-sizing:border-box}}body{{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f4f7fb;color:#18212f}}.sidebar{{position:fixed;left:0;top:0;bottom:0;width:230px;background:#101827;color:white;padding:24px 16px}}.brand{{font-size:19px;font-weight:800;padding:0 12px 25px}}.brand span{{color:#5eead4}}.nav{{display:block;color:#aeb9ca;text-decoration:none;padding:11px 12px;border-radius:10px;margin:4px 0;font-size:14px}}.nav:hover,.nav.active{{background:#1c293c;color:white}}main{{margin-left:230px;min-height:100vh;padding:28px 34px}}.top{{display:flex;justify-content:space-between;align-items:center;margin-bottom:25px}}h1{{font-size:27px;margin:0 0 5px}}.muted{{color:#6b7789;font-size:14px}}.badge{{padding:5px 9px;border-radius:999px;font-size:12px;font-weight:700;background:#e9eef5;color:#41516a}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:22px}}.card{{background:white;border:1px solid #e5eaf1;border-radius:16px;padding:19px;box-shadow:0 4px 16px rgba(18,32,52,.04)}}.metric{{font-size:29px;font-weight:800;margin-top:8px}}.tablewrap{{background:white;border:1px solid #e5eaf1;border-radius:16px;overflow:auto;box-shadow:0 4px 16px rgba(18,32,52,.04)}}table{{width:100%;border-collapse:collapse}}th,td{{padding:13px 15px;border-bottom:1px solid #edf0f4;text-align:left;font-size:13px;white-space:nowrap}}th{{font-size:12px;color:#667388;text-transform:uppercase;letter-spacing:.04em;background:#fbfcfe}}tr:last-child td{{border-bottom:0}}.btn{{display:inline-block;text-decoration:none;border:0;background:#0f766e;color:white;padding:9px 13px;border-radius:9px;font-weight:700;font-size:13px;cursor:pointer}}.btn.secondary{{background:#eef2f7;color:#25344b}}.actions{{display:flex;gap:8px;align-items:center}}.formcard{{max-width:780px}}label{{display:block;font-size:13px;font-weight:700;margin:13px 0 6px}}input,select,textarea{{width:100%;padding:10px 11px;border:1px solid #d8dee8;border-radius:9px;background:white;font:inherit}}textarea{{min-height:90px}}.two{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}.alert{{background:#fff7ed;border:1px solid #fed7aa;color:#9a3412;padding:12px 14px;border-radius:10px;margin-bottom:16px}}.success{{background:#ecfdf5;border:1px solid #a7f3d0;color:#065f46;padding:12px 14px;border-radius:10px;margin-bottom:16px}}.section{{margin:22px 0 12px;display:flex;justify-content:space-between;align-items:center}}.section h2{{font-size:17px;margin:0}}.pill-green{{background:#dcfce7;color:#166534}}.pill-red{{background:#fee2e2;color:#991b1b}}.pill-blue{{background:#dbeafe;color:#1e40af}}@media(max-width:900px){{.sidebar{{position:static;width:auto;height:auto}}main{{margin:0;padding:20px}}.grid{{grid-template-columns:1fr 1fr}}}}@media(max-width:560px){{.grid,.two{{grid-template-columns:1fr}}}}
    </style></head><body><aside class="sidebar"><div class="brand">CBIO204 <span>Biobank</span></div>{links}<div style="position:absolute;bottom:20px;left:28px;color:#718096;font-size:11px">Nadien Ahmed Shawky<br>ID: 221002162</div></aside><main><div class="top"><div><h1>{esc(title)}</h1><div class="muted">Biospecimen Management System · PostgreSQL project demo</div></div><span class="badge">Demo Mode</span></div>{body}</main></body></html>'''

def table(headers, rows):
    h=''.join(f'<th>{esc(x)}</th>' for x in headers); b=''.join('<tr>'+''.join(f'<td>{x}</td>' for x in r)+'</tr>' for r in rows)
    return f'<div class="tablewrap"><table><thead><tr>{h}</tr></thead><tbody>{b or "<tr><td colspan="+str(len(headers))+">No records found.</td></tr>"}</tbody></table></div>'

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def send_html(self,html,status=200):
        data=html.encode(); self.send_response(status); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
    def redirect(self,path): self.send_response(303); self.send_header('Location',path); self.end_headers()
    def body(self):
        n=int(self.headers.get('Content-Length','0')); return parse_qs(self.rfile.read(n).decode())
    def do_GET(self):
        p=urlparse(self.path); path=p.path; qs=parse_qs(p.query)
        if path=='/': return self.dashboard()
        if path=='/donors': return self.donors(qs)
        if path=='/samples': return self.samples(qs)
        if path=='/aliquots': return self.aliquots(qs)
        if path=='/requests': return self.requests(qs)
        if path=='/usage': return self.usage(qs)
        if path=='/tests': return self.tests(qs)
        if path=='/inventory': return self.inventory(qs)
        if path in ['/donors/new','/samples/new','/requests/new','/usage/new','/tests/new']:
            return self.form(path)
        self.send_html(page('Not Found','<div class="alert">Page not found.</div>'),404)
    def do_POST(self):
        path=urlparse(self.path).path; d={k:v[0] for k,v in self.body().items()}
        try:
            c=db()
            if path=='/donors/new':
                c.execute('INSERT INTO donor(donor_code,first_name,last_name,date_of_birth,sex,email,phone,registration_date) VALUES(?,?,?,?,?,?,?,?)',(d['donor_code'],d['first_name'],d['last_name'],d['date_of_birth'],d['sex'],d.get('email'),d.get('phone'),date.today().isoformat())); c.commit(); c.close(); return self.redirect('/donors')
            if path=='/samples/new':
                c.execute('INSERT INTO collection_event(donor_id,collection_date,collection_site,collector_name,protocol_code,notes) VALUES(?,?,?,?,?,?)',(d['donor_id'],d['collection_date'],d['collection_site'],d['collector_name'],d['protocol_code'],d.get('notes'))); ce=c.execute('SELECT last_insert_rowid() id').fetchone()['id']; c.execute('INSERT INTO biospecimen(sample_code,collection_event_id,sample_type_id,volume_ml,collection_time,quality_status,current_status) VALUES(?,?,?,?,?,?,?)',(d['sample_code'],ce,d['sample_type_id'],float(d['volume_ml']),d['collection_date'],'Accepted','Available')); c.commit(); c.close(); return self.redirect('/samples')
            if path=='/requests/new':
                c.execute('INSERT INTO test_request(researcher_id,request_date,purpose,priority,status) VALUES(?,?,?,?,?)',(d['researcher_id'],date.today().isoformat(),d['purpose'],d['priority'],'Requested')); c.commit(); c.close(); return self.redirect('/requests')
            if path=='/usage/new':
                a=c.execute('SELECT volume_ml FROM aliquot WHERE aliquot_id=?',(d['aliquot_id'],)).fetchone();
                if not a: raise ValueError('Aliquot not found')
                qty=float(d['quantity_used_ml'])
                if qty<=0 or qty>a['volume_ml']: raise ValueError(f'Usage {qty:.2f} mL exceeds available aliquot volume {a["volume_ml"]:.2f} mL.')
                c.execute('INSERT INTO sample_usage(test_request_id,aliquot_id,usage_date,quantity_used_ml,result_summary) VALUES(?,?,?,?,?)',(d['test_request_id'],d['aliquot_id'],date.today().isoformat(),qty,d.get('result_summary')))
                c.execute('UPDATE aliquot SET volume_ml=volume_ml-?,status=? WHERE aliquot_id=?',(qty,'Depleted' if abs(a['volume_ml']-qty)<1e-9 else 'Used',d['aliquot_id']))
                c.commit(); c.close(); return self.redirect('/usage')
            if path=='/tests/new':
                c.execute('INSERT INTO sample_test(test_request_id,sample_id,test_name,test_date,result_value,result_unit,result_status) VALUES(?,?,?,?,?,?,?)',(d['test_request_id'],d['sample_id'],d['test_name'],date.today().isoformat(),d.get('result_value'),d.get('result_unit'),d['result_status'])); c.commit(); c.close(); return self.redirect('/tests')
            c.close()
        except Exception as e:
            msg=f'<div class="alert"><b>Action could not be completed:</b> {esc(e)}</div><a class="btn secondary" href="/">Back to dashboard</a>'
            return self.send_html(page('Validation Error',msg),400)
        self.redirect('/')
    def dashboard(self):
        counts={k:one(v)['n'] for k,v in {'Donors':'SELECT COUNT(*) n FROM donor','Samples':'SELECT COUNT(*) n FROM biospecimen','Aliquots':'SELECT COUNT(*) n FROM aliquot','Requests':'SELECT COUNT(*) n FROM test_request'}.items()}
        used=one('SELECT COALESCE(SUM(quantity_used_ml),0) n FROM sample_usage')['n']; avail=one('SELECT COALESCE(SUM(volume_ml),0) n FROM aliquot WHERE status<>"Depleted"')['n']
        recent=q('''SELECT b.sample_code,st.type_name,d.donor_code,b.current_status,b.volume_ml FROM biospecimen b JOIN sample_type st ON st.sample_type_id=b.sample_type_id JOIN collection_event ce ON ce.collection_event_id=b.collection_event_id JOIN donor d ON d.donor_id=ce.donor_id ORDER BY b.sample_id DESC LIMIT 8''')
        cards=''.join(f'<div class="card"><div class="muted">{k}</div><div class="metric">{v}</div></div>' for k,v in counts.items())
        body=f'<div class="grid">{cards}</div><div class="grid"><div class="card"><div class="muted">Available aliquot volume</div><div class="metric">{avail:.2f} mL</div></div><div class="card"><div class="muted">Total volume used</div><div class="metric">{used:.2f} mL</div></div><div class="card"><div class="muted">Accepted samples</div><div class="metric">{one("SELECT COUNT(*) n FROM biospecimen WHERE quality_status=\"Accepted\"")["n"]}</div></div><div class="card"><div class="muted">Active consent</div><div class="metric">{one("SELECT COUNT(*) n FROM consent WHERE status=\"Active\"")["n"]}</div></div></div>'
        rows=[[esc(r['sample_code']),esc(r['donor_code']),esc(r['type_name']),esc(r['current_status']),f'{r["volume_ml"]:.2f} mL'] for r in recent]
        body+='<div class="section"><h2>Recent specimens</h2><a class="btn" href="/samples/new">+ Add sample</a></div>'+table(['Sample','Donor','Type','Status','Volume'],rows)
        self.send_html(page('Dashboard',body))
    def donors(self,qs):
        search=qs.get('q',[''])[0]; rows=q('SELECT donor_id,donor_code,first_name,last_name,date_of_birth,sex,email,status FROM donor WHERE donor_code LIKE ? OR first_name LIKE ? OR last_name LIKE ? ORDER BY donor_id DESC',(f'%{search}%',f'%{search}%',f'%{search}%'))
        trs=[[esc(r['donor_code']),esc(r['first_name']+' '+r['last_name']),esc(r['date_of_birth']),esc(r['sex']),esc(r['email']),f'<span class="badge">{esc(r["status"])}</span>',f'<a class="btn secondary" href="/samples?q={esc(r["donor_code"])}">Samples</a>'] for r in rows]
        body=f'<div class="actions" style="margin-bottom:16px"><form><input name="q" placeholder="Search donor code or name" value="{esc(search)}"></form><a class="btn" href="/donors/new">+ Add donor</a></div>'+table(['Code','Name','DOB','Sex','Email','Status',''],trs)
        self.send_html(page('Donors',body,'donors'))
    def samples(self,qs):
        search=qs.get('q',[''])[0]; rows=q('''SELECT b.sample_code,b.volume_ml,b.quality_status,b.current_status,st.type_name,d.donor_code,d.first_name||' '||d.last_name donor_name FROM biospecimen b JOIN sample_type st ON st.sample_type_id=b.sample_type_id JOIN collection_event ce ON ce.collection_event_id=b.collection_event_id JOIN donor d ON d.donor_id=ce.donor_id WHERE b.sample_code LIKE ? OR d.donor_code LIKE ? OR d.first_name LIKE ? OR st.type_name LIKE ? ORDER BY b.sample_id DESC''',(f'%{search}%',f'%{search}%',f'%{search}%',f'%{search}%'))
        trs=[[esc(r['sample_code']),esc(r['donor_code']),esc(r['donor_name']),esc(r['type_name']),f'{r["volume_ml"]:.2f}',esc(r['quality_status']),esc(r['current_status'])] for r in rows]
        body=f'<div class="actions" style="margin-bottom:16px"><form><input name="q" placeholder="Search sample, donor or type" value="{esc(search)}"></form><a class="btn" href="/samples/new">+ Add sample</a></div>'+table(['Sample','Donor','Donor name','Type','Volume mL','Quality','Status'],trs)
        self.send_html(page('Samples',body,'samples'))
    def aliquots(self,qs):
        rows=q('''SELECT a.aliquot_code,b.sample_code,st.type_name,a.volume_ml,a.status,sl.freezer_code,sl.shelf_no,sl.box_code,sl.position_no,sl.temperature_c FROM aliquot a JOIN biospecimen b ON b.sample_id=a.sample_id JOIN sample_type st ON st.sample_type_id=b.sample_type_id LEFT JOIN storage_location sl ON sl.location_id=a.location_id ORDER BY a.aliquot_id DESC''')
        trs=[[esc(r['aliquot_code']),esc(r['sample_code']),esc(r['type_name']),f'{r["volume_ml"]:.2f}',esc(r['status']),esc(r['freezer_code'] or '-'),str(r['shelf_no'] or '-'),esc(r['box_code'] or '-'),str(r['position_no'] or '-'),f'{r["temperature_c"]:.0f}°C' if r['temperature_c'] is not None else '-'] for r in rows]
        self.send_html(page('Aliquots',table(['Aliquot','Sample','Type','Volume','Status','Freezer','Shelf','Box','Position','Temp'],trs),'aliquots'))
    def requests(self,qs):
        rows=q('SELECT tr.test_request_id,r.researcher_code,r.full_name,tr.request_date,tr.purpose,tr.priority,tr.status FROM test_request tr JOIN researcher r ON r.researcher_id=tr.researcher_id ORDER BY tr.test_request_id DESC')
        trs=[[str(r['test_request_id']),esc(r['researcher_code']),esc(r['full_name']),esc(r['request_date']),esc(r['purpose']),f'<span class="badge">{esc(r["priority"])}</span>',esc(r['status'])] for r in rows]
        body='<div class="section"><h2>Research workflow</h2><a class="btn" href="/requests/new">+ New request</a></div>'+table(['ID','Researcher','Name','Date','Purpose','Priority','Status'],trs)
        self.send_html(page('Test Requests',body,'requests'))
    def usage(self,qs):
        rows=q('''SELECT su.usage_id,tr.test_request_id,a.aliquot_code,b.sample_code,su.usage_date,su.quantity_used_ml,su.result_summary FROM sample_usage su JOIN test_request tr ON tr.test_request_id=su.test_request_id JOIN aliquot a ON a.aliquot_id=su.aliquot_id JOIN biospecimen b ON b.sample_id=a.sample_id ORDER BY su.usage_id DESC''')
        trs=[[str(r['usage_id']),str(r['test_request_id']),esc(r['aliquot_code']),esc(r['sample_code']),esc(r['usage_date']),f'{r["quantity_used_ml"]:.2f}',esc(r['result_summary'] or '-')] for r in rows]
        body='<div class="section"><h2>Automatic inventory deduction</h2><a class="btn" href="/usage/new">+ Record usage</a></div><div class="muted" style="margin-bottom:12px">The app blocks usage greater than the aliquot volume and deducts the used quantity automatically.</div>'+table(['Usage','Request','Aliquot','Sample','Date','Used mL','Result summary'],trs)
        self.send_html(page('Sample Usage',body,'usage'))
    def tests(self,qs):
        rows=q('''SELECT st.sample_test_id,st.test_request_id,b.sample_code,st.test_name,st.test_date,st.result_value,st.result_unit,st.result_status FROM sample_test st JOIN biospecimen b ON b.sample_id=st.sample_id ORDER BY st.sample_test_id DESC''')
        trs=[[str(r['sample_test_id']),str(r['test_request_id']),esc(r['sample_code']),esc(r['test_name']),esc(r['test_date'] or '-'),esc(r['result_value'] or '-'),esc(r['result_unit'] or ''),esc(r['result_status'] or '-') ] for r in rows]
        body='<div class="section"><h2>Laboratory results</h2><a class="btn" href="/tests/new">+ Add result</a></div>'+table(['ID','Request','Sample','Test','Date','Value','Unit','Status'],trs)
        self.send_html(page('Test Results',body,'tests'))
    def inventory(self,qs):
        rows=q('''SELECT b.sample_code,d.donor_code,d.first_name||' '||d.last_name donor_name,st.type_name,b.volume_ml,b.quality_status,b.current_status,COUNT(a.aliquot_id) aliquot_count,COALESCE(SUM(a.volume_ml),0) aliquot_volume FROM biospecimen b JOIN collection_event ce ON ce.collection_event_id=b.collection_event_id JOIN donor d ON d.donor_id=ce.donor_id JOIN sample_type st ON st.sample_type_id=b.sample_type_id LEFT JOIN aliquot a ON a.sample_id=b.sample_id GROUP BY b.sample_id ORDER BY b.sample_id''')
        trs=[[esc(r['sample_code']),esc(r['donor_code']),esc(r['donor_name']),esc(r['type_name']),f'{r["volume_ml"]:.2f}',esc(r['quality_status']),esc(r['current_status']),str(r['aliquot_count']),f'{r["aliquot_volume"]:.2f}'] for r in rows]
        self.send_html(page('Inventory View',table(['Sample','Donor','Donor name','Type','Sample mL','Quality','Status','Aliquots','Aliquot mL'],trs),'inventory'))
    def form(self,path):
        if path=='/donors/new':
            fields='''<div class="two"><div><label>Donor code</label><input name="donor_code" required placeholder="D011"></div><div><label>Sex</label><select name="sex"><option>M</option><option>F</option><option>O</option></select></div></div><div class="two"><div><label>First name</label><input name="first_name" required></div><div><label>Last name</label><input name="last_name" required></div></div><div class="two"><div><label>Date of birth</label><input type="date" name="date_of_birth" required></div><div><label>Phone</label><input name="phone"></div></div><label>Email</label><input type="email" name="email">'''; title='Add Donor'
        elif path=='/samples/new':
            ds=q('SELECT donor_id,donor_code,first_name,last_name FROM donor ORDER BY donor_code'); ts=q('SELECT sample_type_id,type_name FROM sample_type ORDER BY type_name')
            fields=f'''<div class="two"><div><label>Sample code</label><input name="sample_code" required placeholder="S011"></div><div><label>Sample type</label><select name="sample_type_id">{''.join(f'<option value="{r["sample_type_id"]}">{esc(r["type_name"])}</option>' for r in ts)}</select></div></div><label>Donor</label><select name="donor_id">{''.join(f'<option value="{r["donor_id"]}">{esc(r["donor_code"])} — {esc(r["first_name"]+" "+r["last_name"])}</option>' for r in ds)}</select><div class="two"><div><label>Collection date/time</label><input type="datetime-local" name="collection_date" value="2026-08-15T09:00" required></div><div><label>Volume (mL)</label><input type="number" step="0.01" name="volume_ml" value="5" required></div></div><div class="two"><div><label>Collection site</label><input name="collection_site" value="Alexandria Site A" required></div><div><label>Collector</label><input name="collector_name" value="Dr. A. Farid" required></div></div><div class="two"><div><label>Protocol</label><input name="protocol_code" value="COL-01" required></div><div><label>Notes</label><input name="notes"></div></div>'''; title='Add Sample'
        elif path=='/requests/new':
            rs=q('SELECT researcher_id,researcher_code,full_name FROM researcher WHERE active_flag=1 ORDER BY researcher_code')
            fields=f'''<label>Researcher</label><select name="researcher_id">{''.join(f'<option value="{r["researcher_id"]}">{esc(r["researcher_code"])} — {esc(r["full_name"])}</option>' for r in rs)}</select><label>Purpose</label><textarea name="purpose" required placeholder="e.g. Targeted sequencing"></textarea><label>Priority</label><select name="priority"><option>Routine</option><option>High</option><option>Urgent</option></select>'''; title='New Test Request'
        elif path=='/usage/new':
            rs=q('SELECT test_request_id,purpose FROM test_request ORDER BY test_request_id DESC'); als=q('SELECT a.aliquot_id,a.aliquot_code,b.sample_code,a.volume_ml FROM aliquot a JOIN biospecimen b ON b.sample_id=a.sample_id WHERE a.volume_ml>0 ORDER BY a.aliquot_code')
            fields=f'''<label>Test request</label><select name="test_request_id">{''.join(f'<option value="{r["test_request_id"]}">#{r["test_request_id"]} — {esc(r["purpose"])}</option>' for r in rs)}</select><label>Aliquot</label><select name="aliquot_id">{''.join(f'<option value="{r["aliquot_id"]}">{esc(r["aliquot_code"])} / {esc(r["sample_code"])} — {r["volume_ml"]:.2f} mL available</option>' for r in als)}</select><label>Quantity used (mL)</label><input type="number" step="0.01" min="0.01" name="quantity_used_ml" required><label>Result summary</label><textarea name="result_summary"></textarea>'''; title='Record Sample Usage'
        else:
            rs=q('SELECT test_request_id,purpose FROM test_request ORDER BY test_request_id DESC'); ss=q('SELECT sample_id,sample_code FROM biospecimen ORDER BY sample_code')
            fields=f'''<div class="two"><div><label>Test request</label><select name="test_request_id">{''.join(f'<option value="{r["test_request_id"]}">#{r["test_request_id"]} — {esc(r["purpose"])}</option>' for r in rs)}</select></div><div><label>Sample</label><select name="sample_id">{''.join(f'<option value="{r["sample_id"]}">{esc(r["sample_code"])}</option>' for r in ss)}</select></div></div><label>Test name</label><input name="test_name" required placeholder="Protein Biomarker Panel"><div class="two"><div><label>Result value</label><input name="result_value"></div><div><label>Unit</label><input name="result_unit"></div></div><label>Result status</label><select name="result_status"><option>Pending</option><option>Normal</option><option>Abnormal</option><option>Invalid</option></select>'''; title='Add Test Result'
        body=f'<div class="card formcard"><form method="post">{fields}<div class="actions" style="margin-top:18px"><button class="btn" type="submit">Save record</button><a class="btn secondary" href="/">Cancel</a></div></form></div>'
        self.send_html(page(title,body))

if __name__=='__main__':
    print(f'CBIO204 Biobank running at http://127.0.0.1:{PORT}')
    HTTPServer((HOST,PORT),Handler).serve_forever()
