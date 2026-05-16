const express = require('express');
const cors = require('cors');
const Datastore = require('nedb-promises');
const fs = require('fs');
const csv = require('csv-parser');
const path = require('path');

const app = express();
app.use(cors());
app.use(express.json());
app.use(express.static('public')); // serve static files from public directory

// Initialize NeDB databases
const db = Datastore.create({ filename: path.join(__dirname, 'database.db'), autoload: true }); // Inventory
const userDb = Datastore.create({ filename: path.join(__dirname, 'users.db'), autoload: true });
const salesDb = Datastore.create({ filename: path.join(__dirname, 'sales.db'), autoload: true });
const auditDb = Datastore.create({ filename: path.join(__dirname, 'audit.db'), autoload: true });
const settingsDb = Datastore.create({ filename: path.join(__dirname, 'settings.db'), autoload: true });

// Function to seed database from CSV
async function seedDatabase() {
    try {
        // 1. Seed Inventory
        const inventoryCount = await db.count({});
        if (inventoryCount === 0) {
            console.log('Inventory empty. Seeding from CSV...');
            const results = [];
            fs.createReadStream(path.join(__dirname, 'project dataset.csv'))
                .pipe(csv())
                .on('data', (data) => {
                    data.Unit_Cost_USD = parseFloat(data.Unit_Cost_USD) || 0;
                    data.Selling_Price_USD = parseFloat(data.Selling_Price_USD) || 0;
                    data.Quantity_In_Stock = parseInt(data.Quantity_In_Stock, 10) || 0;
                    data.Reorder_Level = parseInt(data.Reorder_Level, 10) || 10;
                    data.Sales_Last_30_Days = parseInt(data.Sales_Last_30_Days, 10) || 0;
                    data.Days_to_Expiry = parseInt(data.Days_to_Expiry, 10) || 0;
                    data.Daily_Consumption_Rate = parseFloat(data.Daily_Consumption_Rate) || 0;
                    data.Days_to_Exhaust_Stock = parseFloat(data.Days_to_Exhaust_Stock) || 0;
                    results.push(data);
                })
                .on('end', async () => {
                    await db.insert(results);
                    console.log(`Seeded inventory with ${results.length} records.`);
                });
        }

        // 2. Seed Default Users
        const userCount = await userDb.count({});
        if (userCount === 0) {
            console.log('Users empty. Seeding defaults...');
            await userDb.insert([
                { username: 'admin', password: 'admin123', role: 'admin' },
                { username: 'pharm', password: 'pharm123', role: 'pharmacist' }
            ]);
            console.log('Seeded default user accounts.');
        }

        // 3. Seed Default Settings
        const settingsCount = await settingsDb.count({});
        if (settingsCount === 0) {
            console.log('Settings empty. Seeding defaults...');
            await settingsDb.insert({
                hospital_name: 'Ghana National Hospital',
                nhis_id: 'GHA-NHIS-9921',
                expiry_threshold: 30,
                currency: 'GH₵'
            });
            console.log('Seeded default system settings.');
        }
    } catch (err) {
        console.error('Error seeding database:', err);
    }
}

// Seed on startup
seedDatabase();

// --- API Endpoints ---

// LOGGING HELPER: Maintain internal audit transparency
async function logEvent(username, event, details, metadata = null) {
    try {
        await auditDb.insert({
            timestamp: new Date().toISOString(),
            username,
            event,
            details,
            metadata
        });
    } catch (e) {
        console.error('Audit Logging Error:', e);
    }
}

// Helper: Automated Expiry Risk Classifier (Dynamic)
async function classifyExpiryRisk(daysToExpiry) {
    const settings = await settingsDb.findOne({}) || { expiry_threshold: 30 };
    const threshold = settings.expiry_threshold;
    
    if (daysToExpiry <= threshold) return 'High Risk';
    if (daysToExpiry <= threshold * 3) return 'Medium Risk';
    return 'Low Risk';
}

// Get dashboard summary
app.get('/api/dashboard', async (req, res) => {
    try {
        const allItems = await db.find({});
        let totalItems = allItems.length;
        let totalStockValue = 0;
        let lowStockCount = 0;
        let riskCount = { 'High Risk': 0, 'Medium Risk': 0, 'Low Risk': 0 };
        let expiredOrNearExpiryCount = 0;

        for (const item of allItems) {
            totalStockValue += item.Quantity_In_Stock * item.Selling_Price_USD;
            if (item.Quantity_In_Stock <= item.Reorder_Level) {
                lowStockCount++;
            }
            
            // Apply Automated Expiry Risk Classifier
            const riskLevel = await classifyExpiryRisk(item.Days_to_Expiry);
            riskCount[riskLevel]++;
            
            const settings = await settingsDb.findOne({}) || { expiry_threshold: 30 };
            if (item.Days_to_Expiry <= settings.expiry_threshold) {
                expiredOrNearExpiryCount++;
            }
        }

        res.json({
            totalItems,
            totalStockValue: totalStockValue.toFixed(2),
            lowStockCount,
            expiredOrNearExpiryCount,
            riskCount
        });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// Get recent critical recommendations (Risk Classifier Results)
app.get('/api/recommendations', async (req, res) => {
    try {
        const allItems = await db.find({}).sort({ Days_to_Expiry: 1 });
        // Dynamically classify and select high risk
        const highRisk = [];
        for (const item of allItems) {
            if (await classifyExpiryRisk(item.Days_to_Expiry) === 'High Risk') {
                highRisk.push(item);
            }
            if (highRisk.length >= 10) break;
        }
        res.json(highRisk);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// Get full inventory (with optional search)
app.get('/api/inventory', async (req, res) => {
    try {
        const query = req.query.search ? this.buildSearchQuery(req.query.search) : {};
        if (req.query.search) {
            const regex = new RegExp(req.query.search, 'i');
            const items = await db.find({ 
                $or: [
                    { Medicine_Name: regex },
                    { Category: regex },
                    { Batch_ID: regex }
                ]
            }).sort({ Medicine_Name: 1 }).limit(100);
            res.json(items);
        } else {
            const items = await db.find({}).sort({ Medicine_Name: 1 }).limit(100);
            res.json(items);
        }
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// Get chart data: Risk Distribution
app.get('/api/charts/risk', async (req, res) => {
    try {
        const allItems = await db.find({});
        const categories = {};
        
        allItems.forEach(item => {
            if (!categories[item.Category]) {
                categories[item.Category] = { name: item.Category, stock: 0 };
            }
            categories[item.Category].stock += item.Quantity_In_Stock;
        });

        res.json(Object.values(categories).slice(0, 5)); // top 5 categories
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// Get Demand Forecasting Data
app.get('/api/forecast', async (req, res) => {
    try {
        const query = req.query.search ? { 
            $or: [
                { Medicine_Name: new RegExp(req.query.search, 'i') },
                { Batch_ID: new RegExp(req.query.search, 'i') }
            ] 
        } : {};
        
        const items = await db.find(query).sort({ Medicine_Name: 1 }).limit(100);
        
        // Calculate dynamic exhaust dates if not present or stale
        const forecastedItems = items.map(item => {
            const stock = item.Quantity_In_Stock || 0;
            const rate = parseFloat(item.Daily_Consumption_Rate) || 0.1; // fallback to avoid div by zero
            
            const daysToExhaust = Math.ceil(stock / rate);
            const stockoutDate = new Date();
            stockoutDate.setDate(stockoutDate.getDate() + daysToExhaust);
            
            return {
                ...item,
                Days_to_Exhaust_Stock: rate > 0 ? daysToExhaust : 'Unlimited',
                Predicted_Stockout_Date: rate > 0 ? stockoutDate.toISOString() : null
            };
        });

        res.json(forecastedItems);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// --- NEW: AUTHENTICATION ---
app.post('/api/login', async (req, res) => {
    const { username, password } = req.body;
    const user = await userDb.findOne({ username, password });
    if (user) {
        logEvent(username, 'Login', `User logged into ${user.role} portal.`, { role: user.role });
        res.json({ success: true, username: user.username, role: user.role });
    } else {
        res.status(401).json({ success: false, message: 'Invalid credentials' });
    }
});

app.post('/api/logout', async (req, res) => {
    const { username } = req.body;
    if (username) {
        logEvent(username, 'Logout', 'User manually closed session.');
        res.json({ success: true });
    } else {
        res.status(400).json({ success: false });
    }
});

// --- NEW: STAFF MANAGEMENT ---
app.get('/api/users', async (req, res) => {
    try {
        const users = await userDb.find({}, { password: 0 }); // Hide passwords
        res.json(users);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

app.post('/api/admin/users', async (req, res) => {
    const { username, password, role, action } = req.body;
    try {
        if (action === 'add') {
            const existing = await userDb.findOne({ username });
            if (existing) return res.json({ success: false, message: 'User already exists' });
            await userDb.insert({ username, password, role });
            logEvent('admin', 'Staff Created', `Added ${username} as ${role}.`);
            res.json({ success: true });
        } else if (action === 'edit') {
            const update = { role };
            if (password) update.password = password;
            await userDb.update({ username }, { $set: update });
            logEvent('admin', 'Staff Updated', `Updated role/password for ${username}.`);
            res.json({ success: true });
        } else if (action === 'delete') {
            await userDb.remove({ username });
            logEvent('admin', 'Staff Removed', `Deleted user account: ${username}.`);
            res.json({ success: true });
        } else {
            res.status(400).json({ success: false, message: 'Invalid action' });
        }
    } catch (err) {
        res.status(500).json({ success: false, message: err.message });
    }
});

// --- NEW: CHECKOUT & SALES ---
app.post('/api/checkout', async (req, res) => {
    const { cart, staff_name, customer_name } = req.body;
    try {
        let total = 0;
        const details = [];

        for (const item of cart) {
            // Update stock
            const dbItem = await db.findOne({ Batch_ID: item.Batch_ID });
            if (!dbItem || dbItem.Quantity_In_Stock < item.qty) {
                return res.status(400).json({ success: false, error: `Insufficient stock for ${item.name}` });
            }

            await db.update({ Batch_ID: item.Batch_ID }, { $inc: { Quantity_In_Stock: -item.qty } });
            total += item.qty * item.price;
            details.push(`${item.qty}x ${item.name}`);
        }

        const saleRecord = {
            timestamp: new Date().toISOString(),
            pharmacist: staff_name,
            customer_name: customer_name || 'Walk-in Customer',
            items: cart.length,
            total_ghs: total,
            details: details.join(', ')
        };

        await salesDb.insert(saleRecord);
        logEvent(staff_name, 'Dispensed Medicine', `Customer: ${saleRecord.customer_name}. Total: GH₵ ${total.toFixed(2)}.`, { cart: cart, total: total });

        res.json({ success: true, total: total.toFixed(2) });
    } catch (err) {
        res.status(500).json({ success: false, error: err.message });
    }
});

// --- NEW: REPORTING & AUDIT ---
app.get('/api/admin/sales', async (req, res) => {
    try {
        const sales = await salesDb.find({}).sort({ timestamp: -1 });
        res.json(sales);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

app.get('/api/sales/today', async (req, res) => {
    const { pharmacist } = req.query;
    try {
        const today = new Date().toISOString().split('T')[0];
        const query = pharmacist ? { pharmacist, timestamp: new RegExp(`^${today}`) } : { timestamp: new RegExp(`^${today}`) };
        const sales = await salesDb.find(query);
        
        const total = sales.reduce((acc, s) => acc + s.total_ghs, 0);
        res.json({ total_revenue_ghs: total, transaction_count: sales.length });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

app.get('/api/my/sales', async (req, res) => {
    const { pharmacist } = req.query;
    try {
        const sales = await salesDb.find({ pharmacist }).sort({ timestamp: -1 });
        res.json(sales);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

console.log('DEBUG: Registering /api/system-audit route');
app.get('/api/system-audit', async (req, res) => {
    try {
        const logs = await auditDb.find({}).sort({ timestamp: -1 });
        res.json(logs);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// --- NEW: SYSTEM SETTINGS ---
app.get('/api/settings', async (req, res) => {
    try {
        const settings = await settingsDb.findOne({});
        res.json(settings);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

app.post('/api/settings', async (req, res) => {
    const { hospital_name, nhis_id, expiry_threshold, currency } = req.body;
    try {
        await settingsDb.update({}, { $set: { 
            hospital_name, 
            nhis_id, 
            expiry_threshold: parseInt(expiry_threshold, 10), 
            currency 
        } }, { upsert: true });
        logEvent('admin', 'Settings Updated', `Hospital: ${hospital_name}, Threshold: ${expiry_threshold} days.`);
        res.json({ success: true });
    } catch (err) {
        res.status(500).json({ success: false, message: err.message });
    }
});

// --- NEW: DATABASE MANAGEMENT ---
app.get('/api/admin/db/stats', async (req, res) => {
    try {
        const stats = {
            inventory: { count: await db.count({}), size: fs.statSync(path.join(__dirname, 'database.db')).size },
            sales: { count: await salesDb.count({}), size: fs.statSync(path.join(__dirname, 'sales.db')).size },
            audit: { count: await auditDb.count({}), size: fs.statSync(path.join(__dirname, 'audit.db')).size },
            users: { count: await userDb.count({}), size: fs.statSync(path.join(__dirname, 'users.db')).size },
            settings: { count: await settingsDb.count({}), size: fs.statSync(path.join(__dirname, 'settings.db')).size }
        };
        res.json(stats);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

app.get('/api/admin/db/export', async (req, res) => {
    try {
        const backup = {
            version: '1.0',
            exportedAt: new Date().toISOString(),
            inventory: await db.find({}),
            sales: await salesDb.find({}),
            audit: await auditDb.find({}),
            users: await userDb.find({}),
            settings: await settingsDb.find({})
        };
        res.setHeader('Content-Type', 'application/json');
        res.setHeader('Content-Disposition', `attachment; filename=medai_backup_${new Date().toISOString().split('T')[0]}.json`);
        res.send(JSON.stringify(backup, null, 2));
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

app.post('/api/admin/db/import', async (req, res) => {
    const { backup } = req.body;
    try {
        if (!backup || !backup.inventory) throw new Error('Invalid backup format');
        
        // 1. Clear existing
        await db.remove({}, { multi: true });
        await salesDb.remove({}, { multi: true });
        await auditDb.remove({}, { multi: true });
        await userDb.remove({}, { multi: true });
        await settingsDb.remove({}, { multi: true });

        // 2. Insert new
        await db.insert(backup.inventory);
        await salesDb.insert(backup.sales);
        await auditDb.insert(backup.audit);
        await userDb.insert(backup.users);
        await settingsDb.insert(backup.settings);

        logEvent('admin', 'Database Restore', 'System restored from a manual backup file.');
        res.json({ success: true });
    } catch (err) {
        res.status(500).json({ success: false, message: err.message });
    }
});

const PORT = process.env.PORT || 5051;
app.listen(PORT, () => {
    console.log(`Server running on http://localhost:${PORT}`);
});
