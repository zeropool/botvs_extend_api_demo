#!encoding=utf8

# 配置BotVS平台的AccessKey与SecretKey


import os, time, urllib, md5, json, sqlite3, datetime
from flask import jsonify, request, Flask, render_template, redirect, url_for
from flask_bootstrap import WebCDN, Bootstrap
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField
from wtforms.validators import InputRequired, Email, Length
from flask_sqlalchemy  import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

BOTVS_ACCESS_KEY = os.getenv('BOTVS_ACCESS_KEY', 'xxxxx')
BOTVS_SECRET_KEY = os.getenv('BOTVS_SECRET_KEY', 'yyyyy')


class cached(object):
    def __init__(self, *args, **kwargs):
        self.kv = {}
        self.timeout = kwargs.get("timeout", 0)
    def __call__(self, func):
        def inner(*args, **kwargs):
            if not kwargs.get('cache', False):
                return func(*args, **kwargs)
            k = str(func) + '|' + ','.join(args)
            now = time.time()
            if self.timeout > 0 and (k not in self.kv or (now - self.kv[k]['fetch_time'] > self.timeout)):
                res = func(*args, **kwargs)
                self.kv[k] = {'data': res, 'fetch_time': now}
            return self.kv[k]['data']
        return inner

@cached(timeout=600)
def api(method, *args, **kwargs):
    d = {
        'version': '1.0',
        'access_key': BOTVS_ACCESS_KEY,
        'method': method,
        'args': json.dumps(list(args)),
        'nonce': int(time.time() * 1000),
        }
    d['sign'] = md5.md5('%s|%s|%s|%d|%s' % (d['version'], d['method'], d['args'], d['nonce'], BOTVS_SECRET_KEY)).hexdigest()
    return json.loads(urllib.urlopen('https://www.botvs.com/api/v1', urllib.urlencode(d)).read())


exchanges_list = None
def get_exchange_list():
    global exchanges_list
    if exchanges_list is None:
        # init exchanges
        #exchanges_list = api('GetExchangeList', cache=True)['data']['result']['exchanges']
        exchanges_list = [
            {u'website': u'https://www.binance.com/', u'name': u'\u5e01\u5b89', u'meta': u'[{"desc": "Access Key", "required": true, "type": "string", "name": "AccessKey", "label": "Access Key"}, {"encrypt": true, "name": "SecretKey", "required": true, "label": "Secret Key", "type": "password", "desc": "Secret Key"}]', u'eid': u'Binance', u'logo': u'binance.png', u'stocks': u'LTC_BTC,ETH_BTC,WTC_BTC', u'id': 0},
            {u'website': u'https://www.okex.com/', u'name': u'OKEX', u'meta': u'[{"desc": "Access Key", "required": true, "type": "string", "name": "AccessKey", "label": "Access Key"}, {"encrypt": true, "name": "SecretKey", "required": true, "label": "Secret Key", "type": "password", "desc": "Secret Key"}]', u'eid': u'OKEX', u'logo': u'okex.png', u'stocks': u'LTC_BTC,ETH_BTC,WTC_BTC', u'id': 1},
            {u'website': u'https://www.huobipro.com/', u'name': u'Huobi Pro', u'meta': u'[{"desc": "Access Key", "required": true, "type": "string", "name": "AccessKey", "label": "Access Key"}, {"encrypt": true, "name": "SecretKey", "required": true, "label": "Secret Key", "type": "password", "desc": "Secret Key"}]', u'eid': u'OKEX', u'logo': u'okex.png', u'stocks': u'LTC_BTC,ETH_BTC,WTC_BTC', u'id': 1},
        ]
        print ' * Initialize %d exchanges' % (len(exchanges_list), )
    return exchanges_list

def get_default_stock(eid):
    for e in get_exchange_list():
        if e['eid'] == eid:
            return e['stocks'].split(',')[0]

def plugin_run(exchanges, code, pair=None):
    settings = { "period": 60, "source": code, "exchanges": []}
    for e in exchanges:
        if pair is None:
            piar = get_default_stock(e.eid)
        settings["exchanges"].append({"eid": e.eid, "pair": pair, "meta" :{"AccessKey": e.accessKey, "SecretKey": e.secretKey}})
    return api('PluginRun', settings)

def robot_run(robotId, appId, exchanges):
    strategyId = -1
    # 从策略库里选出一个包含main字符串的策略运行, 也可以预定义
    for ele in api("GetStrategyList")['data']['result']['strategies']:
        if 'main' in ele['name']:
            strategyId = ele['id']
    if strategyId < 0:
        raise u"not found strategy"
    settings = {
            "name":"robot for %s" % (appId, ),
            "args": [], # our custom arguments for this strategey
            "appid": appId, # 为该机器人设置标签,关联到本用户
            "period": 60,
            "strategy": strategyId,
            "exchanges": [],
            }
    for e in exchanges:
        settings["exchanges"].append({"eid": e.eid, "pair": get_default_stock(e.eid), "meta" :{"AccessKey": e.accessKey, "SecretKey": e.secretKey}})
    if robotId > 0:
        return api('RestartRobot', robotId, settings)
    else:
        return api('NewRobot', settings)


app = Flask(__name__)
app.config['SECRET_KEY'] = 'supposedtobeveryimportantsecret!'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'user.sqlite3')
app.config['BOOTSTRAP_SERVE_LOCAL'] = True
bootstrap = Bootstrap(app)


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

db = SQLAlchemy(app)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(15), unique=True)
    email = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(80))
    date = db.Column(db.DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)

class Exchange(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    eid = db.Column(db.String(80))
    label = db.Column(db.String(80))
    accessKey = db.Column(db.Text)
    secretKey = db.Column(db.Text)
    date = db.Column(db.DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)

db.create_all()
db.session.commit()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class LoginForm(FlaskForm):
    username = StringField(u'用户名', validators=[InputRequired(), Length(min=4, max=15)])
    password = PasswordField(u'密码', validators=[InputRequired(), Length(min=8, max=80)])

class RegisterForm(FlaskForm):
    email = StringField(u'邮箱', validators=[InputRequired(), Email(message='无效的Email'), Length(max=50)])
    username = StringField(u'用户名', validators=[InputRequired(), Length(min=4, max=15)])
    password = PasswordField(u'密码', validators=[InputRequired(), Length(min=8, max=80)])

@app.route('/')
def index():
    return render_template('index.html', current_user=current_user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    error = None
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            if user.password == md5.md5(user.email+'__slat__'+form.password.data).hexdigest():
                login_user(user)
                return redirect(url_for('dashboard'))
        error = u'用户名或密码错误'
    return render_template('login.html', current_user=current_user, form=form, error=error)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_password = md5.md5(form.email.data+'__slat__'+form.password.data).hexdigest()
        ele = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(ele)
        db.session.commit()
        login_user(ele)
        return redirect(url_for('dashboard'))

    return render_template('signup.html', current_user=current_user, form=form)

@app.route('/dashboard')
@login_required
def dashboard():
    appId = "appId_%d" % (current_user.id, )
    # 通过标签或者对应的该用户所有的运行的机器人
    robots = api('GetRobotList', appId)['data']['result']['robots']
    robotId = -1
    profit = .0
    if len(robots) > 0:
        robotId = robots[0]['id']
    isRunning = False
    for ele in robots:
        profit = ele['profit']
        if ele['status'] < 3:
            isRunning = True
            break
    if request.method == "GET":
        result = None
        action = request.args.get('action', None)
        if action:
            if action == "refresh":
                # 刷新收益
                return jsonify({'profit':profit, 'running': isRunning})
            elif action == "run":
                # 运行策略
                result = robot_run(robotId, appId, Exchange.query.filter_by(user_id=current_user.id).all())
            elif action == "stop":
                # 停止策略(停止该用户所有的策略)
                for ele in robots:
                    result = api('StopRobot', ele['id'])
                if not result:
                    result = {'code': 0}
            return jsonify(result)

    platforms = Exchange.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', current_user=current_user, platforms=platforms, running=isRunning, profit=profit)

@app.route('/exchanges', methods=['GET', 'POST'])
@login_required
def exchanges():
    error = None
    if request.method == 'POST':
        eid = request.form.get('eid', None)
        label = request.form.get('label', None)
        accessKey = request.form.get('accessKey', None)
        secretKey = request.form.get('secretKey', None)
        if eid and label and accessKey and secretKey:
            ele = Exchange(user_id=current_user.id, eid=eid, label=label, accessKey=accessKey, secretKey=secretKey)
            db.session.add(ele)
            db.session.commit()
            return redirect(url_for('assets'))
        error = u"表格填写不完整"
    return render_template('dashboard.html', current_user=current_user, exchanges=get_exchange_list(), error=error)

@app.route('/assets', methods=['GET', 'POST'])
@login_required
def assets():
    if request.method == "GET":
        action = request.args.get('action', None)
        if action == "del":
            db.session.delete(Exchange.query.filter_by(user_id=current_user.id, id=request.args.get('pid', -1)).first())
            db.session.commit()
            return jsonify(results=True)
    platforms = Exchange.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', current_user=current_user, platforms=platforms)

@app.route('/hub', methods=['GET', 'POST'])
@login_required
def hub():
    if request.method == "GET":
        action = request.args.get('action', None)
        symbol = request.args.get('symbol', None)
        if action is not None:
            action = action.lower().strip()
        if symbol is not None:
            symbol = symbol.split('.')[1]
        if action == "buy" or action == "sell":
            args = json.loads(request.args.get('args'))
            r = plugin_run([Exchange.query.filter_by(user_id=current_user.id, id=request.args.get('pid', -1)).first()], '''
        function main() {
            exchange.SetTimeout(2000);
            var pfn = '%s' == 'buy' ? exchange.Buy : exchange.Sell;
            return pfn(%f, %f);
        }
            ''' % (action, args[0], args[1]), symbol)
            return jsonify(r)
        elif action == "cancel":
            args = json.loads(request.args.get('args'))
            r = plugin_run([Exchange.query.filter_by(user_id=current_user.id, id=request.args.get('pid', -1)).first()], '''
        function main() {
            exchange.SetTimeout(2000);
            return exchange.CancelOrder(%s)
        }
            ''' % (args[0]), symbol)
            return jsonify(r)
        elif action == "balance":
            # 运行查询脚本(也可以定制实现任何想要的功能, 比如资产统计,一键平仓)
            r = plugin_run([Exchange.query.filter_by(user_id=current_user.id, id=request.args.get('pid', -1)).first()], '''
        function main() {
            exchange.SetTimeout(2000);
            return [exchange.GetOrders(), exchange.GetAccount()];
        }
            ''', symbol)
            return jsonify(r)
    platforms = Exchange.query.filter_by(user_id=current_user.id).all()
    arr = []
    for ele in platforms:
        arr.append({'id': ele.id, 'eid': ele.eid, 'label': ele.label})
    return render_template('dashboard.html', current_user=current_user, platforms=json.dumps(arr))
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
