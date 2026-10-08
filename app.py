from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, abort
from werkzeug.utils import secure_filename
from pathlib import Path
from datetime import date, datetime, timedelta
import sqlite3, uuid

BASE = Path(__file__).resolve().parent
UPLOADS = BASE / 'uploads'
UPLOADS.mkdir(exist_ok=True)
DB = BASE / 'damancare.db'
app = Flask(__name__)
app.secret_key = 'local-demo-change-me'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024


def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db


def init_db():
    with connect() as db:
        db.executescript('''CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            category TEXT NOT NULL, brand TEXT NOT NULL DEFAULT '',
            purchased TEXT NOT NULL, expires TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '', invoice TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS repairs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, device_id INTEGER NOT NULL,
            repaired TEXT NOT NULL, description TEXT NOT NULL, cost REAL NOT NULL DEFAULT 0,
            FOREIGN KEY(device_id) REFERENCES devices(id) ON DELETE CASCADE);
        ''')


def get_device(device_id):
    with connect() as db:
        device = db.execute('SELECT * FROM devices WHERE id=?', (device_id,)).fetchone()
    if not device:
        abort(404)
    return device


def save_invoice(file):
    if not file or not file.filename:
        return ''
    suffix = Path(secure_filename(file.filename)).suffix.lower()
    if suffix not in {'.pdf', '.png', '.jpg', '.jpeg', '.webp'}:
        raise ValueError('نوع الفاتورة غير مدعوم. استخدم PDF أو صورة.')
    name = uuid.uuid4().hex + suffix
    file.save(UPLOADS / name)
    return name


@app.route('/')
def index():
    q = request.args.get('q', '').strip()
    with connect() as db:
        if q:
            devices = db.execute('SELECT * FROM devices WHERE name LIKE ? OR brand LIKE ? OR category LIKE ? ORDER BY id DESC', (f'%{q}%',)*3).fetchall()
        else:
            devices = db.execute('SELECT * FROM devices ORDER BY id DESC').fetchall()
        count_repairs = db.execute('SELECT COUNT(*) FROM repairs').fetchone()[0]
    today = date.today()
    records = []
    for d in devices:
        days = (date.fromisoformat(d['expires']) - today).days
        records.append(dict(d) | {'days': days, 'status': 'منتهي' if days < 0 else ('قريب الانتهاء' if days <= 30 else 'ساري')})
    return render_template('index.html', devices=records, q=q, repairs=count_repairs,
                           active=sum(d['days'] >= 0 for d in records), expired=sum(d['days'] < 0 for d in records),
                           soon=sum(0 <= d['days'] <= 30 for d in records))


@app.route('/device/new', methods=['GET', 'POST'])
def add_device():
    if request.method == 'POST':
        try:
            name = request.form['name'].strip()
            if not name:
                raise ValueError('اسم الجهاز مطلوب.')
            purchased = date.fromisoformat(request.form['purchased'])
            expires = date.fromisoformat(request.form['expires'])
            if expires < purchased:
                raise ValueError('تاريخ انتهاء الضمان يجب أن يكون بعد الشراء.')
            invoice = save_invoice(request.files.get('invoice'))
            with connect() as db:
                db.execute('INSERT INTO devices (name,category,brand,purchased,expires,notes,invoice) VALUES (?,?,?,?,?,?,?)',
                           (name, request.form.get('category','أخرى').strip(), request.form.get('brand','').strip(), purchased.isoformat(), expires.isoformat(), request.form.get('notes','').strip(), invoice))
            flash('تمت إضافة الجهاز بنجاح.', 'success')
            return redirect(url_for('index'))
        except (ValueError, KeyError) as e:
            flash(str(e), 'error')
    return render_template('form.html', device=None, today=date.today().isoformat())


@app.route('/device/<int:device_id>')
def detail(device_id):
    device = get_device(device_id)
    with connect() as db:
        repairs = db.execute('SELECT * FROM repairs WHERE device_id=? ORDER BY repaired DESC, id DESC', (device_id,)).fetchall()
    days = (date.fromisoformat(device['expires']) - date.today()).days
    return render_template('detail.html', device=device, repairs=repairs, days=days, total=sum(r['cost'] for r in repairs), today=date.today().isoformat())


@app.route('/device/<int:device_id>/edit', methods=['GET', 'POST'])
def edit_device(device_id):
    device = get_device(device_id)
    if request.method == 'POST':
        try:
            name = request.form['name'].strip()
            if not name:
                raise ValueError('اسم الجهاز مطلوب.')
            purchased = date.fromisoformat(request.form['purchased'])
            expires = date.fromisoformat(request.form['expires'])
            if expires < purchased:
                raise ValueError('تاريخ انتهاء الضمان يجب أن يكون بعد الشراء.')
            invoice = save_invoice(request.files.get('invoice')) or device['invoice']
            with connect() as db:
                db.execute('UPDATE devices SET name=?,category=?,brand=?,purchased=?,expires=?,notes=?,invoice=? WHERE id=?',
                           (name,request.form.get('category','أخرى').strip(),request.form.get('brand','').strip(),purchased.isoformat(),expires.isoformat(),request.form.get('notes','').strip(),invoice,device_id))
            flash('تم تحديث الجهاز.', 'success')
            return redirect(url_for('detail', device_id=device_id))
        except (ValueError, KeyError) as e:
            flash(str(e), 'error')
    return render_template('form.html', device=device, today=date.today().isoformat())


@app.post('/device/<int:device_id>/delete')
def delete_device(device_id):
    device = get_device(device_id)
    with connect() as db:
        db.execute('DELETE FROM devices WHERE id=?', (device_id,))
    if device['invoice']:
        (UPLOADS / device['invoice']).unlink(missing_ok=True)
    flash('تم حذف الجهاز.', 'success')
    return redirect(url_for('index'))


@app.post('/device/<int:device_id>/repair')
def add_repair(device_id):
    get_device(device_id)
    try:
        repaired = date.fromisoformat(request.form['repaired']).isoformat()
        description = request.form['description'].strip()
        cost = float(request.form.get('cost') or 0)
        if not description or cost < 0:
            raise ValueError('أدخل وصف الصيانة وتكلفة صحيحة.')
        with connect() as db:
            db.execute('INSERT INTO repairs (device_id,repaired,description,cost) VALUES (?,?,?,?)', (device_id,repaired,description,cost))
        flash('تم تسجيل الصيانة.', 'success')
    except (ValueError, KeyError) as e:
        flash(str(e), 'error')
    return redirect(url_for('detail', device_id=device_id))


@app.post('/repair/<int:repair_id>/delete')
def delete_repair(repair_id):
    with connect() as db:
        r = db.execute('SELECT device_id FROM repairs WHERE id=?', (repair_id,)).fetchone()
        if not r:
            abort(404)
        db.execute('DELETE FROM repairs WHERE id=?', (repair_id,))
    flash('تم حذف سجل الصيانة.', 'success')
    return redirect(url_for('detail', device_id=r['device_id']))


@app.route('/invoice/<path:filename>')
def invoice(filename):
    if not filename or '/' in filename or '\\' in filename:
        abort(404)
    with connect() as db:
        exists = db.execute('SELECT 1 FROM devices WHERE invoice=?', (filename,)).fetchone()
    if not exists:
        abort(404)
    return send_from_directory(UPLOADS, filename, as_attachment=True)


init_db()
if __name__ == '__main__':
    app.run(debug=True)
