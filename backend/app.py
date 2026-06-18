import sqlite3
import json
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, g
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DATABASE = 'pharmacy.db'
DEFAULT_OPERATOR = '管理员'


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
            INSERT INTO stock_in (medicine_id, quantity, unit_price, operator, remark, operation_time)
            VALUES (1, 50, 12.0, '系统初始化', '初始库存', '2026-06-01 09:00:00'),
                   (2, 30, 18.0, '系统初始化', '初始库存', '2026-06-01 09:00:00'),
                   (3, 100, 8.0, '系统初始化', '初始库存', '2026-06-01 09:00:00')
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
        query += ' AND m.name LIKE ?'
        params.append(f'%{keyword}%')

    query += ' ORDER BY si.operation_time DESC LIMIT ? OFFSET ?'
    params.extend([per_page, (page - 1) * per_page])

    cursor = db.execute(query, params)
    rows = cursor.fetchall()
    result = [dict(row) for row in rows]

    count_query = 'SELECT COUNT(*) as total FROM stock_in si LEFT JOIN medicines m ON si.medicine_id = m.id WHERE 1=1'
    count_params = []
    if keyword:
        count_query += ' AND m.name LIKE ?'
        count_params.append(f'%{keyword}%')
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

    if not medicine_id or quantity <= 0:
        return jsonify({'error': '药品和数量不能为空'}), 400

    db = get_db()

    medicine = db.execute('SELECT * FROM medicines WHERE id=?', (medicine_id,)).fetchone()
    if not medicine:
        return jsonify({'error': '药品不存在'}), 404

    db.execute('''
        INSERT INTO stock_in (medicine_id, quantity, unit_price, operator, remark)
        VALUES (?, ?, ?, ?, ?)
    ''', (medicine_id, quantity, unit_price, operator, remark))

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
        date = datetime.now().strftime('%Y-%m-%d')

    if period == 'day':
        date_filter = "DATE(operation_time) = ?"
        date_param = date
    elif period == 'week':
        date_filter = "strftime('%Y-%W', operation_time) = ?"
        date_param = date
    elif period == 'month':
        date_filter = "strftime('%Y-%m', operation_time) = ?"
        date_param = date
    else:
        period = 'day'
        date_filter = "DATE(operation_time) = ?"
        date_param = date

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
    return jsonify({
        'medicine_count': row['medicine_count'] or 0,
        'total_stock': row['total_stock'] or 0,
        'total_value': round(row['total_value'] or 0, 2),
        'low_stock_count': row['low_stock_count'] or 0
    })


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
