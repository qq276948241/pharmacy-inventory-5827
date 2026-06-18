const { createApp, ref, reactive, computed, onMounted, watch } = Vue;
const { createRouter, createWebHashHistory } = VueRouter;

const API_BASE = 'http://localhost:5000/api';

async function apiGet(url, params = {}) {
    const query = new URLSearchParams(params).toString();
    const fullUrl = query ? `${API_BASE}${url}?${query}` : `${API_BASE}${url}`;
    const res = await fetch(fullUrl);
    return res.json();
}

async function apiPost(url, data = {}) {
    const res = await fetch(`${API_BASE}${url}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    const result = await res.json();
    if (!res.ok) {
        throw new Error(result.error || '请求失败');
    }
    return result;
}

const EXPIRY_CRITICAL_DAYS = 30;
const EXPIRY_WARNING_DAYS = 90;

const EXPIRY_BG_COLORS = {
    'expired': '#fff1f0',
    'critical': '#fff7e6',
    'warning': '#fffbe6'
};

const EXPIRY_TEXT_CLASSES = {
    'expired': 'text-red',
    'critical': 'text-red',
    'warning': 'text-orange'
};

const EXPIRY_BADGE_CLASSES = {
    'expired': 'badge-danger',
    'critical': 'badge-danger',
    'warning': 'badge-warning'
};

const WARNING_LABELS = {
    'expired': '已过期',
    'critical': '临期(1个月内)',
    'warning': '近效期(3个月内)',
    'normal': '正常',
    'unknown': '未知'
};

function formatDateStr(d) {
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

function getToday() {
    return formatDateStr(new Date());
}

function getWeekNumber(d) {
    const firstDayOfYear = new Date(d.getFullYear(), 0, 1);
    const pastDaysOfYear = (d - firstDayOfYear) / 86400000;
    return Math.ceil((pastDaysOfYear + firstDayOfYear.getDay() + 1) / 7);
}

function shiftDate(dateStr, period, delta) {
    const d = new Date(dateStr);
    if (period === 'day') {
        d.setDate(d.getDate() + delta);
    } else if (period === 'week') {
        d.setDate(d.getDate() + delta * 7);
    } else if (period === 'month') {
        d.setMonth(d.getMonth() + delta);
    }
    return formatDateStr(d);
}

function buildPeriodDateParam(dateStr, period) {
    if (period === 'week') {
        const d = new Date(dateStr);
        const year = d.getFullYear();
        const week = getWeekNumber(d);
        return `${year}-${String(week).padStart(2, '0')}`;
    } else if (period === 'month') {
        return dateStr.substring(0, 7);
    }
    return dateStr;
}

function calcDaysRemaining(expiryDateStr) {
    if (!expiryDateStr) return null;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const expiry = new Date(expiryDateStr);
    expiry.setHours(0, 0, 0, 0);
    return Math.floor((expiry - today) / (1000 * 60 * 60 * 24));
}

function getExpiryWarningLevel(expiryDateStr) {
    const days = calcDaysRemaining(expiryDateStr);
    if (days === null) return { level: 'unknown', label: WARNING_LABELS['unknown'], days_remaining: null };
    if (days <= 0) return { level: 'expired', label: WARNING_LABELS['expired'], days_remaining: days };
    if (days <= EXPIRY_CRITICAL_DAYS) return { level: 'critical', label: WARNING_LABELS['critical'], days_remaining: days };
    if (days <= EXPIRY_WARNING_DAYS) return { level: 'warning', label: WARNING_LABELS['warning'], days_remaining: days };
    return { level: 'normal', label: WARNING_LABELS['normal'], days_remaining: days };
}

function getExpiryBgColor(level) {
    return EXPIRY_BG_COLORS[level] || '';
}

function getExpiryTextClass(level) {
    return EXPIRY_TEXT_CLASSES[level] || '';
}

function getExpiryBadgeClass(level) {
    return EXPIRY_BADGE_CLASSES[level] || '';
}

// ========== 药品目录页面 ==========
const MedicineList = {
    template: `
        <div>
            <div class="card">
                <div class="search-bar">
                    <input 
                        type="text" 
                        class="search-input" 
                        v-model="keyword" 
                        placeholder="搜索药品名称、生产厂家、规格..."
                        @keyup.enter="searchMedicines"
                    >
                    <select class="search-select" v-model="category" @change="searchMedicines">
                        <option value="">全部分类</option>
                        <option v-for="cat in categories" :key="cat" :value="cat">{{ cat }}</option>
                    </select>
                    <button class="btn btn-primary" @click="searchMedicines">搜索</button>
                    <button class="btn btn-default" @click="resetSearch">重置</button>
                    <button class="btn btn-success" style="margin-left: auto;" @click="openAddModal">+ 新增药品</button>
                </div>

                <div class="card-header">
                    <span class="card-title">药品列表 (共 {{ medicines.length }} 条)</span>
                </div>

                <table class="table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>药品名称</th>
                            <th>规格</th>
                            <th>生产厂家</th>
                            <th>单位</th>
                            <th>价格</th>
                            <th>库存</th>
                            <th>预警阈值</th>
                            <th>分类</th>
                            <th>状态</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="med in medicines" :key="med.id">
                            <td>{{ med.id }}</td>
                            <td>{{ med.name }}</td>
                            <td>{{ med.specification }}</td>
                            <td>{{ med.manufacturer }}</td>
                            <td>{{ med.unit }}</td>
                            <td>¥{{ med.price.toFixed(2) }}</td>
                            <td :class="{ 'text-red': med.stock <= med.threshold }">
                                {{ med.stock }} {{ med.unit }}
                            </td>
                            <td>{{ med.threshold }}</td>
                            <td><span class="badge badge-warning">{{ med.category }}</span></td>
                            <td>
                                <span v-if="med.stock <= med.threshold" class="badge badge-danger">库存不足</span>
                                <span v-else class="badge badge-success">正常</span>
                            </td>
                            <td>
                                <button class="btn btn-sm btn-default" @click="openEditModal(med)">编辑</button>
                                <button class="btn btn-sm btn-danger" @click="deleteMedicine(med)">删除</button>
                            </td>
                        </tr>
                        <tr v-if="medicines.length === 0">
                            <td colspan="11" class="empty">暂无数据</td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div v-if="showModal" class="modal-mask" @click.self="closeModal">
                <div class="modal">
                    <div class="modal-header">
                        <span class="modal-title">{{ isEdit ? '编辑药品' : '新增药品' }}</span>
                        <button class="modal-close" @click="closeModal">×</button>
                    </div>
                    <div class="modal-body">
                        <div class="form-group">
                            <label>药品名称 *</label>
                            <input type="text" v-model="form.name" placeholder="请输入药品名称">
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label>规格</label>
                                <input type="text" v-model="form.specification" placeholder="如：0.25g*24粒">
                            </div>
                            <div class="form-group">
                                <label>单位</label>
                                <input type="text" v-model="form.unit" placeholder="如：盒、瓶">
                            </div>
                        </div>
                        <div class="form-group">
                            <label>生产厂家</label>
                            <input type="text" v-model="form.manufacturer" placeholder="请输入生产厂家">
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label>价格 (元) *</label>
                                <input type="number" step="0.01" v-model.number="form.price" placeholder="0.00">
                            </div>
                            <div class="form-group">
                                <label>初始库存</label>
                                <input type="number" v-model.number="form.stock" placeholder="0">
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label>预警阈值</label>
                                <input type="number" v-model.number="form.threshold" placeholder="10">
                            </div>
                            <div class="form-group">
                                <label>分类</label>
                                <input type="text" v-model="form.category" placeholder="如：抗生素">
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-default" @click="closeModal">取消</button>
                        <button class="btn btn-primary" @click="saveMedicine">保存</button>
                    </div>
                </div>
            </div>
        </div>
    `,
    setup() {
        const medicines = ref([]);
        const categories = ref([]);
        const keyword = ref('');
        const category = ref('');
        const showModal = ref(false);
        const isEdit = ref(false);
        const form = reactive({
            id: null,
            name: '',
            specification: '',
            manufacturer: '',
            unit: '盒',
            price: 0,
            stock: 0,
            threshold: 10,
            category: ''
        });

        const loadMedicines = async () => {
            try {
                const data = await apiGet('/medicines', { keyword: keyword.value, category: category.value });
                medicines.value = data;
            } catch (e) {
                alert('加载药品列表失败');
            }
        };

        const loadCategories = async () => {
            try {
                const data = await apiGet('/medicines/categories');
                categories.value = data;
            } catch (e) {}
        };

        const searchMedicines = () => {
            loadMedicines();
        };

        const resetSearch = () => {
            keyword.value = '';
            category.value = '';
            loadMedicines();
        };

        const openAddModal = () => {
            isEdit.value = false;
            form.id = null;
            form.name = '';
            form.specification = '';
            form.manufacturer = '';
            form.unit = '盒';
            form.price = 0;
            form.stock = 0;
            form.threshold = 10;
            form.category = '';
            showModal.value = true;
        };

        const openEditModal = (med) => {
            isEdit.value = true;
            form.id = med.id;
            form.name = med.name;
            form.specification = med.specification;
            form.manufacturer = med.manufacturer;
            form.unit = med.unit;
            form.price = med.price;
            form.stock = med.stock;
            form.threshold = med.threshold;
            form.category = med.category;
            showModal.value = true;
        };

        const closeModal = () => {
            showModal.value = false;
        };

        const saveMedicine = async () => {
            if (!form.name) {
                alert('请输入药品名称');
                return;
            }
            try {
                if (isEdit.value) {
                    await apiPost(`/medicines/${form.id}`, form);
                    alert('更新成功');
                } else {
                    await apiPost('/medicines', form);
                    alert('创建成功');
                }
                closeModal();
                loadMedicines();
                loadCategories();
            } catch (e) {
                alert(e.message);
            }
        };

        const deleteMedicine = (med) => {
            if (!confirm(`确定要删除药品「${med.name}」吗？`)) return;
            fetch(`${API_BASE}/medicines/${med.id}`, { method: 'DELETE' })
                .then(() => {
                    alert('删除成功');
                    loadMedicines();
                })
                .catch(() => alert('删除失败'));
        };

        onMounted(() => {
            loadMedicines();
            loadCategories();
        });

        return {
            medicines, categories, keyword, category,
            showModal, isEdit, form,
            searchMedicines, resetSearch,
            openAddModal, openEditModal, closeModal, saveMedicine, deleteMedicine
        };
    }
};

// ========== 入库登记页面 ==========
const StockIn = {
    template: `
        <div>
            <div class="card">
                <div class="card-header">
                    <span class="card-title">新增入库</span>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>选择药品 *</label>
                        <select class="search-select" v-model="stockInForm.medicine_id" style="width: 100%;">
                            <option value="">请选择药品</option>
                            <option v-for="med in medicineOptions" :key="med.id" :value="med.id">
                                {{ med.name }} - {{ med.specification }} (库存: {{ med.stock }}{{ med.unit }})
                            </option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>入库数量 *</label>
                        <input type="number" v-model.number="stockInForm.quantity" min="1" placeholder="请输入数量">
                    </div>
                    <div class="form-group">
                        <label>单价 (元)</label>
                        <input type="number" step="0.01" v-model.number="stockInForm.unit_price" placeholder="0.00">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>批次号</label>
                        <input type="text" v-model="stockInForm.batch_no" placeholder="请输入批次号">
                    </div>
                    <div class="form-group">
                        <label>有效期</label>
                        <input type="date" v-model="stockInForm.expiry_date">
                    </div>
                    <div class="form-group">
                        <label>操作人</label>
                        <input type="text" v-model="stockInForm.operator" placeholder="请输入操作人姓名">
                    </div>
                </div>
                <div class="form-group">
                    <label>备注</label>
                    <input type="text" v-model="stockInForm.remark" placeholder="选填">
                </div>
                <div style="text-align: right;">
                    <button class="btn btn-success" @click="submitStockIn">确认入库</button>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="card-title">入库记录</span>
                    <input 
                        type="text" 
                        class="search-input" 
                        v-model="searchKeyword" 
                        placeholder="搜索药品名称或批次号..."
                        @keyup.enter="loadStockInList"
                    >
                </div>
                <table class="table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>药品名称</th>
                            <th>规格</th>
                            <th>批次号</th>
                            <th>有效期</th>
                            <th>数量</th>
                            <th>单价</th>
                            <th>操作人</th>
                            <th>操作时间</th>
                            <th>备注</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="item in stockInList" :key="item.id">
                            <td>{{ item.id }}</td>
                            <td>{{ item.medicine_name }}</td>
                            <td>{{ item.specification }}</td>
                            <td><code style="background: #f5f5f5; padding: 2px 6px; border-radius: 4px;">{{ item.batch_no || '-' }}</code></td>
                            <td>{{ item.expiry_date || '-' }}</td>
                            <td class="text-green">+{{ item.quantity }} {{ item.unit }}</td>
                            <td>¥{{ item.unit_price.toFixed(2) }}</td>
                            <td>{{ item.operator }}</td>
                            <td>{{ item.operation_time }}</td>
                            <td>{{ item.remark || '-' }}</td>
                        </tr>
                        <tr v-if="stockInList.length === 0">
                            <td colspan="10" class="empty">暂无数据</td>
                        </tr>
                    </tbody>
                </table>

                <div class="pagination">
                    <button class="page-btn" :disabled="page <= 1" @click="changePage(page - 1)">上一页</button>
                    <button 
                        v-for="p in totalPages" 
                        :key="p" 
                        class="page-btn" 
                        :class="{ active: p === page }"
                        @click="changePage(p)"
                    >{{ p }}</button>
                    <button class="page-btn" :disabled="page >= totalPages" @click="changePage(page + 1)">下一页</button>
                </div>
            </div>
        </div>
    `,
    setup() {
        const medicineOptions = ref([]);
        const stockInList = ref([]);
        const searchKeyword = ref('');
        const page = ref(1);
        const perPage = ref(10);
        const total = ref(0);

        const stockInForm = reactive({
            medicine_id: '',
            quantity: 1,
            unit_price: 0,
            batch_no: '',
            expiry_date: '',
            operator: '管理员',
            remark: ''
        });

        const totalPages = computed(() => Math.ceil(total.value / perPage.value) || 1);

        const loadMedicines = async () => {
            try {
                const data = await apiGet('/medicines');
                medicineOptions.value = data;
            } catch (e) {}
        };

        const loadStockInList = async () => {
            try {
                const data = await apiGet('/stock-in', {
                    page: page.value,
                    per_page: perPage.value,
                    keyword: searchKeyword.value
                });
                stockInList.value = data.list;
                total.value = data.total;
            } catch (e) {}
        };

        const submitStockIn = async () => {
            if (!stockInForm.medicine_id) {
                alert('请选择药品');
                return;
            }
            if (!stockInForm.quantity || stockInForm.quantity <= 0) {
                alert('请输入有效数量');
                return;
            }
            try {
                await apiPost('/stock-in', {
                    medicine_id: stockInForm.medicine_id,
                    quantity: stockInForm.quantity,
                    unit_price: stockInForm.unit_price,
                    batch_no: stockInForm.batch_no,
                    expiry_date: stockInForm.expiry_date,
                    operator: stockInForm.operator,
                    remark: stockInForm.remark
                });
                alert('入库成功');
                stockInForm.medicine_id = '';
                stockInForm.quantity = 1;
                stockInForm.unit_price = 0;
                stockInForm.batch_no = '';
                stockInForm.expiry_date = '';
                stockInForm.remark = '';
                loadStockInList();
                loadMedicines();
            } catch (e) {
                alert(e.message);
            }
        };

        const changePage = (p) => {
            page.value = p;
            loadStockInList();
        };

        onMounted(() => {
            loadMedicines();
            loadStockInList();
        });

        return {
            medicineOptions, stockInList, searchKeyword,
            stockInForm, page, perPage, total, totalPages,
            submitStockIn, changePage, loadStockInList
        };
    }
};

// ========== 销售开单页面 ==========
const Sales = {
    template: `
        <div>
            <div class="card">
                <div class="card-header">
                    <span class="card-title">销售开单</span>
                </div>

                <div class="sale-items">
                    <div class="sale-item-row" v-for="(item, index) in saleItems" :key="index">
                        <div class="sale-item-select">
                            <select 
                                class="search-select" 
                                v-model="item.medicine_id" 
                                style="width: 100%;"
                                @change="onMedicineChange(index)"
                            >
                                <option value="">选择药品</option>
                                <option v-for="med in medicineOptions" :key="med.id" :value="med.id">
                                    {{ med.name }} - {{ med.specification }} (库存: {{ med.stock }}{{ med.unit }})
                                </option>
                            </select>
                        </div>
                        <div class="sale-item-qty">
                            <input type="number" v-model.number="item.quantity" min="1" style="width: 100%; padding: 8px; border: 1px solid #d9d9d9; border-radius: 6px;" placeholder="数量">
                        </div>
                        <div class="sale-item-price">
                            <input type="number" step="0.01" v-model.number="item.unit_price" style="width: 100%; padding: 8px; border: 1px solid #d9d9d9; border-radius: 6px;" placeholder="单价">
                        </div>
                        <div class="sale-item-total">
                            ¥{{ (item.quantity * item.unit_price).toFixed(2) }}
                        </div>
                        <div class="sale-item-remove">
                            <button v-if="saleItems.length > 1" class="btn btn-sm btn-danger" @click="removeItem(index)">×</button>
                        </div>
                    </div>
                    <button class="btn btn-default" style="width: 100%; margin-top: 12px;" @click="addItem">+ 添加药品</button>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label>客户姓名</label>
                        <input type="text" v-model="saleForm.customer" placeholder="选填">
                    </div>
                    <div class="form-group">
                        <label>操作人</label>
                        <input type="text" v-model="saleForm.operator" placeholder="请输入操作人">
                    </div>
                    <div class="form-group">
                        <label>备注</label>
                        <input type="text" v-model="saleForm.remark" placeholder="选填">
                    </div>
                </div>

                <div class="sale-total">
                    <span>合计金额：</span>
                    <span class="total-amount">¥{{ totalAmount.toFixed(2) }}</span>
                </div>

                <div style="text-align: right; margin-top: 16px;">
                    <button class="btn btn-default" @click="resetForm">重置</button>
                    <button class="btn btn-primary" @click="submitSale">确认开单</button>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="card-title">销售记录</span>
                    <div class="flex-gap">
                        <input 
                            type="text" 
                            class="search-input" 
                            v-model="searchKeyword" 
                            placeholder="搜索订单号或药品..."
                            @keyup.enter="loadSalesList"
                        >
                        <select class="search-select" v-model="periodFilter" @change="loadSalesList">
                            <option value="">全部时间</option>
                            <option value="day">按日</option>
                            <option value="week">按周</option>
                            <option value="month">按月</option>
                        </select>
                        <input v-if="periodFilter" type="date" class="search-input" v-model="dateFilter" @change="loadSalesList">
                    </div>
                </div>
                <table class="table">
                    <thead>
                        <tr>
                            <th>订单号</th>
                            <th>药品名称</th>
                            <th>数量</th>
                            <th>单价</th>
                            <th>金额</th>
                            <th>客户</th>
                            <th>操作人</th>
                            <th>操作时间</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="item in salesList" :key="item.id">
                            <td>{{ item.order_no }}</td>
                            <td>{{ item.medicine_name }}</td>
                            <td>{{ item.quantity }} {{ item.unit }}</td>
                            <td>¥{{ item.unit_price.toFixed(2) }}</td>
                            <td class="text-orange">¥{{ item.total_price.toFixed(2) }}</td>
                            <td>{{ item.customer || '-' }}</td>
                            <td>{{ item.operator }}</td>
                            <td>{{ item.operation_time }}</td>
                        </tr>
                        <tr v-if="salesList.length === 0">
                            <td colspan="8" class="empty">暂无数据</td>
                        </tr>
                    </tbody>
                </table>

                <div class="pagination">
                    <button class="page-btn" :disabled="page <= 1" @click="changePage(page - 1)">上一页</button>
                    <button 
                        v-for="p in totalPages" 
                        :key="p" 
                        class="page-btn" 
                        :class="{ active: p === page }"
                        @click="changePage(p)"
                    >{{ p }}</button>
                    <button class="page-btn" :disabled="page >= totalPages" @click="changePage(page + 1)">下一页</button>
                </div>
            </div>
        </div>
    `,
    setup() {
        const medicineOptions = ref([]);
        const salesList = ref([]);
        const searchKeyword = ref('');
        const periodFilter = ref('');
        const dateFilter = ref('');
        const page = ref(1);
        const perPage = ref(10);
        const total = ref(0);

        const saleForm = reactive({
            customer: '',
            operator: '管理员',
            remark: ''
        });

        const saleItems = ref([
            { medicine_id: '', quantity: 1, unit_price: 0 }
        ]);

        const totalPages = computed(() => Math.ceil(total.value / perPage.value) || 1);

        const totalAmount = computed(() => {
            return saleItems.value.reduce((sum, item) => {
                return sum + (item.quantity * item.unit_price);
            }, 0);
        });

        const loadMedicines = async () => {
            try {
                const data = await apiGet('/medicines');
                medicineOptions.value = data;
            } catch (e) {}
        };

        const loadSalesList = async () => {
            const params = {
                page: page.value,
                per_page: perPage.value,
                keyword: searchKeyword.value
            };
            if (periodFilter.value && dateFilter.value) {
                params.period = periodFilter.value;
                params.date = dateFilter.value;
            }
            try {
                const data = await apiGet('/sales', params);
                salesList.value = data.list;
                total.value = data.total;
            } catch (e) {}
        };

        const onMedicineChange = (index) => {
            const item = saleItems.value[index];
            const med = medicineOptions.value.find(m => m.id == item.medicine_id);
            if (med) {
                item.unit_price = med.price;
            }
        };

        const addItem = () => {
            saleItems.value.push({ medicine_id: '', quantity: 1, unit_price: 0 });
        };

        const removeItem = (index) => {
            saleItems.value.splice(index, 1);
        };

        const resetForm = () => {
            saleItems.value = [{ medicine_id: '', quantity: 1, unit_price: 0 }];
            saleForm.customer = '';
            saleForm.remark = '';
        };

        const submitSale = async () => {
            const validItems = saleItems.value.filter(item => item.medicine_id && item.quantity > 0);
            if (validItems.length === 0) {
                alert('请至少添加一个有效药品');
                return;
            }
            try {
                const result = await apiPost('/sales', {
                    items: validItems,
                    operator: saleForm.operator,
                    customer: saleForm.customer,
                    remark: saleForm.remark
                });
                alert(`开单成功！订单号：${result.order_no}\n金额：¥${result.total_amount.toFixed(2)}`);
                resetForm();
                loadSalesList();
                loadMedicines();
            } catch (e) {
                alert(e.message);
            }
        };

        const changePage = (p) => {
            page.value = p;
            loadSalesList();
        };

        onMounted(() => {
            dateFilter.value = getToday();
            loadMedicines();
            loadSalesList();
        });

        return {
            medicineOptions, salesList, searchKeyword,
            periodFilter, dateFilter,
            saleForm, saleItems, totalAmount,
            page, perPage, total, totalPages,
            onMedicineChange, addItem, removeItem,
            resetForm, submitSale, changePage
        };
    }
};

// ========== 库存预警页面 ==========
const StockWarning = {
    template: `
        <div>
            <div class="stat-cards">
                <div class="stat-card">
                    <div class="stat-icon blue">💊</div>
                    <div class="stat-info">
                        <h3>{{ inventoryStats.medicine_count }}</h3>
                        <p>药品种类</p>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon green">📦</div>
                    <div class="stat-info">
                        <h3>{{ inventoryStats.total_stock }}</h3>
                        <p>总库存数量</p>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon orange">💰</div>
                    <div class="stat-info">
                        <h3>¥{{ (inventoryStats.total_value || 0).toFixed(2) }}</h3>
                        <p>库存总价值</p>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon red">⚠️</div>
                    <div class="stat-info">
                        <h3>{{ inventoryStats.low_stock_count }}</h3>
                        <p>库存预警</p>
                    </div>
                </div>
            </div>

            <div class="stat-cards">
                <div class="stat-card">
                    <div class="stat-icon" style="background-color: #fff7e6;">🟡</div>
                    <div class="stat-info">
                        <h3 style="color: #fa8c16;">{{ inventoryStats.expiry_3month_count || 0 }}</h3>
                        <p>3个月内近效期</p>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon" style="background-color: #fff1f0;">🔴</div>
                    <div class="stat-info">
                        <h3 style="color: #ff4d4f;">{{ inventoryStats.expiry_1month_count || 0 }}</h3>
                        <p>1个月内临期</p>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon" style="background-color: #fffbe6;">📦</div>
                    <div class="stat-info">
                        <h3>{{ inventoryStats.expiry_3month_qty || 0 }}</h3>
                        <p>近效期数量</p>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon" style="background-color: #f9f0ff;">💵</div>
                    <div class="stat-info">
                        <h3>¥{{ expiryValue.toFixed(2) }}</h3>
                        <p>近效期货值</p>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="card-title" style="color: #ff4d4f;">🔴 库存预警药品</span>
                    <span class="text-red" style="font-size: 14px;">共 {{ lowStockMedicines.length }} 种药品低于安全库存</span>
                </div>
                <table class="table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>药品名称</th>
                            <th>规格</th>
                            <th>生产厂家</th>
                            <th>当前库存</th>
                            <th>预警阈值</th>
                            <th>差额</th>
                            <th>单价</th>
                            <th>分类</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="med in lowStockMedicines" :key="med.id" style="background-color: #fff1f0;">
                            <td>{{ med.id }}</td>
                            <td class="text-red">{{ med.name }}</td>
                            <td>{{ med.specification }}</td>
                            <td>{{ med.manufacturer }}</td>
                            <td class="text-red" style="font-weight: 600;">{{ med.stock }} {{ med.unit }}</td>
                            <td>{{ med.threshold }} {{ med.unit }}</td>
                            <td class="text-red">-{{ med.threshold - med.stock }} {{ med.unit }}</td>
                            <td>¥{{ med.price.toFixed(2) }}</td>
                            <td><span class="badge badge-warning">{{ med.category }}</span></td>
                            <td>
                                <button class="btn btn-sm btn-success" @click="quickStockIn(med)">快速入库</button>
                            </td>
                        </tr>
                        <tr v-if="lowStockMedicines.length === 0">
                            <td colspan="10" class="empty">
                                <span style="color: #52c41a;">✅ 所有药品库存正常，暂无预警</span>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="card-title">⏰ 近效期预警</span>
                    <div class="flex-gap">
                        <select class="search-select" v-model="expiryFilter" @change="loadExpiryWarning">
                            <option value="all">全部近效期</option>
                            <option value="critical">1个月内（临期）</option>
                            <option value="warning">1-3个月（近效期）</option>
                            <option value="expired">已过期</option>
                        </select>
                    </div>
                </div>
                <table class="table">
                    <thead>
                        <tr>
                            <th>药品名称</th>
                            <th>规格</th>
                            <th>批次号</th>
                            <th>有效期</th>
                            <th>剩余天数</th>
                            <th>剩余库存</th>
                            <th>单价</th>
                            <th>库存价值</th>
                            <th>预警级别</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr 
                            v-for="item in filteredExpiryMedicines" 
                            :key="item.id"
                            :style="{ backgroundColor: getExpiryBgColor(item.warning_level) }"
                        >
                            <td>{{ item.medicine_name }}</td>
                            <td>{{ item.specification }}</td>
                            <td><code style="background: #f5f5f5; padding: 2px 6px; border-radius: 4px;">{{ item.batch_no }}</code></td>
                            <td>{{ item.expiry_date }}</td>
                            <td :class="getExpiryTextClass(item.warning_level)" style="font-weight: 600;">
                                <span v-if="item.days_remaining <= 0">已过期 {{ -item.days_remaining }} 天</span>
                                <span v-else>{{ item.days_remaining }} 天</span>
                            </td>
                            <td>{{ item.quantity }} {{ item.unit }}</td>
                            <td>¥{{ item.price.toFixed(2) }}</td>
                            <td>¥{{ (item.quantity * item.price).toFixed(2) }}</td>
                            <td>
                                <span class="badge" :class="getExpiryBadgeClass(item.warning_level)">
                                    {{ item.warning_label }}
                                </span>
                            </td>
                        </tr>
                        <tr v-if="filteredExpiryMedicines.length === 0">
                            <td colspan="9" class="empty">
                                <span style="color: #52c41a;">✅ 暂无近效期药品</span>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="card-title">全部药品库存一览</span>
                    <div class="flex-gap">
                        <input 
                            type="text" 
                            class="search-input" 
                            v-model="keyword" 
                            placeholder="搜索药品..."
                            @keyup.enter="loadAllMedicines"
                        >
                        <select class="search-select" v-model="sortBy" @change="loadAllMedicines">
                            <option value="stock_asc">库存从低到高</option>
                            <option value="stock_desc">库存从高到低</option>
                            <option value="price_desc">价格从高到低</option>
                            <option value="name">按名称</option>
                        </select>
                    </div>
                </div>
                <table class="table">
                    <thead>
                        <tr>
                            <th>药品名称</th>
                            <th>规格</th>
                            <th>当前库存</th>
                            <th>预警阈值</th>
                            <th>库存状态</th>
                            <th>单价</th>
                            <th>库存价值</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="med in allMedicines" :key="med.id" :style="{ backgroundColor: med.stock <= med.threshold ? '#fff1f0' : '' }">
                            <td>{{ med.name }}</td>
                            <td>{{ med.specification }}</td>
                            <td :class="{ 'text-red': med.stock <= med.threshold }">
                                {{ med.stock }} {{ med.unit }}
                            </td>
                            <td>{{ med.threshold }} {{ med.unit }}</td>
                            <td>
                                <span v-if="med.stock <= med.threshold" class="badge badge-danger">库存不足</span>
                                <span v-else-if="med.stock <= med.threshold * 2" class="badge badge-warning">库存偏低</span>
                                <span v-else class="badge badge-success">库存充足</span>
                            </td>
                            <td>¥{{ med.price.toFixed(2) }}</td>
                            <td>¥{{ (med.stock * med.price).toFixed(2) }}</td>
                        </tr>
                        <tr v-if="allMedicines.length === 0">
                            <td colspan="7" class="empty">暂无数据</td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div v-if="showStockInModal" class="modal-mask" @click.self="closeStockInModal">
                <div class="modal">
                    <div class="modal-header">
                        <span class="modal-title">快速入库 - {{ selectedMedicine?.name }}</span>
                        <button class="modal-close" @click="closeStockInModal">×</button>
                    </div>
                    <div class="modal-body">
                        <div class="form-group">
                            <label>入库数量</label>
                            <input type="number" v-model.number="stockInQty" min="1" placeholder="请输入数量">
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label>批次号</label>
                                <input type="text" v-model="stockInBatchNo" placeholder="请输入批次号">
                            </div>
                            <div class="form-group">
                                <label>有效期</label>
                                <input type="date" v-model="stockInExpiryDate">
                            </div>
                        </div>
                        <div class="form-group">
                            <label>操作人</label>
                            <input type="text" v-model="stockInOperator" placeholder="请输入操作人">
                        </div>
                        <p style="color: #8c8c8c; font-size: 13px; margin-top: 8px;">
                            当前库存：{{ selectedMedicine?.stock }} {{ selectedMedicine?.unit }}
                            <br>预警阈值：{{ selectedMedicine?.threshold }} {{ selectedMedicine?.unit }}
                        </p>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-default" @click="closeStockInModal">取消</button>
                        <button class="btn btn-success" @click="confirmStockIn">确认入库</button>
                    </div>
                </div>
            </div>
        </div>
    `,
    setup() {
        const inventoryStats = ref({
            medicine_count: 0,
            total_stock: 0,
            total_value: 0,
            low_stock_count: 0,
            expiry_1month_count: 0,
            expiry_3month_count: 0
        });
        const lowStockMedicines = ref([]);
        const expiryMedicines = ref([]);
        const allMedicines = ref([]);
        const keyword = ref('');
        const sortBy = ref('stock_asc');
        const expiryFilter = ref('all');

        const showStockInModal = ref(false);
        const selectedMedicine = ref(null);
        const stockInQty = ref(10);
        const stockInBatchNo = ref('');
        const stockInExpiryDate = ref('');
        const stockInOperator = ref('管理员');

        const filteredExpiryMedicines = computed(() => {
            if (expiryFilter.value === 'all') return expiryMedicines.value;
            return expiryMedicines.value.filter(item => item.warning_level === expiryFilter.value);
        });

        const expiryValue = computed(() => {
            return expiryMedicines.value.reduce((sum, item) => {
                return sum + (item.quantity * item.price);
            }, 0);
        });

        const loadStats = async () => {
            try {
                const data = await apiGet('/statistics/inventory-value');
                inventoryStats.value = data;
            } catch (e) {}
        };

        const loadLowStock = async () => {
            try {
                const data = await apiGet('/medicines/low-stock');
                lowStockMedicines.value = data;
            } catch (e) {}
        };

        const loadExpiryWarning = async () => {
            try {
                const data = await apiGet('/medicines/expiry-warning', { days: 90 });
                expiryMedicines.value = data;
            } catch (e) {}
        };

        const loadAllMedicines = async () => {
            try {
                const data = await apiGet('/medicines', { keyword: keyword.value });
                let list = data;
                if (sortBy.value === 'stock_asc') {
                    list.sort((a, b) => a.stock - b.stock);
                } else if (sortBy.value === 'stock_desc') {
                    list.sort((a, b) => b.stock - a.stock);
                } else if (sortBy.value === 'price_desc') {
                    list.sort((a, b) => b.price - a.price);
                } else if (sortBy.value === 'name') {
                    list.sort((a, b) => a.name.localeCompare(b.name));
                }
                allMedicines.value = list;
            } catch (e) {}
        };

        const quickStockIn = (med) => {
            selectedMedicine.value = med;
            stockInQty.value = Math.max(med.threshold - med.stock + 5, 10);
            stockInBatchNo.value = '';
            stockInExpiryDate.value = '';
            showStockInModal.value = true;
        };

        const closeStockInModal = () => {
            showStockInModal.value = false;
            selectedMedicine.value = null;
        };

        const confirmStockIn = async () => {
            if (!selectedMedicine.value || stockInQty.value <= 0) {
                alert('请输入有效数量');
                return;
            }
            try {
                await apiPost('/stock-in', {
                    medicine_id: selectedMedicine.value.id,
                    quantity: stockInQty.value,
                    unit_price: selectedMedicine.value.price,
                    operator: stockInOperator.value,
                    batch_no: stockInBatchNo.value,
                    expiry_date: stockInExpiryDate.value,
                    remark: '快速入库（库存预警）'
                });
                alert('入库成功');
                closeStockInModal();
                loadStats();
                loadLowStock();
                loadExpiryWarning();
                loadAllMedicines();
            } catch (e) {
                alert(e.message);
            }
        };

        onMounted(() => {
            loadStats();
            loadLowStock();
            loadExpiryWarning();
            loadAllMedicines();
        });

        return {
            inventoryStats, lowStockMedicines, expiryMedicines, allMedicines,
            keyword, sortBy, expiryFilter,
            filteredExpiryMedicines, expiryValue,
            getExpiryBgColor, getExpiryTextClass, getExpiryBadgeClass,
            showStockInModal, selectedMedicine, stockInQty, stockInBatchNo, stockInExpiryDate, stockInOperator,
            quickStockIn, closeStockInModal, confirmStockIn,
            loadAllMedicines, loadExpiryWarning
        };
    }
};

// ========== 销售统计页面 ==========
const Statistics = {
    template: `
        <div>
            <div class="card">
                <div class="card-header">
                    <span class="card-title">销售统计</span>
                    <div class="tabs" style="margin-bottom: 0;">
                        <div 
                            class="tab-item" 
                            :class="{ active: period === 'day' }"
                            @click="changePeriod('day')"
                        >按日</div>
                        <div 
                            class="tab-item" 
                            :class="{ active: period === 'week' }"
                            @click="changePeriod('week')"
                        >按周</div>
                        <div 
                            class="tab-item" 
                            :class="{ active: period === 'month' }"
                            @click="changePeriod('month')"
                        >按月</div>
                    </div>
                </div>

                <div class="flex-gap mb-20">
                    <input type="date" class="search-input" v-model="selectedDate" @change="loadData">
                    <button class="btn btn-default" @click="goPrev">← 上一{{ periodLabel }}</button>
                    <button class="btn btn-default" @click="goNext">下一{{ periodLabel }} →</button>
                    <button class="btn btn-primary" @click="goToday">回到今天</button>
                </div>
            </div>

            <div class="stat-cards">
                <div class="stat-card">
                    <div class="stat-icon blue">📋</div>
                    <div class="stat-info">
                        <h3>{{ summary.order_num }}</h3>
                        <p>订单数量</p>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon green">💊</div>
                    <div class="stat-info">
                        <h3>{{ summary.total_quantity }}</h3>
                        <p>销售数量</p>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon orange">💰</div>
                    <div class="stat-info">
                        <h3>¥{{ summary.total_amount.toFixed(2) }}</h3>
                        <p>销售总额</p>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon red">📊</div>
                    <div class="stat-info">
                        <h3>{{ avgAmount }}</h3>
                        <p>客单价</p>
                    </div>
                </div>
            </div>

            <div class="card" v-if="period !== 'day' && dailySales.length > 0">
                <div class="card-header">
                    <span class="card-title">销售趋势</span>
                </div>
                <div class="chart-container">
                    <div v-for="day in dailySales" :key="day.date" class="bar-item">
                        <div class="bar-value">¥{{ day.total_amount.toFixed(0) }}</div>
                        <div class="bar" :style="{ height: getBarHeight(day.total_amount) + 'px' }"></div>
                        <div class="bar-label">{{ formatDateLabel(day.date) }}</div>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="card-title">热销药品排行 TOP 10</span>
                </div>
                <ul class="top-list">
                    <li v-for="(med, index) in topMedicines" :key="med.id">
                        <div style="display: flex; align-items: center;">
                            <span class="top-rank" :class="{ top1: index === 0, top2: index === 1, top3: index === 2 }">
                                {{ index + 1 }}
                            </span>
                            <span class="top-name">{{ med.name }}</span>
                            <span style="color: #8c8c8c; font-size: 13px; margin-left: 12px;">
                                {{ med.specification }}
                            </span>
                        </div>
                        <div style="text-align: right;">
                            <div class="top-amount">¥{{ med.total_amount.toFixed(2) }}</div>
                            <div style="font-size: 12px; color: #8c8c8c;">销量：{{ med.total_quantity }}</div>
                        </div>
                    </li>
                    <li v-if="topMedicines.length === 0" style="justify-content: center;">
                        <span class="empty">暂无销售数据</span>
                    </li>
                </ul>
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="card-title">库存概览</span>
                </div>
                <div class="stat-cards" style="margin-bottom: 0;">
                    <div class="stat-card" style="box-shadow: none; border: 1px solid #f0f0f0;">
                        <div class="stat-icon blue">💊</div>
                        <div class="stat-info">
                            <h3>{{ inventoryStats.medicine_count }}</h3>
                            <p>药品种类</p>
                        </div>
                    </div>
                    <div class="stat-card" style="box-shadow: none; border: 1px solid #f0f0f0;">
                        <div class="stat-icon green">📦</div>
                        <div class="stat-info">
                            <h3>{{ inventoryStats.total_stock }}</h3>
                            <p>总库存</p>
                        </div>
                    </div>
                    <div class="stat-card" style="box-shadow: none; border: 1px solid #f0f0f0;">
                        <div class="stat-icon orange">💰</div>
                        <div class="stat-info">
                            <h3>¥{{ inventoryStats.total_value.toFixed(2) }}</h3>
                            <p>库存价值</p>
                        </div>
                    </div>
                    <div class="stat-card" style="box-shadow: none; border: 1px solid #f0f0f0;">
                        <div class="stat-icon red">⚠️</div>
                        <div class="stat-info">
                            <h3>{{ inventoryStats.low_stock_count }}</h3>
                            <p>预警药品</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `,
    setup() {
        const period = ref('day');
        const selectedDate = ref('');
        const summary = ref({
            order_num: 0,
            total_quantity: 0,
            total_amount: 0
        });
        const topMedicines = ref([]);
        const dailySales = ref([]);
        const inventoryStats = ref({
            medicine_count: 0,
            total_stock: 0,
            total_value: 0,
            low_stock_count: 0
        });

        const periodLabel = computed(() => {
            if (period.value === 'day') return '天';
            if (period.value === 'week') return '周';
            return '月';
        });

        const avgAmount = computed(() => {
            if (summary.value.order_num === 0) return '¥0.00';
            return '¥' + (summary.value.total_amount / summary.value.order_num).toFixed(2);
        });

        const loadData = async () => {
            try {
                const dateParam = buildPeriodDateParam(selectedDate.value, period.value);
                const data = await apiGet('/statistics/sales-summary', {
                    period: period.value,
                    date: dateParam
                });
                summary.value = {
                    order_num: data.order_num,
                    total_quantity: data.total_quantity,
                    total_amount: data.total_amount
                };
                topMedicines.value = data.top_medicines || [];
                dailySales.value = data.daily_sales || [];
            } catch (e) {}
        };

        const loadInventoryStats = async () => {
            try {
                const data = await apiGet('/statistics/inventory-value');
                inventoryStats.value = data;
            } catch (e) {}
        };

        const changePeriod = (p) => {
            period.value = p;
            loadData();
        };

        const goPrev = () => {
            selectedDate.value = shiftDate(selectedDate.value, period.value, -1);
        };

        const goNext = () => {
            selectedDate.value = shiftDate(selectedDate.value, period.value, 1);
        };

        const goToday = () => {
            selectedDate.value = getToday();
        };

        const getBarHeight = (amount) => {
            if (!dailySales.value.length) return 4;
            const maxAmount = Math.max(...dailySales.value.map(d => d.total_amount));
            if (maxAmount === 0) return 4;
            return Math.max(4, (amount / maxAmount) * 200);
        };

        const formatDateLabel = (dateStr) => {
            if (period.value === 'week') {
                const d = new Date(dateStr);
                const weekdays = ['日', '一', '二', '三', '四', '五', '六'];
                return '周' + weekdays[d.getDay()];
            }
            if (period.value === 'month') {
                return dateStr.split('-')[2] + '日';
            }
            return dateStr;
        };

        onMounted(() => {
            selectedDate.value = getToday();
            loadData();
            loadInventoryStats();
        });

        watch(period, () => {
            loadData();
        });

        watch(selectedDate, () => {
            loadData();
        });

        return {
            period, selectedDate, periodLabel,
            summary, topMedicines, dailySales, inventoryStats,
            avgAmount,
            changePeriod, goPrev, goNext, goToday,
            getBarHeight, formatDateLabel
        };
    }
};

// ========== 路由配置 ==========
const routes = [
    { path: '/', component: MedicineList, meta: { title: '药品目录' } },
    { path: '/stock-in', component: StockIn, meta: { title: '入库登记' } },
    { path: '/sales', component: Sales, meta: { title: '销售开单' } },
    { path: '/warning', component: StockWarning, meta: { title: '库存预警' } },
    { path: '/statistics', component: Statistics, meta: { title: '销售统计' } }
];

const router = createRouter({
    history: createWebHashHistory(),
    routes
});

// ========== 主应用 ==========
const App = {
    setup() {
        const pageTitle = ref('药品目录');

        router.afterEach((to) => {
            pageTitle.value = to.meta.title || '药房管理系统';
        });

        return { pageTitle };
    }
};

const app = createApp(App);
app.use(router);
app.mount('#app');
