import os, sqlite3, secrets
from datetime import date, datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from werkzeug.security import generate_password_hash, check_password_hash

app=Flask(__name__)
# Production mode requires an explicitly supplied secret and disables demo seed data.
ENV=os.environ.get('MEYZBAN_ENV','development').lower()
SECRET=os.environ.get('SECRET_KEY')
if ENV=='production' and (not SECRET or len(SECRET)<32):
 raise RuntimeError('Set SECRET_KEY to a cryptographically random value of at least 32 characters')
app.secret_key=SECRET or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=(ENV=='production'), MAX_CONTENT_LENGTH=8*1024*1024)

DB=os.environ.get('DATABASE_PATH',os.path.join(os.path.dirname(__file__),'meyzban.db'))

def conn():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c

def init():
 os.makedirs(os.path.dirname(os.path.abspath(DB)),exist_ok=True)
 with conn() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'guest',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
 CREATE TABLE IF NOT EXISTS properties(id INTEGER PRIMARY KEY,host_id INTEGER NOT NULL,title TEXT NOT NULL,city TEXT NOT NULL,area TEXT NOT NULL,kind TEXT NOT NULL,price INTEGER NOT NULL,guests INTEGER NOT NULL,description TEXT,image TEXT,status TEXT NOT NULL DEFAULT 'active',created_at TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(host_id) REFERENCES users(id));
 CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY,guest_id INTEGER NOT NULL,city TEXT NOT NULL,kind TEXT,checkin TEXT NOT NULL,checkout TEXT NOT NULL,guests INTEGER NOT NULL,budget INTEGER NOT NULL,notes TEXT,status TEXT DEFAULT 'open',created_at TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(guest_id) REFERENCES users(id));
 CREATE TABLE IF NOT EXISTS bids(id INTEGER PRIMARY KEY,request_id INTEGER NOT NULL,host_id INTEGER NOT NULL,property_id INTEGER,amount INTEGER NOT NULL,message TEXT,status TEXT DEFAULT 'pending',created_at TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(request_id,host_id),FOREIGN KEY(request_id) REFERENCES requests(id),FOREIGN KEY(host_id) REFERENCES users(id));
 CREATE TABLE IF NOT EXISTS offers(id INTEGER PRIMARY KEY,property_id INTEGER NOT NULL,guest_id INTEGER NOT NULL,amount INTEGER NOT NULL,checkin TEXT NOT NULL,checkout TEXT NOT NULL,message TEXT,status TEXT DEFAULT 'pending',created_at TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(property_id) REFERENCES properties(id),FOREIGN KEY(guest_id) REFERENCES users(id));
 CREATE TABLE IF NOT EXISTS bookings(id INTEGER PRIMARY KEY,property_id INTEGER NOT NULL,guest_id INTEGER NOT NULL,host_id INTEGER NOT NULL,checkin TEXT NOT NULL,checkout TEXT NOT NULL,amount INTEGER NOT NULL,status TEXT DEFAULT 'confirmed',created_at TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(property_id) REFERENCES properties(id));''')
  if ENV!='production' and os.environ.get('SEED_DEMO','0')=='1' and not c.execute('SELECT 1 FROM users LIMIT 1').fetchone():
   c.execute('INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)',('Demo Host','host@meyzban.test',generate_password_hash('Test12345!'),'host'))
   hid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
   sample=[('Modern Apartment in Gulberg','Lahore','Gulberg','Apartment',12500,4,'Bright two-bedroom apartment close to cafes and shopping.'),('Family House in DHA','Lahore','DHA Phase 5','House',22000,8,'Spacious family stay with private parking.'),('Cozy Guesthouse in Johar Town','Lahore','Johar Town','Guesthouse',6500,2,'Comfortable and affordable private room.'),('Weekend Farmhouse Retreat','Lahore','Bedian Road','Farmhouse',35000,12,'Relaxing getaway with a garden and outdoor seating.'),('Boutique Hotel Suite','Lahore','MM Alam Road','Hotel',16000,2,'Convenient boutique suite in central Lahore.'),('Quiet Studio Near Model Town','Lahore','Model Town','Apartment',8500,2,'Simple studio for business and short stays.')]
   for p in sample:c.execute('INSERT INTO properties(host_id,title,city,area,kind,price,guests,description) VALUES(?,?,?,?,?,?,?,?)',(hid,*p))

@app.after_request
def security_headers(response):
 response.headers['X-Content-Type-Options']='nosniff'
 response.headers['X-Frame-Options']='DENY'
 response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
 response.headers['Content-Security-Policy']="default-src 'self' https: data:; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
 if ENV=='production':response.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
 return response

@app.before_request
def csrf_check():
 if request.method=='POST':
  if request.form.get('csrf')!=session.get('csrf'):abort(400,'Invalid form token. Refresh and try again.')
@app.context_processor
def common():
 if 'csrf' not in session:session['csrf']=secrets.token_hex(24)
 return dict(me=current_user(),csrf=session['csrf'],today=date.today().isoformat())
def current_user():
 if not session.get('uid'):return None
 with conn() as c:return c.execute('SELECT * FROM users WHERE id=?',(session['uid'],)).fetchone()
def login_required(f):
 @wraps(f)
 def inner(*a,**kw):
  if not current_user():flash('Please sign in first.','warning');return redirect(url_for('login',next=request.path))
  return f(*a,**kw)
 return inner
def host_required(f):
 @wraps(f)
 @login_required
 def inner(*a,**kw):
  if current_user()['role']!='host':flash('Switch to a host account to use this feature.','warning');return redirect(url_for('dashboard'))
  return f(*a,**kw)
 return inner
def valid_dates(a,b):
 try:return date.fromisoformat(a)>=date.today() and date.fromisoformat(b)>date.fromisoformat(a)
 except:return False

@app.route('/')
def home():
 with conn() as c:
  q='SELECT p.*,u.name host_name FROM properties p JOIN users u ON u.id=p.host_id WHERE p.status="active"';params=[]
  for key in ['city','kind']:
   if request.args.get(key):q+=f' AND p.{key} LIKE ?';params.append('%'+request.args[key]+'%')
  if request.args.get('guests','').isdigit():q+=' AND p.guests>=?';params.append(int(request.args['guests']))
  q+=' ORDER BY p.id DESC';properties=c.execute(q,params).fetchall()
 return render_template('home.html',properties=properties)
@app.route('/register',methods=['GET','POST'])
def register():
 if request.method=='POST':
  name=request.form.get('name','').strip();email=request.form.get('email','').strip().lower();password=request.form.get('password','');role=request.form.get('role','guest')
  if not name or '@' not in email or len(password)<8 or role not in ('guest','host'):flash('Enter a name, valid email, and password of at least 8 characters.','error')
  else:
   try:
    with conn() as c:
     cur=c.execute('INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)',(name,email,generate_password_hash(password),role));session['uid']=cur.lastrowid
    return redirect(url_for('dashboard'))
   except sqlite3.IntegrityError:flash('This email is already registered.','error')
 return render_template('auth.html',mode='register')
@app.route('/login',methods=['GET','POST'])
def login():
 if request.method=='POST':
  with conn() as c:u=c.execute('SELECT * FROM users WHERE email=?',(request.form.get('email','').strip().lower(),)).fetchone()
  if u and check_password_hash(u['password'],request.form.get('password','')):session['uid']=u['id'];return redirect(url_for('dashboard'))
  flash('Incorrect email or password.','error')
 return render_template('auth.html',mode='login')
@app.route('/logout',methods=['POST'])
def logout():session.clear();return redirect(url_for('home'))
@app.route('/properties/<int:pid>')
def property_detail(pid):
 with conn() as c:p=c.execute('SELECT p.*,u.name host_name FROM properties p JOIN users u ON u.id=p.host_id WHERE p.id=? AND p.status="active"',(pid,)).fetchone()
 if not p:abort(404)
 return render_template('property.html',p=p)
@app.route('/properties/new',methods=['GET','POST'])
@host_required
def property_new():
 if request.method=='POST':
  try:
   price=int(request.form['price']);guests=int(request.form['guests']);assert price>0 and guests>0
   with conn() as c:c.execute('INSERT INTO properties(host_id,title,city,area,kind,price,guests,description) VALUES(?,?,?,?,?,?,?,?)',(session['uid'],request.form['title'].strip(),request.form['city'].strip(),request.form['area'].strip(),request.form['kind'],price,guests,request.form.get('description','').strip()))
   flash('Your property is live in the test marketplace.','success');return redirect(url_for('dashboard'))
  except (ValueError,AssertionError,KeyError):flash('Please provide valid property details.','error')
 return render_template('form.html',kind='property')
@app.route('/requests/new',methods=['GET','POST'])
@login_required
def request_new():
 if request.method=='POST':
  try:
   a=request.form['checkin'];b=request.form['checkout'];budget=int(request.form['budget']);guests=int(request.form['guests']);assert valid_dates(a,b) and budget>0 and guests>0
   with conn() as c:c.execute('INSERT INTO requests(guest_id,city,kind,checkin,checkout,guests,budget,notes) VALUES(?,?,?,?,?,?,?,?)',(session['uid'],request.form['city'].strip(),request.form.get('kind','Any'),a,b,guests,budget,request.form.get('notes','')))
   flash('Your request is published. Hosts can now bid.','success');return redirect(url_for('dashboard'))
  except (ValueError,AssertionError,KeyError):flash('Please check your dates and budget.','error')
 return render_template('form.html',kind='request')
@app.route('/requests')
@host_required
def requests_list():
 with conn() as c:items=c.execute('SELECT r.*,u.name guest_name FROM requests r JOIN users u ON u.id=r.guest_id WHERE r.status="open" ORDER BY r.id DESC').fetchall()
 return render_template('requests.html',items=items)
@app.route('/requests/<int:rid>/bid',methods=['POST'])
@host_required
def bid(rid):
 try:amount=int(request.form['amount']);assert amount>0
 except:flash('Enter a valid bid amount.','error');return redirect(url_for('requests_list'))
 with conn() as c:
  r=c.execute('SELECT * FROM requests WHERE id=? AND status="open"',(rid,)).fetchone()
  if not r:abort(404)
  try:c.execute('INSERT INTO bids(request_id,host_id,amount,message) VALUES(?,?,?,?)',(rid,session['uid'],amount,request.form.get('message','')));flash('Bid sent.','success')
  except sqlite3.IntegrityError:flash('You have already bid on this request.','warning')
 return redirect(url_for('requests_list'))
@app.route('/bids/<int:bid_id>/accept',methods=['POST'])
@login_required
def accept_bid(bid_id):
 with conn() as c:
  b=c.execute('SELECT b.*,r.guest_id,r.checkin,r.checkout,r.status request_status FROM bids b JOIN requests r ON r.id=b.request_id WHERE b.id=?',(bid_id,)).fetchone()
  if not b or b['guest_id']!=session['uid'] or b['request_status']!='open':abort(403)
  c.execute('UPDATE bids SET status="accepted" WHERE id=?',(bid_id,));c.execute('UPDATE bids SET status="declined" WHERE request_id=? AND id<>?',(b['request_id'],bid_id));c.execute('UPDATE requests SET status="matched" WHERE id=?',(b['request_id'],));flash('Bid accepted. Contact and payment are not yet integrated; this is a test match.','success')
 return redirect(url_for('dashboard'))
@app.route('/properties/<int:pid>/offer',methods=['POST'])
@login_required
def offer(pid):
 try:
  amount=int(request.form['amount']);a=request.form['checkin'];b=request.form['checkout'];assert amount>0 and valid_dates(a,b)
 except:flash('Enter a valid offer and future dates.','error');return redirect(url_for('property_detail',pid=pid))
 with conn() as c:
  p=c.execute('SELECT * FROM properties WHERE id=? AND status="active"',(pid,)).fetchone()
  if not p or p['host_id']==session['uid']:abort(403)
  c.execute('INSERT INTO offers(property_id,guest_id,amount,checkin,checkout,message) VALUES(?,?,?,?,?,?)',(pid,session['uid'],amount,a,b,request.form.get('message','')))
 flash('Offer sent to host.','success');return redirect(url_for('dashboard'))
@app.route('/offers/<int:oid>/<decision>',methods=['POST'])
@host_required
def decide_offer(oid,decision):
 if decision not in ('accepted','declined'):abort(404)
 with conn() as c:
  o=c.execute('SELECT o.*,p.host_id FROM offers o JOIN properties p ON p.id=o.property_id WHERE o.id=?',(oid,)).fetchone()
  if not o or o['host_id']!=session['uid'] or o['status']!='pending':abort(403)
  c.execute('UPDATE offers SET status=? WHERE id=?',(decision,oid))
  if decision=='accepted':c.execute('INSERT INTO bookings(property_id,guest_id,host_id,checkin,checkout,amount,status) VALUES(?,?,?,?,?,?,?)',(o['property_id'],o['guest_id'],session['uid'],o['checkin'],o['checkout'],o['amount'],'pending_payment'))
 flash('Offer '+decision+'.','success');return redirect(url_for('dashboard'))
@app.route('/properties/<int:pid>/book',methods=['POST'])
@login_required
def book(pid):
 with conn() as c:
  c.execute('BEGIN IMMEDIATE')
  p=c.execute('SELECT * FROM properties WHERE id=? AND status="active"',(pid,)).fetchone()
  if not p or p['host_id']==session['uid']:abort(403)
  a=request.form.get('checkin','');b=request.form.get('checkout','')
  if not valid_dates(a,b):flash('Please select valid future dates.','error');return redirect(url_for('property_detail',pid=pid))
  if int(request.form.get('guests','1') or 1)>p['guests']:flash('Guest capacity exceeded.','error');return redirect(url_for('property_detail',pid=pid))
  nights=(date.fromisoformat(b)-date.fromisoformat(a)).days
  conflict=c.execute('SELECT 1 FROM bookings WHERE property_id=? AND status IN ("confirmed","pending_payment") AND checkin<? AND checkout>?',(pid,b,a)).fetchone()
  if conflict:flash('These dates are already held by another test booking.','error');return redirect(url_for('property_detail',pid=pid))
  c.execute('INSERT INTO bookings(property_id,guest_id,host_id,checkin,checkout,amount,status) VALUES(?,?,?,?,?,?,?)',(pid,session['uid'],p['host_id'],a,b,nights*p['price'],'pending_payment'))
 flash('Booking created as pending payment. No money has been charged.','success');return redirect(url_for('dashboard'))
@app.route('/bookings/<int:booking_id>/cancel',methods=['POST'])
@login_required
def cancel_booking(booking_id):
 with conn() as c:
  b=c.execute('SELECT * FROM bookings WHERE id=?',(booking_id,)).fetchone()
  if not b or session['uid'] not in (b['guest_id'],b['host_id']):abort(403)
  if b['status'] not in ('pending_payment','confirmed'):abort(400)
  c.execute('UPDATE bookings SET status="cancelled" WHERE id=?',(booking_id,))
 flash('Test booking cancelled.','success');return redirect(url_for('dashboard'))
@app.route('/dashboard')
@login_required
def dashboard():
 uid=session['uid'];host=current_user()['role']=='host'
 with conn() as c:
  props=c.execute('SELECT * FROM properties WHERE host_id=? ORDER BY id DESC',(uid,)).fetchall() if host else []
  myreq=c.execute('SELECT * FROM requests WHERE guest_id=? ORDER BY id DESC',(uid,)).fetchall()
  bids={r['id']:c.execute('SELECT b.*,u.name host_name FROM bids b JOIN users u ON u.id=b.host_id WHERE b.request_id=? ORDER BY b.amount',(r['id'],)).fetchall() for r in myreq}
  offers=c.execute('SELECT o.*,p.title,u.name guest_name FROM offers o JOIN properties p ON p.id=o.property_id JOIN users u ON u.id=o.guest_id WHERE '+('p.host_id=?' if host else 'o.guest_id=?')+' ORDER BY o.id DESC',(uid,)).fetchall()
  bookings=c.execute('SELECT b.*,p.title FROM bookings b JOIN properties p ON p.id=b.property_id WHERE '+('b.host_id=?' if host else 'b.guest_id=?')+' ORDER BY b.id DESC',(uid,)).fetchall()
 return render_template('dashboard.html',host=host,props=props,myreq=myreq,bids=bids,offers=offers,bookings=bookings)
@app.route('/readiness')
def readiness():
 try:
  with conn() as c:c.execute('SELECT 1').fetchone()
  return {'status':'ready','database':'connected'}
 except Exception:return {'status':'unavailable'},503

@app.route('/health')
def health():return {'status':'ok'}
if os.environ.get('SKIP_DB_INIT')!='1':init()
if __name__=='__main__':app.run(debug=os.environ.get('FLASK_DEBUG')=='1',port=int(os.environ.get('PORT',5000)))
