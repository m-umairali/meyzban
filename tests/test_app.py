import os, tempfile, unittest

class TestMeyzban(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory()
  os.environ['DATABASE_PATH']=self.temp.name+'/test.db'
  os.environ['SKIP_DB_INIT']='1'
  os.environ['MEYZBAN_ENV']='development'
  os.environ['SEED_DEMO']='0'
  import app
  self.app=app
  app.DB=os.environ['DATABASE_PATH']
  app.init()
  self.client=app.app.test_client()
 def tearDown(self):self.temp.cleanup()
 def test_health_and_security(self):
  r=self.client.get('/health')
  self.assertEqual(r.status_code,200)
  self.assertEqual(r.headers['X-Frame-Options'],'DENY')
  self.assertEqual(self.client.get('/readiness').status_code,200)
 def test_no_seed_user(self):
  with self.app.conn() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM users').fetchone()[0],0)
 def test_csrf_required(self):
  r=self.client.post('/register',data={'email':'x@y.com'})
  self.assertEqual(r.status_code,400)

if __name__=='__main__':unittest.main()
