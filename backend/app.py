import sqlite3
import json
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, g
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DATABASE = 'pharmacy.db'
DEFAULT_OPERATOR = '管理员'

EXPIRY_CRITICAL_DAYS = 30
EXPIRY_WARNING_DAYS = 90

WARNING_LEVEL_EXPIRED = 'expired'
WARNING_LEVEL_CRITICAL = 'critical'
WARNING_LEVEL_WARNING = 'warning'
WARNING_LEVEL_NORMAL = 'normal'
WARNING_LEVEL_UNKNOWN = 'unknown'

WARNING_LABELS = {
    WARNING_LEVEL_EXPIRED: '已过期',
    WARNING_LEVEL_CRITICAL: '临期(1个月内)',
    WARNING_LEVEL_WARNING: '近效期(3个月内)',
    WARNING_LEVEL_NORMAL: '正常',
    WARNING_LEVEL_UNKNOWN: '未知',
}


def get_today():
    today = datetime.now()
    today_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
    return today_date, today.strftime('%Y-%m-%d')


def get_expiry_thresholds(today_dt=None):
    if today_dt is None:
        today_dt, _ = get_today()
    return {
        'today_str': today_dt.strftime('%Y-%m-%d'),
        'critical_date': (today_dt + timedelta(days=EXPIRY_CRITICAL_DAYS)).strftime('%Y-%m-%d'),
        'warning_date': (today_dt + timedelta(days=EXPIRY_WARNING_DAYS)).strftime('%Y-%m-%d'),
    }


def calc_expiry_info(expiry_date_str, today_dt=None):
    if not expiry_date_str:
        return {
            'days_remaining': None,
            'warning_level': WARNING_LEVEL_UNKNOWN,
            'warning_label': WARNING_LABELS[WARNING_LEVEL_UNKNOWN],
        }
    if today_dt is None:
        today_dt, _ = get_today()
    try:
        expiry_dt = datetime.strptime(expiry_date_str, '%Y-%m-%d')
        days_remaining = (expiry_dt - today_dt).days
    except (ValueError, TypeError):
        return {
            'days_remaining': None,
            'warning_level': WARNING_LEVEL_UNKNOWN,
            'warning_label': WARNING_LABELS[WARNING_LEVEL_UNKNOWN],
        }
    if days_remaining <= 0:
        level = WARNING_LEVEL_EXPIRED
    elif days_remaining <= EXPIRY_CRITICAL_DAYS:
        level = WARNING_LEVEL_CRITICAL
    elif days_remaining <= EXPIRY_WARNING_DAYS:
        level = WARNING_LEVEL_WARNING
    else:
        level = WARNING_LEVEL_NORMAL
    return {
        'days_remaining': days_remaining,
        'warning_level': level,
        'warning_label': WARNING_LABELS[level],
    }


def build_sales_date_filter(period, date_str):
    if period == 'day':
        return "DATE(operation_time) = ?", date_str
    elif period == 'week':
        return "strftime('%Y-%W', operation_time) = ?", date_str
    elif period == 'month':
        return "strftime('%Y-%m', operation_time) = ?", date_str
    return "DATE(operation_time) = ?", date_str


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            specification TEXT,
            manufacturer TEXT,
            unit TEXT DEFAULT '盒',
            price REAL NOT NULL DEFAULT 0,
            stock INTEGER NOT NULL DEFAULT 0,
            threshold INTEGER NOT NULL DEFAULT 10,
            category TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_in (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL DEFAULT 0,
            operator TEXT NOT NULL,
            operation_time TEXT DEFAULT (datetime('now', 'localtime')),
            remark TEXT,
            batch_no TEXT,
            expiry_date TEXT,
            FOREIGN KEY (medicine_id) REFERENCES medicines (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_id INTEGER NOT NULL,
            batch_no TEXT NOT NULL,
            expiry_date TEXT,
            quantity INTEGER NOT NULL DEFAULT 0,
            initial_quantity INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (medicine_id) REFERENCES medicines (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_no TEXT NOT NULL UNIQUE,
            medicine_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            total_price REAL NOT NULL,
            operator TEXT NOT NULL,
            operation_time TEXT DEFAULT (datetime('now', 'localtime')),
            customer TEXT,
            remark TEXT,
            FOREIGN KEY (medicine_id) REFERENCES medicines (id)
        )
    ''')

    cursor.execute('SELECT COUNT(*) as count FROM medicines')
    count = cursor.fetchone()[0]
    if count == 0:
        sample_medicines = [
            ('阿莫西林胶囊', '0.25g*24粒', '华北制药', '盒', 15.50, 50, 10, '抗生素'),
            ('布洛芬缓释胶囊', '0.3g*20粒', '中美史克', '盒', 22.80, 30, 8, '解热镇痛'),
            ('感冒灵颗粒', '10g*9袋', '三九医药', '盒', 12.00, 100, 20, '感冒用药'),
            ('维生素C片', '100mg*100片', '东北制药', '瓶', 5.50, 5, 15, '维生素'),
            ('奥美拉唑肠溶胶囊', '20mg*14粒', '阿斯利康', '盒', 45.00, 8, 5, '消化系统'),
            ('硝苯地平缓释片', '10mg*30片', '拜耳医药', '盒', 32.00, 12, 10, '心血管'),
            ('二甲双胍片', '0.5g*20片', '正大天晴', '盒', 18.50, 6, 10, '糖尿病'),
            ('氯雷他定片', '10mg*6片', '扬子江药业', '盒', 28.00, 25, 8, '抗过敏'),
            ('蒙脱石散', '3g*10袋', '博福-益普生', '盒', 20.00, 3, 10, '消化系统'),
            ('左氧氟沙星片', '0.5g*5片', '扬子江药业', '盒', 38.00, 15, 5, '抗生素'),
        ]
        for med in sample_medicines:
            cursor.execute(
                'INSERT INTO medicines (name, specification, manufacturer, unit, price, stock, threshold, category) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                med
            )

        cursor.execute('''
            INSERT INTO stock_in (medicine_id, quantity, unit_price, operator, remark, operation_time, batch_no, expiry_date)
            VALUES (1, 50, 12.0, '系统初始化', '初始库存', '2026-06-01 09:00:00', 'AMX20250601', '2027-06-30'),
                   (2, 30, 18.0, '系统初始化', '初始库存', '2026-06-01 09:00:00', 'BLF20251215', '2026-08-20'),
                   (3, 100, 8.0, '系统初始化', '初始库存', '2026-06-01 09:00:00', 'GML20260101', '2026-07-15'),
                   (4, 20, 3.5, '系统初始化', '初始库存', '2026-05-15 09:00:00', 'VIT20240820', '2026-07-20'),
                   (5, 15, 38.0, '系统初始化', '初始库存', '2026-04-20 09:00:00', 'OME20250910', '2026-12-31'),
                   (6, 20, 28.0, '系统初始化', '初始库存', '2026-03-10 09:00:00', 'XBD20250301', '2026-09-15'),
                   (7, 10, 15.0, '系统初始化', '初始库存', '2026-02-20 09:00:00', 'EJS20250520', '2026-07-05'),
                   (8, 30, 22.0, '系统初始化', '初始库存', '2026-01-15 09:00:00', 'LLT20251101', '2027-01-20'),
                   (9, 5, 16.0, '系统初始化', '初始库存', '2026-05-25 09:00:00', 'MTS20250610', '2026-06-25'),
                   (10, 20, 32.0, '系统初始化', '初始库存', '2026-06-10 09:00:00', 'ZYF20260201', '2028-02-28')
        ''')

        cursor.execute('''
            INSERT INTO inventory_batches (medicine_id, batch_no, expiry_date, quantity, initial_quantity, created_at)
            VALUES (1, 'AMX20250601', '2027-06-30', 44, 50, '2026-06-01 09:00:00'),
                   (2, 'BLF20251215', '2026-08-20', 27, 30, '2026-06-01 09:00:00'),
                   (3, 'GML20260101', '2026-07-15', 91, 100, '2026-06-01 09:00:00'),
                   (4, 'VIT20240820', '2026-07-20', 17, 20, '2026-05-15 09:00:00'),
                   (5, 'OME20250910', '2026-12-31', 14, 15, '2026-04-20 09:00:00'),
                   (6, 'XBD20250301', '2026-09-15', 18, 20, '2026-03-10 09:00:00'),
                   (7, 'EJS20250520', '2026-07-05', 8, 10, '2026-02-20 09:00:00'),
                   (8, 'LLT20251101', '2027-01-20', 27, 30, '2026-01-15 09:00:00'),
                   (9, 'MTS20250610', '2026-06-25', 3, 5, '2026-05-25 09:00:00'),
                   (10, 'ZYF20260201', '2028-02-28', 19, 20, '2026-06-10 09:00:00')
        ''')

        cursor.execute('''
            INSERT INTO sales (order_no, medicine_id, quantity, unit_price, total_price, operator, customer, remark, operation_time)
            VALUES ('X20260610001', 1, 2, 15.50, 31.00, '张药师', '王女士', '感冒用药', '2026-06-10 09:30:00'),
                   ('X20260610002', 3, 3, 12.00, 36.00, '李药师', '刘先生', '', '2026-06-10 14:20:00'),
                   ('X20260612001', 2, 1, 22.80, 22.80, '张药师', '陈先生', '头痛', '2026-06-12 10:15:00'),
                   ('X20260612002', 8, 2, 28.00, 56.00, '李药师', '赵女士', '过敏', '2026-06-12 16:45:00'),
                   ('X20260612003', 5, 1, 45.00, 45.00, '张药师', '孙先生', '胃病', '2026-06-12 11:30:00'),
                   ('X20260615001', 1, 3, 15.50, 46.50, '张药师', '周女士', '', '2026-06-15 08:50:00'),
                   ('X20260615002', 6, 2, 32.00, 64.00, '李药师', '吴先生', '高血压', '2026-06-15 15:10:00'),
                   ('X20260615003', 9, 2, 20.00, 40.00, '张药师', '郑女士', '腹泻', '2026-06-15 10:30:00'),
                   ('X20260616001', 3, 5, 12.00, 60.00, '李药师', '冯先生', '感冒', '2026-06-16 09:00:00'),
                   ('X20260616002', 10, 1, 38.00, 38.00, '张药师', '陈女士', '消炎药', '2026-06-16 14:00:00'),
                   ('X20260617001', 7, 2, 18.50, 37.00, '李药师', '褚先生', '糖尿病', '2026-06-17 11:20:00'),
                   ('X20260617002', 4, 3, 5.50, 16.50, '张药师', '卫女士', '', '2026-06-17 16:30:00'),
                   ('X20260618001', 2, 2, 22.80, 45.60, '李药师', '蒋先生', '发热', '2026-06-18 08:40:00'),
                   ('X20260618002', 8, 1, 28.00, 28.00, '张药师', '沈女士', '鼻炎', '2026-06-18 10:15:00'),
                   ('X20260618003', 1, 1, 15.50, 15.50, '李药师', '韩先生', '', '2026-06-18 15:30:00')
        ''')

    conn.commit()
    conn.close()


# ========== 药品模块 ==========

@app.route('/api/medicines', methods=['GET'])
def get_medicines():
    db = get_db()
    keyword = request.args.get('keyword', '')
    category = request.args.get('category', '')
    low_stock = request.args.get('low_stock', 'false')

    query = 'SELECT * FROM medicines WHERE 1=1'
    params = []

    if keyword:
        query += ' AND (name LIKE ? OR manufacturer LIKE ? OR specification LIKE ?)'
        params.extend([f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'])
    if category:
        query += ' AND category = ?'
        params.append(category)
    if low_stock == 'true':
        query += ' AND stock <= threshold'

    query += ' ORDER BY updated_at DESC'

    cursor = db.execute(query, params)
    rows = cursor.fetchall()
    result = [dict(row) for row in rows]
    return jsonify(result)


@app.route('/api/medicines/<int:med_id>', methods=['GET'])
def get_medicine(med_id):
    db = get_db()
    cursor = db.execute('SELECT * FROM medicines WHERE id = ?', (med_id,))
    row = cursor.fetchone()
    if row is None:
        return jsonify({'error': '药品不存在'}), 404
    return jsonify(dict(row))


@app.route('/api/medicines', methods=['POST'])
def create_medicine():
    data = request.json
    db = get_db()
    cursor = db.execute('''
        INSERT INTO medicines (name, specification, manufacturer, unit, price, stock, threshold, category)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data.get('name', ''),
        data.get('specification', ''),
        data.get('manufacturer', ''),
        data.get('unit', '盒'),
        data.get('price', 0),
        data.get('stock', 0),
        data.get('threshold', 10),
        data.get('category', '')
    ))
    db.commit()
    return jsonify({'id': cursor.lastrowid, 'message': '创建成功'}), 201


@app.route('/api/medicines/<int:med_id>', methods=['PUT'])
def update_medicine(med_id):
    data = request.json
    db = get_db()
    db.execute('''
        UPDATE medicines SET name=?, specification=?, manufacturer=?, unit=?, price=?, threshold=?, category=?, updated_at=datetime('now', 'localtime')
        WHERE id=?
    ''', (
        data.get('name', ''),
        data.get('specification', ''),
        data.get('manufacturer', ''),
        data.get('unit', '盒'),
        data.get('price', 0),
        data.get('threshold', 10),
        data.get('category', ''),
        med_id
    ))
    db.commit()
    return jsonify({'message': '更新成功'})


@app.route('/api/medicines/<int:med_id>', methods=['DELETE'])
def delete_medicine(med_id):
    db = get_db()
    db.execute('DELETE FROM medicines WHERE id=?', (med_id,))
    db.commit()
    return jsonify({'message': '删除成功'})


@app.route('/api/medicines/categories', methods=['GET'])
def get_categories():
    db = get_db()
    cursor = db.execute('SELECT DISTINCT category FROM medicines WHERE category IS NOT NULL AND category != "" ORDER BY category')
    rows = cursor.fetchall()
    result = [row['category'] for row in rows]
    return jsonify(result)


@app.route('/api/medicines/low-stock', methods=['GET'])
def get_low_stock():
    db = get_db()
    cursor = db.execute('''
        SELECT m.*, 
               CASE WHEN stock <= threshold THEN 1 ELSE 0 END as is_low
        FROM medicines m
        WHERE stock <= threshold
        ORDER BY stock ASC
    ''')
    rows = cursor.fetchall()
    result = [dict(row) for row in rows]
    return jsonify(result)


# ========== 入库模块 ==========

@app.route('/api/stock-in', methods=['GET'])
def get_stock_in():
    db = get_db()
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    keyword = request.args.get('keyword', '')

    query = '''
        SELECT si.*, m.name as medicine_name, m.specification, m.unit
        FROM stock_in si
        LEFT JOIN medicines m ON si.medicine_id = m.id
        WHERE 1=1
    '''
    params = []

    if keyword:
        query += ' AND (m.name LIKE ? OR si.batch_no LIKE ?)'
        params.extend([f'%{keyword}%', f'%{keyword}%'])

    query += ' ORDER BY si.operation_time DESC LIMIT ? OFFSET ?'
    params.extend([per_page, (page - 1) * per_page])

    cursor = db.execute(query, params)
    rows = cursor.fetchall()
    result = [dict(row) for row in rows]

    count_query = 'SELECT COUNT(*) as total FROM stock_in si LEFT JOIN medicines m ON si.medicine_id = m.id WHERE 1=1'
    count_params = []
    if keyword:
        count_query += ' AND (m.name LIKE ? OR si.batch_no LIKE ?)'
        count_params.extend([f'%{keyword}%', f'%{keyword}%'])
    total = db.execute(count_query, count_params).fetchone()['total']

    return jsonify({'list': result, 'total': total, 'page': page, 'per_page': per_page})


@app.route('/api/stock-in', methods=['POST'])
def create_stock_in():
    data = request.json
    medicine_id = data.get('medicine_id')
    quantity = data.get('quantity', 0)
    unit_price = data.get('unit_price', 0)
    operator = data.get('operator', DEFAULT_OPERATOR)
    remark = data.get('remark', '')
    batch_no = data.get('batch_no', '')
    expiry_date = data.get('expiry_date', '')

    if not medicine_id or quantity <= 0:
        return jsonify({'error': '药品和数量不能为空'}), 400

    db = get_db()

    medicine = db.execute('SELECT * FROM medicines WHERE id=?', (medicine_id,)).fetchone()
    if not medicine:
        return jsonify({'error': '药品不存在'}), 404

    if expiry_date:
        expiry_info = calc_expiry_info(expiry_date)
        if expiry_info['warning_level'] == WARNING_LEVEL_EXPIRED:
            return jsonify({'error': f'该批次有效期已过期，无法入库'}), 400

    db.execute('''
        INSERT INTO stock_in (medicine_id, quantity, unit_price, operator, remark, batch_no, expiry_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (medicine_id, quantity, unit_price, operator, remark, batch_no, expiry_date))

    if batch_no:
        existing_batch = db.execute(
            'SELECT * FROM inventory_batches WHERE medicine_id=? AND batch_no=?',
            (medicine_id, batch_no)
        ).fetchone()
        if existing_batch:
            db.execute('''
                UPDATE inventory_batches 
                SET quantity = quantity + ?, initial_quantity = initial_quantity + ?
                WHERE id = ?
            ''', (quantity, quantity, existing_batch['id']))
        else:
            db.execute('''
                INSERT INTO inventory_batches (medicine_id, batch_no, expiry_date, quantity, initial_quantity)
                VALUES (?, ?, ?, ?, ?)
            ''', (medicine_id, batch_no, expiry_date, quantity, quantity))

    db.execute('''
        UPDATE medicines 
        SET stock = stock + ?, updated_at = datetime('now', 'localtime')
        WHERE id = ?
    ''', (quantity, medicine_id))

    db.commit()
    return jsonify({'message': '入库成功'}), 201


# ========== 销售模块 ==========

@app.route('/api/sales', methods=['GET'])
def get_sales():
    db = get_db()
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    keyword = request.args.get('keyword', '')
    date = request.args.get('date', '')
    period = request.args.get('period', '')

    query = '''
        SELECT s.*, m.name as medicine_name, m.specification, m.unit
        FROM sales s
        LEFT JOIN medicines m ON s.medicine_id = m.id
        WHERE 1=1
    '''
    params = []

    if keyword:
        query += ' AND (m.name LIKE ? OR s.order_no LIKE ?)'
        params.extend([f'%{keyword}%', f'%{keyword}%'])

    if date and period:
        if period == 'day':
            query += ' AND DATE(s.operation_time) = ?'
            params.append(date)
        elif period == 'week':
            query += " AND strftime('%Y-%W', s.operation_time) = ?"
            params.append(date)
        elif period == 'month':
            query += " AND strftime('%Y-%m', s.operation_time) = ?"
            params.append(date)

    query += ' ORDER BY s.operation_time DESC LIMIT ? OFFSET ?'
    params.extend([per_page, (page - 1) * per_page])

    cursor = db.execute(query, params)
    rows = cursor.fetchall()
    result = [dict(row) for row in rows]

    count_query = '''
        SELECT COUNT(*) as total 
        FROM sales s 
        LEFT JOIN medicines m ON s.medicine_id = m.id 
        WHERE 1=1
    '''
    count_params = []
    if keyword:
        count_query += ' AND (m.name LIKE ? OR s.order_no LIKE ?)'
        count_params.extend([f'%{keyword}%', f'%{keyword}%'])
    if date and period:
        if period == 'day':
            count_query += ' AND DATE(s.operation_time) = ?'
            count_params.append(date)
        elif period == 'week':
            count_query += " AND strftime('%Y-%W', s.operation_time) = ?"
            count_params.append(date)
        elif period == 'month':
            count_query += " AND strftime('%Y-%m', s.operation_time) = ?"
            count_params.append(date)
    total = db.execute(count_query, count_params).fetchone()['total']

    return jsonify({'list': result, 'total': total, 'page': page, 'per_page': per_page})


@app.route('/api/sales', methods=['POST'])
def create_sale():
    data = request.json
    items = data.get('items', [])
    operator = data.get('operator', DEFAULT_OPERATOR)
    customer = data.get('customer', '')
    remark = data.get('remark', '')

    if not items:
        return jsonify({'error': '销售明细不能为空'}), 400

    db = get_db()

    try:
        order_date = datetime.now().strftime('%Y%m%d')
        cursor = db.execute("SELECT COUNT(*) FROM sales WHERE order_no LIKE ?", (f'X{order_date}%',))
        order_count = cursor.fetchone()[0] + 1
        order_no = f'X{order_date}{order_count:03d}'

        total_amount = 0
        today_dt, today_str = get_today()

        for item in items:
            medicine_id = item.get('medicine_id')
            quantity = item.get('quantity', 0)
            unit_price = item.get('unit_price', 0)

            if not medicine_id or quantity <= 0:
                continue

            medicine = db.execute('SELECT * FROM medicines WHERE id=?', (medicine_id,)).fetchone()
            if not medicine:
                raise ValueError(f'药品ID {medicine_id} 不存在')

            if medicine['stock'] < quantity:
                raise ValueError(f"药品 {medicine['name']} 库存不足，当前库存: {medicine['stock']}")

            batch_count = db.execute(
                'SELECT COUNT(*) as cnt FROM inventory_batches WHERE medicine_id = ? AND quantity > 0',
                (medicine_id,)
            ).fetchone()['cnt']

            if batch_count > 0:
                valid_qty_row = db.execute('''
                    SELECT SUM(quantity) as valid_qty
                    FROM inventory_batches
                    WHERE medicine_id = ? 
                      AND quantity > 0
                      AND expiry_date IS NOT NULL
                      AND expiry_date >= ?
                ''', (medicine_id, today_str)).fetchone()
                valid_qty = valid_qty_row['valid_qty'] or 0
                if valid_qty < quantity:
                    if valid_qty == 0:
                        raise ValueError(f"药品 {medicine['name']} 已全部过期，无法销售")
                    else:
                        raise ValueError(f"药品 {medicine['name']} 有效库存不足，有效库存: {valid_qty} {medicine['unit']}")

            total_price = unit_price * quantity
            total_amount += total_price

            db.execute('''
                INSERT INTO sales (order_no, medicine_id, quantity, unit_price, total_price, operator, customer, remark)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (order_no, medicine_id, quantity, unit_price, total_price, operator, customer, remark))

            db.execute('''
                UPDATE medicines 
                SET stock = stock - ?, updated_at = datetime('now', 'localtime')
                WHERE id = ?
            ''', (quantity, medicine_id))

        db.commit()
        return jsonify({'order_no': order_no, 'total_amount': total_amount, 'message': '销售开单成功'}), 201

    except ValueError as e:
        db.rollback()
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500


# ========== 统计模块 ==========

@app.route('/api/statistics/sales-summary', methods=['GET'])
def get_sales_summary():
    db = get_db()
    period = request.args.get('period', 'day')
    date = request.args.get('date', '')

    if not date:
        _, date = get_today()

    date_filter, date_param = build_sales_date_filter(period, date)

    summary = db.execute(f'''
        SELECT 
            COUNT(*) as order_count,
            COUNT(DISTINCT order_no) as order_num,
            SUM(quantity) as total_quantity,
            SUM(total_price) as total_amount
        FROM sales
        WHERE {date_filter}
    ''', (date_param,)).fetchone()

    top_medicines = db.execute(f'''
        SELECT 
            m.id,
            m.name,
            m.specification,
            SUM(s.quantity) as total_quantity,
            SUM(s.total_price) as total_amount
        FROM sales s
        LEFT JOIN medicines m ON s.medicine_id = m.id
        WHERE {date_filter}
        GROUP BY s.medicine_id
        ORDER BY total_amount DESC
        LIMIT 10
    ''', (date_param,)).fetchall()
    top_medicines = [dict(row) for row in top_medicines]

    daily_sales = []
    if period == 'month':
        year, month = date.split('-')
        daily_sales = db.execute('''
            SELECT 
                strftime('%Y-%m-%d', operation_time) as date,
                COUNT(DISTINCT order_no) as order_num,
                SUM(quantity) as total_quantity,
                SUM(total_price) as total_amount
            FROM sales
            WHERE strftime('%Y-%m', operation_time) = ?
            GROUP BY strftime('%Y-%m-%d', operation_time)
            ORDER BY date
        ''', (f'{year}-{month}',)).fetchall()
        daily_sales = [dict(row) for row in daily_sales]

    if period == 'week':
        year, week = date.split('-')
        daily_sales = db.execute('''
            SELECT 
                strftime('%Y-%m-%d', operation_time) as date,
                COUNT(DISTINCT order_no) as order_num,
                SUM(quantity) as total_quantity,
                SUM(total_price) as total_amount
            FROM sales
            WHERE strftime('%Y-%W', operation_time) = ?
            GROUP BY strftime('%Y-%m-%d', operation_time)
            ORDER BY date
        ''', (date,)).fetchall()
        daily_sales = [dict(row) for row in daily_sales]

    result = {
        'period': period,
        'date': date,
        'order_count': summary['order_count'] or 0,
        'order_num': summary['order_num'] or 0,
        'total_quantity': summary['total_quantity'] or 0,
        'total_amount': round(summary['total_amount'] or 0, 2),
        'top_medicines': top_medicines,
        'daily_sales': daily_sales
    }

    return jsonify(result)


@app.route('/api/statistics/inventory-value', methods=['GET'])
def get_inventory_value():
    db = get_db()
    cursor = db.execute('''
        SELECT 
            COUNT(*) as medicine_count,
            SUM(stock) as total_stock,
            SUM(stock * price) as total_value,
            SUM(CASE WHEN stock <= threshold THEN 1 ELSE 0 END) as low_stock_count
        FROM medicines
    ''')
    row = cursor.fetchone()

    thresholds = get_expiry_thresholds()
    today_str = thresholds['today_str']
    one_month = thresholds['critical_date']
    three_months = thresholds['warning_date']

    expiry_cursor = db.execute('''
        SELECT 
            SUM(CASE WHEN expiry_date < ? AND quantity > 0 THEN 1 ELSE 0 END) as expired_count,
            SUM(CASE WHEN expiry_date < ? AND quantity > 0 THEN quantity ELSE 0 END) as expired_qty,
            SUM(CASE WHEN expiry_date >= ? AND expiry_date <= ? AND quantity > 0 THEN 1 ELSE 0 END) as expiry_1month,
            SUM(CASE WHEN expiry_date > ? AND expiry_date <= ? AND quantity > 0 THEN 1 ELSE 0 END) as expiry_3month_only,
            SUM(CASE WHEN expiry_date >= ? AND expiry_date <= ? AND quantity > 0 THEN quantity ELSE 0 END) as expiry_1month_qty,
            SUM(CASE WHEN expiry_date > ? AND expiry_date <= ? AND quantity > 0 THEN quantity ELSE 0 END) as expiry_3month_only_qty
        FROM inventory_batches
    ''', (today_str, today_str,
          today_str, one_month,
          one_month, three_months,
          today_str, one_month,
          one_month, three_months))
    expiry_row = expiry_cursor.fetchone()

    expired_qty = expiry_row['expired_qty'] or 0
    expiry_1month_count = expiry_row['expiry_1month'] or 0
    expiry_3month_only_count = expiry_row['expiry_3month_only'] or 0
    expiry_3month_count = expiry_1month_count + expiry_3month_only_count
    expiry_1month_qty = expiry_row['expiry_1month_qty'] or 0
    expiry_3month_qty = expiry_1month_qty + (expiry_row['expiry_3month_only_qty'] or 0)
    expired_value = 0
    if expired_qty > 0:
        expired_value_row = db.execute('''
            SELECT SUM(ib.quantity * m.price) as expired_value
            FROM inventory_batches ib
            LEFT JOIN medicines m ON ib.medicine_id = m.id
            WHERE ib.expiry_date < ? AND ib.quantity > 0
        ''', (today_str,)).fetchone()
        expired_value = expired_value_row['expired_value'] or 0

    return jsonify({
        'medicine_count': row['medicine_count'] or 0,
        'total_stock': row['total_stock'] or 0,
        'total_value': round(row['total_value'] or 0, 2),
        'low_stock_count': row['low_stock_count'] or 0,
        'expired_count': expiry_row['expired_count'] or 0,
        'expired_qty': expired_qty,
        'expired_value': round(expired_value, 2),
        'expiry_1month_count': expiry_1month_count,
        'expiry_1month_qty': expiry_1month_qty,
        'expiry_3month_count': expiry_3month_count,
        'expiry_3month_qty': expiry_3month_qty
    })


@app.route('/api/medicines/expiry-warning', methods=['GET'])
def get_expiry_warning():
    db = get_db()
    days = int(request.args.get('days', 90))

    today_dt, today_str = get_today()
    limit_date = (today_dt + timedelta(days=days)).strftime('%Y-%m-%d')

    cursor = db.execute('''
        SELECT 
            ib.id,
            ib.medicine_id,
            ib.batch_no,
            ib.expiry_date,
            ib.quantity,
            ib.initial_quantity,
            m.name as medicine_name,
            m.specification,
            m.unit,
            m.price,
            m.category
        FROM inventory_batches ib
        LEFT JOIN medicines m ON ib.medicine_id = m.id
        WHERE ib.expiry_date IS NOT NULL 
          AND ib.expiry_date <= ? 
          AND ib.quantity > 0
        ORDER BY ib.expiry_date ASC
    ''', (limit_date,))

    rows = cursor.fetchall()
    result = []
    for row in rows:
        row_dict = dict(row)
        expiry_info = calc_expiry_info(row_dict.get('expiry_date'), today_dt)
        row_dict.update(expiry_info)
        result.append(row_dict)

    return jsonify(result)


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
