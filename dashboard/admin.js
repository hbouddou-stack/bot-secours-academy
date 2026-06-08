// Extracted from admin.html script block 1, original line 7174.
window.addEventListener('error', function(e) {
    const errorDiv = document.createElement('div');
    errorDiv.style.cssText = 'position:fixed; top:0; left:0; width:100%; background:red; color:white; z-index:999999; padding:20px; font-size:16px; direction:ltr; text-align:left;';
    errorDiv.innerHTML = '<h2>JavaScript Error Caught:</h2><p>' + e.message + '</p><pre>' + (e.error ? e.error.stack : '') + '</pre>';
    document.body.appendChild(errorDiv);
});
window.addEventListener('unhandledrejection', function(e) {
    const errorDiv = document.createElement('div');
    errorDiv.style.cssText = 'position:fixed; top:0; left:0; width:100%; background:darkred; color:white; z-index:999999; padding:20px; font-size:16px; direction:ltr; text-align:left;';
    errorDiv.innerHTML = '<h2>Unhandled Promise Rejection:</h2><p>' + (e.reason ? (e.reason.message || e.reason) : 'Unknown reason') + '</p><pre>' + (e.reason ? e.reason.stack : '') + '</pre>';
    document.body.appendChild(errorDiv);
});

        // ─── App Global State ───

        const state = {

            customViews: JSON.parse(localStorage.getItem('admin_custom_views')) || [],

            userId: null,

            username: "مشرف",

            activeSheet: 'pending',

            fullSheetMode: (localStorage.getItem('admin_view_mode') || 'drawer') !== 'split',

            panoramicMode: false,

            viewMode: localStorage.getItem('admin_view_mode') || 'drawer', // 'split', 'drawer', or 'focus'

            adminRole: 'super_admin',

            firstName: "مشرف",

            pendingReports: [],

            pendingProposals: [],

            tickets: [],

            transcripts: [],

            currentItems: [],

            selectedItemIndex: 0,

            transcriptViewMode: 'single', // 'single' or 'thematic'

            filters: {

                search: '',

                type: 'all',

                subject: 'all',

                status: 'pending',
                sort: 'newest',
                year: 'all',
                academicYear: 'all',
                gender: 'all'
            },
            students: [],

            studentsFilters: {

                search: ''

            },

            dashboardScope: document.documentElement.dataset.dashboardScope || 'all'

        };

        const dashboardModes = {
            all: {
                title: "لوحة تحكم المشرفين | أكاديمية الباجي",
                logo: "🎓 أكاديمية <span>الباجي</span>",
                subtitle: "لوحة التحكم الشاملة"
            },
            bot: {
                title: "لوحة بوت التقييم | أكاديمية الباجي",
                logo: "🤖 بوت <span>التقييم</span>",
                subtitle: "تذاكر البوت والتقييمات"
            },
            support: {
                title: "لوحة دعم الأكاديمية | أكاديمية الباجي",
                logo: "🎓 دعم <span>الأكاديمية</span>",
                subtitle: "طلبات الطلاب والإدارة"
            }
        };

        function isMyClaim(item) {
            return item.claimedBy === state.firstName ||
                   item.claimedBy === state.username ||
                   ((state.userId === 2045194295 || state.adminRole === 'super_admin') && item.claimedBy === "Super Admin");
        }

        function isSupportAcademyItem(item) {
            const source = (item.source || '').toString().toLowerCase();
            const reportType = (item.reportType || '').toString().toLowerCase();
            const supportSources = ['academy_form', 'support_form', 'external', 'web', 'whatsapp', 'gmail', 'manual', 'zetude'];
            const supportTypes = ['schooling', 'payment', 'registration', 'inscription', 'exam', 'interface', 'access', 'account', 'administrative', 'admin'];
            return item.type === 'ticket' && (supportSources.includes(source) || supportTypes.includes(reportType));
        }

        function itemMatchesDashboardScope(item) {
            if (state.dashboardScope === 'support') return isSupportAcademyItem(item);
            if (state.dashboardScope === 'bot') return !isSupportAcademyItem(item);
            return true;
        }

        function applyDashboardModeText() {
            const mode = dashboardModes[state.dashboardScope] || dashboardModes.all;
            document.title = mode.title;
            const logo = document.querySelector('.sidebar-logo');
            if (logo) logo.innerHTML = mode.logo;
            const subtitle = document.querySelector('.sidebar-subtitle');
            if (subtitle) subtitle.textContent = mode.subtitle;
            document.getElementById('dashboard-mode-switcher')?.remove();
        }

        // ─── Sheets & View Management ───

        function selectSubjectFilter(subjectName) {

            state.filters.subject = subjectName;

            

            // Sync with select element in sidebar

            const selectEl = document.getElementById('filter-subject');

            if (selectEl) selectEl.value = subjectName;

            

            document.querySelectorAll('.subject-btn').forEach(btn => btn.classList.remove('active'));

            const activeBtn = document.getElementById(`subj-btn-${subjectName}`) || document.querySelector(`[data-subject="${subjectName}"]`);

            if (activeBtn) activeBtn.classList.add('active');

            if (state.dashboardScope === 'question_bank') {
                loadQuestions();
            } else {
                renderInbox();
            }

        }

        function onSubjectSelectChange() {

            const val = document.getElementById('filter-subject').value;

            selectSubjectFilter(val);

        }

        function toggleFilterSidebar() {

            const sidebar = document.getElementById('filter-sidebar');

            const btnText = document.getElementById('btn-toggle-filters-text');

            if (!sidebar) return;

            

            sidebar.classList.toggle('collapsed');

            

            if (sidebar.classList.contains('collapsed')) {

                sidebar.style.display = 'none';

                if (btnText) btnText.textContent = 'إظهار الفلاتر';

            } else {

                sidebar.style.display = 'flex';

                if (btnText) btnText.textContent = 'إخفاء الفلاتر';

            }

        }

        function switchSheet(sheetName) {

            state.activeSheet = sheetName;
            state.activeTab = 'inbox';

            renderInbox();

            if (typeof switchTab === 'function') {

                switchTab('inbox');

            }

        }

        window.switchSheet = switchSheet;

        window.switchTicketScope = function(scope, sheetName) {
            state.dashboardScope = scope;
            switchSheet(sheetName);
        };

        function clickSidebarSettings() {

            state.activeTab = 'inbox';

            switchSheet('config');

        }

        window.clickSidebarSettings = clickSidebarSettings;

        window.switchViewMode = function(mode) {

            state.viewMode = mode;

            localStorage.setItem('admin_view_mode', mode);

            state.fullSheetMode = (mode !== 'split');

            

            renderInbox();

            

            if (state.selectedItemIndex !== null && state.selectedItemIndex !== undefined) {

                selectDashboardItem(state.selectedItemIndex, true);

            }

            showToast("🖥️ وضع العرض: " + (mode === 'split' ? 'شاشة مقسمة' : (mode === 'focus' ? 'تركيز كامل' : 'عرض جانبي')), "success");

        };

        function closeDetailPanel() {

            state.fullSheetMode = true;

            const workspace = document.querySelector('.helpdesk-workspace');

            if (workspace) {

                workspace.classList.add('full-sheet-mode');

            }

            const detail = document.getElementById('helpdesk-detail');

            const backdrop = document.getElementById('drawer-backdrop');

            if (detail) detail.classList.remove('open');

            if (backdrop) backdrop.classList.remove('open');

            const btnIcon = document.getElementById('full-sheet-btn-icon');

            const btnText = document.getElementById('full-sheet-btn-text');

            if (btnIcon) btnIcon.textContent = '🖥️';

            if (btnText) btnText.textContent = 'ملء الشاشة';

        }

        // Close every open drawer/backdrop across all tabs to prevent cross-tab blocking

        function closeAllDrawers() {

            const drawers = [

                { el: 'helpdesk-detail',            bd: 'drawer-backdrop' },

                { el: 'transcript-detail-drawer',   bd: 'transcript-drawer-backdrop' },

                { el: 'question-detail-drawer',     bd: 'question-drawer-backdrop' },

                { el: 'qb-course-thematic-detail',  bd: 'qb-thematic-drawer-backdrop' },

                { el: 'qb-ai-generate-panel',       bd: 'qb-ai-generate-modal' },

                { el: 'student-detail-drawer',      bd: 'student-drawer-backdrop' },

            ];

            drawers.forEach(({ el, bd }) => {

                const panel = document.getElementById(el);

                const back  = document.getElementById(bd);

                if (panel) panel.classList.remove('open', 'show');

                if (back)  back.classList.remove('open', 'show');

            });

        }

        function toggleFullSheetMode() {

            state.fullSheetMode = !state.fullSheetMode;

            const workspace = document.querySelector('.helpdesk-workspace');

            const btnIcon = document.getElementById('full-sheet-btn-icon');

            const btnText = document.getElementById('full-sheet-btn-text');

            

            if (workspace) {

                if (state.fullSheetMode) {

                    workspace.classList.add('full-sheet-mode');

                    if (btnIcon) btnIcon.textContent = '🖥️';

                    if (btnText) btnText.textContent = 'ملء الشاشة';

                } else {

                    workspace.classList.remove('full-sheet-mode');

                    if (btnIcon) btnIcon.textContent = '📄';

                    if (btnText) btnText.textContent = 'وضع الفيشة';

                }

            }

        }

        // ─── Theme Management ───

        function initTheme() {

            const savedTheme = localStorage.getItem('admin-theme') || 'light';

            const btnIcon = document.getElementById('theme-toggle-icon');

            const btnLabel = document.getElementById('theme-toggle-label');

            const themeBtn = document.getElementById('theme-toggle');

            

            if (savedTheme === 'light') {

                document.documentElement.classList.add('light-theme');

                if (btnIcon && btnLabel) {

                    btnIcon.textContent = '☀️';

                    btnLabel.textContent = 'المظهر الفاتح';

                } else if (themeBtn) {

                    themeBtn.textContent = '☀️';

                }

                if (window.Telegram?.WebApp) {

                    window.Telegram.WebApp.setHeaderColor('#ffffff');

                    window.Telegram.WebApp.setBackgroundColor('#f8fafc');

                }

            } else {

                document.documentElement.classList.remove('light-theme');

                if (btnIcon && btnLabel) {

                    btnIcon.textContent = '🌙';

                    btnLabel.textContent = 'المظهر الداكن';

                } else if (themeBtn) {

                    themeBtn.textContent = '🌙';

                }

                if (window.Telegram?.WebApp) {

                    window.Telegram.WebApp.setHeaderColor('#131926');

                    window.Telegram.WebApp.setBackgroundColor('#090d16');

                }

            }

        }

        function toggleSidebarSection(sectionId) {

            const section = document.getElementById(sectionId);

            if (section) {

                section.classList.toggle('collapsed');

            }

        }

        window.toggleSidebarSection = toggleSidebarSection;

        function toggleTheme() {

            const isLight = document.documentElement.classList.toggle('light-theme');

            localStorage.setItem('admin-theme', isLight ? 'light' : 'dark');

            

            const btnIcon = document.getElementById('theme-toggle-icon');

            const btnLabel = document.getElementById('theme-toggle-label');

            const themeBtn = document.getElementById('theme-toggle');

            

            if (btnIcon && btnLabel) {

                btnIcon.textContent = isLight ? '☀️' : '🌙';

                btnLabel.textContent = isLight ? 'المظهر الفاتح' : 'المظهر الداكن';

            } else if (themeBtn) {

                themeBtn.textContent = isLight ? '☀️' : '🌙';

            }

            

            if (window.Telegram?.WebApp) {

                if (isLight) {

                    window.Telegram.WebApp.setHeaderColor('#ffffff');

                    window.Telegram.WebApp.setBackgroundColor('#f8fafc');

                } else {

                    window.Telegram.WebApp.setHeaderColor('#131926');

                    window.Telegram.WebApp.setBackgroundColor('#090d16');

                }

            }

        }

        // Initialize Telegram WebApp

        const tg = window.Telegram?.WebApp;

        if (tg) {

            tg.expand();

            tg.ready();

            

            // Set header & background color

            tg.setHeaderColor('#131926');

            tg.setBackgroundColor('#090d16');

        }

        // ─── Lifecycle / Startup ───

        window.addEventListener('DOMContentLoaded', () => {

            applyDashboardModeText();

            initTheme();

            detectUser();

        });

        function detectUser() {

            try {

                // Check URL parameters for state.userId bypass

                const urlParams = new URLSearchParams(window.location.search);

                const urlAdminId = urlParams.get('state.userId');

                if (urlAdminId) {

                    state.userId = parseInt(urlAdminId);

                    state.username = "admin_url";

                    state.firstName = "مشرف بالرابط";

                    document.getElementById('admin-name').textContent = state.firstName;

                    loadDashboardData();

                    return;

                }

                // Check if we are truly inside a Telegram WebApp (not just the SDK loaded)

                const user = tg && tg.initDataUnsafe && tg.initDataUnsafe.user;

                if (user && user.id) {

                    state.userId = user.id;

                    state.username = user.username || `user_${user.id}`;

                    state.firstName = user.first_name || "مشرف";

                    document.getElementById('admin-name').textContent = state.firstName;

                    loadDashboardData();

                } else {

                    // Not in Telegram — show manual login overlay

                    document.getElementById('config-overlay').style.display = 'flex';

                }

            } catch(e) {

                document.getElementById('config-overlay').style.display = 'flex';

            }

        }

        function submitManualUserId() {

            const input = document.getElementById('manual-user-id').value;

            if (!input) {

                showToast("⚠️ يرجى إدخال معرف صحيح", "error");

                return;

            }

            state.userId = parseInt(input);

            state.username = `admin_test`;

            state.firstName = "مشرف تجريبي";

            

            document.getElementById('config-overlay').style.display = 'none';

            document.getElementById('admin-name').textContent = state.firstName;

            loadDashboardData();

        }

        function arabicRoleLabel(role) {

            switch (role) {

                case 'super_admin': return 'مدير عام';

                case 'backup_admin': return 'مدير احتياطي';

                case 'support_admin': return 'الدعم التقني';

                case 'moderator': return 'مراجعة المحتوى';

                case 'improvement_admin': return 'التطوير والتحسين';

                default: return 'مشرف';

            }

        }

        // ─── API Integrations & Data Load ───

        async function loadDashboardData(silent = false) {

            try {
                if (window.__botConfigReady) {
                    await window.__botConfigReady;
                }

                if (!silent) showToast("🔄 جاري مزامنة البيانات...", "info");

                

                // Fetch admin info first to determine role and customize display

                try {

                    const infoRes = await fetch('/admin/info', {

                        method: 'POST',

                        headers: { 'Content-Type': 'application/json' },

                        body: JSON.stringify({ userId: state.userId })

                    });

                    const infoData = await infoRes.json();

                    if (infoData.success) {

                        state.firstName = infoData.info.firstName || state.firstName;

                        state.username = infoData.info.username || state.username;

                        state.adminRole = infoData.info.role || "moderator";

                        state.allowedSubjects = infoData.info.allowedSubjects || null; // null = all

                        state.visibleSections = infoData.info.visibleSections || null; // null = all

                        document.getElementById('admin-name').textContent = `${state.firstName} (${arabicRoleLabel(state.adminRole)})`;

                        

                        // Apply UI Role Restrictions

                        const role = state.adminRole;

                        const configTab = document.getElementById('btn-tab-config');

                        if (configTab) {

                            configTab.style.display = (role === 'super_admin') ? 'flex' : 'none';

                        }

                        

                        const editorTab = document.getElementById('btn-tab-editor');

                        if (editorTab) {

                            editorTab.style.display = 'none';

                        }

                        

                        const questionsTab = document.getElementById('btn-tab-questions');

                        if (questionsTab) {

                            questionsTab.style.display = (role === 'super_admin' || role === 'improvement_admin' || role === 'academie_admin') ? 'flex' : 'none';

                        }

                        

                        const filterTypeEl = document.getElementById('filter-type');

                        if (filterTypeEl && (role === 'support_admin' || role === 'tech_admin')) {

                            Array.from(filterTypeEl.options).forEach(opt => {

                                if (opt.value === 'report' || opt.value === 'proposal') {

                                    opt.style.display = 'none';

                                }

                            });

                            if (state.filters.type !== 'ticket') {

                                filterTypeEl.value = 'ticket';

                                state.filters.type = 'ticket';

                            }

                        }

                        // ── Phase 2: Apply visible_sections from DB ──

                        applyVisibleSections(state.visibleSections, role);

                        // ── Phase 3: Load shared custom views from DB ──

                        loadSharedCustomViews();

                    }

                } catch (e) {

                    console.error("Could not fetch admin role info:", e);

                }

                

                // 1. Fetch pending reports

                const reportsRes = await fetch('/admin/reports', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({ userId: state.userId })

                });

                

                if (reportsRes.status === 403) {

                    if (!silent) showToast("❌ عذراً، ليس لديك صلاحيات المشرفين!", "error");

                    document.getElementById('admin-name').textContent = "مرفوض 🔒";

                    document.getElementById('badge-admin').style.borderColor = 'var(--danger)';

                    document.getElementById('inbox-feed').innerHTML = `

                        <div class="empty-feed" style="border-color: var(--danger);">

                            <div class="empty-feed-icon" style="color: var(--danger);">🔒</div>

                            <h3>تم رفض الوصول</h3>

                            <p style="margin-top: 8px;">معرف التليجرام الخاص بك (<b>${state.userId}</b>) غير مسجل في قائمة المشرفين المؤهلين للبوت البديل.</p>

                        </div>

                    `;

                    return;

                }

                

                const reportsData = await reportsRes.json();

                state.pendingReports = reportsData.success ? reportsData.reports : [];

                // 2. Fetch pending proposals

                try {
                    const proposalsRes = await fetch('/admin/proposals', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ userId: state.userId })
                    });
                    if (proposalsRes.ok) {
                        const proposalsData = await proposalsRes.json();
                        state.pendingProposals = proposalsData.success ? proposalsData.proposals : [];
                    } else { state.pendingProposals = []; }
                } catch(e) { state.pendingProposals = []; }

                // 3. Fetch tickets from question_reports (suggestions, tech, etc.)

                try {
                    const ticketsRes = await fetch('/admin/tickets', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ userId: state.userId })
                    });
                    if (ticketsRes.ok) {
                        const ticketsData = await ticketsRes.json();
                        state.tickets = ticketsData.success ? ticketsData.tickets : [];
                    } else { state.tickets = []; }
                } catch(e) { state.tickets = []; }

                // 3.5 Fetch canned responses templates

                try {

                    const cannedRes = await fetch('/admin/canned-responses', {

                        method: 'POST',

                        headers: { 'Content-Type': 'application/json' },

                        body: JSON.stringify({ userId: state.userId })

                    });

                    const cannedData = await cannedRes.json();

                    state.cannedResponses = cannedData.success ? cannedData.templates : [];

                } catch (cannedErr) {

                    console.error("Failed to load canned responses:", cannedErr);

                    state.cannedResponses = [];

                }

                // 4. Fetch course transcripts (lessons list)

                const transcriptsRes = await fetch('/transcripts.json');

                state.transcripts = await transcriptsRes.json();

                // Build displays

                updateSubjectButtons();

                renderInbox();

                updateStats();

                updateLessonFilterDropdown();

                if (!silent) showToast("✅ تمت المزامنة بنجاح", "success");

                

                // Initialize auto-refresh once

                if (!window.autoRefreshInitialized) {

                    window.autoRefreshInitialized = true;

                    setInterval(() => {

                        if (state.activeTab === 'inbox') {

                            loadDashboardData(true);

                        } else {

                            // Update stats even if we're not actively on the inbox tab to keep badge pulsing

                            loadDashboardData(true);

                        }

                    }, 30000);

                }

            } catch (err) {

                console.error("Error loading dashboard data:", err);

                if (!silent) showToast("❌ فشل تحميل البيانات من الخادم", "error");

            }

        }

        // ─── Stats Rendering ───

        function updateStats() {

            const pendingTotal = state.pendingReports.filter(r => r.status === 'pending').length + state.pendingProposals.filter(p => p.status === 'pending').length + (state.tickets || []).filter(t => t.status === 'pending').length;            if(document.getElementById('stat-pending-items')) document.getElementById('stat-pending-items').textContent = pendingTotal;

            if(document.getElementById('stat-active-users')) document.getElementById('stat-active-users').textContent = "نشط";

            

            // Badge counter on tab button

            const badge = document.getElementById('badge-inbox-total');

            if (pendingTotal > 0) {

                badge.textContent = pendingTotal;

                badge.style.display = 'inline-block';

            } else {

                badge.style.display = 'none';

            }

        }

        // --- ADMIN STATS DASHBOARD LOGIC ---
        window.loadDashboardStats = async function() {
            try {
                const res = await fetch('/admin/dashboard-stats', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ userId: state.userId })
                });
                const data = await res.json();
                if (!data.success) {
                    console.error('Failed to load stats:', data.error);
                    return;
                }
                const stats = data.stats;
                
                document.getElementById('stat-total-students').textContent = stats.total_students || 0;
                document.getElementById('stat-active-24h').textContent = stats.active_users_24h || 0;
                document.getElementById('stat-new-24h').textContent = stats.new_users_24h || 0;
                
                if (stats.success_rate) {
                    let total = stats.success_rate.total;
                    let correct = stats.success_rate.correct;
                    let rate = total > 0 ? Math.round((correct / total) * 100) : 0;
                    document.getElementById('stat-success-rate').textContent = rate + '%';
                }

                if (stats.gender_distribution) {
                    let totalGen = Object.values(stats.gender_distribution).reduce((a,b)=>a+b, 0);
                    let container = document.getElementById('gender-distribution-bars');
                    if (container) {
                        let html = '';
                        for (const [gender, count] of Object.entries(stats.gender_distribution)) {
                            let percentage = totalGen > 0 ? Math.round((count / totalGen) * 100) : 0;
                            let label = gender === 'homme' || gender === 'male' ? '👨 طلاب' : (gender === 'femme' || gender === 'female' ? '👩طالبات' : '❓غير محدد');
                            let color = gender === 'homme' || gender === 'male' ? '#3b82f6' : (gender === 'femme' || gender === 'female' ? '#ec4899' : '#9ca3af');
                            html += `
                            <div style="display: flex; align-items: center; justify-content: space-between; font-weight: 700; color: var(--text-primary); font-size: 0.95rem;">
                                <span>${label}</span>
                                <span>${count} (${percentage}%)</span>
                            </div>
                            <div style="width: 100%; background: rgba(255,255,255,0.05); height: 10px; border-radius: 10px; overflow: hidden; margin-bottom: 10px;">
                                <div style="width: ${percentage}%; background: ${color}; height: 100%; border-radius: 10px;"></div>
                            </div>
                            `;
                        }
                        container.innerHTML = html;
                    }
                }

                if (stats.top_students) {
                    let tbody = document.getElementById('top-students-table-body');
                    if (tbody) {
                        if (stats.top_students.length === 0) {
                            tbody.innerHTML = '<tr><td colspan="3" style="text-align:center; padding: 20px; color: var(--text-secondary);">لا توجد بيانات بعد</td></tr>';
                        } else {
                            let html = '';
                            stats.top_students.forEach((s, idx) => {
                                let medal = idx === 0 ? '🥇' : (idx === 1 ? '🥈' : (idx === 2 ? '🥉' : (idx + 1)));
                                html += `
                                <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                                    <td style="padding: 12px 10px; font-weight: 900; color: var(--gold); font-size: 1.1rem;">${medal}</td>
                                    <td style="padding: 12px 10px; font-weight: 700;">${s.first_name || 'طالب مجهول'} <div style="font-size: 0.75rem; color: var(--text-secondary); font-weight:normal;">@${s.username || '-'}</div></td>
                                    <td style="padding: 12px 10px; text-align: center; font-weight: 800; color: #10b981;" data-sort-value="${Number(s.answer_count) || 0}">${s.answer_count}</td>
                                </tr>
                                `;
                            });
                            tbody.innerHTML = html;
                        }
                    }
                }
            } catch (e) {
                console.error('Error loading dashboard stats:', e);
            }
        };

        // ─── Tab Switching ───
        function switchTab(tabId) {
            state.activeTab = tabId;
            closeAllDrawers(); // Prevent any open drawer from blocking the new tab
            
            if (tabId === 'stats') {
                window.loadDashboardStats();
            }

            

            // If switching away from inbox, ensure sheet is not config when coming back unless specifically clicked

            if (tabId !== 'inbox' && state.activeSheet === 'config') {

                state.activeSheet = 'pending';

            }

            // Update active state in buttons

            document.querySelectorAll('.tab-btn, .sidebar-btn').forEach(btn => btn.classList.remove('active'));

            let btnId = `btn-tab-${tabId}`;

            if (tabId === 'inbox') {

                if (state.activeSheet === 'config') {

                    btnId = 'btn-tab-config';

                } else if (state.activeSheet === 'my_tickets') {

                    btnId = 'btn-tab-my-tickets';

                } else if (state.dashboardScope === 'bot') {

                    btnId = 'btn-tab-bot-tickets';

                } else {

                    btnId = 'btn-tab-inbox';

                }

            } else if (tabId === 'transcripts') {

                // The التفريغ button kept its id as btn-tab-courses from the merge

                btnId = 'btn-tab-courses';

            }

            const activeBtn = document.getElementById(btnId);

            if (activeBtn) activeBtn.classList.add('active');

            // Update active state in panels

            document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.remove('active'));

            const activePanel = document.getElementById(`panel-${tabId}`);

            if (activePanel) activePanel.classList.add('active');

            // Toggle filter sidebar and its toggle button visibility based on active tab

            const filterSidebar = document.getElementById('filter-sidebar');

            const toggleFiltersBtn = document.getElementById('btn-toggle-filters');

            if (tabId === 'inbox' && state.activeSheet !== 'config') {

                if (filterSidebar) {

                    if (filterSidebar.classList.contains('collapsed')) {

                        filterSidebar.style.display = 'none';

                    } else {

                        filterSidebar.style.display = 'flex';

                    }

                }

                if (toggleFiltersBtn) toggleFiltersBtn.style.display = 'flex';

            } else {

                if (filterSidebar) filterSidebar.style.display = 'none';

                if (toggleFiltersBtn) toggleFiltersBtn.style.display = 'none';

            }

            if (tabId === 'students') {

                loadStudentsData();

            } else if (tabId === 'questions') {

                initQuestionBank();

            } else if (tabId === 'transcripts') {

                loadTranscripts();

            } else if (tabId === 'media') {

                loadMediaDashboard();

            }

        }

        window.switchTab = switchTab;

        window.openAdminsManagement = function() {
            switchSheet('config');
            setTimeout(() => {
                if (typeof window.switchSettingsTab === 'function') {
                    window.switchSettingsTab('admins');
                }
                if (typeof window.loadAdminsList === 'function') {
                    window.loadAdminsList();
                }
            }, 0);
        };

        // ─── INBOX RENDERING ───

        const SUBJECTS_AR = {

            "aqida": "العقيدة",

            "aqeeda": "العقيدة",

            "fiqh": "الفقه",

            "sira": "السيرة",

            "nahw": "النحو",

            "tajweed": "التجويد",

            "hadith": "الحديث",

            "tazkiyah": "التزكية"

        };

        SUBJECTS_AR.histoire = "histoire";

        const SUBJECT_COLORS = {

            all: "var(--gold-light)",

            aqida: "#3b82f6",

            aqeeda: "#3b82f6",

            fiqh: "#10b981",

            sira: "#f59e0b",

            nahw: "#8b5cf6",

            tajweed: "#ec4899",

            hadith: "#14b8a6",

            tazkiyah: "#059669",

            histoire: "#64748b"

        };

        const STATUS_AR = {

            pending: "قيد الانتظار",

            open: "مفتوحة",

            in_progress: "قيد المعالجة",

            transferred: "محالة للمختص",

            resolved: "تم الحل",

            closed: "مغلقة",

            approved: "مقبولة",

            accepted: "مقبولة",

            accepted_modified: "مقبولة مع تعديل",

            rejected: "مرفوضة",

            reviewed: "تمت المراجعة",

            replied: "تم الرد"

        };

        const REPORT_TYPE_AR = {

            suggestion: "اقتراح",

            question_error: "خطأ في سؤال",

            expl_error: "خطأ في الشرح",

            course_question: "سؤال في المقرر",

            tech: "مشكلة تقنية",

            content: "بلاغ محتوى",

            other: "رسالة أخرى"

        };

        const URGENCY_AR = {

            Critique: "عاجل جداً",

            "Élevé": "عالٍ",

            Eleve: "عالٍ",

            Moyen: "متوسط",

            Faible: "منخفض",

            critical: "عاجل جداً",

            high: "عالٍ",

            medium: "متوسط",

            low: "منخفض"

        };

        function normalizeStatus(status) {

            return (status || "pending").toString().toLowerCase();

        }

        function arabicSubject(subject) {

            const key = (subject || "").toString().toLowerCase();

            return SUBJECTS_AR[key] || subject || "غير محدد";

        }

        function arabicStatus(status) {

            return STATUS_AR[normalizeStatus(status)] || status || "غير محددة";

        }

        function arabicReportType(type) {

            return REPORT_TYPE_AR[type] || type || "رسالة أخرى";

        }

        function arabicUrgency(urgency) {

            return URGENCY_AR[urgency] || URGENCY_AR[(urgency || "").toString().toLowerCase()] || urgency || "متوسط";

        }

        function onFilterChange() {

            state.filters.search = document.getElementById('filter-search').value.toLowerCase().trim();

            state.filters.type = document.getElementById('filter-type').value;

            const subjectSelect = document.getElementById('filter-subject');

            if (subjectSelect) state.filters.subject = subjectSelect.value;

            state.filters.status = document.getElementById('filter-status').value;

            state.filters.sort = document.getElementById('filter-sort').value;

            

            const yearSelect = document.getElementById('filter-year');
            if (yearSelect) {
                state.filters.year = yearSelect.value;
                state.filters.academicYear = yearSelect.value;
            }
            

            const genderSelect = document.getElementById('filter-gender');

            if (genderSelect) state.filters.gender = genderSelect.value;

            

            renderInbox();

        }

        function isDoneStatus(status) {

            return ['resolved', 'approved', 'accepted', 'accepted_modified', 'reviewed', 'replied', 'closed'].includes(normalizeStatus(status));

        }

        function typeLabel(item) {

            if (item.type === 'report') return 'بلاغ محتوى';

            if (item.type === 'proposal') return 'سؤال مقترح';

            return arabicReportType(item.reportType);

        }

        function typeIcon(item) {

            if (item.type === 'report') return '🚩';

            if (item.type === 'proposal') return '💡';

            if (item.reportType === 'tech') return '🔧';

            if (item.reportType === 'suggestion') return '💡';

            if (item.reportType === 'question_error') return '🚩';

            return '📩';

        }

        function typePill(item) {

            let cls = 'pill-info';

            if (item.type === 'proposal' || item.reportType === 'suggestion') cls = 'pill-warn';

            if (item.type === 'report' || ['tech', 'question_error', 'expl_error'].includes(item.reportType)) cls = 'pill-danger';

            if (isDoneStatus(item.status)) cls = 'pill-ok';

            return `<span class="pill ${cls}">${typeIcon(item)} ${typeLabel(item)}</span>`;

        }

        function itemTitle(item) {

            if (item.type === 'report') return item.reportText || 'بلاغ بدون نص';

            if (item.type === 'proposal') return item.question || 'سؤال مقترح';

            return item.notes || 'تذكرة دعم';

        }

        function itemSubject(item) {

            if (item.type === 'ticket') return item.questionId ? `سؤال #${item.questionId}` : 'دعم عام';

            return arabicSubject(item.subject);

        }

        function subjectPill(item) {

            const raw = (item.subject || '').toString().toLowerCase();

            const label = item.subject ? arabicSubject(item.subject) : itemSubject(item);

            const color = SUBJECT_COLORS[raw] || '#64748b';

            return `<span class="pill pill-subject" style="background-color:${color};">${escapeHtml(label)}</span>`;

        }

        function collectInboxSubjects() {

            const subjects = new Set([

                "aqida",

                "fiqh",

                "sira",

                "nahw",

                "tajweed",

                "hadith",

                "tazkiyah"

            ]);

            state.pendingReports.forEach(item => item.subject && subjects.add(item.subject.toLowerCase()));

            state.pendingProposals.forEach(item => item.subject && subjects.add(item.subject.toLowerCase()));

            state.tickets.forEach(item => item.subject && subjects.add(item.subject.toLowerCase()));

            return Array.from(subjects).sort((a, b) => arabicSubject(a).localeCompare(arabicSubject(b)));

        }

        function updateSubjectButtons() {

            const container = document.getElementById('subject-buttons-container');

            if (!container) return;

            const subjects = collectInboxSubjects();

            const buttons = [

                `<span style="font-size: 0.8rem; color: var(--text-secondary); align-self: center; font-weight: 700; margin-left: 8px;">📚 المادة:</span>`,

                `<button class="subject-btn ${state.filters.subject === 'all' ? 'active' : ''} all" onclick="selectSubjectFilter('all')" id="subj-btn-all">الكل</button>`

            ];

            subjects.forEach(subject => {

                const color = SUBJECT_COLORS[subject] || "#64748b";

                const active = state.filters.subject === subject ? 'active' : '';

                const activeStyle = active ? `style="background-color:${color}!important;border-color:${color}!important;color:#fff!important;"` : '';

                buttons.push(`<button class="subject-btn ${active}" data-subject="${escapeHtml(subject)}" onclick='selectSubjectFilter(${JSON.stringify(subject)})' ${activeStyle}>${escapeHtml(arabicSubject(subject))}</button>`);

            });

            container.innerHTML = buttons.join('');

        }

        function statusPill(item) {

            const status = normalizeStatus(item.status);

            const cls = status === 'rejected' ? 'pill-danger' : (isDoneStatus(status) ? 'pill-ok' : 'pill-warn');

            const icon = status === 'rejected' ? '❌' : (isDoneStatus(status) ? '✅' : '⏳');

            return `<span class="pill ${cls}">${icon} ${arabicStatus(status)}</span>`;

        }

        function priorityPill(item) {

            if (item.type !== 'ticket') return '<span class="cell-muted">عادي</span>';

            const urgent = arabicUrgency(item.urgency);

            const danger = ['Critique', 'critical'].includes(item.urgency);

            return `<span class="pill ${danger ? 'pill-danger' : 'pill-warn'}">⚡ ${urgent}</span>`;

        }

        function priorityBadge(item) {

            if (item.type !== 'ticket') return '<span class="pill pill-neutral">عادي</span>';

            const urgent = arabicUrgency(item.urgency);

            const danger = ['Critique', 'critical'].includes(item.urgency);

            const high = ['Élevé', 'Ã‰levÃ©', 'high', 'Eleve'].includes(item.urgency);

            const cls = danger ? 'pill-danger' : (high ? 'pill-warn' : 'pill-neutral');

            return `<span class="pill ${cls}">⚡ ${urgent}</span>`;

        }

        function formatTime(dt) {

            if (!dt) return '-';

            let d = dt;

            if (!(d instanceof Date)) {

                if (typeof d === 'number') {

                    if (d < 10000000000) {

                        d = new Date(d * 1000);

                    } else {

                        d = new Date(d);

                    }

                } else if (typeof d === 'string') {

                    // Handle SQLite datetime string 'YYYY-MM-DD HH:MM:SS'

                    d = new Date(d.replace(' ', 'T'));

                } else {

                    return '-';

                }

            }

            if (isNaN(d.getTime())) return '-';

            return d.toLocaleString('ar-EG', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

        }

        function getSourceIcon(source) {

            const s = (source || 'telegram').toLowerCase();

            if (s === 'whatsapp') return '💬';

            if (s === 'gmail' || s === 'email') return '📧';

            if (s === 'platform' || s === 'web') return '🌐';

            return '📱';

        }

        function buildInboxItems() {

            const items = [];

            state.pendingReports.forEach(r => items.push({

                type: 'report',

                id: r.id,

                userId: r.userId,

                username: r.username,

                firstName: r.firstName,

                subject: r.subject,

                lessonNum: r.lessonNum,

                chapterIdx: r.chapterIdx,

                reportText: r.report,

                status: r.status || 'pending',

                adminReply: r.adminReply || '',

                timestamp: new Date(r.timestamp),

                source: r.source || 'telegram',

                contactInfo: r.contactInfo || '',

                claimedBy: r.claimedBy || '',

                tags: r.tags || [],
                mediaFileId: r.mediaFileId || '',
                mediaType: r.mediaType || '',
                academicYear: r.academicYear || r.academic_year || null
            }));
            state.pendingProposals.forEach(p => items.push({

                type: 'proposal',

                id: p.id,

                userId: p.userId,

                username: p.username,

                firstName: p.firstName,

                subject: p.subject,

                topic: p.topic,

                lesson: p.lesson,

                question: p.question,

                choiceA: p.choiceA,

                choiceB: p.choiceB,

                choiceC: p.choiceC,

                choiceD: p.choiceD,

                correctAnswer: p.correctAnswer,

                explanation: p.explanation,

                status: p.status || 'pending',

                adminReply: p.adminReply || '',

                timestamp: new Date(p.createdAt),

                source: p.source || 'telegram',

                contactInfo: p.contactInfo || '',

                claimedBy: p.claimedBy || '',

                tags: p.tags || [],
                mediaFileId: p.mediaFileId || '',
                mediaType: p.mediaType || '',
                academicYear: p.academicYear || p.academic_year || null
            }));
            (state.tickets || []).forEach(t => items.push({

                type: 'ticket',

                id: t.id,

                userId: t.userId,

                username: t.username,

                firstName: t.firstName,

                reportType: t.reportType,

                subject: t.subject || '',

                courseNumber: t.courseNumber,

                notes: t.notes,

                urgency: t.urgency,

                questionId: t.questionId,

                target: t.target,

                status: t.status || 'pending',

                adminReply: t.adminReply || '',

                timestamp: new Date(t.createdAt),

                source: t.source || 'telegram',

                contactInfo: t.contactInfo || '',

                claimedBy: t.claimedBy || '',

                tags: t.tags || [],
                mediaFileId: t.mediaFileId || '',
                mediaType: t.mediaType || '',
                academicYear: t.academicYear || t.academic_year || null
            }));
            // Filter items based on Admin Role

            let filteredItems = [...items];

            const role = state.adminRole || 'super_admin';

            if (role === 'support_admin') {

                // Support admins only see tech and other general tickets

                filteredItems = items.filter(i => i.type === 'ticket' && (i.reportType === 'tech' || i.reportType === 'other'));

            } else if (role === 'moderator' || role === 'improvement_admin') {

                // Pédagogique/Moderator only see content corrections, proposals, and question errors

                filteredItems = items.filter(i => i.type === 'report' || i.type === 'proposal' || (i.type === 'ticket' && i.reportType === 'question_error'));

            }

            

            filteredItems = filteredItems.filter(itemMatchesDashboardScope);

            return filteredItems;

        }

        function setPanoramicMode(enabled) {

            state.panoramicMode = enabled;

            renderInbox();

        }

        function selectAcademicYear(year) {
            state.filters.year = year;
            state.filters.academicYear = year;
            state.filters.subject = 'all'; // Reset subject filter when switching years
            const yearSelect = document.getElementById('filter-year');
            if (yearSelect) yearSelect.value = year;
            renderInbox();
        }
        function clickYearMatrixCell(subjectKey, yearKey) {
            state.panoramicMode = false;
            state.filters.year = yearKey;
            state.filters.academicYear = yearKey;
            state.filters.subject = subjectKey;
            

            const yearSelect = document.getElementById('filter-year');

            if (yearSelect) yearSelect.value = yearKey;

            const subjectFilterEl = document.getElementById('filter-subject');

            if (subjectFilterEl) subjectFilterEl.value = subjectKey;

            

            renderInbox();

        }

        function getYearMatrixCellBadge(allItems, subjectKey, yearKey) {

            let filtered = allItems;

            if (subjectKey === 'all_others') {

                const knownSubjects = ['aqida', 'fiqh', 'sira', 'nahw', 'tajweed', 'hadith', 'tazkiyah'];

                filtered = filtered.filter(i => !i.subject || !knownSubjects.includes(i.subject.toLowerCase()));

            } else {

                filtered = filtered.filter(i => i.subject && i.subject.toLowerCase() === subjectKey);

            }

            if (yearKey !== 'all') {

                filtered = filtered.filter(i => {

                    const y = i.academicYear || i.academic_year;

                    return y && y.toString() === yearKey.toString();

                });

            }

            filtered = filtered.filter(i => ['pending', 'open', 'in_progress', 'transferred'].includes(normalizeStatus(i.status)));

            const count = filtered.length;

            if (count === 0) return `<span class="matrix-badge zero">0</span>`;

            const urgentCount = filtered.filter(i => ['Critique', 'critical', 'Élevé', 'high', 'Eleve'].includes(i.urgency)).length;

            if (urgentCount > 0) {

                return `<span class="matrix-badge urgent" style="background:#ef4444; color:#fff; font-weight:800; border-radius:4px; padding:2px 6px;">${count} ⚡</span>`;

            }

            return `<span class="matrix-badge pending" style="background:#f59e0b; color:#000; font-weight:800; border-radius:4px; padding:2px 6px;">${count} 🔴</span>`;

        }

        function clickMatrixCell(subjectKey, sheetKey) {

            state.panoramicMode = false;

            state.activeSheet = sheetKey;

            state.filters.subject = subjectKey;

            

            // update selectors in UI if they exist

            const subjectFilterEl = document.getElementById('filter-subject');

            if (subjectFilterEl) {

                subjectFilterEl.value = subjectKey;

            }

            

            renderInbox();

        }

        function getMatrixCellBadge(allItems, subjectKey, sheetKey) {

            let filtered = allItems;

            

            // Filter by subject

            if (subjectKey === 'all_others') {

                const knownSubjects = ['aqida', 'fiqh', 'sira', 'nahw', 'tajweed', 'hadith', 'tazkiyah'];

                filtered = filtered.filter(i => !i.subject || !knownSubjects.includes(i.subject.toLowerCase()));

            } else {

                filtered = filtered.filter(i => i.subject && i.subject.toLowerCase() === subjectKey);

            }

            

            // Filter by sheet tab

            switch (sheetKey) {

                case 'pending':

                    filtered = filtered.filter(i => ['pending', 'open', 'in_progress', 'transferred'].includes(normalizeStatus(i.status)));

                    break;

                case 'urgent':

                    filtered = filtered.filter(i => ['Critique', 'critical', 'Élevé', 'high', 'Eleve'].includes(i.urgency) && ['pending', 'open', 'in_progress', 'transferred'].includes(normalizeStatus(i.status)));

                    break;

                case 'proposals':

                    filtered = filtered.filter(i => i.type === 'proposal' && ['pending'].includes(normalizeStatus(i.status)));

                    break;

                case 'resolved':

                    filtered = filtered.filter(i => isDoneStatus(i.status));

                    break;

                case 'rejected':

                    filtered = filtered.filter(i => normalizeStatus(i.status) === 'rejected');

                    break;

            }

            

            const count = filtered.length;

            if (count === 0) return `<span class="matrix-badge zero">0</span>`;

            

            return `<span class="matrix-badge ${sheetKey}">${count}</span>`;

        }

        function filterInboxItems(items) {

            let filtered = [...items];

            

            // 1. Filter by sheet tab

            if (state.activeSheet.startsWith('custom_')) {

                const cv = state.customViews.find(v => v.id === state.activeSheet);

                if (cv) {

                    filtered = filtered.filter(i => {

                        if (cv.filters.subject && cv.filters.subject !== 'all' && (i.subject || '').toLowerCase() !== cv.filters.subject.toLowerCase()) return false;

                        

                        if (cv.filters.status && cv.filters.status.length > 0) {

                            const normalized = normalizeStatus(i.status);

                            let statusMatch = false;

                            if (cv.filters.status.includes('pending') && ['pending', 'open', 'in_progress', 'transferred'].includes(normalized)) statusMatch = true;

                            if (cv.filters.status.includes('resolved') && isDoneStatus(normalized)) statusMatch = true;

                            if (cv.filters.status.includes('rejected') && normalized === 'rejected') statusMatch = true;

                            if (!statusMatch) return false;

                        }

                        if (cv.filters.urgency && cv.filters.urgency.length > 0) {

                            const isCrit = ['Critique', 'critical'].includes(i.urgency);

                            const isHigh = ['Élevé', 'high', 'Eleve'].includes(i.urgency);

                            const isNorm = !isCrit && !isHigh;

                            let urgMatch = false;

                            if (cv.filters.urgency.includes('critical') && isCrit) urgMatch = true;

                            if (cv.filters.urgency.includes('high') && isHigh) urgMatch = true;

                            if (cv.filters.urgency.includes('normal') && isNorm) urgMatch = true;

                            if (!urgMatch) return false;

                        }

                        if (cv.filters.tags && cv.filters.tags.length > 0) {

                            const itemTags = i.tags || [];

                            const hasAnyTag = cv.filters.tags.some(t => itemTags.includes(t));

                            if (!hasAnyTag) return false;

                        }

                        if (cv.filters.claimedBy === 'me') {

                            const isMyClaim = i.claimedBy === state.firstName || 

                                              i.claimedBy === state.username || 

                                              ((state.userId === 2045194295 || state.adminRole === 'super_admin') && i.claimedBy === "Super Admin");

                            if (!isMyClaim) return false;

                        }

                        return true;

                    });

                }

            } else {

                switch (state.activeSheet) {

                    case 'pending': // Non traités / Nouveaux

                        filtered = filtered.filter(i => ['pending', 'open'].includes(normalizeStatus(i.status)));

                        break;

                    case 'in_progress': // En cours de traitement

                        filtered = filtered.filter(i => ['in_progress', 'transferred'].includes(normalizeStatus(i.status)));

                        break;

                    case 'resolved': // Traités / Résolus

                        filtered = filtered.filter(i => isDoneStatus(i.status) || normalizeStatus(i.status) === 'rejected');

                        break;

                    case 'urgent': // Urgences actives

                        filtered = filtered.filter(i => ['Critique', 'critical', 'Élevé', 'high', 'Eleve'].includes(i.urgency) && ['pending', 'open', 'in_progress', 'transferred'].includes(normalizeStatus(i.status)));

                        break;

                    case 'my_tickets':

                        filtered = filtered.filter(i => isMyClaim(i) && ['pending', 'open', 'in_progress', 'transferred'].includes(normalizeStatus(i.status)));

                        break;

                    case 'all': // Tout

                    default:

                        break;

                }

            }

            // 2. Filter by type secondary filter

            if (state.filters.type !== 'all') {

                filtered = filtered.filter(item => item.type === state.filters.type);

            }

            if (state.filters.subject && state.filters.subject !== 'all') {

                filtered = filtered.filter(item => (item.subject || '').toLowerCase() === state.filters.subject.toLowerCase());

            }
            // Filter by Academic Year
            const selectedAcademicYear = state.filters.academicYear && state.filters.academicYear !== 'all'
                ? state.filters.academicYear
                : state.filters.year;
            if (selectedAcademicYear && selectedAcademicYear !== 'all') {
                filtered = filtered.filter(item => {
                    const y = item.academicYear || item.academic_year;
                    return y && y.toString() === selectedAcademicYear.toString();
                });
            }
            // Filter by Gender

            if (state.filters.gender && state.filters.gender !== 'all') {

                filtered = filtered.filter(item => {

                    const g = item.gender || 'indetermine';

                    return g && g.toString().toLowerCase() === state.filters.gender.toLowerCase();

                });

            }

            if (state.filters.search) {

                const query = state.filters.search;

                filtered = filtered.filter(item => {

                    const haystack = [

                        item.firstName,

                        item.username,

                        item.userId,

                        itemTitle(item),

                        itemSubject(item),

                        item.id

                    ].join(' ').toLowerCase();

                    return haystack.includes(query);

                });

            }

            filtered.sort((a, b) => state.filters.sort === 'newest' ? b.timestamp - a.timestamp : a.timestamp - b.timestamp);

            return filtered;

        }

        function renderInbox() {

            const feed = document.getElementById('inbox-feed');
            // Preserve current selected item info to restore after render
            const currentlySelected = state.currentItems && state.selectedItemIndex !== undefined && state.selectedItemIndex !== -1 ? state.currentItems[state.selectedItemIndex] : null;
            const selectedId = currentlySelected ? currentlySelected.id : null;
            const selectedType = currentlySelected ? currentlySelected.type : null;
            const detailPanel = document.getElementById('helpdesk-detail');
            const detailWasOpen = detailPanel ? detailPanel.classList.contains('open') : false;


            const allItems = buildInboxItems();

            const items = filterInboxItems(allItems);

            state.currentItems = items;

            state.selectedItemIndex = Math.min(state.selectedItemIndex || 0, Math.max(items.length - 1, 0));

            // Reset bulk selection state on every render

            if (typeof bulkState !== 'undefined') {

                bulkState.selectedIndices.clear();

                const bar = document.getElementById('bulk-actions-bar');

                if (bar) bar.classList.remove('show');

            }

            const nonTraitesCount = allItems.filter(i => ['pending', 'open'].includes(normalizeStatus(i.status))).length;

            const enCoursCount = allItems.filter(i => ['in_progress', 'transferred'].includes(normalizeStatus(i.status))).length;

            const traitesCount = allItems.filter(i => isDoneStatus(i.status) || normalizeStatus(i.status) === 'rejected').length;

            const urgentCount = allItems.filter(i => ['Critique', 'critical', 'Élevé', 'high', 'Eleve'].includes(i.urgency) && ['pending', 'open', 'in_progress', 'transferred'].includes(normalizeStatus(i.status))).length;

            

            // Re-define counts used in the summary cards to prevent Javascript crashes

            const openCount = nonTraitesCount + enCoursCount;

            const myOpenTicketsCount = allItems.filter(i => 

                isMyClaim(i) &&

                ['pending', 'open', 'in_progress', 'transferred'].includes(normalizeStatus(i.status))

            ).length;

            const proposalCount = allItems.filter(i => i.type === 'proposal' && normalizeStatus(i.status) === 'pending').length;

            const academicSubjects = [
                { key: 'aqida', label: 'العقيدة' },
                { key: 'fiqh', label: 'الفقه' },
                { key: 'sira', label: 'السيرة' },
                { key: 'nahw', label: 'النحو' },
                { key: 'tajweed', label: 'التجويد' },
                { key: 'hadith', label: 'الحديث' },
                { key: 'tazkiyah', label: 'التزكية' },
                { key: 'all_others', label: 'أخرى / دعم عام' }
            ];

            const yearCounts = {
                1: allItems.filter(i => (i.academicYear || i.academic_year) == 1).length,
                2: allItems.filter(i => (i.academicYear || i.academic_year) == 2).length,
                3: allItems.filter(i => (i.academicYear || i.academic_year) == 3).length,
                4: allItems.filter(i => (i.academicYear || i.academic_year) == 4).length
            };

            const yearMatrixRowsHtml = academicSubjects.map(subj => `
                <tr style="border-bottom:1px solid var(--border);">
                    <td style="padding:12px; text-align:right;"><strong>${subj.label}</strong></td>
                    <td class="matrix-cell" style="padding:12px; cursor:pointer;" onclick="clickYearMatrixCell('${subj.key}', 'all')">${getYearMatrixCellBadge(allItems, subj.key, 'all')}</td>
                    <td class="matrix-cell" style="padding:12px; cursor:pointer;" onclick="clickYearMatrixCell('${subj.key}', '1')">${getYearMatrixCellBadge(allItems, subj.key, '1')}</td>
                    <td class="matrix-cell" style="padding:12px; cursor:pointer;" onclick="clickYearMatrixCell('${subj.key}', '2')">${getYearMatrixCellBadge(allItems, subj.key, '2')}</td>
                    <td class="matrix-cell" style="padding:12px; cursor:pointer;" onclick="clickYearMatrixCell('${subj.key}', '3')">${getYearMatrixCellBadge(allItems, subj.key, '3')}</td>
                    <td class="matrix-cell" style="padding:12px; cursor:pointer;" onclick="clickYearMatrixCell('${subj.key}', '4')">${getYearMatrixCellBadge(allItems, subj.key, '4')}</td>
                </tr>
            `).join('');

            // Define subjects dynamically by Selected Academic Year
            const subjectsByYear = {
                'all': [
                    { key: 'aqida', label: 'العقيدة' },
                    { key: 'fiqh', label: 'الفقه' },
                    { key: 'sira', label: 'السيرة' },
                    { key: 'nahw', label: 'النحو' },
                    { key: 'tajweed', label: 'التجويد' },
                    { key: 'hadith', label: 'الحديث' },
                    { key: 'tazkiyah', label: 'التزكية' }
                ],
                '1': [
                    { key: 'aqida', label: 'العقيدة' },
                    { key: 'fiqh', label: 'الفقه' },
                    { key: 'sira', label: 'السيرة' },
                    { key: 'tajweed', label: 'التجويد' }
                ],
                '2': [
                    { key: 'tafsir', label: 'التفسير' },
                    { key: 'nahw', label: 'النحو' },
                    { key: 'hadith', label: 'الحديث' },
                    { key: 'tazkiyah', label: 'التزكية' }
                ],
                '3': [
                    { key: 'mustalah', label: 'مصطلح الحديث' },
                    { key: 'ousoul', label: 'أصول الفقه' },
                    { key: 'faraid', label: 'الفرائض' }
                ],
                '4': [
                    { key: 'adyan', label: 'مقارنة الأديان' },
                    { key: 'tarikh', label: 'التاريخ الإسلامي' },
                    { key: 'dawah', label: 'الدعوة' }
                ]
            };

            const selectedYear = state.filters.year || 'all';
            const activeSubjects = subjectsByYear[selectedYear] || subjectsByYear['all'];

            const yearColors = { 'all': 'var(--gold)', '1': '#10b981', '2': '#f59e0b', '3': '#3b82f6', '4': '#8b5cf6' };
            const selectedYearColor = yearColors[selectedYear] || 'var(--gold)';
            const activeTextColor = ['all', '2'].includes(selectedYear) ? '#000' : '#fff';

            const activeSubjectBadgesHtml = activeSubjects.map(subj => {
                // Count dynamic matching items for this subject under selected academic year
                let subjItems = allItems.filter(i => i.subject && i.subject.toLowerCase() === subj.key.toLowerCase());
                if (selectedYear !== 'all') {
                    subjItems = subjItems.filter(i => {
                        const y = i.academicYear || i.academic_year;
                        return y && y.toString() === selectedYear.toString();
                    });
                }
                const count = subjItems.length;
                const isActive = state.filters.subject.toLowerCase() === subj.key.toLowerCase();
                
                // Active styles matching year theme color
                const activeStyle = isActive 
                    ? `background: ${selectedYearColor} !important; border-color: ${selectedYearColor} !important; color: ${activeTextColor} !important; box-shadow: 0 4px 10px ${selectedYearColor}40 !important;`
                    : '';
                
                return `
                    <button class="subject-btn ${subj.key} ${isActive ? 'active' : ''}" onclick="selectSubjectFilter('${subj.key}')" data-subject="${subj.key}" id="subj-btn-${subj.key}" style="${activeStyle}">
                        ${subj.label} <span style="font-size: 0.7rem; font-weight: 800; background: ${isActive ? (['all', '2'].includes(selectedYear) ? 'rgba(0,0,0,0.15)' : 'rgba(255,255,255,0.2)') : 'rgba(255,255,255,0.08)'}; color: ${isActive ? activeTextColor : selectedYearColor}; padding: 2px 6px; border-radius: 4px;">${count}</span>
                    </button>
                `;
            }).join('');

            // Populate summary cards into the collapsible right filter sidebar
            const sidebarSummary = document.getElementById('sidebar-summary-container');
            if (sidebarSummary) {
                sidebarSummary.innerHTML = `
                    <div class="sidebar-summary-card" style="background-color: var(--bg); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 6px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center;">
                        <span style="font-size: 0.65rem; color: var(--text-secondary); font-weight: 700;">المهام المفتوحة</span>
                        <strong style="font-size: 1rem; color: var(--gold-light); font-weight: 800; margin-top: 2px;">${openCount}</strong>
                    </div>
                    <div class="sidebar-summary-card" style="background-color: var(--bg); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 6px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center;">
                        <span style="font-size: 0.65rem; color: var(--text-secondary); font-weight: 700;">تذاكري</span>
                        <strong style="font-size: 1rem; color: var(--gold-light); font-weight: 800; margin-top: 2px;">${myOpenTicketsCount}</strong>
                    </div>
                    <div class="sidebar-summary-card" style="background-color: var(--bg); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 6px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center;">
                        <span style="font-size: 0.65rem; color: var(--text-secondary); font-weight: 700;">العاجلة</span>
                        <strong style="font-size: 1rem; color: var(--gold-light); font-weight: 800; margin-top: 2px;">${urgentCount}</strong>
                    </div>
                    <div class="sidebar-summary-card" style="background-color: var(--bg); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 6px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center;">
                        <span style="font-size: 0.65rem; color: var(--text-secondary); font-weight: 700;">المراجعة</span>
                        <strong style="font-size: 1rem; color: var(--gold-light); font-weight: 800; margin-top: 2px;">${proposalCount}</strong>
                    </div>
                `;
            }

            const mainContentHtml = state.activeSheet === 'config' ? `
                                <button class="workbook-tab active">
                                    ⚙️ الإعدادات العامة
                                </button>
                            ` : state.activeSheet === 'courses' ? `
                                <button class="workbook-tab active">
                                    📚 إدارة المواد والمناهج
                                </button>
                            ` : `
                                <button class="workbook-tab ${state.activeSheet === 'all' ? 'active' : ''}" onclick="switchSheet('all')" id="sheet-tab-all">
                                    📁 الكل (Tout)
                                </button>
                                <button class="workbook-tab ${state.activeSheet === 'pending' ? 'active' : ''}" onclick="switchSheet('pending')" id="sheet-tab-pending">
                                    📥 غير معالجة (${nonTraitesCount})
                                </button>
                                <button class="workbook-tab ${state.activeSheet === 'in_progress' ? 'active' : ''}" onclick="switchSheet('in_progress')" id="sheet-tab-in_progress">
                                    🔄 قيد المعالجة (${enCoursCount})
                                </button>
                                <button class="workbook-tab ${state.activeSheet === 'resolved' ? 'active' : ''}" onclick="switchSheet('resolved')" id="sheet-tab-resolved">
                                    ✅ معالجة (${traitesCount})
                                </button>
                                <button class="workbook-tab ${state.activeSheet === 'urgent' ? 'active' : ''}" onclick="switchSheet('urgent')" id="sheet-tab-urgent">
                                    ⚡ العاجلة النشطة (${urgentCount})
                                </button>
                                ${(state.customViews || []).map(cv => `
                                    <button class="workbook-tab ${state.activeSheet === cv.id ? 'active' : ''}" onclick="switchSheet('${cv.id}')" style="position:relative; padding-right: ${state.adminRole === 'super_admin' || (!cv._fromDB && cv.createdBy === state.userId) ? '48px' : '30px'};">
                                        ${cv.icon || '📌'} ${escapeHtml(cv.name)}
                                        ${cv._fromDB && cv.isLocked ? '<span style="font-size:0.6rem; opacity:0.6;">🔒</span>' : ''}
                                        ${state.adminRole === 'super_admin' || (!cv._fromDB && cv.createdBy === state.userId) ? `
                                            <span onclick="event.stopPropagation(); editCustomViewFromTab('${cv.id}')" style="position:absolute; right:24px; top:50%; transform:translateY(-50%); color:var(--gold); font-size:11px; cursor:pointer;" title="تعديل العرض">✏️</span>
                                        ` : ''}
                                        <span onclick="deleteCustomView(event, '${cv.id}')" style="position:absolute; right:6px; top:50%; transform:translateY(-50%); color:var(--danger); font-size:12px; cursor:pointer;" title="حذف العرض">❌</span>
                                    </button>
                                `).join('')}
                                <button class="workbook-tab" onclick="openCustomViewModal()" style="border: 1px dashed var(--gold); background: transparent; color: var(--gold-dark); margin-right: 12px;">
                                    ➕ إضافة عرض جديد
                                </button>
                            `;

            feed.innerHTML = `
                <div class="helpdesk-workspace ${state.fullSheetMode ? 'full-sheet-mode' : ''} ${state.viewMode === 'split' ? 'view-mode-split' : (state.viewMode === 'focus' ? 'view-mode-focus' : 'view-mode-drawer')}">
                    <div class="helpdesk-table-wrap">
                        ${state.activeSheet !== 'config' && state.activeSheet !== 'courses' ? `
                            <!-- Beautiful 3D Academic Years Bar at the Top with Slide Switcher -->
                            <div class="academic-year-tabs" style="display: flex; gap: 12px; padding: 14px 18px; background: rgba(255, 255, 255, 0.02); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border-bottom: 1px solid rgba(255,255,255,0.08); direction: rtl; align-items: center; overflow-x: auto; border-radius: 8px 8px 0 0; margin-bottom: 0px;">
                                <span style="font-size: 0.8rem; font-weight: 800; color: var(--gold-light); margin-left: 14px; white-space: nowrap; display: flex; align-items: center; gap: 6px; text-shadow: 0 2px 4px rgba(0,0,0,0.5);">🎓 السنة الدراسية:</span>
                                
                                <button class="year-tab-3d" onclick="selectAcademicYear('all')" style="padding: 8px 16px; font-size: 0.8rem; font-weight: 700; border-radius: 8px; cursor: pointer; white-space: nowrap; transition: all 0.2s ease-in-out; border: 1px solid ${state.filters.year === 'all' ? 'var(--gold)' : 'rgba(255,255,255,0.08)'}; background: ${state.filters.year === 'all' ? 'linear-gradient(145deg, var(--gold-light), var(--gold-dark))' : 'rgba(255,255,255,0.05)'}; color: ${state.filters.year === 'all' ? '#000' : 'var(--text-secondary)'}; box-shadow: ${state.filters.year === 'all' ? '0 4px 12px rgba(212,175,55,0.35), inset 0 1px 2px rgba(255,255,255,0.4)' : 'none'}; transform: ${state.filters.year === 'all' ? 'translateY(-1px)' : 'translateY(0)'}; font-weight: ${state.filters.year === 'all' ? '800' : '700'};">
                                    📊 كل السنوات (${allItems.length})
                                </button>
                                
                                <button class="year-tab-3d" onclick="selectAcademicYear('1')" style="padding: 8px 16px; font-size: 0.8rem; font-weight: 700; border-radius: 8px; cursor: pointer; white-space: nowrap; transition: all 0.2s ease-in-out; border: 1px solid ${state.filters.year === '1' ? '#10b981' : 'rgba(255,255,255,0.08)'}; background: ${state.filters.year === '1' ? 'linear-gradient(145deg, #34d399, #059669)' : 'rgba(255,255,255,0.05)'}; color: ${state.filters.year === '1' ? '#fff' : 'var(--text-secondary)'}; box-shadow: ${state.filters.year === '1' ? '0 4px 12px rgba(16,185,129,0.35), inset 0 1px 2px rgba(255,255,255,0.4)' : 'none'}; transform: ${state.filters.year === '1' ? 'translateY(-1px)' : 'translateY(0)'}; font-weight: ${state.filters.year === '1' ? '800' : '700'};">
                                    🟢 السنة الأولى (${yearCounts[1]})
                                </button>
                                
                                <button class="year-tab-3d" onclick="selectAcademicYear('2')" style="padding: 8px 16px; font-size: 0.8rem; font-weight: 700; border-radius: 8px; cursor: pointer; white-space: nowrap; transition: all 0.2s ease-in-out; border: 1px solid ${state.filters.year === '2' ? '#f59e0b' : 'rgba(255,255,255,0.08)'}; background: ${state.filters.year === '2' ? 'linear-gradient(145deg, #fbbf24, #d97706)' : 'rgba(255,255,255,0.05)'}; color: ${state.filters.year === '2' ? '#000' : 'var(--text-secondary)'}; box-shadow: ${state.filters.year === '2' ? '0 4px 12px rgba(245,158,11,0.35), inset 0 1px 2px rgba(255,255,255,0.4)' : 'none'}; transform: ${state.filters.year === '2' ? 'translateY(-1px)' : 'translateY(0)'}; font-weight: ${state.filters.year === '2' ? '800' : '700'};">
                                    🟡 السنة الثانية (${yearCounts[2]})
                                </button>
                                
                                <button class="year-tab-3d" onclick="selectAcademicYear('3')" style="padding: 8px 16px; font-size: 0.8rem; font-weight: 700; border-radius: 8px; cursor: pointer; white-space: nowrap; transition: all 0.2s ease-in-out; border: 1px solid ${state.filters.year === '3' ? '#3b82f6' : 'rgba(255,255,255,0.08)'}; background: ${state.filters.year === '3' ? 'linear-gradient(145deg, #60a5fa, #2563eb)' : 'rgba(255,255,255,0.05)'}; color: ${state.filters.year === '3' ? '#fff' : 'var(--text-secondary)'}; box-shadow: ${state.filters.year === '3' ? '0 4px 12px rgba(59,130,246,0.35), inset 0 1px 2px rgba(255,255,255,0.4)' : 'none'}; transform: ${state.filters.year === '3' ? 'translateY(-1px)' : 'translateY(0)'}; font-weight: ${state.filters.year === '3' ? '800' : '700'};">
                                    🔵 السنة الثالثة (${yearCounts[3]})
                                </button>
                                
                                <button class="year-tab-3d" onclick="selectAcademicYear('4')" style="padding: 8px 16px; font-size: 0.8rem; font-weight: 700; border-radius: 8px; cursor: pointer; white-space: nowrap; transition: all 0.2s ease-in-out; border: 1px solid ${state.filters.year === '4' ? '#8b5cf6' : 'rgba(255,255,255,0.08)'}; background: ${state.filters.year === '4' ? 'linear-gradient(145deg, #a78bfa, #7c3aed)' : 'rgba(255,255,255,0.05)'}; color: ${state.filters.year === '4' ? '#fff' : 'var(--text-secondary)'}; box-shadow: ${state.filters.year === '4' ? '0 4px 12px rgba(139,92,246,0.35), inset 0 1px 2px rgba(255,255,255,0.4)' : 'none'}; transform: ${state.filters.year === '4' ? 'translateY(-1px)' : 'translateY(0)'}; font-weight: ${state.filters.year === '4' ? '800' : '700'};">
                                    🟣 السنة الرابعة (${yearCounts[4]})
                                </button>

                                <!-- 3D Hardware Sliding Switcher for View Mode -->
                                <div class="view-switch-3d" style="margin-right: auto; padding-right: 12px; display: flex; align-items: center; gap: 8px; direction: ltr;">
                                    <span style="font-size: 0.75rem; font-weight: 800; color: var(--text-secondary); direction: rtl; margin: 0; line-height: 1; display: inline-flex; align-items: center;">طريقة العرض:</span>
                                    <div class="switch-outer" onclick="setPanoramicMode(!state.panoramicMode)" style="position: relative; width: 110px; height: 32px; background: rgba(255, 255, 255, 0.05); border-radius: 16px; border: 1px solid rgba(255,255,255,0.08); box-shadow: inset 1px 1px 3px rgba(0,0,0,0.4), 1px 1px 2px rgba(255,255,255,0.05); cursor: pointer; display: flex; align-items: center; justify-content: space-between; padding: 0 8px; transition: all 0.3s ease;">
                                        <!-- Slider pill -->
                                        <div class="switch-slider" style="position: absolute; top: 2px; left: ${state.panoramicMode ? '56px' : '2px'}; width: 52px; height: 26px; background: linear-gradient(145deg, var(--gold-light), var(--gold-dark)); border-radius: 13px; box-shadow: 0 2px 5px rgba(0,0,0,0.5), inset 0 1px 1px rgba(255,255,255,0.4); transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1); z-index: 1;"></div>
                                        
                                        <!-- Text labels -->
                                        <span style="font-size: 0.7rem; font-weight: 800; color: ${state.panoramicMode ? 'var(--text-secondary)' : '#000'}; z-index: 2; pointer-events: none; transition: color 0.2s; line-height: 1; display: inline-flex; align-items: center; height: 100%;">📋 Liste</span>
                                        <span style="font-size: 0.7rem; font-weight: 800; color: ${state.panoramicMode ? '#000' : 'var(--text-secondary)'}; z-index: 2; pointer-events: none; transition: color 0.2s; line-height: 1; display: inline-flex; align-items: center; height: 100%;">📊 Grille</span>
                                    </div>
                                </div>
                            </div>

                            <!-- Dynamic Active Subject Quick Badges (centered sub-tabs navigation directly below the years) -->
                            ${!state.panoramicMode ? `
                                <div class="active-subject-badges" style="display: flex; gap: 12px; padding: 12px 18px; background: transparent; border-bottom: 1px solid rgba(255,255,255,0.06); direction: rtl; align-items: center; justify-content: center; overflow-x: auto; flex-wrap: wrap; width: 100%;">
                                    <span style="font-size: 0.75rem; font-weight: 800; color: var(--text-secondary); margin-left: 8px;">📚 المواد:</span>
                                    <button class="subject-btn all ${state.filters.subject === 'all' ? 'active' : ''}" onclick="selectSubjectFilter('all')" data-subject="all" style="${state.filters.subject === 'all' ? `background: ${selectedYearColor} !important; border-color: ${selectedYearColor} !important; color: ${activeTextColor} !important; box-shadow: 0 4px 10px ${selectedYearColor}40 !important;` : ''}">الكل</button>
                                    ${activeSubjectBadgesHtml}
                                </div>
                            ` : ''}
                        ` : ''}

                        <!-- Workbook sheets tabs connected directly to the table header -->
                        <div class="workbook-tabs" style="display: flex; align-items: flex-end; justify-content: flex-start; gap: 4px; padding-bottom: 0;">
                            ${mainContentHtml}
                        </div>

                        ${state.activeSheet === 'config' ? `
                            <!-- Settings Panel Slot -->
                            <div id="settings-panel-slot"></div>
                        ` : state.activeSheet === 'courses' ? `
                            <!-- Courses/Content Management Panel Slot -->
                            <div id="courses-panel-slot"></div>
                        ` : state.panoramicMode ? `
                            <!-- Interactive Matrix Grid View (Proposal B) -->
                            <div class="panoramic-grid-wrap" style="padding: 16px;">
                                <h3 style="color:var(--gold-light); margin-bottom:12px; font-weight:800; font-size:1.1rem; text-align:right;">📊 مصفوفة تذاكر الدعم والأسئلة (المواد ✖ السنوات الدراسية)</h3>
                                <table class="panoramic-table" style="width:100%; border-collapse:collapse; text-align:center;">
                                    <thead>
                                        <tr style="background:rgba(255,255,255,0.05);">
                                            <th style="padding:12px; font-weight:800; text-align:right;">المادة</th>
                                            <th style="padding:12px; font-weight:800;">📊 كل السنوات</th>
                                            <th style="padding:12px; font-weight:800;">🟢 السنة الأولى</th>
                                            <th style="padding:12px; font-weight:800;">🟡 السنة الثانية</th>
                                            <th style="padding:12px; font-weight:800;">🔵 السنة الثالثة</th>
                                            <th style="padding:12px; font-weight:800;">🟣 السنة الرابعة</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${yearMatrixRowsHtml}
                                    </tbody>
                                </table>
                            </div>
                        ` : `
                            <!-- Traditional List Table View -->
                            <table class="helpdesk-table">
                                <thead>
                                    <tr>
                                        <th style="width:36px; padding: 0 8px;">
                                            <input type="checkbox" id="bulk-select-all" title="تحديد الكل" onchange="toggleSelectAll(this)" style="cursor:pointer; width:15px; height:15px; accent-color: var(--gold);">
                                        </th>
                                        <th style="width:70px;">ID</th>
                                        <th style="width:140px;">النوع</th>
                                        <th style="width:100px;">الأولوية</th>
                                        <th style="width:115px;">الحالة</th>
                                        <th style="width:100px;">المادة</th>
                                        <th style="width:135px;">الطالب</th>
                                        <th>الملخص</th>
                                        <th style="width:100px;">التاريخ</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${items.length === 0 ? `
                                        <tr>
                                            <td colspan="9" style="text-align: center; padding: 48px;">
                                                <div class="empty-feed" style="border: none; background: transparent; padding: 0;">
                                                    <div class="empty-feed-icon">🎉</div>
                                                    <h3 style="color: var(--text-primary);">لا توجد نتائج تطابق خيارات التصفية!</h3>
                                                    <p style="margin-top: 8px; font-size: 0.85rem; color: var(--text-secondary);">يرجى تجربة معايير تصفية مختلفة أو البحث عن كلمات أخرى.</p>
                                                </div>
                                            </td>
                                        </tr>
                                    ` : items.map((item, index) => {
                                        const urgentClass = ['Critique', 'critical'].includes(item.urgency) ? 'row-critical' : (['Élevé', 'high', 'Eleve'].includes(item.urgency) ? 'row-high' : '');
                                        return `
                                        <tr id="helpdesk-row-${index}" class="${urgentClass}" data-item-index="${index}" data-item-id="${item.id}" data-item-type="${item.type}">
                                            <td style="padding: 0 8px;" onclick="event.stopPropagation()">
                                                <input type="checkbox" class="row-checkbox" data-index="${index}" onchange="onRowCheckboxChange(this)" style="cursor:pointer; width:15px; height:15px; accent-color: var(--gold);">
                                            </td>
                                            <td onclick="selectDashboardItem(${index})"><strong>#${item.id}</strong></td>
                                            <td onclick="selectDashboardItem(${index})">${typePill(item)}</td>
                                            <td onclick="selectDashboardItem(${index})">${priorityBadge(item)}</td>
                                            <td onclick="selectDashboardItem(${index})">${statusPill(item)}</td>
                                            <td onclick="selectDashboardItem(${index})">${subjectPill(item)}</td>
                                            <td onclick="selectDashboardItem(${index})">
                                                <span class="cell-title">${getSourceIcon(item.source)} ${item.firstName || 'طالب'}</span>
                                                ${item.academicYear ? `<span class="badge" style="background:#f3e8ff; color:#7e22ce; margin-right:4px;">السنة ${item.academicYear}</span>` : ''}
                                            </td>
                                            <td onclick="selectDashboardItem(${index})"><span class="cell-title">${itemTitle(item)} ${item.mediaFileId ? '📎' : ''}</span>${item.questionId ? `<span class="cell-muted">Question #${item.questionId}</span>` : ''}
                                                <div style="margin-top:4px;">
                                                    ${(item.tags || []).map(tag => `<span class="badge" style="background:#e0e7ff; color:#3730a3; border:1px solid #c7d2fe; margin-left:4px;">${escapeHtml(tag)}</span>`).join('')}
                                                </div>
                                            </td>
                                            <td onclick="selectDashboardItem(${index})" data-sort-value="${item.timestamp instanceof Date ? item.timestamp.getTime() : new Date(item.timestamp || 0).getTime()}"><span class="cell-muted">${formatTime(item.timestamp)}</span></td>
                                        </tr>
                                    `; }).join('')}
                                </tbody>
                            </table>
                        `}
                    </div>
                    <div id="drawer-backdrop" class="drawer-backdrop" onclick="closeDetailPanel()"></div>
                    <aside id="helpdesk-detail" class="helpdesk-detail-panel"></aside>
                </div>
            `;

            if (state.activeSheet === 'config') {
                loadConfigPanel();
            } else if (state.activeSheet === 'courses') {
                if (typeof window.loadCoursesPanel === 'function') {
                    window.loadCoursesPanel();
                } else if (typeof loadCoursesPanel === 'function') {
                    loadCoursesPanel();
                }
            } else {
                selectDashboardItem(state.selectedItemIndex, false);
            }
        }

        function selectDashboardItem(index, remember = true) {

            const item = state.currentItems[index];

            if (!item) return;

            if (remember) state.selectedItemIndex = index;

            document.querySelectorAll('.helpdesk-table tbody tr').forEach(row => row.classList.remove('active'));

            const row = document.getElementById(`helpdesk-row-${index}`);

            if (row) row.classList.add('active');

            

            const detail = document.getElementById('helpdesk-detail');

            if (detail) detail.innerHTML = renderItemDetail(item);

            if (remember) {

                const backdrop = document.getElementById('drawer-backdrop');

                if (detail) detail.classList.add('open');

                if (state.viewMode === 'drawer' && backdrop) {

                    backdrop.classList.add('open');

                } else if (backdrop) {

                    backdrop.classList.remove('open');

                }

                

                // Déclenchement automatique de la recherche d'historique (AI Match)

                const queryText = item.notes || item.reportText || item.report || '';

                if (queryText) {

                    setTimeout(() => {

                        window.fetchAiSuggestions(item.id, queryText);

                    }, 100);

                }

            }

        }

        function renderMetaGrid(item) {

            const yearBadge = item.academicYear ? `<span class="badge" style="background:#f3e8ff; color:#7e22ce;">السنة ${item.academicYear}</span>` : '<span class="cell-muted">-</span>';

            const sourceInfo = item.source && item.source !== 'telegram' 

                ? `<div class="detail-field"><span>المصدر</span><strong>${getSourceIcon(item.source)} ${item.source} ${item.contactInfo ? '('+item.contactInfo+')' : ''}</strong></div>`

                : '';

            const claimedByText = item.claimedBy 

                ? `<span style="color: var(--gold-light); font-weight: 700;">🙋‍♂️ ${item.claimedBy}</span>` 

                : '<span class="cell-muted">غير مستلمة</span>';

                

            return `

                <div class="detail-grid">

                    <div class="detail-field"><span>الرقم</span><strong>#${item.id}</strong></div>

                    <div class="detail-field"><span>الحالة</span><strong>${arabicStatus(item.status)}</strong></div>

                    <div class="detail-field"><span>الطالب</span><strong>${item.firstName || 'طالب'} ${item.username ? `@${item.username}` : ''}</strong></div>

                    <div class="detail-field"><span>المعرّف</span><strong>${item.userId || '-'}</strong></div>

                    ${sourceInfo}

                    <div class="detail-field"><span>المادة</span><strong>${subjectPill(item)}</strong></div>

                    <div class="detail-field"><span>السنة الدراسية</span><strong>${yearBadge}</strong></div>

                    <div class="detail-field"><span>التاريخ</span><strong>${formatTime(item.timestamp)}</strong></div>

                    <div class="detail-field"><span>المستلم</span><strong>${claimedByText}</strong></div>

                </div>

            `;

        }

        function renderDetailActionPanel(item) {

            if (item.type === 'report') {

                return `

                    <div class="detail-action-panel">

                        <div class="detail-action-title">✏️ Action directe</div>

                        <p>Ouvre exactement le cours et le bloc signales, corrige la transcription, puis reviens ici pour repondre et fermer le ticket.</p>

                        <div class="detail-action-list">

                            <button class="btn btn-secondary" onclick="openChapterInEditor('${item.subject}', ${item.lessonNum}, ${item.chapterIdx})">✏️ Ouvrir dans l'editeur</button>

                        </div>

                    </div>

                `;

            }

            if (item.type === 'proposal') {

                return `

                    <div class="detail-action-panel">

                        <div class="detail-action-title">💡 Revue du QCM proposé</div>

                        <p>Contrôle la question, les choix, la bonne réponse et l'explication. Vous pouvez éditer le QCM proposé directement ici avant de l'accepter pour l'intégrer parfaitement.</p>

                        <div class="detail-action-list">

                            <button class="btn btn-secondary" onclick="loadProposalEditor('${item.id}')">✏️ Éditer la proposition</button>

                        </div>

                        <div id="proposal-editor-slot-${item.id}"></div>

                    </div>

                `;

            }

            if (item.reportType === 'question_error' || item.questionId) {

                return `

                    <div class="detail-action-panel">

                        <div class="detail-action-title">🧩 Question a corriger</div>

                        <p>Ticket lie a la question #${item.questionId || '-'}${item.target ? ` (${item.target})` : ''}. Charge la question, corrige-la ici, puis reponds a l'eleve et ferme le ticket.</p>

                        <div class="detail-action-list">

                            <button class="btn btn-secondary" onclick="loadQuestionEditor('${item.id}', ${item.questionId || 0})">🧩 Charger l'editeur de question</button>

                        </div>

                        <div id="question-editor-slot-${item.id}"></div>

                    </div>

                `;

            }

        }

        function renderClaimNotice(item) {

            if (!item.claimedBy && ['pending', 'open'].includes(normalizeStatus(item.status))) {

                return `

                    <div class="detail-action-panel" style="margin: 12px 0; padding: 12px; border: 1px solid var(--gold); border-radius: var(--radius-sm); background: rgba(212,175,55,0.05); display: flex; flex-direction: column; gap: 8px;">

                        <div class="detail-action-title" style="color: var(--gold-light); font-size: 0.85rem; font-weight: 700; display: flex; align-items: center; gap: 6px; margin-bottom: 2px;">

                            🙋‍♂️ تذكرة غير مستلمة (Non assignée)

                        </div>

                        <p style="font-size: 0.75rem; margin: 0; color: var(--text-secondary); line-height: 1.4;">

                            هذه التذكرة لم يتم استلامها بعد من قبل أي مشرف. يرجى الضغط أدناه لتسجيل استلامها وتفادي العمل المزدوج عليها.

                        </p>

                        <button class="btn" style="background: var(--gold); color: #000; font-weight: 700; font-size: 0.8rem; border-radius: var(--radius-sm); padding: 8px; width: 100%; border: none; cursor: pointer; transition: all 0.2s;" onclick="claimTicket('${item.id}', '${item.type}')">

                            🙋‍♂️ استلام ومعالجة التذكرة (Prendre en charge)

                        </button>

                    </div>

                `;

            }

            if (item.claimedBy) {

                return `

                    <div class="detail-action-panel" style="margin: 12px 0; padding: 10px 12px; border: 1px solid var(--success); border-radius: var(--radius-sm); background: rgba(74,222,128,0.05); display: flex; align-items: center; gap: 8px;">

                        <span style="font-size: 1.1rem;">🙋‍♂️</span>

                        <div style="font-size: 0.75rem; color: var(--text-secondary);">

                            قيد المعالجة بواسطة: <strong style="color: var(--success);">${item.claimedBy}</strong>

                        </div>

                    </div>

                `;

            }

            return '';

        }

        window.applyCannedTemplate = function(textareaId, content) {

            if (!content) return;

            const tx = document.getElementById(textareaId);

            if (tx) {

                if (tx.value.trim().length > 0) {

                    tx.value = tx.value.trim() + "\n\n" + content;

                } else {

                    tx.value = content;

                }

                showToast("📝 تم تطبيق نموذج الرد", "success");

            }

            document.querySelectorAll('select[id^="template-select-"]').forEach(sel => sel.value = "");

        };

        function renderTagsSection(item) {

            const tags = item.tags || [];

            const pillsHtml = tags.map(tag => 

                `<span class="badge" style="background:#e0e7ff; color:#3730a3; border:1px solid #c7d2fe; display:inline-flex; align-items:center; gap:4px; margin:2px;">

                    ${escapeHtml(tag)}

                    <span onclick="removeTag('${item.id}', '${item.type}', '${escapeHtml(tag)}')" style="cursor:pointer;font-weight:bold;">×</span>

                </span>`

            ).join('');

            

            return `

                <div class="detail-action-panel" style="margin-top: 12px; padding: 12px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: rgba(255,255,255,0.02);">

                    <div class="detail-action-title" style="font-size: 0.85rem; font-weight: 700; margin-bottom: 6px; display: flex; align-items: center; gap: 6px;">

                        🏷️ العلامات الوصفية (Tags)

                    </div>

                    <div style="margin-bottom: 8px;">

                        ${pillsHtml || '<span style="font-size:0.75rem; color:var(--text-secondary);">لا توجد علامات (Aucun tag)</span>'}

                    </div>

                    <div style="display:flex; gap:6px;">

                        <input type="text" id="new-tag-${item.id}" placeholder="مثال: مراجعة الإدارة..." style="flex:1; padding:6px; border-radius:var(--radius-sm); border:1px solid var(--border); background:var(--bg); color:var(--text-primary); font-size:0.8rem;">

                        <button class="btn btn-secondary" onclick="addTag('${item.id}', '${item.type}')" style="padding:6px 10px; font-size:0.8rem;">إضافة</button>

                    </div>

                </div>

            `;

        }

        async function updateTagsBackend(itemId, itemType, newTags) {

            try {

                const res = await fetch('/admin/update-ticket-tags', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({

                        userId: state.userId,

                        itemId: itemId,

                        itemType: itemType,

                        tags: newTags

                    })

                });

                const data = await res.json();

                if (data.success) {

                    showToast("✅ تم تحديث العلامات", "success");

                    loadInbox(); // Reload inbox to refresh tags

                } else {

                    showToast("❌ خطأ: " + data.error, "error");

                }

            } catch (e) {

                showToast("❌ خطأ في الاتصال", "error");

            }

        }

        function addTag(itemId, itemType) {

            const input = document.getElementById(`new-tag-${itemId}`);

            if (!input) return;

            const tag = input.value.trim();

            if (!tag) return;

            

            const item = state.currentItems.find(i => i.id == itemId && i.type == itemType);

            if (!item) return;

            

            const tags = item.tags || [];

            if (!tags.includes(tag)) {

                tags.push(tag);

                updateTagsBackend(itemId, itemType, tags);

            }

            input.value = '';

        }

        function removeTag(itemId, itemType, tag) {

            const item = state.currentItems.find(i => i.id == itemId && i.type == itemType);

            if (!item) return;

            

            const tags = item.tags || [];

            const newTags = tags.filter(t => t !== tag);

            updateTagsBackend(itemId, itemType, newTags);

        }

        function renderMediaAttachment(item) {

            if (!item.mediaFileId) return '';

            const type = item.mediaType || 'document';

            let mediaHtml = '';

            if (type === 'photo') {

                mediaHtml = `<img src="/api/media?file_id=${item.mediaFileId}" style="max-width: 100%; max-height: 400px; border-radius: 8px; margin-top: 8px; cursor: pointer; object-fit: contain;" onclick="window.open(this.src, '_blank')">`;

            } else if (type === 'voice' || type === 'audio') {

                mediaHtml = `<audio controls src="/api/media?file_id=${item.mediaFileId}" style="width: 100%; margin-top: 8px;"></audio>`;

            } else {

                mediaHtml = `<a href="/api/media?file_id=${item.mediaFileId}" target="_blank" class="btn btn-secondary" style="margin-top: 8px; display: inline-block;">📎 تحميل المرفق (${type})</a>`;

            }

            return `

                <div class="detail-action-panel" style="margin-top: 12px; padding: 12px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: rgba(255,255,255,0.02);">

                    <div class="detail-action-title" style="font-size: 0.85rem; font-weight: 700; margin-bottom: 6px; display: flex; align-items: center; gap: 6px;">

                        📎 المرفقات (Fichiers joints)

                    </div>

                    ${mediaHtml}

                </div>

            `;

        }

        window.insertPlaceholderToTextarea = function(textareaId, placeholderText) {

            const tx = document.getElementById(textareaId);

            if (tx) {

                const start = tx.selectionStart;

                const end = tx.selectionEnd;

                const text = tx.value;

                tx.value = text.substring(0, start) + placeholderText + text.substring(end);

                tx.focus();

                tx.selectionStart = tx.selectionEnd = start + placeholderText.length;

            }

        };

        window.toggleElementVisibility = function(id) {

            const el = document.getElementById(id);

            const arrow = document.getElementById('tech-arrow-' + id.split('-').pop());

            if (el) {

                if (el.style.display === 'none') {

                    el.style.display = 'block';

                    if (arrow) arrow.textContent = '▼';

                } else {

                    el.style.display = 'none';

                    if (arrow) arrow.textContent = '▲';

                }

            }

        };

        function renderItemDetail(item) {

            const ticketIdBadge = item.id ? `<span style="display:inline-block; background:rgba(255,255,255,0.07); color:var(--text-secondary); font-family:monospace; font-size:0.72rem; padding:2px 7px; border-radius:4px; border:1px solid var(--border); letter-spacing:0.5px; vertical-align:middle; margin-right:6px;">#${String(item.id).slice(0, 8)}</span>` : '';

            const closeBtn = `<button class="close-detail-btn" onclick="closeDetailPanel()" title="إغلاق" style="min-width:32px; min-height:32px; font-size:1.1rem; display:flex; align-items:center; justify-content:center;">✕</button>`;

            

            // Sélecteur de mode de vue compact

            const modeSwitcher = `

                <div class="view-mode-switcher" style="display: inline-flex; background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 2px; gap: 2px; direction: ltr; margin: 0 12px; vertical-align: middle;">

                    <button class="btn btn-sm ${state.viewMode === 'split' ? 'btn-primary' : 'btn-secondary'}" onclick="switchViewMode('split')" style="padding: 4px 8px; font-size: 0.7rem; border: none; cursor: pointer; font-weight: bold;" title="Écran scindé">📊 Scindé</button>

                    <button class="btn btn-sm ${state.viewMode === 'drawer' ? 'btn-primary' : 'btn-secondary'}" onclick="switchViewMode('drawer')" style="padding: 4px 8px; font-size: 0.7rem; border: none; cursor: pointer; font-weight: bold;" title="Tiroir large">🗂️ Tiroir</button>

                    <button class="btn btn-sm ${state.viewMode === 'focus' ? 'btn-primary' : 'btn-secondary'}" onclick="switchViewMode('focus')" style="padding: 4px 8px; font-size: 0.7rem; border: none; cursor: pointer; font-weight: bold;" title="Focus Plein écran">🖥️ Focus</button>

                </div>

            `;

            const templates = state.cannedResponses || [];

            const dropdownId = `template-select-${item.id}`;

            const textareaId = item.type === 'report' ? `reply-report-${item.id}` : (item.type === 'proposal' ? `reply-proposal-${item.id}` : `reply-ticket-${item.id}`);

            

            const templateDropdownHtml = templates.length > 0 ? `

                <div style="margin-bottom: 8px;">

                    <select id="${dropdownId}" onchange="applyCannedTemplate('${textareaId}', this.value)" style="width: 100%; padding: 8px; border-radius: var(--radius-sm); background: var(--bg-card); color: var(--text-primary); border: 1px solid var(--border); font-size: 0.85rem; cursor: pointer; outline: none;">

                        <option value="">📝 اختر نموذج رد جاهز... (Canned response)</option>

                        ${templates.map(t => `<option value="${escapeHtml(t.content)}">${escapeHtml(t.title)}</option>`).join('')}

                    </select>

                </div>

            ` : `

                <div style="font-size: 0.75rem; color: var(--text-secondary); margin-bottom: 8px;">

                    📝 لا توجد نماذج ردود مسجلة. يمكنك إضافتها من صفحة الإعدادات.

                </div>

            `;

            // Boutons d'insertion rapide de placeholders

            const insertHelperHtml = `

                <div class="reply-insert-helper" style="display: flex; gap: 8px; margin: 6px 0; align-items: center; flex-wrap: wrap;">

                    <span style="font-size: 0.72rem; color: var(--text-secondary);">⚡ إدراج سريع (Insertion) :</span>

                    <button class="btn btn-secondary" onclick="insertPlaceholderToTextarea('${textareaId}', '${escapeHtml(item.firstName || 'طالب')}')" style="padding: 3px 8px; font-size: 0.75rem; border-radius: var(--radius-sm); border: 1px solid var(--border); background: var(--bg-card); cursor: pointer;">

                        👤 الإسم (${escapeHtml(item.firstName || 'طالب')})

                    </button>

                    ${item.username ? `

                    <button class="btn btn-secondary" onclick="insertPlaceholderToTextarea('${textareaId}', '@${escapeHtml(item.username)}')" style="padding: 3px 8px; font-size: 0.75rem; border-radius: var(--radius-sm); border: 1px solid var(--border); background: var(--bg-card); cursor: pointer;">

                        🏷️ المعرف (@${escapeHtml(item.username)})

                    </button>

                    ` : ''}

                </div>

            `;

            // Zone des suggestions d'historique de réponses (AI Match)

            const aiSuggestionsHtml = `

                <div id="ai-similarity-suggestions-${item.id}" style="margin: 12px 0; padding: 12px; border: 1px dashed var(--border); border-radius: var(--radius-sm); background: rgba(255,255,255,0.01);">

                    <span style="font-size: 0.78rem; color: var(--text-secondary);">⏳ جاري البحث عن إجابات مشابهة بالذكاء الاصطناعي...</span>

                </div>

            `;

            // Construction de la section technique (triage, tags, etc.) collapsable en bas

            let typeSelectorHtml = '';

            if (item.type === 'ticket') {

                typeSelectorHtml = `

                    <div class="detail-action-panel" style="margin-top: 12px; padding: 12px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: rgba(255,255,255,0.02);">

                        <div class="detail-action-title" style="font-size: 0.85rem; font-weight: 700; margin-bottom: 6px; display: flex; align-items: center; gap: 6px;">

                            🔄 تصنيف التذكرة (Triage)

                        </div>

                        <select onchange="updateTicketType('${item.id}', this.value)" style="width: 100%; padding: 8px; border-radius: var(--radius-sm); background: var(--bg-card); color: var(--text-primary); border: 1px solid var(--border); font-size: 0.85rem; cursor: pointer; outline: none;">

                            <option value="other" ${item.reportType === 'other' ? 'selected' : ''}>📩 رسالة عامة / أخرى (Other)</option>

                            <option value="tech" ${item.reportType === 'tech' ? 'selected' : ''}>🔧 مشكلة تقنية (Tech)</option>

                            <option value="suggestion" ${item.reportType === 'suggestion' ? 'selected' : ''}>💡 اقتراح (Suggestion)</option>

                            <option value="question_error" ${item.reportType === 'question_error' ? 'selected' : ''}>🚩 خطأ في سؤال (Question Error)</option>

                        </select>

                    </div>

                `;

            }

            const technicalSectionHtml = `

                <div class="ticket-technical-section" style="margin-top: 24px; padding-top: 16px; border-top: 1px solid var(--border);">

                    <div style="font-size: 0.85rem; font-weight: bold; color: var(--text-secondary); margin-bottom: 12px; cursor: pointer; display: flex; align-items: center; justify-content: space-between;" onclick="toggleElementVisibility('tech-details-${item.id}')">

                        <span>🛠️ تفاصيل تقنية وإعدادات التذكرة (Détails techniques)</span>

                        <span id="tech-arrow-tech-details-${item.id}" style="font-size:0.75rem;">▼</span>

                    </div>

                    <div id="tech-details-${item.id}" style="display: block;">

                        ${renderClaimNotice(item)}

                        ${renderMetaGrid(item)}

                        ${typeSelectorHtml}

                        ${renderTagsSection(item)}

                        ${renderDetailActionPanel(item)}

                    </div>

                </div>

            `;

            // Rendu final conditionnel selon le type

            if (item.type === 'report') {

                let chapterTitle = `المحور ${item.chapterIdx + 1}`;

                try {

                    const lesson = state.transcripts.find(l => l.subject === item.subject && l.lessonNum === item.lessonNum);

                    if (lesson?.thematic_blocks?.[item.chapterIdx]) chapterTitle = lesson.thematic_blocks[item.chapterIdx].title;

                } catch(e) {}

                

                return `

                    <div class="detail-head">

                        <div style="display:flex; align-items:center; gap:8px;">

                            ${closeBtn}

                            <div>

                                <h3>🚩 بلاغ محتوى ${ticketIdBadge}</h3>

                                <span class="cell-muted">${arabicSubject(item.subject)} ← الدرس ${item.lessonNum} ← ${chapterTitle}</span>

                            </div>

                        </div>

                        <div style="display:flex; align-items:center; gap:10px;">

                            ${modeSwitcher}

                            ${statusPill(item)}

                        </div>

                    </div>

                    <!-- Message étudiant (Bulle de dialogue principale) en haut -->

                    <div class="detail-section-title" style="margin-top: 12px;">📝 بلاغ الطالب (Message)</div>

                    <div class="detail-body" style="font-size: 1rem; padding: 16px; line-height: 1.5; background-color: var(--surface-hover); border-color: var(--border); font-weight: normal; margin-bottom: 12px;">

                        ${item.reportText || item.report || '-'}

                    </div>

                    ${renderMediaAttachment(item)}

                    ${aiSuggestionsHtml}

                    <!-- Zone de réponse -->

                    ${normalizeStatus(item.status) === 'pending' ? `

                        <div class="card-actions" style="margin-top: 16px;">

                            ${templateDropdownHtml}

                            ${insertHelperHtml}

                            <textarea id="reply-report-${item.id}" class="reply-textarea" style="min-height: 120px;" placeholder="اكتب ردك التوجيهي أو التصحيحي للطالب..."></textarea>

                            <div class="btn-group">

                                <button class="btn btn-primary" onclick="resolveReport('${item.id}')">✅ تم التعديل والإرسال للطالب</button>

                            </div>

                        </div>

                    ` : `

                        <div class="detail-section-title">رد الإدارة (Réponse admin)</div>

                        <div class="detail-body" style="background-color: rgba(16, 185, 129, 0.05); border-color: var(--success);">${item.adminReply || 'تم الحل'}</div>

                    `}

                    <!-- Détails techniques et configuration -->

                    ${technicalSectionHtml}

                `;

            }

            if (item.type === 'proposal') {

                return `

                    <div class="detail-head">

                        <div style="display:flex; align-items:center; gap:8px;">

                            ${closeBtn}

                            <div>

                                <h3>💡 سؤال مقترح ${ticketIdBadge}</h3>

                                <span class="cell-muted">${arabicSubject(item.subject)} ← الدرس ${item.lesson || '-'}</span>

                            </div>

                        </div>

                        <div style="display:flex; align-items:center; gap:10px;">

                            ${modeSwitcher}

                            ${statusPill(item)}

                        </div>

                    </div>

                    <!-- Question proposée en haut -->

                    <div class="detail-section-title" style="margin-top: 12px;">📝 السؤال المقترح (Question proposée)</div>

                    <div class="detail-body" style="font-size: 1rem; padding: 16px; background-color: var(--surface-hover); border-color: var(--border); margin-bottom: 12px;">

                        ${item.question || '-'}

                    </div>

                    <div class="detail-section-title">الاختيارات (Options de réponses)</div>

                    <div class="proposal-qcm-box" style="margin-bottom: 12px;">

                        <div class="proposal-choice ${item.correctAnswer === 'a' ? 'correct' : ''}">أ) ${item.choiceA || '-'}</div>

                        <div class="proposal-choice ${item.correctAnswer === 'b' ? 'correct' : ''}">ب) ${item.choiceB || '-'}</div>

                        ${item.choiceC ? `<div class="proposal-choice ${item.correctAnswer === 'c' ? 'correct' : ''}">ج) ${item.choiceC}</div>` : ''}

                        ${item.choiceD ? `<div class="proposal-choice ${item.correctAnswer === 'd' ? 'correct' : ''}">د) ${item.choiceD}</div>` : ''}

                    </div>

                    ${item.explanation ? `

                        <div class="detail-section-title">التفسير المرفق (Explication)</div>

                        <div class="detail-body" style="font-style: italic; margin-bottom: 12px;">${item.explanation}</div>

                    ` : ''}

                    ${renderMediaAttachment(item)}

                    <!-- Zone de décision admin -->

                    ${normalizeStatus(item.status) === 'pending' ? `

                        <div class="card-actions" style="margin-top: 16px;">

                            ${templateDropdownHtml}

                            ${insertHelperHtml}

                            <textarea id="reply-proposal-${item.id}" class="reply-textarea" style="min-height: 100px;" placeholder="أدخل تعليقك أو سبب القبول/الرفض..."></textarea>

                            <div class="btn-group">

                                <button class="btn btn-danger" onclick="resolveProposal('${item.id}', 'rejected')">❌ رفض المقترح</button>

                                <button class="btn btn-primary" onclick="resolveProposal('${item.id}', 'approved')">✅ قبول وإضافة لقائمة الأسئلة</button>

                            </div>

                        </div>

                    ` : `

                        <div class="detail-section-title">قرار الإدارة (Décision)</div>

                        <div class="detail-body" style="background-color: var(--surface-hover);">${item.adminReply || '-'}</div>

                    `}

                    <!-- Détails techniques et configuration -->

                    ${technicalSectionHtml}

                `;

            }

            // Type ticket (Défaut)

            return `

                <div class="detail-head">

                    <div style="display:flex; align-items:center; gap:8px;">

                        ${closeBtn}

                        <div>

                            <h3>${typeIcon(item)} ${arabicReportType(item.reportType)} ${ticketIdBadge}</h3>

                            <span class="cell-muted">${priorityBadge(item)}</span>

                        </div>

                    </div>

                    <div style="display:flex; align-items:center; gap:10px;">

                        ${modeSwitcher}

                        ${statusPill(item)}

                    </div>

                </div>

                <!-- Message de l'élève en haut -->

                <div class="detail-section-title" style="margin-top: 12px;">📝 رسالة الطالب (Message de l'étudiant)</div>

                <div class="detail-body" style="font-size: 1rem; padding: 16px; line-height: 1.5; background-color: var(--surface-hover); border-color: var(--border); font-weight: normal; margin-bottom: 12px;">

                    ${item.notes || '-'}

                </div>

                ${renderMediaAttachment(item)}

                ${aiSuggestionsHtml}

                <!-- Zone de réponse -->

                ${['pending', 'in_progress', 'open', 'transferred'].includes(normalizeStatus(item.status)) ? `

                    <div class="card-actions" style="margin-top: 16px;">

                        ${templateDropdownHtml}

                        ${insertHelperHtml}

                        <textarea id="reply-ticket-${item.id}" class="reply-textarea" style="min-height: 120px;" placeholder="اكتب ردك للطالب... سيصله مباشرة ${item.source === 'telegram' ? 'عبر التليجرام' : 'عبر ' + item.source}"></textarea>

                        <div class="btn-group">

                            <button class="btn btn-danger" onclick="resolveTicket('${item.id}', 'rejected')">❌ إغلاق دون رد</button>

                            <button class="btn btn-primary" onclick="resolveTicket('${item.id}', 'resolved')">✅ رد وإغلاق التذكرة</button>

                        </div>

                    </div>

                ` : `

                    <div class="detail-section-title">رد الإدارة (Réponse)</div>

                    <div class="detail-body" style="background-color: rgba(16, 185, 129, 0.05); border-color: var(--success);">${item.adminReply || '-'}</div>

                `}

                <!-- Détails techniques et configuration -->

                ${technicalSectionHtml}

            `;

        }

        async function claimTicket(ticketId, itemType) {

            try {

                showToast("⏳ جاري استلام التذكرة...", "info");

                const res = await fetch('/admin/tickets/claim', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({

                        userId: state.userId,

                        ticketId: ticketId,

                        itemType: itemType

                    })

                });

                const data = await res.json();

                if (data.success) {

                    showToast(`🙋‍♂️ تم استلام التذكرة بنجاح بواسطة ${data.claimedBy}`, "success");

                    if (itemType === 'report') {

                        state.pendingReports.forEach(r => { if (r.id == ticketId) { r.claimedBy = data.claimedBy; r.status = 'in_progress'; } });

                    } else if (itemType === 'proposal') {

                        state.pendingProposals.forEach(p => { if (p.id == ticketId) { p.claimedBy = data.claimedBy; p.status = 'in_progress'; } });

                    } else {

                        state.tickets.forEach(t => { if (t.id == ticketId) { t.claimedBy = data.claimedBy; t.status = 'in_progress'; } });

                    }

                    

                    if (state.activeSheet === 'unassigned') {

                        switchSheet('my_tickets');

                    } else {

                        renderInbox();

                    }

                    

                    // Re-locate and select the claimed ticket in the updated list view

                    const newIdx = state.currentItems.findIndex(i => i.id == ticketId && i.type === itemType);

                    if (newIdx !== -1) {

                        selectDashboardItem(newIdx, true);

                    } else if (state.currentItems.length > 0) {

                        selectDashboardItem(0, true);

                    }

                    updateStats();

                } else {

                    showToast("❌ خطأ أثناء استلام التذكرة: " + (data.error || ""), "error");

                }

            } catch (e) {

                console.error(e);

                showToast("❌ فشل الاتصال بالخادم", "error");

            }

        }

        // ─── Action Handlers: Resolve Report ───

        async function resolveReport(reportId) {

            const replyText = document.getElementById(`reply-report-${reportId}`).value.trim();

            if (!replyText) {

                showToast("⚠️ يرجى كتابة الرد التوجيهي للطالب أولاً", "error");

                return;

            }

            try {

                showToast("⏳ جاري الإرسال والمعالجة...", "info");

                const res = await fetch('/admin/resolve-report', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({

                        userId: state.userId,

                        reportId: reportId,

                        adminReply: replyText

                    })

                });

                const data = await res.json();

                

                if (data.success) {

                    showToast("🎉 تم حل البلاغ وإرسال رسالة شكر للطالب", "success");

                    // Remove from local list & render

                    state.pendingReports.forEach(r => { if (r.id == reportId) { r.status = 'resolved'; r.adminReply = replyText; } });

                    renderInbox();

                    updateStats();

                } else {

                    showToast("❌ خطأ أثناء المعالجة", "error");

                }

            } catch(e) {

                console.error(e);

                showToast("❌ عذراً، فشل الاتصال بالخادم", "error");

            }

        }

        // ─── Action Handlers: Resolve Proposal ───

        async function resolveProposal(proposalId, action) {

            const feedbackText = document.getElementById(`reply-proposal-${proposalId}`).value.trim();

            if (action === 'rejected' && !feedbackText) {

                showToast("⚠️ يرجى توضيح سبب رفض المقترح في حقل النص", "error");

                return;

            }

            try {

                showToast("⏳ جاري معالجة المقترح...", "info");

                const res = await fetch('/admin/resolve-proposal', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({

                        userId: state.userId,

                        proposalId: proposalId,

                        action: action,

                        rejectionReason: feedbackText,

                        adminFeedback: feedbackText

                    })

                });

                const data = await res.json();

                if (data.success) {

                    const statusMsg = action === 'approved' ? "🎉 تمت الموافقة وإضافة السؤال للبوت" : "💬 تم رفض المقترح وإشعار الطالب";

                    showToast(statusMsg, "success");

                    state.pendingProposals.forEach(p => { if (p.id == proposalId) { p.status = action; p.adminReply = feedbackText; } });

                    renderInbox();

                    updateStats();

                } else {

                    showToast("❌ خطأ أثناء معالجة القرار", "error");

                }

            } catch(e) {

                console.error(e);

                showToast("❌ فشل الاتصال بالخادم", "error");

            }

        }

        // ─── Action Handlers: Resolve Ticket (question_reports) ───

        async function resolveTicket(ticketId, action) {

            const replyText = document.getElementById(`reply-ticket-${ticketId}`)?.value.trim() || '';

            try {

                showToast("⏳ جاري إرسال الرد...", "info");

                const res = await fetch('/admin/resolve-ticket', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({

                        userId: state.userId,

                        ticketId: ticketId,

                        adminReply: replyText,

                        status: action

                    })

                });

                const data = await res.json();

                if (data.success) {

                    showToast(action === 'resolved' ? "✅ تم الرد وإغلاق التذكرة" : "❌ تم إغلاق التذكرة", "success");

                    state.tickets.forEach(t => { if (t.id == ticketId) { t.status = action; t.adminReply = replyText; } });

                    renderInbox();

                    updateStats();

                } else {

                    showToast("❌ خطأ أثناء معالجة التذكرة", "error");

                }

            } catch(e) {

                console.error(e);

                showToast("❌ فشل الاتصال بالخادم", "error");

            }

        }

        async function updateTicketType(ticketId, newType) {

            try {

                showToast("⏳ جاري تحديث تصنيف التذكرة...", "info");

                const res = await fetch('/admin/update-ticket-type', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({

                        userId: state.userId,

                        ticketId: ticketId,

                        reportType: newType

                    })

                });

                const data = await res.json();

                if (data.success) {

                    showToast("✅ تم تحديث تصنيف التذكرة بنجاح", "success");

                    state.tickets.forEach(t => { if (t.id == ticketId) { t.reportType = newType; } });

                    const currentIdx = state.selectedItemIndex;

                    renderInbox();

                    selectDashboardItem(currentIdx, true);

                    updateStats();

                } else {

                    showToast("❌ خطأ أثناء تحديث التصنيف: " + (data.error || ""), "error");

                }

            } catch(e) {

                console.error(e);

                showToast("❌ فشل الاتصال بالخادم", "error");

            }

        }

        window.fetchAiSuggestions = async function(itemId, queryText, useAi = false) {

            const container = document.getElementById(`ai-similarity-suggestions-${itemId}`);

            if (!container) return;

            

            const msg = useAi 

                ? "⏳ جاري البحث عن إجابات مشابهة بالذكاء الاصطناعي (Gemini)..." 

                : "⏳ جاري البحث المحلي عن إجابات مشابهة...";

            container.innerHTML = `<span style="font-size: 0.8rem; color: var(--text-secondary);">${msg}</span>`;

            

            try {

                const res = await fetch('/api/triage/match', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({ query: queryText, use_ai: useAi })

                });

                const data = await res.json();

                if (data.success && data.matches && data.matches.length > 0) {

                    let matchesHtml = `

                        <div style="font-size: 0.8rem; font-weight: 700; color: var(--gold-light); margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 6px;">

                            <span>🔍 إجابات مشابهة مقترحة (مطابقة ${useAi ? 'ذكاء اصطناعي' : 'محلية'}):</span>

                            ${!useAi ? `<button class="btn btn-secondary" style="padding: 2px 6px; font-size: 0.72rem; cursor: pointer; border-radius: var(--radius-sm); border: 1px solid var(--border); background: var(--bg-card);" onclick="fetchAiSuggestions('${itemId}', \`${escapeHtml(queryText)}\`, true)">🤖 تعميق البحث بالذكاء الاصطناعي</button>` : ''}

                        </div>

                        <div style="display: flex; flex-direction: column; gap: 8px; max-height: 250px; overflow-y: auto;">

                    `;

                    data.matches.forEach(m => {

                        const scorePercent = Math.round(m.score * 100);

                        const escapedAnswer = m.answer.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '&quot;').replace(/\n/g, '\\n');

                        matchesHtml += `

                            <div style="padding: 8px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--bg); cursor: pointer; transition: all 0.2s;" 

                                 onclick="applyAiSuggestion('${itemId}', '${escapedAnswer}')" 

                                 onmouseover="this.style.borderColor='var(--gold)'" 

                                 onmouseout="this.style.borderColor='var(--border)'"

                                 title="انقر لتطبيق هذا الرد">

                                <div style="display: flex; justify-content: space-between; font-size: 0.7rem; color: var(--text-secondary); margin-bottom: 4px;">

                                    <span>سؤال مشابه (طابق بنسبة ${scorePercent}%)</span>

                                    <span style="color: var(--gold-light); font-weight: bold;">نقرة لتطبيق الرد 👈</span>

                                </div>

                                <div style="font-size: 0.75rem; color: var(--text-secondary); font-style: italic; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 4px;">

                                    "${escapeHtml(m.question)}"

                                </div>

                                <div style="font-size: 0.8rem; color: var(--text-primary); line-height: 1.4;">

                                    ${escapeHtml(m.answer)}

                                </div>

                            </div>

                        `;

                    });

                    matchesHtml += `

                        </div>

                    `;

                    container.innerHTML = matchesHtml;

                } else {

                    container.innerHTML = `

                        <div style="font-size: 0.8rem; color: var(--text-secondary); display: flex; flex-direction: column; align-items: center; gap: 6px;">

                            <span>⚠️ لم نجد أي إجابات مشابهة كافية في قاعدة البيانات.</span>

                            <div style="display:flex; gap:6px;">

                                <button class="btn btn-secondary" style="font-size: 0.75rem; padding: 4px 8px;" onclick="fetchAiSuggestions('${itemId}', \`${escapeHtml(queryText)}\`, false)">🔄 إعادة المحاولة</button>

                                ${!useAi ? `<button class="btn btn-primary" style="font-size: 0.75rem; padding: 4px 8px; background: var(--gold); border:none; color:#000; font-weight:bold; cursor:pointer;" onclick="fetchAiSuggestions('${itemId}', \`${escapeHtml(queryText)}\`, true)">🤖 البحث بالذكاء الاصطناعي</button>` : ''}

                            </div>

                        </div>

                    `;

                }

            } catch (e) {

                console.error(e);

                container.innerHTML = `

                    <div style="font-size: 0.8rem; color: var(--danger); display: flex; flex-direction: column; align-items: center; gap: 6px;">

                        <span>❌ فشل الاتصال بالخادم للبحث.</span>

                        <button class="btn btn-secondary" style="font-size: 0.75rem; padding: 4px 8px;" onclick="resetAiSuggestionsContainer('${itemId}', \`${escapeHtml(queryText)}\`)">🔄 إعادة المحاولة</button>

                    </div>

                `;

            }

        };

        window.applyAiSuggestion = function(itemId, answerText) {

            const reportTextarea = document.getElementById(`reply-report-${itemId}`);

            const proposalTextarea = document.getElementById(`reply-proposal-${itemId}`);

            const ticketTextarea = document.getElementById(`reply-ticket-${itemId}`);

            const tx = reportTextarea || proposalTextarea || ticketTextarea;

            

            if (tx) {

                tx.value = answerText;

                showToast("📝 تم تطبيق الرد المقترح بالذكاء الاصطناعي", "success");

            }

        };

        window.resetAiSuggestionsContainer = function(itemId, queryText) {

            const container = document.getElementById(`ai-similarity-suggestions-${itemId}`);

            if (container) {

                container.innerHTML = `

                    <button class="btn btn-secondary" style="width: 100%; font-size: 0.8rem; padding: 6px 10px; display: flex; align-items: center; justify-content: center; gap: 6px;" onclick="fetchAiSuggestions('${itemId}', \`${escapeHtml(queryText)}\`)">

                        🔍 البحث عن إجابات مشابهة في قاعدة البيانات (AI Match)

                    </button>

                `;

            }

        };

        // ─── CONTENT EDITOR TAB FUNCTIONS ───

        function questionEditorField(ticketId, id) {

            const el = document.getElementById(`qe-${ticketId}-${id}`);

            return el ? el.value.trim() : "";

        }

        function escapeHtml(value) {

            return (value || '').toString()

                .replaceAll('&', '&amp;')

                .replaceAll('<', '&lt;')

                .replaceAll('>', '&gt;')

                .replaceAll('"', '&quot;')

                .replaceAll("'", '&#039;');

        }

        async function loadQuestionEditor(ticketId, questionId) {

            const slot = document.getElementById(`question-editor-slot-${ticketId}`);

            if (!slot) return;

            if (!questionId) {

                slot.innerHTML = `<div class="detail-inline-note">Aucune question liee a ce ticket.</div>`;

                return;

            }

            slot.innerHTML = `<div class="detail-inline-note">Chargement de la question #${questionId}...</div>`;

            try {

                const res = await fetch('/admin/question', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({ userId: state.userId, questionId })

                });

                const data = await res.json();

                if (!data.success) throw new Error(data.error || 'Question introuvable');

                const q = data.question;

                const correct = (q.correct_answer || '').toLowerCase();

                slot.innerHTML = `

                    <div class="question-editor-card">

                        <div class="detail-section-title">Edition directe de la question #${q.id}</div>

                        <div class="question-editor-grid">

                            <div>

                                <label>Question</label>

                                <textarea id="qe-${ticketId}-question" class="reply-textarea">${escapeHtml(q.question)}</textarea>

                            </div>

                            <div>

                                <label>Choix A</label>

                                <input id="qe-${ticketId}-choice-a" class="form-input" value="${escapeHtml(q.choice_a)}">

                            </div>

                            <div>

                                <label>Choix B</label>

                                <input id="qe-${ticketId}-choice-b" class="form-input" value="${escapeHtml(q.choice_b)}">

                            </div>

                            <div>

                                <label>Choix C</label>

                                <input id="qe-${ticketId}-choice-c" class="form-input" value="${escapeHtml(q.choice_c)}">

                            </div>

                            <div>

                                <label>Choix D</label>

                                <input id="qe-${ticketId}-choice-d" class="form-input" value="${escapeHtml(q.choice_d)}">

                            </div>

                            <div>

                                <label>Bonne reponse</label>

                                <select id="qe-${ticketId}-correct" class="form-select">

                                    <option value="a" ${correct === 'a' ? 'selected' : ''}>A</option>

                                    <option value="b" ${correct === 'b' ? 'selected' : ''}>B</option>

                                    <option value="c" ${correct === 'c' ? 'selected' : ''}>C</option>

                                    <option value="d" ${correct === 'd' ? 'selected' : ''}>D</option>

                                </select>

                            </div>

                            <div>

                                <label>Explication</label>

                                <textarea id="qe-${ticketId}-explanation" class="reply-textarea">${escapeHtml(q.explanation)}</textarea>

                            </div>

                            <div style="grid-column: 1 / -1; margin-bottom: 10px;">

                                <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">

                                    <input type="checkbox" id="qe-${ticketId}-active" ${q.is_active !== 0 ? 'checked' : ''} style="width: 18px; height: 18px;">

                                    <span>✅ Question active (Décochez pour masquer temporairement)</span>

                                </label>

                            </div>

                            <button class="btn btn-primary" style="grid-column: 1 / -1;" onclick="saveQuestionEdit('${ticketId}', ${q.id})">💾 Enregistrer la correction</button>

                        </div>

                    </div>

                `;

            } catch (err) {

                slot.innerHTML = `<div class="detail-inline-note">Impossible de charger la question : ${err.message}</div>`;

            }

        }

        async function saveQuestionEdit(ticketId, questionId) {

            const activeEl = document.getElementById(`qe-${ticketId}-active`);

            const payload = {

                userId: state.userId,

                questionId,

                question: questionEditorField(ticketId, 'question'),

                choiceA: questionEditorField(ticketId, 'choice-a'),

                choiceB: questionEditorField(ticketId, 'choice-b'),

                choiceC: questionEditorField(ticketId, 'choice-c'),

                choiceD: questionEditorField(ticketId, 'choice-d'),

                correctAnswer: questionEditorField(ticketId, 'correct'),

                explanation: questionEditorField(ticketId, 'explanation'),

                isActive: activeEl ? activeEl.checked : true

            };

            if (!payload.question || !payload.choiceA || !payload.choiceB) {

                showToast("Question et choix A/B obligatoires", "error");

                return;

            }

            try {

                showToast("Sauvegarde de la question...", "info");

                const res = await fetch('/admin/update-question', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify(payload)

                });

                const data = await res.json();

                if (!data.success) throw new Error(data.error || 'Echec de sauvegarde');

                showToast("Question corrigee", "success");

                const replyEl = document.getElementById(`reply-ticket-${ticketId}`);

                if (replyEl && !replyEl.value.trim()) {

                    replyEl.value = "تم تصحيح السؤال، شكراً على تنبيهك ومساعدتك في تحسين المحتوى.";

                }

            } catch (err) {

                showToast(err.message, "error");

            }

        }

        function loadProposalEditor(ticketId) {

            const slot = document.getElementById(`proposal-editor-slot-${ticketId}`);

            if (!slot) return;

            const item = state.currentItems.find(i => String(i.id) === String(ticketId));

            if (!item) return;

            const correct = (item.correctAnswer || '').toLowerCase();

            slot.innerHTML = `

                <div class="question-editor-card" style="margin-top: 12px; border-top: 1px dashed var(--border-color); padding-top: 12px;">

                    <div class="detail-section-title">✏️ Édition de la proposition</div>

                    <div class="question-editor-grid">

                        <div>

                            <label>Question</label>

                            <textarea id="pe-${ticketId}-question" class="reply-textarea">${escapeHtml(item.question || '')}</textarea>

                        </div>

                        <div>

                            <label>Choix A</label>

                            <input id="pe-${ticketId}-choice-a" class="form-input" value="${escapeHtml(item.choiceA || '')}">

                        </div>

                        <div>

                            <label>Choix B</label>

                            <input id="pe-${ticketId}-choice-b" class="form-input" value="${escapeHtml(item.choiceB || '')}">

                        </div>

                        <div>

                            <label>Choix C</label>

                            <input id="pe-${ticketId}-choice-c" class="form-input" value="${escapeHtml(item.choiceC || '')}">

                        </div>

                        <div>

                            <label>Choix D</label>

                            <input id="pe-${ticketId}-choice-d" class="form-input" value="${escapeHtml(item.choiceD || '')}">

                        </div>

                        <div>

                            <label>Bonne réponse</label>

                            <select id="pe-${ticketId}-correct" class="form-select">

                                <option value="a" ${correct === 'a' ? 'selected' : ''}>A</option>

                                <option value="b" ${correct === 'b' ? 'selected' : ''}>B</option>

                                <option value="c" ${correct === 'c' ? 'selected' : ''}>C</option>

                                <option value="d" ${correct === 'd' ? 'selected' : ''}>D</option>

                            </select>

                        </div>

                        <div>

                            <label>Explication</label>

                            <textarea id="pe-${ticketId}-explanation" class="reply-textarea">${escapeHtml(item.explanation || '')}</textarea>

                        </div>

                        <button class="btn btn-primary" onclick="saveProposalEdit('${ticketId}')">💾 Enregistrer les modifications</button>

                    </div>

                </div>

            `;

        }

        async function saveProposalEdit(ticketId) {

            const getVal = (field) => {

                const el = document.getElementById(`pe-${ticketId}-${field}`);

                return el ? el.value.trim() : '';

            };

            const payload = {

                userId: state.userId,

                proposalId: ticketId,

                question: getVal('question'),

                choiceA: getVal('choice-a'),

                choiceB: getVal('choice-b'),

                choiceC: getVal('choice-c'),

                choiceD: getVal('choice-d'),

                correctAnswer: getVal('correct'),

                explanation: getVal('explanation')

            };

            if (!payload.question || !payload.choiceA || !payload.choiceB) {

                showToast("Question et choix A/B obligatoires", "error");

                return;

            }

            try {

                showToast("Sauvegarde de la proposition...", "info");

                const res = await fetch('/admin/update-proposal', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify(payload)

                });

                const data = await res.json();

                if (!data.success) throw new Error(data.error || 'Échec de sauvegarde');

                showToast("Proposition modifiée", "success");

                

                // Update item in local state

                const item = state.currentItems.find(i => String(i.id) === String(ticketId));

                if (item) {

                    item.question = payload.question;

                    item.choiceA = payload.choiceA;

                    item.choiceB = payload.choiceB;

                    item.choiceC = payload.choiceC;

                    item.choiceD = payload.choiceD;

                    item.correctAnswer = payload.correctAnswer;

                    item.explanation = payload.explanation;

                    

                    // Re-render the details to show the updated QCM details

                    const detail = document.getElementById('helpdesk-detail');

                    if (detail) {

                        detail.innerHTML = renderItemDetail(item);

                        detail.classList.add('open');

                    }

                }

            } catch (err) {

                showToast(err.message, "error");

            }

        }

        async function loadConfigPanel() {

            const slot = document.getElementById('settings-panel-slot');

            if (!slot) return;

            slot.innerHTML = `

                <div class="settings-panel">

                    <div class="settings-header">

                        <h3>⚙️ جاري تحميل الإعدادات...</h3>

                        <p>يرجى الانتظار أثناء الاتصال بالخادم...</p>

                    </div>

                </div>

            `;

            

            try {

                const res = await fetch('/admin/settings', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({ userId: state.userId })

                });

                const data = await res.json();

                if (!data.success) throw new Error(data.error || "Échec de chargement");

                

                const s = data.settings;

                state.configs = s;

                const bool = (key) => s[key] === "True" ? "checked" : "";

                const val  = (key) => s[key] || '';

                const num  = (key) => parseInt(s[key]) || 0;

                const maintActive = s.maintenance_mode === "True";

                const maintenanceBadge = maintActive

                    ? `<span class="maintenance-badge">🔴 وضع الصيانة نشط</span>`

                    : '';

                slot.innerHTML = `

                    <style>

                        .settings-tabs {

                            display: flex; gap: 8px; margin-bottom: 20px;

                            border-bottom: 1px solid var(--border);

                            padding-bottom: 12px; overflow-x: auto;

                        }

                        .settings-tab-btn {

                            padding: 8px 16px; border: none; background: transparent;

                            color: var(--text-secondary); cursor: pointer;

                            font-weight: 600; border-radius: 8px;

                            transition: 0.2s; white-space: nowrap;

                        }

                        .settings-tab-btn:hover { background: var(--hover); }

                        .settings-tab-btn.active { 

                            background: var(--primary); color: white; 

                        }

                        .settings-tab-content { display: none; }

                        .settings-tab-content.active { display: flex; flex-direction: column; gap: 16px; }

                    </style>

                    <div class="settings-panel">

                        <div class="settings-header">

                            <div style="display:flex; align-items:center; gap:12px; flex-wrap:wrap;">

                                <h3 style="margin:0;">⚙️ لوحة إعدادات البوت والمنصة</h3>

                                ${maintenanceBadge}

                            </div>

                            <p>تعديل متغيرات التشغيل مباشرة في قاعدة البيانات — تنعكس على البوت تليجرام فوراً</p>

                        </div>

                        <div class="settings-tabs">

                            <button class="settings-tab-btn active" onclick="switchSettingsTab('security', event)">🔰 الوصول والأمان</button>

                            <button class="settings-tab-btn" onclick="switchSettingsTab('messages', event)">💬 الرسائل والنصوص</button>

                            <button class="settings-tab-btn" onclick="switchSettingsTab('quiz', event)">📚 الاختبارات والتعلم</button>

                            <button class="settings-tab-btn" onclick="switchSettingsTab('notifications', event)">📣 الإشعارات والرسائل</button>

                            <button class="settings-tab-btn" onclick="switchSettingsTab('admins', event); loadAdminsList();">👥 إدارة المشرفين</button>

                            <button class="settings-tab-btn" onclick="switchSettingsTab('canned', event); loadCannedResponsesList();">📝 نماذج الردود</button>

                            <button class="settings-tab-btn" onclick="switchSettingsTab('data', event)">⚠️ الصيانة والبيانات</button>

                        </div>

                        <div class="settings-group" style="padding-top: 0;">

                            

                            <!-- TAB: SECURITY -->

                            <div id="stab-security" class="settings-tab-content active">

                                <div class="settings-card" style="flex-direction: column; align-items: stretch; gap: 15px;">

                                    <div class="settings-card-info" style="margin-bottom: 5px;">

                                        <div class="settings-card-title">🆔 معرف المجموعة الرسمية (Academy Group ID)</div>

                                        <div class="settings-card-desc">معرف المجموعة الرئيسية على تيليجرام. يجب أن يبدأ بـ -100.</div>

                                    </div>

                                    <div style="display: flex; gap: 10px;">

                                        <input type="text" id="sc-academy-group" class="settings-textarea" style="min-height: 40px; height: 40px; flex: 1;" value="${val('academy_group_id')}">

                                        <button class="settings-action-btn" onclick="saveTextSetting('academy_group_id', 'sc-academy-group')">💾 حفظ</button>

                                        <button class="settings-action-btn" onclick="testGroup('sc-academy-group')" style="background-color: var(--secondary); color: var(--background);">🔄 اختبار</button>

                                    </div>

                                </div>

                                

                                <div class="settings-card" style="flex-direction: column; align-items: stretch; gap: 15px;">

                                    <div class="settings-card-info" style="margin-bottom: 5px;">

                                        <div class="settings-card-title">🧪 معرف مجموعة الاختبار (Test Group ID)</div>

                                        <div class="settings-card-desc">اختياري: مجموعة اختبار ثانوية لعدم حظر الطلاب في حالة الاختبار.</div>

                                    </div>

                                    <div style="display: flex; gap: 10px;">

                                        <input type="text" id="sc-test-group" class="settings-textarea" style="min-height: 40px; height: 40px; flex: 1;" value="${val('test_group_id')}">

                                        <button class="settings-action-btn" onclick="saveTextSetting('test_group_id', 'sc-test-group')">💾 حفظ</button>

                                        <button class="settings-action-btn" onclick="testGroup('sc-test-group')" style="background-color: var(--secondary); color: var(--background);">🔄 اختبار</button>

                                    </div>

                                </div>

                                <div class="settings-card">

                                    <div class="settings-card-info">

                                        <div class="settings-card-title">🔐 تقييد الدخول للمجموعة الرسمية</div>

                                        <div class="settings-card-desc">عند تفعيله، لن يتمكن سوى أعضاء مجموعة الأكاديمية الرسمية من استخدام خدمات البوت.</div>

                                    </div>

                                    <label class="toggle-switch">

                                        <input type="checkbox" id="sc-restrict" ${bool('restrict_to_academy_group')} onchange="saveToggleSetting('restrict_to_academy_group', 'sc-restrict')">

                                        <span class="toggle-slider"></span>

                                    </label>

                                </div>

                                <div class="settings-card">

                                    <div class="settings-card-info">

                                        <div class="settings-card-title">🤖 حظر ميزات الذكاء الاصطناعي للطلاب</div>

                                        <div class="settings-card-desc">عند تفعيله، يُحظر توليد الأسئلة عبر Gemini للطلاب — يُستخدم فقط قاعدة الأسئلة الرسمية.</div>

                                    </div>

                                    <label class="toggle-switch">

                                        <input type="checkbox" id="sc-disable-ai" ${bool('disable_ai_for_students')} onchange="saveToggleSetting('disable_ai_for_students', 'sc-disable-ai')">

                                        <span class="toggle-slider"></span>

                                    </label>

                                </div>

                            </div>

                            <!-- TAB: MESSAGES -->

                            <div id="stab-messages" class="settings-tab-content">

                                <div class="settings-card full-width">

                                    <div class="settings-card-info">

                                        <div class="settings-card-title">👋 رسالة الترحيب بالبوت</div>

                                        <div class="settings-card-desc">النص الكامل الذي يُرسله البوت للطالب عند أول تفاعل أو عند الأمر /start. يدعم HTML.</div>

                                    </div>

                                    <textarea id="sc-welcome-msg" class="settings-textarea" placeholder="اكتب رسالة الترحيب هنا..." style="min-height: 150px;">${val('bot_welcome_message')}</textarea>

                                    <button class="settings-action-btn" onclick="saveTextSetting('bot_welcome_message', 'sc-welcome-msg')">💾 حفظ الرسالة الترحيبية</button>

                                </div>

                                <div class="settings-card full-width">

                                    <div class="settings-card-info">

                                        <div class="settings-card-title">✏️ رسالة وضع الصيانة</div>

                                        <div class="settings-card-desc">النص الذي يراه الطالب عندما يكتب للبوت أثناء فترة الصيانة. يدعم HTML.</div>

                                    </div>

                                    <textarea id="sc-maintenance-msg" class="settings-textarea" placeholder="اكتب رسالة الصيانة هنا..." style="min-height: 100px;">${val('maintenance_message')}</textarea>

                                    <button class="settings-action-btn" onclick="saveTextSetting('maintenance_message', 'sc-maintenance-msg')">💾 حفظ رسالة الصيانة</button>

                                </div>

                            </div>

                            <!-- TAB: QUIZ -->

                            <div id="stab-quiz" class="settings-tab-content">

                                <div class="settings-card">

                                    <div class="settings-card-info">

                                        <div class="settings-card-title">🔢 عدد الأسئلة لكل جلسة اختبار</div>

                                        <div class="settings-card-desc">عدد الأسئلة التي يتلقاها الطالب في كل جلسة مراجعة (من 5 إلى 50 سؤال).</div>

                                    </div>

                                    <div class="settings-slider-wrap">

                                        <input type="range" id="sc-quiz-count" class="settings-slider" min="5" max="50" step="5" value="${num('quiz_questions_per_session')}"

                                            oninput="document.getElementById('sc-quiz-count-val').textContent=this.value"

                                            onchange="saveSliderSetting('quiz_questions_per_session', 'sc-quiz-count')">

                                        <span id="sc-quiz-count-val" class="settings-slider-value">${num('quiz_questions_per_session')}</span>

                                    </div>

                                </div>

                                <div class="settings-card">

                                    <div class="settings-card-info">

                                        <div class="settings-card-title">⏱️ فترة الانتظار بين الاختبارات (دقيقة)</div>

                                        <div class="settings-card-desc">الحد الأدنى من الوقت بين جلستين متتاليتين لنفس الطالب. 0 = بدون قيود.</div>

                                    </div>

                                    <div class="settings-slider-wrap">

                                        <input type="range" id="sc-cooldown" class="settings-slider" min="0" max="1440" step="30" value="${num('quiz_cooldown_minutes')}"

                                            oninput="document.getElementById('sc-cooldown-val').textContent=this.value+'دق'"

                                            onchange="saveSliderSetting('quiz_cooldown_minutes', 'sc-cooldown')">

                                        <span id="sc-cooldown-val" class="settings-slider-value">${num('quiz_cooldown_minutes')}دق</span>

                                    </div>

                                </div>

                                <div class="settings-card">

                                    <div class="settings-card-info">

                                        <div class="settings-card-title">🎯 نسبة النجاح المطلوبة (%)</div>

                                        <div class="settings-card-desc">الحد الأدنى من الإجابات الصحيحة لاعتبار الاختبار ناجحاً.</div>

                                    </div>

                                    <div class="settings-slider-wrap">

                                        <input type="range" id="sc-pass-threshold" class="settings-slider" min="0" max="100" step="5" value="${num('quiz_pass_threshold')}"

                                            oninput="document.getElementById('sc-pass-val').textContent=this.value+'%'"

                                            onchange="saveSliderSetting('quiz_pass_threshold', 'sc-pass-threshold')">

                                        <span id="sc-pass-val" class="settings-slider-value">${num('quiz_pass_threshold')}%</span>

                                    </div>

                                </div>

                                <div class="settings-card">

                                    <div class="settings-card-info">

                                        <div class="settings-card-title">🔄 تفعيل وضع المراجعة</div>

                                        <div class="settings-card-desc">في وضع المراجعة يُركّز البوت على الأسئلة التي أخطأ فيها الطالب سابقاً.</div>

                                    </div>

                                    <label class="toggle-switch">

                                        <input type="checkbox" id="sc-revision" ${bool('enable_revision_mode')} onchange="saveToggleSetting('enable_revision_mode', 'sc-revision')">

                                        <span class="toggle-slider"></span>

                                    </label>

                                </div>

                            </div>

                            <!-- TAB: NOTIFICATIONS -->

                            <div id="stab-notifications" class="settings-tab-content">

                                <div class="settings-card full-width" style="border: 1px solid var(--primary); background: rgba(99, 102, 241, 0.05);">

                                    <div class="settings-card-info">

                                        <div class="settings-card-title">📢 إرسال رسالة جماعية (Broadcast)</div>

                                        <div class="settings-card-desc">إرسال رسالة إلى <b>جميع الطلاب المسجلين</b> في البوت، أو لطلبة سنة دراسية معينة. يدعم HTML.</div>

                                    </div>

                                    <div style="margin-bottom: 10px;">

                                        <select id="sc-broadcast-year" class="form-select" style="max-width: 200px;">

                                            <option value="">🎯 جميع السنوات الدراسية</option>

                                            <option value="1">🎓 السنة الأولى</option>

                                            <option value="2">🎓 السنة الثانية</option>

                                            <option value="3">🎓 السنة الثالثة</option>

                                            <option value="4">🎓 السنة الرابعة</option>

                                        </select>

                                    </div>

                                    <textarea id="sc-broadcast-msg" class="settings-textarea" placeholder="اكتب رسالتك لجميع الطلاب هنا..."></textarea>

                                    <button class="settings-action-btn" onclick="sendBroadcastMessage()" style="background: var(--primary); color: white;">🚀 إرسال الرسالة</button>

                                </div>

                                <div class="settings-card">

                                    <div class="settings-card-info">

                                        <div class="settings-card-title">📋 مستوى تفاصيل تذاكر الإدارة</div>

                                        <div class="settings-card-desc">تحديد حجم وسياق البيانات المرسلة للمشرفين عند فتح تذكرة دعم أو بلاغ جديد.</div>

                                    </div>

                                    <select id="sc-detail-level" class="form-select" style="max-width: 160px; padding: 6px;" onchange="saveSelectSetting('ticket_detail_level', 'sc-detail-level')">

                                        <option value="compact" ${s.ticket_detail_level === 'compact' ? 'selected' : ''}>موجز (Compact)</option>

                                        <option value="full" ${s.ticket_detail_level === 'full' ? 'selected' : ''}>كامل (Full)</option>

                                    </select>

                                </div>

                                <div class="settings-card">

                                    <div class="settings-card-info">

                                        <div class="settings-card-title">🔔 إشعار عند وصول بلاغ جديد</div>

                                        <div class="settings-card-desc">عند التفعيل، يُرسَل للمشرف إشعار فوري على تيليجرام عند وصول أي بلاغ أو مقترح جديد.</div>

                                    </div>

                                    <label class="toggle-switch">

                                        <input type="checkbox" id="sc-notify-report" ${bool('notify_on_new_report')} onchange="saveToggleSetting('notify_on_new_report', 'sc-notify-report')">

                                        <span class="toggle-slider"></span>

                                    </label>

                                </div>

                                <div class="settings-card">

                                    <div class="settings-card-info">

                                        <div class="settings-card-title">⏰ تفعيل التذكيرات التلقائية بالاختبارات</div>

                                        <div class="settings-card-desc">عند التفعيل، يُذكّر البوت الطلاب تلقائياً بجلسات المراجعة إذا مرت فترة طويلة بدون نشاط.</div>

                                    </div>

                                    <label class="toggle-switch">

                                        <input type="checkbox" id="sc-quiz-reminder" ${bool('quiz_reminder_enabled')} onchange="saveToggleSetting('quiz_reminder_enabled', 'sc-quiz-reminder')">

                                        <span class="toggle-slider"></span>

                                    </label>

                                </div>

                            </div>

                            <!-- TAB: ADMINS -->

                            <div id="stab-admins" class="settings-tab-content">

                                <div class="settings-card full-width">

                                    <div class="settings-card-info" style="margin-bottom: 15px;">

                                        <div class="settings-card-title">👥 إدارة فريق المشرفين</div>

                                        <div class="settings-card-desc">إضافة أو إزالة المشرفين وتحديد صلاحياتهم في لوحة التحكم.</div>

                                    </div>

                                    <div style="display: flex; gap: 10px; margin-bottom: 20px; align-items: center; flex-wrap: wrap;">

                                        <input type="number" id="new-admin-id" class="settings-textarea" style="height: 40px; min-height: 40px; width: 150px; flex: none;" placeholder="معرف تيليجرام (ID)">

                                        <select id="new-admin-role" class="form-select" style="height: 40px; max-width: 150px;">

                                            <option value="moderator">مشرف محتوى</option>

                                            <option value="support_admin">دعم فني</option>

                                            <option value="super_admin">مدير عام</option>

                                        </select>

                                        <button class="settings-action-btn" onclick="addAdmin()" style="background-color: var(--primary); color: white; width: auto; margin: 0; padding: 0 20px;">➕ إضافة مشرف</button>

                                    </div>

                                    <div id="admins-list-container" style="background: var(--bg); border-radius: 8px; border: 1px solid var(--border); padding: 10px;">

                                        <p style="text-align: center; color: var(--text-secondary);">جاري تحميل قائمة المشرفين...</p>

                                    </div>

                                </div>

                            </div>

                            <!-- TAB: DATA & MAINTENANCE -->

                            <div id="stab-data" class="settings-tab-content">

                                <div class="settings-card" style="border-color: ${maintActive ? 'rgba(239,68,68,0.5)' : 'var(--border)'}; background: ${maintActive ? 'rgba(239,68,68,0.05)' : ''};">

                                    <div class="settings-card-info">

                                        <div class="settings-card-title">🚧 وضع الصيانة (Bot hors service)</div>

                                        <div class="settings-card-desc">عند التفعيل، يرد البوت برسالة الصيانة لكل مستخدم ويوقف جميع الوظائف مؤقتاً.</div>

                                    </div>

                                    <label class="toggle-switch">

                                        <input type="checkbox" id="sc-maintenance" ${bool('maintenance_mode')} onchange="saveToggleSetting('maintenance_mode', 'sc-maintenance'); location.reload();">

                                        <span class="toggle-slider"></span>

                                    </label>

                                </div>

                                <div class="settings-card settings-danger-card">

                                    <div class="settings-card-info">

                                        <div class="settings-card-title">📥 تصدير بيانات التذاكر (CSV)</div>

                                        <div class="settings-card-desc">تنزيل جميع البلاغات والمقترحات المرئية حالياً في الجدول كملف CSV قابل للفتح في Excel.</div>

                                    </div>

                                    <button class="settings-action-btn" onclick="exportCurrentTableAsCSV()">📥 تصدير CSV</button>

                                </div>

                                <div class="settings-card settings-danger-card">

                                    <div class="settings-card-info">

                                        <div class="settings-card-title">🗑️ حذف التذاكر المنجزة القديمة</div>

                                        <div class="settings-card-desc">حذف نهائي لجميع التذاكر والبلاغات بحالة "مُنجز" أو "مرفوض" الأقدم من 30 يوماً.</div>

                                    </div>

                                    <button class="settings-action-btn danger" onclick="triggerPurgeOldTickets()">🗑️ تنظيف الأرشيف</button>

                                </div>

                            </div>

                        </div>

                    </div>

                `;

            } catch (err) {

                slot.innerHTML = `

                    <div class="settings-panel">

                        <div class="settings-header" style="border-bottom:none; text-align:center;">

                            <span style="font-size: 2rem;">❌</span>

                            <h3 style="margin-top:12px; color:var(--danger);">خطأ في تحميل الإعدادات</h3>

                            <p>${err.message}</p>

                        </div>

                    </div>

                `;

            }

        }

        // ─── Courses & Content Management Functions ───

        // ─── Courses & Content Management Functions ───

        window.loadCoursesPanel = function() {

            const slot = document.getElementById('courses-panel-slot');

            if (!slot) return;

            

            if (!state.transcripts || state.transcripts.length === 0) {

                slot.innerHTML = '<div class="settings-panel"><div class="settings-header"><h3>لا يوجد مواد دراسية</h3><p>يرجى التأكد من توفر ملف transcripts.json</p></div></div>';

                return;

            }

            

            // Group by subject

            const subjectsObj = {};

            state.transcripts.forEach(t => {

                if (!subjectsObj[t.subject]) subjectsObj[t.subject] = [];

                subjectsObj[t.subject].push(t);

            });

            const subjectsList = Object.keys(subjectsObj);

            

            if (!state.selectedCourseSubject) state.selectedCourseSubject = subjectsList[0];

            

            const currentSubject = state.selectedCourseSubject;

            const lessons = subjectsObj[currentSubject] || [];

            

            // Sort lessons by lessonNum

            lessons.sort((a,b) => parseInt(a.lessonNum) - parseInt(b.lessonNum));

            

            const activeTab = state.coursesSubTab || 'explorer';

            let tabHeader = `

                <style>

                    .courses-tab-header {

                        display: flex;

                        gap: 10px;

                        margin-bottom: 20px;

                        border-bottom: 1px solid var(--border);

                        padding-bottom: 12px;

                    }

                    .courses-tab-btn {

                        padding: 8px 16px;

                        border: none;

                        background: transparent;

                        color: var(--text-secondary);

                        cursor: pointer;

                        font-weight: 600;

                        border-radius: 8px;

                        transition: 0.2s;

                        font-size: 0.95rem;

                    }

                    .courses-tab-btn:hover {

                        background: var(--hover);

                    }

                    .courses-tab-btn.active {

                        background: var(--primary);

                        color: white;

                    }

                    

                    /* Form elements styling in factory */

                    .factory-form-group {

                        display: flex;

                        flex-direction: column;

                        gap: 5px;

                        margin-bottom: 12px;

                    }

                    .factory-form-group label {

                        font-weight: 600;

                        color: var(--text-secondary);

                        font-size: 0.85rem;

                    }

                    .factory-select, .factory-input, .factory-textarea {

                        background: var(--bg);

                        border: 1px solid var(--border);

                        border-radius: 8px;

                        color: var(--text-primary);

                        padding: 10px;

                        font-size: 0.9rem;

                        outline: none;

                        transition: 0.2s;

                    }

                    .factory-select:focus, .factory-input:focus, .factory-textarea:focus {

                        border-color: var(--primary);

                    }

                    

                    /* AI Question Preview Card */

                    .factory-question-card {

                        background: rgba(255, 255, 255, 0.02);

                        border: 1px solid var(--border);

                        border-radius: 12px;

                        padding: 18px;

                        margin-bottom: 18px;

                        display: flex;

                        flex-direction: column;

                        gap: 12px;

                        position: relative;

                    }

                    .factory-question-header {

                        display: flex;

                        justify-content: space-between;

                        align-items: center;

                        border-bottom: 1px dashed var(--border);

                        padding-bottom: 8px;

                        margin-bottom: 5px;

                    }

                    .factory-question-title {

                        font-weight: bold;

                        color: var(--gold-light);

                        font-size: 1rem;

                    }

                </style>

                

                <div class="courses-tab-header">

                    <button class="courses-tab-btn ${activeTab === 'explorer' ? 'active' : ''}" 

                            onclick="state.coursesSubTab = 'explorer'; loadCoursesPanel();">

                        📁 مستكشف الدروس (التقليدي)

                    </button>

                    <button class="courses-tab-btn ${activeTab === 'production' ? 'active' : ''}" 

                            onclick="state.coursesSubTab = 'production'; loadCoursesPanel();">

                        🤖 usine de production (مصنع الأسئلة بالذكاء الاصطناعي)

                    </button>

                </div>

            `;

            if (activeTab === 'explorer') {

                slot.innerHTML = tabHeader + `

                    <div class="settings-panel" style="display: flex; flex-direction: row; gap: 20px; padding: 20px; min-height: 500px; border-top:none; margin-top:-20px;">

                        <!-- Sidebar: Subjects -->

                        <div style="width: 200px; flex-shrink: 0; border-left: 1px solid var(--border); padding-left: 15px;">

                            <h4 style="margin-bottom: 15px; color: var(--text-primary);"><span style="font-size:1.2rem;">📚</span> المواد الدراسية</h4>

                            <div style="display: flex; flex-direction: column; gap: 8px;">

                                ${subjectsList.map(sub => `

                                    <button class="settings-tab-btn ${sub === currentSubject ? 'active' : ''}" 

                                            style="text-align: right; width: 100%; justify-content: flex-start; padding: 10px; border-radius: 8px; border: 1px solid ${sub === currentSubject ? 'var(--primary)' : 'transparent'}; background: ${sub === currentSubject ? 'var(--primary)' : 'transparent'}; color: ${sub === currentSubject ? 'white' : 'var(--text-secondary)'}; cursor: pointer;"

                                            onclick="state.selectedCourseSubject = '${sub}'; loadCoursesPanel();">

                                        ${sub}

                                    </button>

                                `).join('')}

                            </div>

                        </div>

                        

                        <!-- Main Area: Lessons & Chapters -->

                        <div style="flex: 1; overflow-y: auto;">

                            <h4 style="margin-bottom: 15px; color: var(--text-primary);">📖 دروس مادة: ${currentSubject}</h4>

                            <div style="margin-bottom: 15px; display: flex; gap: 10px;">

                                <input type="text" id="course-search-input" placeholder="🔍 ابحث عن محور أو كلمة في هذه المادة..." class="factory-input" style="flex: 1;" oninput="filterCourseLessons(this.value)">

                            </div>

                            <div style="display: flex; flex-direction: column; gap: 15px; padding-bottom: 30px;">

                                ${lessons.map((lesson, lIdx) => `

                                    <div class="settings-card" style="flex-direction: column; align-items: stretch; padding: 15px;">

                                        <div style="display: flex; justify-content: space-between; align-items: center; cursor: pointer; border-radius: 6px;">

                                            <div onclick="toggleLessonDetails('${lesson.subject}_${lesson.lessonNum}')" style="font-weight: bold; font-size: 1.1rem; color: var(--gold-light); flex: 1; cursor: pointer;">الدرس ${lesson.lessonNum}</div>

                                            <div style="display: flex; align-items: center; gap: 8px;">

                                                ${lesson.segments && lesson.segments.length ? `<button class="btn btn-primary btn-sm" style="padding: 4px 10px; font-size: 0.75rem; height: auto; line-height: 1; white-space: nowrap;" onclick="event.stopPropagation(); openTranscriptDrawer('${lesson.subject}', ${lesson.lessonNum})">📝 تحرير التفريغ</button>` : ''}

                                                <div onclick="toggleLessonDetails('${lesson.subject}_${lesson.lessonNum}')" style="color: var(--primary); font-size: 0.9rem; cursor: pointer;">▼ عرض/تعديل المحاور</div>

                                            </div>

                                        </div>

                                        

                                        <div id="lesson-details-${lesson.subject}_${lesson.lessonNum}" style="display: none; flex-direction: column; gap: 15px; margin-top: 15px; border-top: 1px solid var(--border); padding-top: 15px;">

                                            <!-- Resource Files Management Row -->

                                            <div style="background: rgba(212, 175, 55, 0.06); border: 2px solid var(--gold-light); box-shadow: 0 4px 15px rgba(212, 175, 55, 0.1); border-radius: 12px; padding: 18px; display: flex; flex-direction: column; gap: 12px; margin-bottom: 10px;">

                                                <div style="font-weight: bold; color: var(--gold-light); font-size: 1rem; display: flex; align-items: center; gap: 8px;">

                                                    <span>📂</span> 

                                                    <span>إدارة المستندات والخرائط الذهنية (Telegram File IDs)</span>

                                                </div>

                                                <p style="margin: 0; font-size: 0.8rem; color: var(--text-secondary); line-height: 1.4;">هذا القسم مخصص لربط ملفات الدرس (الخلاصة المكتوبة والخارطة الذهنية) بالبوت عبر معرفات الملفات (File IDs) المرسلة من تيليجرام.</p>

                                                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 15px;">

                                                    <div style="display: flex; flex-direction: column; gap: 5px;">

                                                        <label style="font-size: 0.8rem; color: var(--text-secondary);">🗺️ معرّف ملف الخارطة الذهنية (Mind Map ID) :</label>

                                                        <div style="display: flex; gap: 5px;">

                                                            <input type="text" id="res-mindmap-${lesson.subject}-${lesson.lessonNum}" class="settings-textarea" style="height: 35px; min-height: 35px; font-size: 0.8rem; flex: 1; direction: ltr;" placeholder="مثال: AgACAgQAAx0C..." value="">

                                                            <button class="btn btn-primary btn-sm" style="height: 35px; padding: 0 10px; white-space: nowrap;" onclick="saveLessonResource('${lesson.subject}', ${lesson.lessonNum}, 'mind_map')" title="حفظ الخارطة">💾 حفظ</button>

                                                        </div>

                                                    </div>

                                                    <div style="display: flex; flex-direction: column; gap: 5px;">

                                                        <label style="font-size: 0.8rem; color: var(--text-secondary);">📝 معرّف ملف الملخص الشامل (Summary ID) :</label>

                                                        <div style="display: flex; gap: 5px;">

                                                            <input type="text" id="res-summary-${lesson.subject}-${lesson.lessonNum}" class="settings-textarea" style="height: 35px; min-height: 35px; font-size: 0.8rem; flex: 1; direction: ltr;" placeholder="مثال: BQACAgQAAx0C..." value="">

                                                            <button class="btn btn-primary btn-sm" style="height: 35px; padding: 0 10px; white-space: nowrap;" onclick="saveLessonResource('${lesson.subject}', ${lesson.lessonNum}, 'summary')" title="حفظ الملخص">💾 حفظ</button>

                                                        </div>

                                                    </div>

                                                </div>

                                            </div>

                                                                                        <div style="background: rgba(15, 23, 42, 0.2); border: 1px solid var(--border); border-radius: 12px; padding: 20px; display: flex; flex-direction: column; gap: 15px; align-items: center; justify-content: center; text-align: center; margin-top: 10px; width: 100%;">
                                                <div style="font-size: 2.5rem;">📝</div>
                                                <div style="font-weight: bold; font-size: 1.1rem; color: var(--gold-light);">لوحة التحكم وإدارة المحاور التفاعلية للدرس</div>
                                                <p style="margin: 0; font-size: 0.85rem; color: var(--text-secondary); max-width: 500px; line-height: 1.5;">
                                                    تحتوي هذه اللوحة على ${lesson.thematic_blocks ? lesson.thematic_blocks.length : 0} محاور. يمكنك تعديل العناوين، الشروحات، روابط الفيديو، وقصائد السيرة بشكل كامل وبشاشة كاملة لراحة أكبر في التنقل والتحرير وتقسيم النصوص.
                                                </p>
                                                <button class="settings-action-btn" style="background: var(--primary); color: white; display: inline-flex; align-items: center; gap: 8px; font-weight: bold; padding: 10px 20px; border-radius: 8px; width: auto;" 
                                                        onclick="openAxesEditor('${lesson.subject}', ${lesson.lessonNum})">
                                                    <span>📝 فتح لوحة تعديل المحاور الشاملة (100% Plein Écran)</span>
                                                </button>
                                            </div>

                                        </div>

                                    </div>

                                `).join('')}

                            </div>

                        </div>

                    </div>

                `;

            } else if (activeTab === 'production') {

                if (!state.factorySubject) state.factorySubject = subjectsList[0];

                const factoryLessons = subjectsObj[state.factorySubject] || [];

                factoryLessons.sort((a,b) => parseInt(a.lessonNum) - parseInt(b.lessonNum));

                

                if (!state.factoryLessonNum && factoryLessons.length > 0) {

                    state.factoryLessonNum = factoryLessons[0].lessonNum;

                }

                

                const selectedLesson = factoryLessons.find(l => parseInt(l.lessonNum) === parseInt(state.factoryLessonNum));

                const factoryChapters = (selectedLesson && selectedLesson.thematic_blocks) ? selectedLesson.thematic_blocks : [];

                

                if (state.factoryChapterIdx === undefined || state.factoryChapterIdx === "") {

                    state.factoryChapterIdx = factoryChapters.length > 0 ? "0" : "-1";

                }

                

                const selectedChapter = factoryChapters[parseInt(state.factoryChapterIdx)];

                const defaultTheme = selectedChapter ? selectedChapter.title : '';

                

                const refKey = `${state.factorySubject}_${state.factoryLessonNum}_${state.factoryChapterIdx}`;

                if (state.lastChapterRef !== refKey) {

                    state.factoryTheme = defaultTheme;

                    state.lastChapterRef = refKey;

                }

                if (state.factoryTheme === undefined) state.factoryTheme = defaultTheme;

                state.generatedQuestions = state.generatedQuestions || [];

                // --- Calcul du HTML de la stratégie AVANT le template principal ---
                const _isBalanced = !state.factoryStrategy || state.factoryStrategy === 'balanced';
                const _isSpecific = state.factoryStrategy === 'specific';
                const _b1 = _isBalanced ? 'rgba(99,102,241,0.5)' : 'rgba(255,255,255,0.08)';
                const _bg1 = _isBalanced ? 'rgba(99,102,241,0.1)' : 'transparent';
                const _b2 = _isSpecific ? 'rgba(99,102,241,0.5)' : 'rgba(255,255,255,0.08)';
                const _bg2 = _isSpecific ? 'rgba(99,102,241,0.1)' : 'transparent';
                const _chOpts = factoryChapters.map(function(ch) {
                    const _sel = state.factorySpecificSubtheme === ch.title ? ' selected' : '';
                    const _v = ch.title.replace(/"/g, '&quot;');
                    return '<option value="' + _v + '"' + _sel + '>' + ch.title + '</option>';
                }).join('');
                const _custSel = state.factorySpecificSubtheme === '__custom__' ? ' selected' : '';
                const _custVal = (state.factorySpecificSubthemeCustom || '').replace(/"/g, '&quot;');
                const _custInput = state.factorySpecificSubtheme === '__custom__'
                    ? '<input type="text" class="factory-input" style="margin-top:6px;" id="factory-specific-subtheme-custom" placeholder="\u0627\u0643\u062a\u0628 \u0627\u0633\u0645 \u0627\u0644\u062c\u0632\u0626\u064a\u0629..." value="' + _custVal + '" oninput="state.factorySpecificSubthemeCustom = this.value;">'
                    : '';
                const _specPanel = _isSpecific
                    ? '<div style="animation:fadeIn 0.2s ease;margin-top:4px;"><label style="font-size:0.78rem;color:var(--text-secondary);font-weight:700;display:block;margin-bottom:5px;">📌 \u0627\u062e\u062a\u0631 \u0627\u0644\u062c\u0632\u0626\u064a\u0629 \u0627\u0644\u0645\u0633\u062a\u0647\u062f\u0641\u0629 :</label><select class="factory-select" id="factory-specific-subtheme" onchange="state.factorySpecificSubtheme = this.value; loadCoursesPanel();"><option value="">-- \u0627\u062e\u062a\u0631 \u062c\u0632\u0626\u064a\u0629 --</option>' + _chOpts + '<option value="__custom__"' + _custSel + '>\u270f\ufe0f \u0623\u062f\u062e\u0644 \u064a\u062f\u0648\u064a\u0627\u064b...</option></select>' + _custInput + '</div>'
                    : '';
                const strategyHTML = '<div class="factory-form-group" style="background:rgba(99,102,241,0.07);border:1px solid rgba(99,102,241,0.25);border-radius:10px;padding:12px;display:flex;flex-direction:column;gap:10px;">'
                    + '<label style="color:var(--primary);font-weight:900;font-size:0.9rem;margin-bottom:2px;">\uD83C\uDFAF \u0625\u0633\u062a\u0631\u0627\u062a\u064a\u062c\u064a\u0629 \u0627\u0644\u062a\u0648\u0644\u064a\u062f :</label>'
                    + '<label style="display:flex;align-items:flex-start;gap:10px;cursor:pointer;padding:8px;border-radius:8px;border:1px solid ' + _b1 + ';background:' + _bg1 + ';transition:all 0.2s;" onclick="state.factoryStrategy = \'balanced\'; loadCoursesPanel();">' 
                    + '<input type="radio" name="factory-strategy" value="balanced"' + (_isBalanced ? ' checked' : '') + ' style="margin-top:2px;accent-color:var(--primary);">'
                    + '<div><div style="font-weight:800;font-size:0.82rem;color:var(--text-primary);">\uD83D\uDD04 Option 1 \u2014 \u062a\u0648\u0632\u064a\u0639 \u0630\u0643\u064a \u0648\u0645\u062a\u0648\u0627\u0632\u0646</div>'
                    + '<div style="font-size:0.75rem;color:var(--text-secondary);line-height:1.4;margin-top:2px;">\u064a\u0648\u0632\u0651\u0639 \u0627\u0644\u0623\u0633\u0626\u0644\u0629 \u062a\u0644\u0642\u0627\u0626\u064a\u0627\u064b \u0639\u0644\u0649 \u062c\u0645\u064a\u0639 \u0627\u0644\u0645\u062d\u0627\u0648\u0631\u060c \u0645\u0639 \u0627\u0644\u0623\u0648\u0644\u0648\u064a\u0629 \u0644\u0644\u0645\u062d\u0627\u0648\u0631 \u0627\u0644\u062a\u064a \u062a\u0646\u0642\u0635\u0647\u0627 \u0623\u0633\u0626\u0644\u0629.</div></div></label>'
                    + '<label style="display:flex;align-items:flex-start;gap:10px;cursor:pointer;padding:8px;border-radius:8px;border:1px solid ' + _b2 + ';background:' + _bg2 + ';transition:all 0.2s;" onclick="state.factoryStrategy = \'specific\'; loadCoursesPanel();">'
                    + '<input type="radio" name="factory-strategy" value="specific"' + (_isSpecific ? ' checked' : '') + ' style="margin-top:2px;accent-color:var(--primary);">'
                    + '<div><div style="font-weight:800;font-size:0.82rem;color:var(--text-primary);">\uD83C\uDFAF Option 2 \u2014 \u062a\u0648\u0644\u064a\u062f \u0645\u064f\u0631\u0643\u0651\u0632 \u0639\u0644\u0649 \u0645\u062d\u0648\u0631 \u0645\u062d\u062f\u062f</div>'
                    + '<div style="font-size:0.75rem;color:var(--text-secondary);line-height:1.4;margin-top:2px;">\u062a\u0648\u0644\u064a\u062f \u0643\u0644 \u0627\u0644\u0623\u0633\u0626\u0644\u0629 \u0639\u0644\u0649 \u062c\u0632\u0626\u064a\u0629 \u0641\u0631\u0639\u064a\u0629 \u0648\u0627\u062d\u062f\u0629 \u0645\u062d\u062f\u062f\u0629 \u0628\u062f\u0642\u0629.</div></div></label>'
                    + _specPanel
                    + '</div>';

                slot.innerHTML = tabHeader + `

                    <div class="settings-panel" style="display: flex; flex-direction: row; gap: 20px; padding: 20px; min-height: 500px; border-top:none; margin-top:-20px; flex-wrap: wrap;">

                        <!-- Configuration Form (Left Panel) -->

                        <div style="width: 300px; flex-shrink: 0; border-left: 1px solid var(--border); padding-left: 20px; display:flex; flex-direction:column; gap:10px;">

                            <h4 style="margin: 0 0 10px 0; color: var(--gold-light); font-size:1.1rem;">⚙️ إعدادات مصنع الأسئلة</h4>

                            

                            <div class="factory-form-group">

                                <label>📚 المادة الدراسية :</label>

                                <select class="factory-select" onchange="state.factorySubject = this.value; state.factoryLessonNum = ''; state.factoryChapterIdx = ''; loadCoursesPanel();">

                                    ${subjectsList.map(sub => `<option value="${sub}" ${sub === state.factorySubject ? 'selected' : ''}>${sub}</option>`).join('')}

                                </select>

                            </div>

                            

                            <div class="factory-form-group">

                                <label>📖 الدرس :</label>

                                <select class="factory-select" onchange="state.factoryLessonNum = this.value; state.factoryChapterIdx = ''; loadCoursesPanel();">

                                    ${factoryLessons.map(l => `<option value="${l.lessonNum}" ${parseInt(l.lessonNum) === parseInt(state.factoryLessonNum) ? 'selected' : ''}>الدرس ${l.lessonNum}: ${l.title || ''}</option>`).join('')}

                                </select>

                            </div>

                            

                            <div class="factory-form-group">

                                <label>📌 المحور / الفقرة :</label>

                                <select class="factory-select" onchange="state.factoryChapterIdx = this.value; loadCoursesPanel();">

                                    <option value="-1" ${state.factoryChapterIdx === "-1" ? 'selected' : ''}>-- كامل الدرس (دون تحديد محور) --</option>

                                    ${factoryChapters.map((ch, idx) => `<option value="${idx}" ${String(idx) === String(state.factoryChapterIdx) ? 'selected' : ''}>المحور ${idx+1}: ${ch.title || ''}</option>`).join('')}

                                </select>

                            </div>

                            

                            <div class="factory-form-group">

                                <label>🏷️ المحور الرئيسي (Theme) :</label>

                                <input type="text" class="factory-input" value="${state.factoryTheme || ''}" oninput="state.factoryTheme = this.value;" placeholder="مثال: أركان الصلاة">

                            </div>

                            <!-- ─── STRATÉGIE HYBRIDE IA ─── -->
                            ${strategyHTML}

                            <div class="factory-form-group">

                                <label>🤖 نموذج التوليد :</label>

                                <select id="factory-model" class="factory-select">

                                    <option value="gemini-1.5-flash" selected>Gemini 1.5 Flash (مستقر وسريع)</option>

                                    <option value="gemini-1.5-flash-lite">Gemini 1.5 Flash Lite (خفيف)</option>

                                </select>

                            </div>

                            

                            <div class="factory-form-group">

                                <label>🔢 عدد الأسئلة المطلوبة :</label>

                                <select id="factory-count" class="factory-select">

                                    <option value="1">1 سؤال</option>

                                    <option value="3" selected>3 أسئلة</option>

                                    <option value="5">5 أسئلة</option>

                                    <option value="10">10 أسئلة</option>

                                </select>

                            </div>

                            

                            <div class="factory-form-group">

                                <label>✍️ توجيهات إضافية للذكاء الاصطناعي :</label>

                                <textarea id="factory-instructions" class="factory-textarea" style="min-height: 80px;" placeholder="مثال: ركز على الجوانب العملية، أو اجعل الخيارات متقاربة الصعوبة..."></textarea>

                            </div>

                            

                            <button id="btn-factory-generate" class="settings-action-btn" style="background: var(--primary); color: white; width:100%; font-size:0.95rem; height:42px; margin-top:10px;" onclick="generateQuestionsViaAI()">

                                🚀 توليد الأسئلة المقترحة

                            </button>

                        </div>

                        

                        <!-- Questions Preview/Editor (Right Panel) -->

                        <div style="flex: 1; min-width: 320px; display:flex; flex-direction:column; gap:15px;">

                            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">

                                <h4 style="margin:0; color:var(--text-primary);">📝 مراجعة وتحرير الأسئلة المولدة (${state.generatedQuestions.length})</h4>

                                ${state.generatedQuestions.length > 0 ? `

                                    <div style="display:flex; gap:10px; align-items:center;">

                                        <button class="btn btn-secondary btn-sm" onclick="state.generatedQuestions = []; loadCoursesPanel();" style="padding: 6px 12px; font-size: 0.8rem; height:32px;">🗑️ إفراغ المسودة</button>

                                        <button class="btn btn-primary btn-sm" onclick="saveBulkQuestionsToDB()" style="padding: 6px 12px; font-size: 0.8rem; height:32px;">💾 اعتماد وحفظ الكل</button>

                                    </div>

                                ` : ''}

                            </div>

                            

                            <div id="factory-preview-area" style="max-height: 68vh; overflow-y:auto; padding-right:5px;">

                                ${state.generatedQuestions.length === 0 ? `

                                    <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; border:2px dashed var(--border); border-radius:12px; height:320px; color:var(--text-secondary); text-align:center; padding:20px;">

                                        <span style="font-size:3rem; margin-bottom:12px;">🤖</span>

                                        <h4 style="margin:0 0 8px 0; color:var(--text-primary);">مصنع الأسئلة الذكي</h4>

                                        <p style="margin:0; max-width:380px; font-size:0.85rem; line-height:1.4;">اختر المادة والدرس المطلوب من لوحة التحكم الجانبية، ثم اضغط على زر التوليد. سيقوم الذكاء الاصطناعي بتحليل النص وصياغة أسئلة تفاعلية مع خياراتها وتفسيرها العلمي لمراجعتها واعتمادها.</p>

                                    </div>

                                ` : `

                                    ${state.generatedQuestions.map((q, qIdx) => `

                                        <div class="factory-question-card">

                                            <button style="position:absolute; left:15px; top:15px; border:none; background:transparent; color:var(--danger); cursor:pointer; font-size:1.1rem;" onclick="removeGeneratedQuestion(${qIdx})" title="حذف السؤال">❌</button>

                                            <div class="factory-question-header">

                                                <div class="factory-question-title">السؤال المقترح #${qIdx + 1}</div>

                                            </div>

                                            

                                            <div style="display:flex; flex-direction:column; gap:10px;">

                                                <div style="display:flex; flex-direction:column; gap:4px;">

                                                    <span style="font-size:0.8rem; font-weight:600; color:var(--text-secondary);">نص السؤال :</span>

                                                    <input type="text" class="factory-input" style="font-weight:600;" value="${(q.question || '').replace(/"/g, '&quot;')}" oninput="state.generatedQuestions[${qIdx}].question = this.value;">

                                                </div>

                                                

                                                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px;">

                                                    <div style="display:flex; flex-direction:column; gap:3px;">

                                                        <span style="font-size:0.75rem; color:var(--text-secondary);">أ) خيار أ :</span>

                                                        <input type="text" class="factory-input" value="${(q.choice_a || '').replace(/"/g, '&quot;')}" oninput="state.generatedQuestions[${qIdx}].choice_a = this.value;">

                                                    </div>

                                                    <div style="display:flex; flex-direction:column; gap:3px;">

                                                        <span style="font-size:0.75rem; color:var(--text-secondary);">ب) خيار ب :</span>

                                                        <input type="text" class="factory-input" value="${(q.choice_b || '').replace(/"/g, '&quot;')}" oninput="state.generatedQuestions[${qIdx}].choice_b = this.value;">

                                                    </div>

                                                    <div style="display:flex; flex-direction:column; gap:3px;">

                                                        <span style="font-size:0.75rem; color:var(--text-secondary);">ج) خيار ج :</span>

                                                        <input type="text" class="factory-input" value="${(q.choice_c || '').replace(/"/g, '&quot;')}" oninput="state.generatedQuestions[${qIdx}].choice_c = this.value;">

                                                    </div>

                                                    <div style="display:flex; flex-direction:column; gap:3px;">

                                                        <span style="font-size:0.75rem; color:var(--text-secondary);">د) خيار د :</span>

                                                        <input type="text" class="factory-input" value="${(q.choice_d || '').replace(/"/g, '&quot;')}" oninput="state.generatedQuestions[${qIdx}].choice_d = this.value;">

                                                    </div>

                                                </div>

                                                

                                                <div style="display:grid; grid-template-columns: 1.2fr 1.2fr 0.8fr; gap:15px; margin-top:3px;">

                                                    <div style="display:flex; flex-direction:column; gap:4px;">

                                                        <span style="font-size:0.8rem; font-weight:600; color:var(--text-secondary);">الإجابة الصحيحة :</span>

                                                        <select class="factory-select" onchange="state.generatedQuestions[${qIdx}].correct_answer = this.value;">

                                                            <option value="a" ${q.correct_answer === 'a' ? 'selected' : ''}>خيار أ</option>

                                                            <option value="b" ${q.correct_answer === 'b' ? 'selected' : ''}>خيار ب</option>

                                                            <option value="c" ${q.correct_answer === 'c' ? 'selected' : ''}>خيار ج</option>

                                                            <option value="d" ${q.correct_answer === 'd' ? 'selected' : ''}>خيار د</option>

                                                        </select>

                                                    </div>

                                                    <div style="display:flex; flex-direction:column; gap:4px;">

                                                        <span style="font-size:0.8rem; font-weight:600; color:var(--text-secondary);">المحور الرئيسي (Theme) :</span>

                                                        <input type="text" class="factory-input" value="${q.theme || ''}" oninput="state.generatedQuestions[${qIdx}].theme = this.value;">

                                                    </div>

                                                    <div style="display:flex; flex-direction:column; gap:4px;">

                                                        <span style="font-size:0.8rem; font-weight:600; color:var(--text-secondary);">الجزئية/الأخذ (Axe/Sub) :</span>

                                                        <input type="text" class="factory-input" value="${q.sub_theme || ''}" oninput="state.generatedQuestions[${qIdx}].sub_theme = this.value;">

                                                    </div>

                                                </div>

                                                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:15px; margin-top:3px;">
                                                    <div style="display:flex; flex-direction:column; gap:4px;">
                                                        <span style="font-size:0.8rem; font-weight:600; color:var(--text-secondary);">السنة الهجرية (Sira) :</span>
                                                        <input type="number" class="factory-input" value="${q.hijra_year || ''}" oninput="state.generatedQuestions[${qIdx}].hijra_year = this.value ? parseInt(this.value) : null;">
                                                    </div>
                                                </div>

                                                

                                                <div style="display:flex; flex-direction:column; gap:4px; margin-top:3px;">

                                                    <span style="font-size:0.8rem; font-weight:600; color:var(--text-secondary);">التفسير العلمي المرفق بالحل :</span>

                                                    <textarea class="factory-textarea" style="min-height:50px; font-size:0.85rem;" oninput="state.generatedQuestions[${qIdx}].explanation = this.value;">${q.explanation || ''}</textarea>

                                                </div>

                                            </div>

                                        </div>

                                    `).join('')}

                                `}

                            </div>

                        </div>

                    </div>

                `;

            }

        };

        

        window.toggleLessonDetails = function(id) {

            const el = document.getElementById('lesson-details-' + id);

            if (el) {

                const isOpening = el.style.display === 'none';

                el.style.display = isOpening ? 'flex' : 'none';

                if (isOpening) {

                    // Extract subject and lessonNum from id (format: subject_lessonNum)

                    const parts = id.split('_');

                    if (parts.length >= 2) {

                        const subject = parts[0];

                        const lessonNum = parts[1];

                        loadLessonResourcesInputs(subject, lessonNum);

                    }

                }

            }

        };

        window.loadLessonResourcesInputs = async function(subject, lessonNum) {

            try {

                const res = await fetch('/admin/lesson-resources', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({ userId: state.userId, subject, lessonNum: parseInt(lessonNum) })

                });

                const data = await res.json();

                if (data.success && data.resources) {

                    const mmEl = document.getElementById(`res-mindmap-${subject}-${lessonNum}`);

                    const smEl = document.getElementById(`res-summary-${subject}-${lessonNum}`);

                    if (mmEl) mmEl.value = data.resources.mind_map_file_id || '';

                    if (smEl) smEl.value = data.resources.summary_file_id || '';

                }

            } catch(e) {

                console.error("Failed to load lesson resources:", e);

            }

        };

        window.saveLessonResource = async function(subject, lessonNum, resourceType) {

            const inputId = resourceType === 'mind_map' ? `res-mindmap-${subject}-${lessonNum}` : `res-summary-${subject}-${lessonNum}`;

            const el = document.getElementById(inputId);

            if (!el) return;

            const fileId = el.value.trim();

            try {

                showToast("⏳ جاري حفظ معرف الملف...", "info");

                const res = await fetch('/admin/save-lesson-resources', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({

                        userId: state.userId,

                        subject,

                        lessonNum: parseInt(lessonNum),

                        resourceType,

                        fileId: fileId || null

                    })

                });

                const data = await res.json();

                if (data.success) {

                    showToast("✅ تم حفظ معرف الملف بنجاح", "success");

                } else {

                    showToast("❌ فشل حفظ معرف الملف", "error");

                }

            } catch(e) {

                console.error(e);

                showToast("❌ فشل الاتصال بالخادم لحفظ الملف", "error");

            }

        };

        window.filterCourseLessons = function(query) {

            query = query.toLowerCase().trim();

            const cards = document.querySelectorAll('.settings-card');

            cards.forEach(card => {

                if (!query) {

                    card.style.display = 'flex';

                    // Collapse expanded lesson details if searching is cleared

                    return;

                }

                const text = card.textContent.toLowerCase();

                const inputs = card.querySelectorAll('input[type="text"], textarea');

                let found = text.includes(query);

                inputs.forEach(input => {

                    if (input.value.toLowerCase().includes(query)) {

                        found = true;

                    }

                });

                card.style.display = found ? 'flex' : 'none';

                

                // Proactively expand if keyword matches inside details

                if (found && query.length > 2) {

                    const details = card.querySelector('div[id^="lesson-details-"]');

                    if (details) details.style.display = 'flex';

                }

            });

        };

        window.saveChapterContent = async function(subject, lessonNum, chapterIdx) {

            const titleEl = document.getElementById(`edit-title-${subject}-${lessonNum}-${chapterIdx}`);

            const urlEl = document.getElementById(`edit-url-${subject}-${lessonNum}-${chapterIdx}`);

            const textEl = document.getElementById(`edit-text-${subject}-${lessonNum}-${chapterIdx}`);

            

            if (!titleEl || !textEl) return;

            

            const newTitle = titleEl.value.trim();

            const newUrl = urlEl.value.trim();

            const newText = textEl.value.trim();

            

            if (!newTitle) {

                showToast("⚠️ عنوان المحور مطلوب", "error");

                return;

            }

            

            try {

                const res = await fetch('/admin/edit-chapter', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({

                        userId: state.userId,

                        subject: subject,

                        lessonNum: parseInt(lessonNum),

                        chapterIdx: parseInt(chapterIdx),

                        newTitle: newTitle,

                        newText: newText,

                        newVideoUrl: newUrl

                    })

                });

                

                const data = await res.json();

                if (data.success) {

                    showToast("✅ تم حفظ المحور بنجاح", "success");

                    // Update local state to avoid refetching

                    const lesson = state.transcripts.find(l => l.subject === subject && parseInt(l.lessonNum) === parseInt(lessonNum));

                    if (lesson && lesson.thematic_blocks && lesson.thematic_blocks[chapterIdx]) {

                        lesson.thematic_blocks[chapterIdx].title = newTitle;

                        lesson.thematic_blocks[chapterIdx].explanation = newText;

                        lesson.thematic_blocks[chapterIdx].video_link = newUrl;

                    }

                } else {

                    showToast("❌ " + data.error, "error");

                }

            } catch (err) {

                showToast("❌ حدث خطأ أثناء الحفظ", "error");

            }

        };

        window.generateQuestionsViaAI = async function() {

            const btn = document.getElementById('btn-factory-generate');

            const modelVal = document.getElementById('factory-model').value;

            const countVal = document.getElementById('factory-count').value;

            const instructionsVal = document.getElementById('factory-instructions').value.trim();

            if (!state.factorySubject || !state.factoryLessonNum) {

                showToast("⚠️ يرجى تحديد المادة والدرس أولاً", "error");

                return;

            }

            try {

                if (btn) {

                    btn.disabled = true;

                    btn.innerText = "⚡ جاري التوليد...";

                }

                const res = await fetch('/admin/questions/generate-ia', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({

                        userId: state.userId,

                        subject: state.factorySubject,

                        lessonNum: parseInt(state.factoryLessonNum),

                        chapterIdx: (state.factoryChapterIdx === undefined || state.factoryChapterIdx === "" || state.factoryChapterIdx === "-1") ? null : parseInt(state.factoryChapterIdx),

                        theme: state.factoryTheme || "",

                        numQuestions: parseInt(countVal),

                        instructions: instructionsVal,

                        model: modelVal,

                        strategy: state.factoryStrategy || 'balanced',

                        specificSubtheme: (() => {
                            if (state.factoryStrategy !== 'specific') return '';
                            if (state.factorySpecificSubtheme === '__custom__') return state.factorySpecificSubthemeCustom || '';
                            return state.factorySpecificSubtheme || '';
                        })()

                    })

                });

                const data = await res.json();

                if (data.success) {

                    state.generatedQuestions = data.questions || [];

                    showToast(`✅ تم توليد ${state.generatedQuestions.length} أسئلة بنجاح`, "success");

                    loadCoursesPanel();

                } else {

                    showToast("❌ " + (data.error || "فشل التوليد"), "error");

                }

            } catch (err) {

                showToast("❌ حدث خطأ أثناء التوليد عبر الذكاء الاصطناعي", "error");

            } finally {

                if (btn) {

                    btn.disabled = false;

                    btn.innerText = "🚀 توليد الأسئلة المقترحة";

                }

            }

        };

        window.removeGeneratedQuestion = function(idx) {

            if (state.generatedQuestions && state.generatedQuestions[idx] !== undefined) {

                state.generatedQuestions.splice(idx, 1);

                loadCoursesPanel();

                showToast("🗑️ تم إزالة السؤال من المسودة", "info");

            }

        };

        window.saveBulkQuestionsToDB = async function() {

            if (!state.generatedQuestions || state.generatedQuestions.length === 0) {

                showToast("⚠️ لا توجد أسئلة لحفظها", "error");

                return;

            }

            try {

                const res = await fetch('/admin/questions/save-bulk', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({

                        userId: state.userId,

                        subject: state.factorySubject,

                        lessonNum: parseInt(state.factoryLessonNum),

                        questions: state.generatedQuestions

                    })

                });

                const data = await res.json();

                if (data.success) {

                    showToast(`✅ تم حفظ ${data.inserted_count} سؤال بنجاح في قاعدة البيانات`, "success");

                    state.generatedQuestions = [];

                    loadCoursesPanel();

                } else {

                    showToast("❌ " + (data.error || "فشل حفظ الأسئلة"), "error");

                }

            } catch (err) {

                showToast("❌ حدث خطأ أثناء الاتصال بقاعدة البيانات", "error");

            }

        };

        window.switchSettingsTab = function(tabId, event) {

            document.querySelectorAll('.settings-tab-content').forEach(el => el.classList.remove('active'));

            document.querySelectorAll('.settings-tab-btn').forEach(el => el.classList.remove('active'));

            document.getElementById('stab-' + tabId).classList.add('active');

            if (event && event.currentTarget) {

                event.currentTarget.classList.add('active');

            }

        };

        // ─── Admins Management Functions ───

        window.loadAdminsList = async function() {

            const container = document.getElementById('admins-list-container');

            if (!container) return;

            try {

                const res = await fetch('/admin/list-admins', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({ userId: state.userId })

                });

                const data = await res.json();

                if (data.success) {

                    if (data.admins.length === 0) {

                        container.innerHTML = '<p style="text-align: center; color: var(--text-secondary);">لا يوجد مشرفين إضافيين.</p>';

                        return;

                    }

                    container.innerHTML = data.admins.map(a => `

                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px; border-bottom: 1px solid var(--border);">

                            <div>

                                <strong style="color: var(--text-primary); font-size: 1.1rem;">${a.user_id}</strong>

                                <span class="badge" style="margin-right: 8px;">${a.role}</span>

                                <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 4px;">أضيف بواسطة ${a.added_by} في ${formatTime(a.added_at)}</div>

                            </div>

                            <button class="settings-action-btn danger" style="width: auto; margin: 0; padding: 6px 12px; height: 32px;" onclick="removeAdmin(${a.user_id})">إزالة ❌</button>

                        </div>

                    `).join('');

                } else {

                    container.innerHTML = `<p style="color: var(--danger); text-align: center;">${data.error}</p>`;

                }

            } catch (err) {

                container.innerHTML = '<p style="color: var(--danger); text-align: center;">خطأ في تحميل المشرفين</p>';

            }

        };

        window.addAdmin = async function() {

            const tid = document.getElementById('new-admin-id').value.trim();

            const role = document.getElementById('new-admin-role').value;

            if (!tid) {

                showToast('⚠️ يرجى إدخال معرف المشرف', 'error');

                return;

            }

            try {

                const res = await fetch('/admin/add-admin', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({ userId: state.userId, targetId: tid, role: role })

                });

                const data = await res.json();

                if (data.success) {

                    showToast('✅ تم إضافة/تحديث المشرف بنجاح', 'success');

                    document.getElementById('new-admin-id').value = '';

                    loadAdminsList();

                } else {

                    showToast('❌ ' + data.error, 'error');

                }

            } catch (err) {

                showToast('❌ خطأ في الاتصال', 'error');

            }

        };

        window.removeAdmin = async function(tid) {

            if (!confirm('هل أنت متأكد من إزالة هذا المشرف؟')) return;

            try {

                const res = await fetch('/admin/remove-admin', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({ userId: state.userId, targetId: tid })

                });

                const data = await res.json();

                if (data.success) {

                    showToast('✅ تم إزالة المشرف', 'success');

                    loadAdminsList();

                } else {

                    showToast('❌ ' + data.error, 'error');

                }

            } catch (err) {

                showToast('❌ خطأ في الاتصال', 'error');

            }

        };

        // ─── Canned Responses Management Functions ───

        window.loadCannedResponsesList = async function() {

            const container = document.getElementById('canned-list-container');

            if (!container) return;

            try {

                const res = await fetch('/admin/canned-responses', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({ userId: state.userId })

                });

                const data = await res.json();

                if (data.success) {

                    state.cannedResponses = data.templates;

                    if (data.templates.length === 0) {

                        container.innerHTML = '<p style="text-align: center; color: var(--text-secondary); padding: 15px;">لا توجد نماذج ردود مسجلة بعد.</p>';

                        return;

                    }

                    container.innerHTML = data.templates.map(t => {

                        const catLabels = {

                            other: 'عام',

                            tech: 'تقني',

                            schooling: 'أكاديمي',

                            correct_answer: 'تصحيح'

                        };

                        return `

                        <div class="canned-response-item" style="display: flex; justify-content: space-between; align-items: flex-start; padding: 12px; border-bottom: 1px solid var(--border); gap: 15px;">

                            <div style="flex: 1;">

                                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">

                                    <strong style="color: var(--text-primary);">${escapeHtml(t.title)}</strong>

                                    <span class="badge" style="background: rgba(212,175,55,0.1); color: var(--gold-light); font-size: 0.7rem; border: 1px solid rgba(212,175,55,0.2);">${catLabels[t.category] || t.category}</span>

                                </div>

                                <div style="font-size: 0.8rem; color: var(--text-secondary); white-space: pre-wrap; line-height: 1.4;">${escapeHtml(t.content)}</div>

                            </div>

                            <div style="display: flex; gap: 8px;">

                                <button class="btn btn-secondary" style="padding: 4px 8px; font-size: 0.75rem;" onclick="editCannedResponse(${t.id}, '${t.title.replace(/'/g, "\\'")}', '${t.category}', '${t.content.replace(/'/g, "\\'").replace(/\n/g, '\\n')}')">✏️ تعديل</button>

                                <button class="btn btn-danger" style="padding: 4px 8px; font-size: 0.75rem; background: var(--danger);" onclick="deleteCannedResponse(${t.id})">🗑️ حذف</button>

                            </div>

                        </div>

                        `;

                    }).join('');

                } else {

                    container.innerHTML = `<p style="text-align: center; color: var(--danger); padding: 15px;">خطأ: ${data.error}</p>`;

                }

            } catch (err) {

                console.error("Error loading canned responses:", err);

                container.innerHTML = '<p style="text-align: center; color: var(--danger); padding: 15px;">فشل الاتصال بالخادم.</p>';

            }

        };

        window.saveCannedResponse = async function() {

            const templateId = document.getElementById('canned-id').value;

            const title = document.getElementById('canned-title').value.trim();

            const category = document.getElementById('canned-category').value;

            const content = document.getElementById('canned-content').value.trim();

            if (!title || !content) {

                showToast("⚠️ يرجى ملء العنوان والمحتوى", "error");

                return;

            }

            try {

                showToast("⏳ جاري الحفظ...", "info");

                const res = await fetch('/admin/canned-responses/save', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({

                        userId: state.userId,

                        id: templateId ? parseInt(templateId) : null,

                        title: title,

                        category: category,

                        content: content

                    })

                });

                const data = await res.json();

                if (data.success) {

                    showToast("✅ تم حفظ النموذج بنجاح", "success");

                    resetCannedForm();

                    loadCannedResponsesList();

                } else {

                    showToast("❌ خطأ في الحفظ: " + data.error, "error");

                }

            } catch (err) {

                console.error(err);

                showToast("❌ فشل الاتصال بالخادم", "error");

            }

        };

        window.editCannedResponse = function(id, title, category, content) {

            document.getElementById('canned-id').value = id;

            document.getElementById('canned-title').value = title;

            document.getElementById('canned-category').value = category;

            document.getElementById('canned-content').value = content;

            document.getElementById('canned-title').focus();

            showToast("✏️ جاري تعديل النموذج: " + title, "info");

        };

        window.deleteCannedResponse = async function(id) {

            if (!confirm("⚠️ هل أنت متأكد من حذف هذا النموذج نهائياً؟")) return;

            try {

                showToast("⏳ جاري الحذف...", "info");

                const res = await fetch('/admin/canned-responses/delete', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({

                        userId: state.userId,

                        id: id

                    })

                });

                const data = await res.json();

                if (data.success) {

                    showToast("✅ تم حذف النموذج", "success");

                    loadCannedResponsesList();

                } else {

                    showToast("❌ خطأ: " + data.error, "error");

                }

            } catch (err) {

                console.error(err);

                showToast("❌ فشل الاتصال بالخادم", "error");

            }

        };

        window.resetCannedForm = function() {

            document.getElementById('canned-id').value = '';

            document.getElementById('canned-title').value = '';

            document.getElementById('canned-category').value = 'other';

            document.getElementById('canned-content').value = '';

        };

        // ─── Settings Helper Functions ───

        async function saveToggleSetting(key, elementId) {

            const el = document.getElementById(elementId);

            if (!el) return;

            await saveConfigSetting(key, el.checked ? "True" : "False");

        }

        async function saveSliderSetting(key, elementId) {

            const el = document.getElementById(elementId);

            if (!el) return;

            await saveConfigSetting(key, el.value);

        }

        async function saveTextSetting(key, elementId) {

            const el = document.getElementById(elementId);

            if (!el) return;

            const value = el.value.trim();

            if (!value) { showToast("⚠️ لا يمكن حفظ نص فارغ", "error"); return; }

            await saveConfigSetting(key, value);

        }

        async function saveSelectSetting(key, elementId) {

            const el = document.getElementById(elementId);

            if (!el) return;

            await saveConfigSetting(key, el.value);

        }

        async function testGroup(elementId) {

            const el = document.getElementById(elementId);

            if (!el) return;

            const groupId = el.value.trim();

            if (!groupId) {

                showToast("⚠️ الرجاء إدخال معرف المجموعة", "error");

                return;

            }

            

            try {

                const response = await fetch('/admin/test-group', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({ userId: state.userId, groupId: groupId })

                });

                

                const data = await response.json();

                if (data.success) {

                    showToast(`✅ تم الوصول للمجموعة بنجاح: ${data.chat_title}`, "success");

                } else {

                    showToast(`❌ تعذر الوصول للمجموعة: ${data.error || 'تأكد من إضافة البوت كمسؤول في المجموعة'}`, "error");

                }

            } catch (err) {

                showToast("❌ حدث خطأ في الاتصال", "error");

            }

        }

        async function sendBroadcastMessage() {

            const el = document.getElementById('sc-broadcast-msg');

            const yearEl = document.getElementById('sc-broadcast-year');

            const message = el.value.trim();

            const year = yearEl ? yearEl.value : "";

            

            if (!message) {

                showToast("⚠️ الرجاء كتابة رسالة", "error");

                return;

            }

            

            const targetText = year ? `طلبة السنة ${year}` : "جميع الطلاب المسجلين بالكامل";

            if (!confirm(`هل أنت متأكد أنك تريد إرسال هذه الرسالة لـ (${targetText})؟ هذا الإجراء لا يمكن التراجع عنه.`)) {

                return;

            }

            try {

                showToast("جاري إرسال الرسالة للجميع، يرجى الانتظار...", "info");

                const response = await fetch('/admin/broadcast', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({ userId: state.userId, message: message, academicYear: year || null })

                });

                const data = await response.json();

                if (data.success) {

                    showToast(`✅ تم بدء الإرسال لـ ${data.total_users} طالب بنجاح! يتم الإرسال تدريجياً.`, "success");

                    el.value = "";

                } else {

                    showToast(`❌ فشل الإرسال: ${data.error}`, "error");

                }

            } catch (err) {

                showToast("❌ حدث خطأ في الاتصال", "error");

            }

        }

        // Legacy aliases (keep for backward compat)

        async function toggleConfigSetting(key) {

            const inputId = key === 'restrict_to_academy_group' ? 'sc-restrict' : 'sc-disable-ai';

            await saveToggleSetting(key, inputId);

        }

        async function saveSelectConfigSetting(key) {

            await saveSelectSetting(key, 'sc-detail-level');

        }

        async function saveConfigSetting(key, value) {

            try {

                showToast("⏳ جاري حفظ التغييرات...", "info");

                const res = await fetch('/admin/update-setting', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({ userId: state.userId, key, value })

                });

                const data = await res.json();

                if (!data.success) throw new Error(data.error || "Échec de sauvegarde");

                showToast("✅ تم حفظ الإعدادات بنجاح في قاعدة البيانات", "success");

            } catch (err) {

                showToast("❌ فشل حفظ الإعدادات: " + err.message, "error");

            }

        }

        async function triggerPurgeOldTickets() {

            if (!confirm("⚠️ هل أنت متأكد؟ سيتم حذف جميع التذاكر المنجزة/المرفوضة الأقدم من 30 يوماً بشكل نهائي!")) return;

            try {

                showToast("⏳ جاري تنظيف الأرشيف...", "info");

                const res = await fetch('/admin/purge-old-tickets', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({ userId: state.userId, days: 30 })

                });

                const data = await res.json();

                if (!data.success) throw new Error(data.error);

                showToast(`✅ تم حذف ${data.deleted} سجل قديم بنجاح`, "success");

                await loadDashboardData();

            } catch (err) {

                showToast("❌ فشل التنظيف: " + err.message, "error");

            }

        }

        async function updateThemeFilterDropdown() {
            const subject = document.getElementById('qb-subject-filter').value;
            const themeSelect = document.getElementById('qb-theme-filter');
            const subthemeSelect = document.getElementById('qb-subtheme-filter');
            
            if (!themeSelect || !subthemeSelect) return;
            
            themeSelect.innerHTML = '<option value="">كل المحاور الكبرى</option>';
            subthemeSelect.innerHTML = '<option value="">كل الجزئيات</option>';
            subthemeSelect.disabled = true;
            
            if (!subject) {
                themeSelect.disabled = true;
                themeSelect.style.display = 'none';
                subthemeSelect.style.display = 'none';
                return;
            }
            
            themeSelect.disabled = true;
            try {
                const response = await fetch('/admin/get-themes', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ userId: state.userId, subject: subject })
                });
                const data = await response.json();
                if (data.success && data.themes && data.themes.length > 0) {
                    themeSelect.style.display = 'inline-block';
                    data.themes.forEach(theme => {
                        const opt = document.createElement('option');
                        opt.value = theme;
                        opt.textContent = theme;
                        themeSelect.appendChild(opt);
                    });
                    themeSelect.disabled = false;
                } else {
                    themeSelect.style.display = 'none';
                    subthemeSelect.style.display = 'none';
                }
            } catch(e) {
                console.error("Error fetching themes", e);
            }
        }

        async function updateSubThemeFilterDropdown() {
            const subject = document.getElementById('qb-subject-filter').value;
            const theme = document.getElementById('qb-theme-filter').value;
            const subthemeSelect = document.getElementById('qb-subtheme-filter');
            
            if (!subthemeSelect) return;
            
            subthemeSelect.innerHTML = '<option value="">كل الجزئيات</option>';
            
            if (!subject || !theme) {
                subthemeSelect.disabled = true;
                subthemeSelect.style.display = 'none';
                return;
            }
            
            subthemeSelect.disabled = true;
            try {
                const response = await fetch('/admin/get-themes', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ userId: state.userId, subject: subject, theme: theme })
                });
                const data = await response.json();
                if (data.success && data.sub_themes && data.sub_themes.length > 0) {
                    subthemeSelect.style.display = 'inline-block';
                    data.sub_themes.forEach(sub => {
                        const opt = document.createElement('option');
                        opt.value = sub;
                        opt.textContent = sub;
                        subthemeSelect.appendChild(opt);
                    });
                    subthemeSelect.disabled = false;
                } else {
                    subthemeSelect.style.display = 'none';
                }
            } catch(e) {
                console.error("Error fetching sub themes", e);
            }
        }

        function updateLessonFilterDropdown() {

            const subject = document.getElementById('qb-subject-filter').value;

            const lessonSelect = document.getElementById('qb-lesson-filter');

            if (!lessonSelect) return;

            

            // Save currently selected lesson number

            const currentSelected = lessonSelect.value;

            

            // Clear existing options, keep only default option

            lessonSelect.innerHTML = '<option value="">كل الدروس</option>';

            

            if (!subject) {

                // If no subject selected, disable or show empty lesson list

                lessonSelect.disabled = true;

                return;

            }

            

            lessonSelect.disabled = false;

            

            if (!state.transcripts || !state.transcripts.length) {

                return;

            }

            

            // Filter transcripts for this subject

            const lessons = state.transcripts

                .filter(l => l.subject === subject)

                .map(l => l.lessonNum)

                .sort((a, b) => a - b);

                

            // Deduplicate lesson numbers

            const uniqueLessons = [...new Set(lessons)];

            

            for (const lNum of uniqueLessons) {

                const opt = document.createElement('option');

                opt.value = lNum;

                opt.textContent = `الدرس ${lNum}`;

                if (currentSelected && parseInt(currentSelected) === lNum) {

                    opt.selected = true;

                }

                lessonSelect.appendChild(opt);

            }

            updateChapterFilterDropdown();

        }

        function updateChapterFilterDropdown() {

            const subjectFilter = document.getElementById('qb-subject-filter').value;

            const subject = subjectFilter === 'aqeeda' ? 'aqida' : subjectFilter;

            const lessonNum = document.getElementById('qb-lesson-filter').value;

            const chapterSelect = document.getElementById('qb-chapter-filter');

            if (!chapterSelect) return;

            

            const currentSelected = chapterSelect.value;

            chapterSelect.innerHTML = '<option value="">كل المحاور</option>';

            

            if (!subject || !lessonNum || !state.questionsStats) {

                chapterSelect.disabled = true;

                return;

            }

            

            chapterSelect.disabled = false;

            const courseData = (state.questionsStats[subject] || {})[lessonNum];

            const chapters = courseData ? courseData.chapters || [] : [];

            

            chapters.forEach(ch => {

                const opt = document.createElement('option');

                opt.value = ch.chapter_index;

                opt.textContent = `المحور ${ch.chapter_index}: ${ch.title}`;

                if (currentSelected && parseInt(currentSelected) === parseInt(ch.chapter_index)) {

                    opt.selected = true;

                }

                chapterSelect.appendChild(opt);

            });

        }

        // ─── TRANSCRIPT TABS + VIEW LOGIC ───

        if (!window._trSubjectInit) {

            window._trSubjectInit = true;

            window.state = window.state || {};

            window.state.trActiveSubject = '';

            window.state.trViewMode = 'card'; // 'card' or 'list'

        }

        function selectTranscriptSubject(subject) {

            state.trActiveSubject = subject;

            // Update tab active state

            document.querySelectorAll('#tr-sheets-tabs .qb-sheet-tab').forEach(t => t.classList.remove('active'));

            const tabId = subject ? `tr-tab-${subject}` : 'tr-tab-all';

            const activeTab = document.getElementById(tabId);

            if (activeTab) activeTab.classList.add('active');

            loadTranscripts();

        }

        function setTranscriptView(mode) {

            state.trViewMode = mode;

            const cardBtn = document.getElementById('btn-tr-view-card');

            const listBtn = document.getElementById('btn-tr-view-list');

            if (cardBtn && listBtn) {

                if (mode === 'card') {

                    cardBtn.style.background = 'var(--gold)';

                    cardBtn.style.color = '#000';

                    cardBtn.style.fontWeight = '700';

                    listBtn.style.background = 'var(--surface-hover)';

                    listBtn.style.color = 'var(--text-secondary)';

                    listBtn.style.fontWeight = '600';

                    document.getElementById('transcripts-grid').style.gridTemplateColumns = 'repeat(auto-fill, minmax(280px, 1fr))';

                } else {

                    listBtn.style.background = 'var(--gold)';

                    listBtn.style.color = '#000';

                    listBtn.style.fontWeight = '700';

                    cardBtn.style.background = 'var(--surface-hover)';

                    cardBtn.style.color = 'var(--text-secondary)';

                    cardBtn.style.fontWeight = '600';

                    document.getElementById('transcripts-grid').style.gridTemplateColumns = '1fr';

                }

            }

            loadTranscripts();

        }

        window.loadTranscripts = function() {

            // Support both legacy select and new tab state

            const subjectFromTab = (typeof state !== 'undefined' && state.trActiveSubject !== undefined) ? state.trActiveSubject : '';

            const subject = subjectFromTab || (document.getElementById('tr-subject-filter') ? document.getElementById('tr-subject-filter').value : '');

            const search = document.getElementById('tr-search-input').value.toLowerCase().trim();

            const grid = document.getElementById('transcripts-grid');

            if (!grid) return;

            if (!state.transcripts || !state.transcripts.length) {

                grid.innerHTML = '<div style="grid-column: 1/-1; text-align:center; padding:40px; color:var(--text-secondary);">لا توجد تفريغات متوفرة.</div>';

                return;

            }

            // Filter transcripts

            const filtered = state.transcripts.filter(t => {

                if (subject && t.subject !== subject) return false;

                if (search) {

                    const matchTitle = (t.title || '').toLowerCase().includes(search);

                    const matchLesson = (t.lesson || '').toLowerCase().includes(search);

                    const matchText = (t.full_text || '').toLowerCase().includes(search);

                    const matchSubjectLabel = (t.subjectLabel || '').toLowerCase().includes(search);

                    if (!matchTitle && !matchLesson && !matchText && !matchSubjectLabel) return false;

                }

                return true;

            });

            // Sort by subject first, then by lessonNum

            filtered.sort((a, b) => {

                if (a.subject !== b.subject) {

                    return a.subject.localeCompare(b.subject);

                }

                return parseInt(a.lessonNum || 0) - parseInt(b.lessonNum || 0);

            });

            if (!filtered.length) {

                grid.innerHTML = '<div style="grid-column: 1/-1; text-align:center; padding:40px; color:var(--text-secondary);">لا توجد نتائج تطابق البحث.</div>';

                return;

            }

            // Render cards

            let html = '';

            filtered.forEach(lesson => {

                const subLabel = lesson.subjectLabel || SUBJECTS_AR[lesson.subject] || lesson.subject;

                const subColor = SUBJECT_COLORS[lesson.subject] || 'var(--primary)';

                const segmentsCount = lesson.segments ? lesson.segments.length : 0;

                

                if (state.transcriptViewMode === 'thematic' && lesson.thematic_blocks && lesson.thematic_blocks.length > 0) {

                    // THEMATIC VIEW

                    html += `

                        <div class="settings-card" style="grid-column: 1/-1; flex-direction: column; align-items: stretch; padding: 24px; margin-bottom: 20px; border-top: 4px solid ${subColor}; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); border-radius: 12px; background: var(--surface);">

                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid var(--border); padding-bottom: 16px;">

                                <div style="display: flex; align-items: center; gap: 12px;">

                                    <span class="badge" style="background: ${subColor}22; color: ${subColor}; font-weight: bold; border: 1px solid ${subColor}44; padding: 6px 12px; border-radius: 8px; font-size: 0.9rem;">${subLabel}</span>

                                    <h2 style="margin: 0; font-size: 1.4rem; color: var(--text-primary); font-weight: 700;">${lesson.title || `الدرس ${lesson.lessonNum}`}</h2>

                                </div>

                                <div style="display: flex; gap: 12px; align-items: center;">

                                    <span style="font-size: 0.9rem; color: var(--text-secondary); font-weight: 500;">🧩 ${segmentsCount} فقرة</span>

                                    <button class="btn btn-primary" onclick="openTranscriptDrawer('${lesson.subject}', ${lesson.lessonNum})">📝 تحرير التفريغ الكامل</button>

                                </div>

                            </div>

                            <div style="display: flex; flex-direction: column; gap: 16px;">

                                                                 ${lesson.thematic_blocks.map((block, idx) => `
                                     <div style="background: var(--bg); border: 1px solid var(--border); border-radius: 10px; padding: 16px; margin-bottom: 16px; display: flex; flex-direction: column; gap: 12px;">
                                         <div style="display: flex; justify-content: space-between; align-items: center;">
                                             <h4 style="margin: 0; font-size: 1.1rem; color: var(--primary);"><span style="color: var(--text-secondary); font-size: 0.9rem; margin-left: 8px;">محور ${idx + 1}:</span> ${block.title}</h4>
                                             ${block.timestamp ? `<span style="font-size: 0.8rem; color: var(--text-secondary); background: var(--surface-hover); padding: 4px 8px; border-radius: 6px;">⏱ ${block.timestamp}</span>` : ''}
                                         </div>
                                         ${block.explanation ? `
                                             <div style="background: rgba(212, 175, 55, 0.06); border-right: 4px solid var(--gold); padding: 12px; border-radius: 6px; font-size: 0.95rem; color: var(--text-primary); line-height: 1.7;">
                                                 ${block.explanation}
                                             </div>
                                         ` : '<p style="color: var(--text-secondary); margin: 0;">لا يوجد شرح لهذا المحور</p>'}
                                         ${block.poetry_verses ? `
                                             <div style="background: rgba(212, 175, 55, 0.04); border: 1px dashed rgba(212, 175, 55, 0.3); padding: 14px; border-radius: 6px; text-align: center; font-style: italic; font-size: 1.1rem; color: var(--text-primary); line-height: 1.8; white-space: pre-line; direction: rtl;">
                                                 ${block.poetry_verses}
                                             </div>
                                         ` : ''}
                                     </div>
                                 `).join('')}

                            </div>

                        </div>

                    `;

                } else {

                    const isListMode = (state.trViewMode === 'list');

                    if (isListMode) {

                        // LIST VIEW - compact row

                        html += `

                            <div style="display:flex; align-items:center; gap:12px; padding:12px 16px; background:var(--surface); border:1px solid var(--border); border-right:4px solid ${subColor}; border-radius:10px; transition:background 0.2s;" onmouseover="this.style.background='var(--surface-hover)'" onmouseout="this.style.background='var(--surface)'">

                                <span style="font-size:0.75rem; font-weight:700; background:${subColor}22; color:${subColor}; border:1px solid ${subColor}44; padding:3px 8px; border-radius:6px; white-space:nowrap; min-width:60px; text-align:center;">${subLabel}</span>

                                <span style="font-size:0.8rem; color:var(--text-secondary); white-space:nowrap; min-width:60px;">\u0627\u0644\u062f\u0631\u0633 ${lesson.lessonNum}</span>

                                <span style="flex:1; font-size:0.95rem; color:var(--text-primary); font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${lesson.title || `\u0627\u0644\u062f\u0631\u0633 ${lesson.lessonNum}`}</span>

                                <span style="font-size:0.8rem; color:var(--text-secondary); white-space:nowrap;">\ud83e\udde9 ${segmentsCount} \u0641\u0642\u0631\u0629</span>

                                <button class="btn btn-primary btn-sm" style="padding: 5px 12px; font-size: 0.78rem; height: auto; white-space:nowrap;" onclick="openTranscriptDrawer('${lesson.subject}', ${lesson.lessonNum})">

                                    \ud83d\udcdd \u062a\u062d\u0631\u064a\u0631

                                </button>

                            </div>

                        `;

                    } else {

                        // CARD VIEW

                        html += `

                            <div class="settings-card" style="flex-direction: column; align-items: stretch; padding: 20px; min-height: 180px; display: flex; justify-content: space-between; border-top: 4px solid ${subColor}; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06); border-radius: 12px; background: var(--surface);">

                                <div>

                                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">

                                        <span class="badge" style="background: ${subColor}22; color: ${subColor}; font-weight: bold; border: 1px solid ${subColor}44; padding: 4px 8px; border-radius: 6px; font-size: 0.8rem;">${subLabel}</span>

                                        <span style="font-size: 0.85rem; color: var(--text-secondary); font-weight: 500;">\u0627\u0644\u062f\u0631\u0633 ${lesson.lessonNum}</span>

                                    </div>

                                    <h3 style="margin: 0 0 10px 0; font-size: 1.1rem; color: var(--text-primary); font-weight: 600;">${lesson.title || `\u0627\u0644\u062f\u0631\u0633 ${lesson.lessonNum}`}</h3>

                                    <p style="margin: 0 0 15px 0; font-size: 0.85rem; color: var(--text-secondary); line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">

                                        ${lesson.full_text ? lesson.full_text.substring(0, 150) + '...' : '\u0644\u0627 \u064a\u0648\u062c\u062f \u0646\u0635 \u0644\u0644\u062a\u0641\u0631\u064a\u063a'}

                                    </p>

                                </div>

                                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: auto; border-top: 1px solid var(--border); padding-top: 12px; gap: 8px;">

                                    <span style="font-size: 0.8rem; color: var(--text-secondary); font-weight: 500;">\ud83e\udde9 ${segmentsCount} \u0641\u0642\u0631\u0629</span>

                                    <button class="btn btn-primary btn-sm" style="padding: 6px 12px; font-size: 0.8rem; height: auto;" onclick="openTranscriptDrawer('${lesson.subject}', ${lesson.lessonNum})">

                                        \ud83d\udcdd \u062a\u062d\u0631\u064a\u0631 \u0627\u0644\u062a\u0641\u0631\u064a\u063a

                                    </button>

                                </div>

                            </div>

                        `;

                    }

                }

            });

            grid.innerHTML = html;

        }

        // ─── QUESTION BANK LOGIC ───

        let currentQuestionBank = [];

        let questionsSearchTimeout = null;

        async function initQuestionBank() {

            if (!state.qbViewMode) state.qbViewMode = 'grid';

            if (!state.selectedQbSubject) state.selectedQbSubject = 'aqida';

            

            document.querySelectorAll('.view-switcher-group .btn').forEach(btn => btn.classList.remove('active'));

            const activeSwitchBtn = document.getElementById(`btn-qb-view-${state.qbViewMode}`);

            if (activeSwitchBtn) activeSwitchBtn.classList.add('active');

            document.querySelectorAll('.qb-sheet-tab').forEach(tab => tab.classList.remove('active'));

            const activeTab = document.getElementById(`tab-qb-${state.selectedQbSubject}`);

            if (activeTab) activeTab.classList.add('active');

            document.getElementById('qb-grid-view').style.display = state.qbViewMode === 'grid' ? 'block' : 'none';

            document.getElementById('qb-table-view').style.display = state.qbViewMode === 'table' ? 'block' : 'none';

            document.getElementById('qb-roadmap-view').style.display = state.qbViewMode === 'roadmap' ? 'block' : 'none';

            if (state.qbViewMode === 'table') {

                const subjFilter = document.getElementById('qb-subject-filter');

                if (subjFilter) {

                    if (state.selectedQbSubject === 'aqida') {

                        subjFilter.value = 'aqeeda';

                    } else {

                        subjFilter.value = state.selectedQbSubject;

                    }

                    updateLessonFilterDropdown();

                }

                loadQuestions(1);

            } else {

                await loadQuestionsStats();

            }

        }

        function filterQuestionsBySource(subject, lessonNum, source, chapterIdx = null) {

            closeQbThematicDrawer();

            state.qbViewMode = 'table';

            

            document.querySelectorAll('.view-switcher-group .btn').forEach(btn => btn.classList.remove('active'));

            const activeBtn = document.getElementById(`btn-qb-view-table`);

            if (activeBtn) activeBtn.classList.add('active');

            

            document.getElementById('qb-grid-view').style.display = 'none';

            document.getElementById('qb-table-view').style.display = 'block';

            document.getElementById('qb-roadmap-view').style.display = 'none';

            

            // Normalize subject: always use 'aqeeda' in the select (matches transcript data)

            const normalizedSubj = (subject === 'aqida') ? 'aqeeda' : subject;

            const subjFilter = document.getElementById('qb-subject-filter');

            if (subjFilter) {

                subjFilter.value = normalizedSubj;

                updateLessonFilterDropdown(); // populates lesson options from state.transcripts

            }

            

            // Set lesson value AFTER dropdown is populated, then enable it

            const lessonFilter = document.getElementById('qb-lesson-filter');

            if (lessonFilter) {

                lessonFilter.disabled = false;

                // If the exact option doesn't exist yet, add it on the fly

                if (!lessonFilter.querySelector(`option[value="${lessonNum}"]`)) {

                    const opt = document.createElement('option');

                    opt.value = lessonNum;

                    opt.textContent = `الدرس ${lessonNum}`;

                    lessonFilter.appendChild(opt);

                }

                lessonFilter.value = String(lessonNum);

                updateChapterFilterDropdown();

            }

            

            const chapterFilter = document.getElementById('qb-chapter-filter');

            if (chapterFilter && chapterIdx !== null) {

                chapterFilter.disabled = false;

                if (!chapterFilter.querySelector(`option[value="${chapterIdx}"]`)) {

                    const opt = document.createElement('option');

                    opt.value = chapterIdx;

                    opt.textContent = `المحور ${parseInt(chapterIdx)+1}`;

                    chapterFilter.appendChild(opt);

                }

                chapterFilter.value = String(chapterIdx);

            } else if (chapterFilter) {

                chapterFilter.value = '';

            }

            

            const sourceFilter = document.getElementById('qb-source-filter');

            if (sourceFilter) {

                sourceFilter.value = source;

            }

            

            loadQuestions(1);

        }

        async function loadQuestionsStats() {

            const gridContainer = document.getElementById('qb-courses-grid-container');

            const roadmapContainer = document.getElementById('qb-roadmap-flow-container');

            

            gridContainer.innerHTML = '<div style="grid-column: 1/-1; text-align:center; padding: 40px;">جاري تحميل إحصائيات بنك الأسئلة... ⏳</div>';

            roadmapContainer.innerHTML = '<div style="text-align:center; padding: 40px;">جاري تحميل إحصائيات بنك الأسئلة... ⏳</div>';

            try {

                const response = await fetch('/admin/questions/stats', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({ userId: state.userId })

                });

                const data = await response.json();

                

                if (data.success) {

                    state.questionsStats = data.stats;

                    updateQbTabLabels(data.stats);

                    renderQuestionsGrid();

                    renderQuestionsRoadmap();

                } else {

                    gridContainer.innerHTML = `<div style="grid-column: 1/-1; text-align:center; color: red; padding: 20px;">خطأ: ${data.error}</div>`;

                    roadmapContainer.innerHTML = `<div style="text-align:center; color: red; padding: 20px;">خطأ: ${data.error}</div>`;

                }

            } catch (err) {

                gridContainer.innerHTML = `<div style="grid-column: 1/-1; text-align:center; color: red; padding: 20px;">خطأ في الاتصال بقاعدة البيانات</div>`;

                roadmapContainer.innerHTML = `<div style="text-align:center; color: red; padding: 20px;">خطأ في الاتصال بقاعدة البيانات</div>`;

            }

        }

        function updateQbTabLabels(stats) {
            if (!stats) return;
            const arabNames = {
                aqida: "العقيدة",
                fiqh: "الفقه",
                sira: "السيرة",
                nahw: "النحو",
                tajweed: "التجويد"
            };
            Object.keys(arabNames).forEach(subject => {
                const tabEl = document.getElementById(`tab-qb-${subject}`);
                if (!tabEl) return;
                const subjectStats = stats[subject] || {};
                let totalQ = 0;
                let hasEmpty = false;
                
                Object.values(subjectStats).forEach(cData => {
                    totalQ += (cData.total || 0);
                    if (cData.total === 0) {
                        hasEmpty = true;
                    }
                    if (cData.chapters && cData.chapters.some(ch => ch.count === 0)) {
                        hasEmpty = true;
                    }
                });
                
                let label = `📑 ${arabNames[subject]} (${totalQ})`;
                if (hasEmpty) {
                    label += ` <span class="qb-tab-warning-dot" style="display:inline-block; width:8px; height:8px; background:#ef4444; border-radius:50%; margin-left:6px; box-shadow: 0 0 8px #ef4444;" title="يفتقر لبعض الأسئلة"></span>`;
                }
                tabEl.innerHTML = label;
            });
        }

        function closeQbThematicDrawer() {

            const backdrop = document.getElementById('qb-thematic-drawer-backdrop');

            const drawer = document.getElementById('qb-course-thematic-detail');

            if (backdrop) backdrop.classList.remove('show');

            if (drawer) drawer.classList.remove('open');

            state.selectedQbCourse = null;

        }

        function renderQuestionsGrid() {

            const container = document.getElementById('qb-courses-grid-container');

            container.innerHTML = '';

            

            const stats = state.questionsStats;

            if (!stats) return;

            

            const selectedSubject = state.selectedQbSubject;

            const subjectStats = stats[selectedSubject] || {};

            

            const courses = Object.keys(subjectStats).map(Number).sort((a, b) => a - b);

            

            if (courses.length === 0) {

                container.innerHTML = '<div style="grid-column: 1/-1; text-align:center; padding: 40px; color: var(--text-secondary);">لا توجد دروس أو أسئلة لهذه Mادة حالياً.</div>';

                return;

            }

            

            courses.forEach(cNum => {

                const cData = subjectStats[cNum];

                const card = document.createElement('div');

                card.className = `qb-course-card`;

                card.style.borderTop = `3px solid ${SUBJECT_COLORS[selectedSubject] || '#ccc'}`;

                card.onclick = () => showCourseThematics(cNum);

                

                card.innerHTML = `

                    <div class="qb-course-card-header">

                        <span>الدرس ${cNum}</span>

                        <span style="font-size: 0.72rem; color: var(--text-secondary);">تفاصيل 🔍</span>

                    </div>

                    <div class="qb-course-card-total" style="${cData.total === 0 ? 'color:#ef4444; font-weight:bold; font-size:1.1rem; margin:2px 0;' : 'font-size:1.2rem; margin:2px 0;'}">
                        ${cData.total === 0 
                            ? `0 <span style="font-size: 0.75rem; font-weight: 500; color: #ef4444;">أسئلة ⚠️ يفتقر للأسئلة</span>` 
                            : `${cData.total} <span style="font-size: 0.75rem; font-weight: 500; color: var(--text-secondary);">أسئلة</span>${(cData.chapters && cData.chapters.some(ch => ch.count === 0)) ? ' <span style="color:#ef4444; font-size:0.8rem; margin-left:4px;" title="بعض المحاور فارغة">⚠️</span>' : ''}`
                        }
                    </div>

                    <div class="qb-card-sources-list">

                        <div class="qb-card-source-row qb-source-official" onclick="filterQuestionsBySource('${selectedSubject}', ${cNum}, 'official', null); event.stopPropagation();">

                            <span class="qb-card-source-emoji">🎓</span>

                            <span class="qb-card-source-text">رسمي</span>

                            <span class="qb-card-source-count">${cData.official}</span>

                        </div>

                        <div class="qb-card-source-row qb-source-proposal" onclick="filterQuestionsBySource('${selectedSubject}', ${cNum}, 'student_proposal', null); event.stopPropagation();">

                            <span class="qb-card-source-emoji">💡</span>

                            <span class="qb-card-source-text">مقترح</span>

                            <span class="qb-card-source-count">${cData.student_proposal}</span>

                        </div>

                        <div class="qb-card-source-row qb-source-ai" onclick="filterQuestionsBySource('${selectedSubject}', ${cNum}, 'ai_generated', null); event.stopPropagation();">

                            <span class="qb-card-source-emoji">🪄</span>

                            <span class="qb-card-source-text">ذكاء</span>

                            <span class="qb-card-source-count">${cData.ai_generated}</span>

                        </div>

                    </div>

                    <button class="btn" style="margin-top:8px; width:100%; padding:6px 8px; font-size:0.78rem; background: linear-gradient(135deg,#7c3aed,#5b21b6); color:#fff; border:none; border-radius:8px; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:5px;" onclick="openAiGenerateModal('${selectedSubject}', ${cNum}, 0, 'توليد أسئلة جديدة'); event.stopPropagation();">🪄 توليد أسئلة ذكاء اصطناعي</button>

                `;

                container.appendChild(card);

            });

            

            if (state.selectedQbCourse && subjectStats[state.selectedQbCourse]) {

                showCourseThematics(state.selectedQbCourse);

            } else {

                closeQbThematicDrawer();

            }

        }

        let activeAiGenerationParams = null;

        let generatedAiQuestionsCache = null;

        function openAiGenerateModal(subject, lessonNum, chapterIdx, themeTitle) {

            // Normalize: SUBJECTS_AR uses 'aqeeda', stats uses 'aqida' - handle both

            const subjForDisplay = (subject === 'aqida') ? 'aqeeda' : subject;

            const subjLabel = SUBJECTS_AR[subjForDisplay] || SUBJECTS_AR[subject] || subject;

            activeAiGenerationParams = { subject, lessonNum, chapterIdx, theme: themeTitle };

            generatedAiQuestionsCache = null;

            document.getElementById('qb-ai-modal-subtitle').innerText = `${subjLabel} — الدرس ${lessonNum}${chapterIdx > 0 ? ' — المحور ' + (chapterIdx + 1) : ''}: ${themeTitle}`;

            document.getElementById('qb-ai-instructions').value = '';

            document.getElementById('qb-ai-preview-section').style.display = 'none';

            document.getElementById('qb-ai-preview-list').innerHTML = '';

            // Reset strategy selector
            const strategySelect = document.getElementById('qb-ai-strategy');
            if (strategySelect) strategySelect.value = 'smart';
            const specCont = document.getElementById('qb-ai-specific-subtheme-container');
            if (specCont) specCont.style.display = 'none';

            // Populate specific subthemes
            const specSelect = document.getElementById('qb-ai-specific-subtheme');
            if (specSelect) {
                specSelect.innerHTML = '<option value="">-- اختر المحور الفرعي --</option>';
                const subj = subject.toLowerCase() === 'aqeeda' ? 'aqida' : subject.toLowerCase();
                if (state.questionsStats && state.questionsStats[subj] && state.questionsStats[subj][lessonNum]) {
                    const chapters = state.questionsStats[subj][lessonNum].chapters || [];
                    chapters.forEach(ch => {
                        const opt = document.createElement('option');
                        opt.value = ch.title;
                        opt.textContent = ch.title;
                        specSelect.appendChild(opt);
                    });
                }
            }

            document.getElementById('qb-ai-generate-modal').classList.add('show');

            document.getElementById('qb-ai-generate-panel').classList.add('open');

        }

        window.onAiStrategyChange = function() {
            const strategy = document.getElementById('qb-ai-strategy').value;
            const container = document.getElementById('qb-ai-specific-subtheme-container');
            if (container) {
                container.style.display = strategy === 'specific' ? 'block' : 'none';
            }
        };

        function closeAiGenerateModal() {

            document.getElementById('qb-ai-generate-modal').classList.remove('show');

            document.getElementById('qb-ai-generate-panel').classList.remove('open');

            activeAiGenerationParams = null;

            generatedAiQuestionsCache = null;

        }

        async function submitAiGenerateQuestions() {

            if (!activeAiGenerationParams) return;

            

            const submitBtn = document.getElementById('btn-qb-ai-generate-submit');

            const previewSection = document.getElementById('qb-ai-preview-section');

            const previewList = document.getElementById('qb-ai-preview-list');

            

            submitBtn.disabled = true;

            submitBtn.innerText = '⏳ جاري التوليد الذكي عبر Gemini...';

            previewSection.style.display = 'none';

            previewList.innerHTML = '';

            

            const numQuestions = document.getElementById('qb-ai-num-questions').value;

            const modelName = document.getElementById('qb-ai-model').value;

            const instructions = document.getElementById('qb-ai-instructions').value;

            

            try {

                const response = await fetch('/admin/questions/generate-ia', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({

                        userId: state.userId,

                        subject: activeAiGenerationParams.subject,

                        lessonNum: activeAiGenerationParams.lessonNum,

                        chapterIdx: activeAiGenerationParams.chapterIdx,

                        theme: activeAiGenerationParams.theme,

                        numQuestions: parseInt(numQuestions),

                        instructions: instructions,

                        model: modelName,

                        strategy: document.getElementById('qb-ai-strategy').value,

                        specificSubtheme: document.getElementById('qb-ai-specific-subtheme').value

                    })

                });

                const data = await response.json();

                

                if (data.success) {

                    generatedAiQuestionsCache = data.questions;

                    

                    let html = '';

                    data.questions.forEach((q, idx) => {

                        html += `

                            <div style="background: var(--bg); border: 1px solid var(--border); padding: 12px; border-radius: var(--radius-sm); direction: rtl; text-align: right;">

                                <strong>السؤال ${idx + 1}:</strong> ${escapeHtml(q.question)}

                                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px;">

                                    <div style="${q.correct_answer === 'a' ? 'color:#10b981; font-weight:bold;' : ''}">أ) ${escapeHtml(q.choice_a)}</div>

                                    <div style="${q.correct_answer === 'b' ? 'color:#10b981; font-weight:bold;' : ''}">ب) ${escapeHtml(q.choice_b)}</div>

                                    <div style="${q.correct_answer === 'c' ? 'color:#10b981; font-weight:bold;' : ''}">ج) ${escapeHtml(q.choice_c || '')}</div>

                                    <div style="${q.correct_answer === 'd' ? 'color:#10b981; font-weight:bold;' : ''}">د) ${escapeHtml(q.choice_d || '')}</div>

                                </div>

                                ${q.explanation ? `<div style="font-size:0.8rem; color:var(--text-secondary); border-top:1px dashed var(--border); margin-top:8px; padding-top:6px;">💡 شرح الإجابة: ${escapeHtml(q.explanation)}</div>` : ''}

                            </div>

                        `;

                    });

                    

                    previewList.innerHTML = html;

                    previewSection.style.display = 'block';

                    showNotification('تم توليد الأسئلة بنجاح! راجعها بالأسفل لحفظها.', 'success');

                } else {

                    showNotification('خطأ: ' + data.error, 'error');

                }

            } catch (err) {

                showNotification('خطأ في الاتصال بالذكاء الاصطناعي', 'error');

            } finally {

                submitBtn.disabled = false;

                submitBtn.innerText = '🪄 بدء التوليد الذكي';

            }

        }

        async function saveBulkAiQuestions() {

            if (!activeAiGenerationParams || !generatedAiQuestionsCache || generatedAiQuestionsCache.length === 0) return;

            

            const saveBtn = document.getElementById('btn-qb-ai-save-all');

            saveBtn.disabled = true;

            saveBtn.innerText = '⏳ جاري الحفظ والدمج في قاعدة البيانات...';

            

            try {

                const response = await fetch('/admin/questions/save-bulk', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({

                        userId: state.userId,

                        subject: activeAiGenerationParams.subject,

                        lessonNum: activeAiGenerationParams.lessonNum,

                        questions: generatedAiQuestionsCache

                    })

                });

                const data = await response.json();

                

                if (data.success) {

                    showNotification(`تم حفظ ${generatedAiQuestionsCache.length} أسئلة بنجاح في بنك الأسئلة!`, 'success');

                    closeAiGenerateModal();

                    

                    state.questionsStats = null;

                    if (state.qbViewMode === 'table') {

                        loadQuestions(1);

                    } else {

                        loadQuestionsStats();

                    }

                } else {

                    showNotification('خطأ في حفظ الأسئلة: ' + data.error, 'error');

                }

            } catch (err) {

                showNotification('خطأ في الاتصال بالسيرفر أثناء حفظ الأسئلة', 'error');

            } finally {

                saveBtn.disabled = false;

                saveBtn.innerText = '💾 حفظ وحقن كل الأسئلة في بنك الأسئلة';

            }

        }

        async function showCourseThematics(courseNum) {
            state.selectedQbCourse = courseNum;
            const detailContainer = document.getElementById('qb-course-thematic-detail');
            const backdrop = document.getElementById('qb-thematic-drawer-backdrop');
            
            const stats = state.questionsStats;
            if (!stats) return;
            
            const selectedSubject = state.selectedQbSubject;
            const courseData = (stats[selectedSubject] || {})[courseNum];
            if (!courseData) return;
            
            if (backdrop) backdrop.classList.add('show');
            if (detailContainer) {
                detailContainer.classList.add('open');
                detailContainer.innerHTML = '<div style="padding: 40px; text-align: center; color: var(--text-secondary);">جاري تحميل الأسئلة (Lecture Rapide)... ⏳</div>';
            }
            
            let questions = [];
            try {
                const response = await fetch('/admin/questions-list', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ userId: state.userId, page: 1, per_page: 500, subject: selectedSubject, lessonNum: courseNum })
                });
                const data = await response.json();
                if (data.success) {
                    questions = data.questions;
                }
            } catch (err) {
                console.error("Failed to load questions for rapid read mode", err);
            }

            let html = `
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; border-bottom:1px solid var(--border); padding-bottom:16px;">
                    <div>
                        <h2 style="margin:0; font-size:1.2rem; color: var(--text-primary);">📚 التغطية الموضوعية للدرس ${courseNum} (Lecture Rapide)</h2>
                        <div style="font-size:0.8rem; color:var(--text-secondary); margin-top:4px;">${SUBJECTS_AR[selectedSubject]}</div>
                    </div>
                    <button class="btn btn-secondary" onclick="closeQbThematicDrawer()" style="padding: 6px 12px; height: auto;">✖ إغلاق</button>
                </div>
                <div class="qb-thematics-list" style="display: flex; flex-direction: column; gap: 16px;">
            `;
            
            const chapters = courseData.chapters || [];
            if (chapters.length === 0 && questions.length === 0) {
                html += `<div style="text-align: center; color: var(--text-secondary); padding: 20px;">لا توجد محاور أو أسئلة مسجلة لهذا الدرس بعد.</div>`;
            } else {
                chapters.forEach(ch => {
                    const emptyWarning = ch.count === 0 
                        ? `<div style="color: #ef4444; font-size: 0.72rem; font-weight: bold; background: rgba(239, 68, 68, 0.08); padding: 4px 8px; border-radius: 4px; display: inline-flex; align-items: center; gap: 4px; margin-top: 4px;">⚠️ منطقة بيضاء (المحور يفتقر تماماً للأسئلة)</div>`
                        : '';
                    
                    html += `
                        <div class="qb-thematic-item" style="flex-direction: column; align-items: stretch; gap: 8px; padding: 16px; border-radius: var(--radius-md); border: 1px solid var(--border); ${ch.count === 0 ? 'border-right: 4px solid #ef4444; background: rgba(239, 68, 68, 0.03);' : 'border-right: 4px solid ' + (SUBJECT_COLORS[selectedSubject] || 'var(--border)') + '; background: var(--bg);'}">
                            <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
                                <span class="qb-thematic-title" style="font-size: 1rem; font-weight: 700; color: var(--text-primary);">المحور ${ch.chapter_index}: ${escapeHtml(ch.title)}</span>
                                <div style="display: flex; align-items: center; gap: 8px;">
                                    <span class="badge" style="background: var(--surface-hover); color: var(--text-primary); border: 1px solid var(--border); font-size: 0.75rem; font-weight: 700;">${ch.count} أسئلة</span>
                                    <button class="btn btn-primary btn-3d" style="padding: 2px 6px; font-size: 0.68rem; height: auto; font-weight: bold;" onclick="openAiGenerateModal('${selectedSubject}', ${courseNum}, ${ch.chapter_index - 1}, '${escapeHtml(ch.title).replace(/'/g, "\\'")}')">🪄 توليد ذكاء</button>
                                </div>
                            </div>
                            ${emptyWarning}
                    `;

                    const chQuestions = questions.filter(q => String(q.chapter_index) === String(ch.chapter_index));
                    if (chQuestions.length > 0) {
                        html += `<div style="margin-top: 12px; display: flex; flex-direction: column; gap: 10px;">`;
                        chQuestions.forEach(q => {
                            const sourceClass = q.source === 'IA' ? 'source-ai' : (q.source === 'USER' ? 'source-user' : 'source-official');
                            html += `
                                <div class="draggable-question ${sourceClass}" style="background: var(--surface-hover); border: 1px solid var(--border);">
                                    <div class="draggable-question-header" style="justify-content: space-between;">
                                        <div style="display: flex; align-items: center; gap: 8px;">
                                            <span class="question-id-badge" style="position: static; font-size: 0.7rem;">#${q.id}</span>
                                            <span style="font-size: 0.75rem; color: var(--text-secondary); font-weight: bold;">
                                                ${q.source === 'IA' ? '🪄 ذكاء اصطناعي' : (q.source === 'USER' ? '💡 مقترح' : '🎓 رسمي')}
                                            </span>
                                        </div>
                                        <button class="btn btn-secondary btn-sm" style="font-size: 0.75rem; padding: 4px 8px;" onclick="openQuestionDrawer(${q.id})">✏️ Détails</button>
                                    </div>
                                    <div class="draggable-question-text" style="margin-top: 8px; font-size: 0.95rem;">${q.question || 'بدون نص'}</div>
                                </div>
                            `;
                        });
                        html += `</div>`;
                    }
                    html += `</div>`;
                });
            }
            
            // Show unmapped questions
            const unmappedQuestions = questions.filter(q => q.chapter_index === null || q.chapter_index === undefined || q.chapter_index === '');
            if (unmappedQuestions.length > 0) {
                html += `
                    <div class="qb-thematic-item" style="flex-direction: column; align-items: stretch; gap: 8px; padding: 16px; border-radius: var(--radius-md); border: 1px solid var(--border); border-right: 4px solid var(--text-secondary); background: var(--bg);">
                        <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
                            <span class="qb-thematic-title" style="font-size: 1rem; font-weight: 700; color: var(--text-secondary);">أسئلة غير مصنفة بمحور</span>
                            <span class="badge" style="background: var(--surface-hover); color: var(--text-primary); border: 1px solid var(--border); font-size: 0.75rem; font-weight: 700;">${unmappedQuestions.length} أسئلة</span>
                        </div>
                        <div style="margin-top: 12px; display: flex; flex-direction: column; gap: 10px;">
                `;
                unmappedQuestions.forEach(q => {
                    const sourceClass = q.source === 'IA' ? 'source-ai' : (q.source === 'USER' ? 'source-user' : 'source-official');
                    html += `
                        <div class="draggable-question ${sourceClass}" style="background: var(--surface-hover); border: 1px solid var(--border);">
                            <div class="draggable-question-header" style="justify-content: space-between;">
                                <div style="display: flex; align-items: center; gap: 8px;">
                                    <span class="question-id-badge" style="position: static; font-size: 0.7rem;">#${q.id}</span>
                                    <span style="font-size: 0.75rem; color: var(--text-secondary); font-weight: bold;">
                                        ${q.source === 'IA' ? '🪄 ذكاء اصطناعي' : (q.source === 'USER' ? '💡 مقترح' : '🎓 رسمي')}
                                    </span>
                                </div>
                                <button class="btn btn-secondary btn-sm" style="font-size: 0.75rem; padding: 4px 8px;" onclick="openQuestionDrawer(${q.id})">✏️ Détails</button>
                            </div>
                            <div class="draggable-question-text" style="margin-top: 8px; font-size: 0.95rem;">${q.question || 'بدون نص'}</div>
                        </div>
                    `;
                });
                html += `</div></div>`;
            }

            html += `</div>`;
            if (detailContainer) detailContainer.innerHTML = html;
        }

        function renderQuestionsRoadmap() {

            const container = document.getElementById('qb-roadmap-flow-container');

            container.innerHTML = '';

            

            const stats = state.questionsStats;

            if (!stats) return;

            

            const selectedSubject = state.selectedQbSubject;

            const subjectStats = stats[selectedSubject] || {};

            

            const courses = Object.keys(subjectStats).map(Number).sort((a, b) => a - b);

            

            if (courses.length === 0) {

                container.innerHTML = '<div style="text-align:center; padding: 40px; color: var(--text-secondary);">لا توجد دروس أو أسئلة لهذه المادة حالياً لعرض خارطة المنهج.</div>';

                return;

            }

            

            let html = `

                <div style="margin-bottom: 20px; border-bottom: 1px solid var(--border); padding-bottom: 12px;">

                    <h3 style="margin: 0; color: var(--text-primary);">🗺️ الخارطة الزمنية وتغطية المنهج - ${SUBJECTS_AR[selectedSubject]}</h3>

                    <p style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 4px;">تتبع تسلسلي لجميع الدروس ومحاورها لقياس تغطية الأسئلة.</p>

                </div>

                <div class="qb-roadmap-flow">

            `;

            

            courses.forEach(cNum => {

                const cData = subjectStats[cNum];

                const chapters = cData.chapters || [];

                

                const emptyChapsCount = chapters.filter(ch => ch.count === 0).length;

                let statusBadge = `<span class="badge badge-success">مغطى بالكامل</span>`;

                if (chapters.length === 0) {

                    statusBadge = `<span class="badge badge-secondary">لا توجد محاور</span>`;

                } else if (emptyChapsCount === chapters.length) {

                    statusBadge = `<span class="badge badge-danger">غير مغطى إطلاقاً</span>`;

                } else if (emptyChapsCount > 0) {

                    statusBadge = `<span class="badge badge-warning">تغطية جزئية (${chapters.length - emptyChapsCount}/${chapters.length})</span>`;

                }

                

                html += `

                    <div class="qb-roadmap-node ${cData.total > 0 ? 'active' : ''}" style="border-right: 4px solid ${SUBJECT_COLORS[selectedSubject] || 'var(--border)'}">

                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">

                            <strong style="font-size: 1rem; color: var(--text-primary);">الدرس ${cNum}</strong>

                            <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">

                                ${statusBadge}

                                <span class="badge" style="background: var(--border-glow); color: var(--text-primary); border: 1px solid var(--border); font-size: 0.75rem;">إجمالي: ${cData.total} أسئلة</span>

                                <span class="qb-source-pill qb-source-official" style="font-size:0.7rem; padding: 2px 6px;">🎓 رسمي: ${cData.official}</span>

                                <span class="qb-source-pill qb-source-proposal" style="font-size:0.7rem; padding: 2px 6px;">💡 مقترح: ${cData.student_proposal}</span>

                                <span class="qb-source-pill qb-source-ai" style="font-size:0.7rem; padding: 2px 6px;">🪄 ذكاء: ${cData.ai_generated}</span>

                            </div>

                        </div>

                        <div style="font-size: 0.82rem; color: var(--text-secondary);">

                `;

                

                if (chapters.length === 0) {

                    html += `<div style="padding: 4px 0; font-style: italic;">لا توجد محاور لهذا الدرس في قاعدة البيانات.</div>`;

                } else {

                    html += `<div style="display: flex; flex-direction: column; gap: 4px; margin-top: 8px;">`;

                    chapters.forEach(ch => {

                        const icon = ch.count > 0 ? '✅' : '❌';

                        const colorStyle = ch.count > 0 ? '' : 'color: #ef4444; font-weight: bold;';

                        html += `

                            <div style="display: flex; justify-content: space-between; align-items: center; padding: 4px 8px; background: rgba(255,255,255,0.01); border-radius: 4px;">

                                <span style="${colorStyle}">${icon} المحور ${ch.chapter_index}: ${escapeHtml(ch.title)}</span>

                                <span style="font-size: 0.75rem; color: var(--text-secondary);">${ch.count} أسئلة</span>

                            </div>

                        `;

                    });

                    html += `</div>`;

                }

                

                html += `

                        </div>

                    </div>

                `;

            });

            

            html += `</div>`;

            container.innerHTML = html;

        }

        function switchQbViewMode(mode) {
            state.qbViewMode = mode;
            
            document.querySelectorAll('.view-switcher-group .btn').forEach(btn => btn.classList.remove('active'));
            const activeBtn = document.getElementById(`btn-qb-view-${mode}`);
            if (activeBtn) activeBtn.classList.add('active');
            
            document.getElementById('qb-grid-view').style.display = mode === 'grid' ? 'block' : 'none';
            document.getElementById('qb-table-view').style.display = (mode === 'table' || mode === 'panoramic') ? 'block' : 'none';
            document.getElementById('qb-roadmap-view').style.display = mode === 'roadmap' ? 'block' : 'none';
            
            const panoramicView = document.getElementById('qb-panoramic-view');
            if (panoramicView) {
                panoramicView.style.display = mode === 'panoramic' ? 'block' : 'none';
            }
            
            const tableContainer = document.querySelector('.table-container');
            if (tableContainer) {
                tableContainer.style.display = mode === 'panoramic' ? 'none' : 'block';
            }
            
            if (mode === 'table' || mode === 'panoramic') {
                const subjFilter = document.getElementById('qb-subject-filter');
                if (subjFilter) {
                    if (state.selectedQbSubject === 'aqida') {
                        subjFilter.value = 'aqeeda';
                    } else {
                        subjFilter.value = state.selectedQbSubject;
                    }
                    updateLessonFilterDropdown();
                    updateThemeFilterDropdown();
                }
                loadQuestions(1);
            } else {
                if (state.questionsStats) {
                    if (mode === 'grid') renderQuestionsGrid();
                    if (mode === 'roadmap') renderQuestionsRoadmap();
                } else {
                    loadQuestionsStats();
                }
            }
        }

        

        async function selectQbSubject(subject) {

            state.selectedQbSubject = subject;

            state.selectedQbCourse = null;

            

            document.querySelectorAll('.qb-sheet-tab').forEach(tab => tab.classList.remove('active'));

            const activeTab = document.getElementById(`tab-qb-${subject}`);

            if (activeTab) activeTab.classList.add('active');

            

            if (state.qbViewMode === 'table' || state.qbViewMode === 'panoramic') {

                const subjFilter = document.getElementById('qb-subject-filter');

                if (subjFilter) {

                    if (subject === 'aqida') {

                        subjFilter.value = 'aqeeda';

                    } else {

                        subjFilter.value = subject;

                    }

                    updateLessonFilterDropdown();
                    updateThemeFilterDropdown();

                }

                loadQuestions(1);

            } else {

                if (state.questionsStats) {

                    renderQuestionsGrid();

                    renderQuestionsRoadmap();

                } else {

                    await loadQuestionsStats();

                }

            }

        }

        function debounceLoadQuestions() {

            clearTimeout(questionsSearchTimeout);

            questionsSearchTimeout = setTimeout(() => loadQuestions(1), 500);

        }

        async function loadQuestions(page) {

            const subject = document.getElementById('qb-subject-filter').value;

            const lessonNum = document.getElementById('qb-lesson-filter').value;

            const source = document.getElementById('qb-source-filter').value;

            const search = document.getElementById('qb-search-input').value;
            const chapterIdx = document.getElementById('qb-chapter-filter') ? document.getElementById('qb-chapter-filter').value : '';
            const theme = document.getElementById('qb-theme-filter') ? document.getElementById('qb-theme-filter').value : '';
            const sub_theme = document.getElementById('qb-subtheme-filter') ? document.getElementById('qb-subtheme-filter').value : '';

            const tbody = document.getElementById('questions-table-body');
            const panoramicContainer = document.getElementById('qb-panoramic-container');

            if (state.qbViewMode === 'table' && tbody) {
                tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding: 40px;">جاري تحميل الأسئلة... ⏳</td></tr>';
            } else if (state.qbViewMode === 'panoramic' && panoramicContainer) {
                panoramicContainer.innerHTML = '<div style="text-align:center; padding: 40px;">جاري تحميل الأسئلة... ⏳</div>';
            }

            try {
                const response = await fetch('/admin/questions-list', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ userId: state.userId, page, per_page: state.qbViewMode === 'panoramic' ? 100 : 50, subject, lessonNum, source, search, chapterIdx, theme, sub_theme })
                });

                const data = await response.json();

                

                if (data.success) {
                    currentQuestionBank = data.questions;
                    if (state.qbViewMode === 'panoramic') {
                        renderQuestionsPanoramic(data.questions);
                    } else {
                        renderQuestions(data.questions);
                    }
                    renderQuestionsPagination(data.pagination);

                } else {

                    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color: red;">خطأ: ${data.error}</td></tr>`;

                }

            } catch (err) {
                tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color: red;">خطأ في الاتصال</td></tr>`;
            }
        }

        async function deleteQuestion(questionId) {
            if (!confirm('هل أنت متأكد من رغبتك في حذف هذا السؤال نهائياً؟ لا يمكن التراجع عن هذا الإجراء.')) return;
            try {
                const response = await fetch('/admin/delete-question', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ userId: state.userId, questionId })
                });
                const data = await response.json();
                if (data.success) {
                    showToast('تم حذف السؤال بنجاح', 'success');
                    loadQuestions(state.questionsPage);
                    state.questionsStats = null;
                } else {
                    showToast('خطأ: ' + data.error, 'error');
                }
            } catch (err) {
                showToast('خطأ في الاتصال بالسيرفر', 'error');
            }
        }

        function toggleAllQuestions(checkbox) {
            const rowCheckboxes = document.querySelectorAll('.q-row-checkbox');
            rowCheckboxes.forEach(cb => {
                cb.checked = checkbox.checked;
                const row = cb.closest('tr');
                if (checkbox.checked) row.classList.add('selected-row');
                else row.classList.remove('selected-row');
            });
            updateBulkDeleteButton();
        }

        function toggleQuestionRowCheckbox(event, id) {
            // Prevent toggling if clicking on buttons or inputs
            if (event.target.tagName === 'BUTTON' || event.target.tagName === 'INPUT' || event.target.closest('button')) return;
            const cb = document.querySelector(`.q-row-checkbox[value="${id}"]`);
            if (cb) {
                cb.checked = !cb.checked;
                const row = cb.closest('tr');
                if (cb.checked) row.classList.add('selected-row');
                else row.classList.remove('selected-row');
                updateBulkDeleteButton();
            }
        }

        function updateBulkDeleteButton() {
            const checkedCount = document.querySelectorAll('.q-row-checkbox:checked').length;
            const btn = document.getElementById('btn-bulk-delete-q');
            const countSpan = document.getElementById('bulk-q-count');
            
            if (checkedCount > 0) {
                btn.style.display = 'flex';
                countSpan.textContent = checkedCount;
            } else {
                btn.style.display = 'none';
            }
        }

        async function deleteSelectedQuestions() {
            const checkedBoxes = document.querySelectorAll('.q-row-checkbox:checked');
            const questionIds = Array.from(checkedBoxes).map(cb => parseInt(cb.value));
            
            if (questionIds.length === 0) return;
            
            if (!confirm(`هل أنت متأكد من رغبتك في حذف ${questionIds.length} سؤال نهائياً؟ لا يمكن التراجع عن هذا الإجراء.`)) return;
            
            try {
                // Call bulk delete endpoint
                const response = await fetch('/admin/delete-bulk-questions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ userId: state.userId, questionIds })
                });
                const data = await response.json();
                if (data.success) {
                    showToast(`تم حذف ${questionIds.length} سؤال بنجاح`, 'success');
                    loadQuestions(state.questionsPage);
                    state.questionsStats = null;
                } else {
                    showToast('خطأ: ' + data.error, 'error');
                }
            } catch (err) {
                showToast('خطأ في الاتصال بالسيرفر', 'error');
            }
        }

        async function toggleQuestionActive(questionId, checkbox) {

            const isActive = checkbox.checked;

            const originalState = !isActive;

            try {

                const response = await fetch('/admin/toggle-question-active', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({ userId: state.userId, questionId, isActive })

                });

                const data = await response.json();

                if (data.success) {

                    showToast(isActive ? 'تم تفعيل السؤال بنجاح' : 'تم إخفاء السؤال بنجاح', 'success');

                    state.questionsStats = null;

                } else {

                    showToast('خطأ: ' + data.error, 'error');

                    checkbox.checked = originalState;

                }

            } catch (err) {

                showToast('خطأ في الاتصال بالسيرفر', 'error');

                checkbox.checked = originalState;

            }

        }

        function renderQuestions(questions) {

            const tbody = document.getElementById('questions-table-body');

            if (!questions.length) {

                tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding: 40px;">لا توجد أسئلة تطابق بحثك.</td></tr>';

                return;

            }

            

            let html = '';

            for (const q of questions) {

                const statusToggle = `

                    <label class="modern-toggle-switch" title="${q.is_active === 0 ? 'مخفي' : 'نشط'}">

                        <input type="checkbox" ${q.is_active !== 0 ? 'checked' : ''} onchange="toggleQuestionActive(${q.id}, this)">

                        <span class="modern-toggle-slider"></span>

                    </label>

                `;

                    

                const subjColor = SUBJECT_COLORS[q.subject] || '#ccc';

                

                let sourceBadgeHtml = '<span class="source-badge source-official">رسمي 🎓</span>';

                if (q.source === 'student_proposal') {

                    const proposerText = q.proposed_by 

                        ? `طالب: ${escapeHtml(q.proposed_by.first_name)}${q.proposed_by.username ? ' (@' + escapeHtml(q.proposed_by.username) + ')' : ''}` 

                        : 'مقترح طالب';

                    sourceBadgeHtml = `<span class="source-badge source-proposal" title="${proposerText}">${proposerText} 💡</span>`;

                } else if (q.source === 'ai_generated' || q.source === 'generated_by_gemini') {

                    sourceBadgeHtml = '<span class="source-badge source-ai">ذكاء اصطناعي 🪄</span>';

                } else if (q.source === 'whatsapp') {

                    sourceBadgeHtml = '<span class="source-badge source-whatsapp">واتساب 💬</span>';

                } else if (q.source === 'telegram') {

                    sourceBadgeHtml = '<span class="source-badge source-telegram">تيليجرام 📱</span>';

                } else if (q.source) {

                    // Translate any fallback text to Arabic if known

                    let sourceName = escapeHtml(q.source);

                    if (sourceName.toLowerCase() === 'official') sourceName = 'رسمي 🎓';

                    sourceBadgeHtml = `<span class="source-badge source-official">${sourceName}</span>`;

                }

                // Format theme / thematic index or title nicely

                const themeText = q.theme ? escapeHtml(q.theme) : 'غير محدد 📍';

                

                // Format created_at date nicely in Arabic
                let formattedDate = 'غير محدد 📅';
                if (q.created_at) {
                    try {
                        const dateObj = new Date(q.created_at.replace(' ', 'T'));
                        if (!isNaN(dateObj.getTime())) {
                            const monthsAr = [
                                "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
                                "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"
                            ];
                            const day = dateObj.getDate();
                            const month = monthsAr[dateObj.getMonth()];
                            const year = dateObj.getFullYear();
                            formattedDate = `${day} ${month} ${year}`;
                        }
                    } catch (e) {
                        console.error("Error formatting date:", e);
                    }
                }

                html += `

                    <tr class="ticket-row" onclick="toggleQuestionRowCheckbox(event, ${q.id})">

                        <td style="text-align: center;"><input type="checkbox" class="q-row-checkbox" value="${q.id}" onchange="updateBulkDeleteButton()"></td>

                        <td>${q.id}</td>

                        <td><span class="badge" style="background: ${subjColor}20; color: ${subjColor}; border: 1px solid ${subjColor}40;">${SUBJECTS_AR[q.subject] || q.subject}</span></td>

                        <td>الدرس ${q.course_number}</td>

                        <td><span class="badge" style="background: rgba(255,255,255,0.05); color: var(--text-secondary); border: 1px solid rgba(255,255,255,0.1); font-size: 0.8rem; padding: 4px 8px; border-radius: 4px;">${themeText}</span></td>

                        <td>${(() => {
                            if (!q.sub_theme) return '<span style="color:var(--text-secondary); font-style:italic; font-size:0.8rem;">-- غير محدد --</span>';
                            let hash = 0;
                            const text = q.sub_theme;
                            for (let i = 0; i < text.length; i++) {
                                hash = text.charCodeAt(i) + ((hash << 5) - hash);
                            }
                            const hue = Math.abs(hash % 360);
                            const color = `hsl(${hue}, 70%, 75%)`;
                            return `<span class="badge" style="background: hsl(${hue}, 40%, 15%); color: ${color}; border: 1px solid hsl(${hue}, 40%, 30%); font-size: 0.8rem; padding: 4px 8px; border-radius: 4px; font-weight: 800; text-shadow: 0 1px 2px rgba(0,0,0,0.5);">${escapeHtml(text)}</span>`;
                        })()}</td>

                        <td>${sourceBadgeHtml}</td>

                        <td><div style="white-space: normal; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; line-height: 1.4; overflow: hidden; text-overflow: ellipsis;" title="${escapeHtml(q.question)}">${escapeHtml(q.question)}</div></td>

                        <td data-sort-value="${q.created_at ? new Date(q.created_at.replace(' ', 'T')).getTime() : 0}"><span style="font-size: 0.82rem; color: var(--text-secondary); white-space: nowrap;">${formattedDate}</span></td>

                        <td style="text-align: center; vertical-align: middle;" onclick="event.stopPropagation()">${statusToggle}</td>

                        <td style="text-align: left; vertical-align: middle;" onclick="event.stopPropagation()">
                            <button class="btn btn-secondary btn-sm" onclick="openQuestionDrawer(${q.id})">✏️ تعديل</button>
                            <button class="btn btn-danger btn-sm" style="margin-right: 5px;" onclick="deleteQuestion(${q.id})">🗑️ حذف</button>
                        </td>
                    </tr>
                `;

            }

            tbody.innerHTML = html;
            
            // Reset selection state when re-rendering
            const selectAllCheck = document.getElementById('bulk-q-select-all');
            if (selectAllCheck) selectAllCheck.checked = false;
            updateBulkDeleteButton();

        }

        function renderQuestionsPanoramic(questions) {
            const container = document.getElementById('qb-panoramic-container');
            if (!container) return;
            
            if (!questions || questions.length === 0) {
                container.innerHTML = '<div class="empty-state" style="text-align:center; padding: 40px; color: var(--text-secondary);">لا توجد أسئلة تطابق الفلاتر الحالية.</div>';
                return;
            }

            // Group by sub_theme
            const groups = {};
            questions.forEach(q => {
                const sub = q.sub_theme || "بدون جزئية";
                if (!groups[sub]) groups[sub] = [];
                groups[sub].push(q);
            });

            container.innerHTML = '';
            
            Object.keys(groups).sort().forEach(sub => {
                const groupDiv = document.createElement('div');
                groupDiv.style.marginBottom = '32px';
                
                const groupTitle = document.createElement('h3');
                groupTitle.textContent = `📌 ${sub} (${groups[sub].length})`;
                groupTitle.style.borderBottom = '2px solid var(--primary)';
                groupTitle.style.paddingBottom = '8px';
                groupTitle.style.marginBottom = '16px';
                groupTitle.style.color = 'var(--text)';
                
                const cardsGrid = document.createElement('div');
                cardsGrid.style.display = 'grid';
                cardsGrid.style.gridTemplateColumns = 'repeat(auto-fill, minmax(300px, 1fr))';
                cardsGrid.style.gap = '16px';
                
                groups[sub].forEach(q => {
                    const card = document.createElement('div');
                    
                    const sourceMap = {
                        'official': 'source-official',
                        'student_proposal': 'source-user',
                        'USER': 'source-user',
                        'ai_generated': 'source-ai',
                        'generated_by_gemini': 'source-ai',
                        'IA': 'source-ai'
                    };
                    const sourceClass = sourceMap[q.source] || 'source-official';
                    
                    card.className = `draggable-question ${sourceClass}`;
                    card.style.backgroundColor = 'var(--surface)';
                    
                    let srcBadge = '';
                    if (sourceClass === 'source-official') srcBadge = '<span class="status-badge" style="background:#28a745; color:white; padding:2px 6px; border-radius:4px; font-size:0.75rem;">🎓 رسمي</span>';
                    else if (sourceClass === 'source-user') srcBadge = '<span class="status-badge" style="background:#fd7e14; color:white; padding:2px 6px; border-radius:4px; font-size:0.75rem;">💡 مقترح</span>';
                    else if (sourceClass === 'source-ai') srcBadge = '<span class="status-badge" style="background:#17a2b8; color:white; padding:2px 6px; border-radius:4px; font-size:0.75rem;">🪄 ذكاء</span>';
                    
                    // Question text
                    let html = `<div class="draggable-question-header" style="justify-content:space-between; align-items:flex-start; margin-bottom:8px;">
                        <span class="question-id-badge" style="position:static; font-size:0.75rem; margin-left:8px;">#${q.id}</span>
                        <div>${srcBadge}</div>
                    </div>
                    <div class="draggable-question-text" style="font-weight:bold; font-size:1.05rem; color:var(--primary); line-height:1.4; margin-bottom:12px;">${q.question || 'بدون نص'}</div>`;
                    
                    // Choices
                    const choices = ['a', 'b', 'c', 'd'];
                    const letters = ['أ', 'ب', 'ج', 'د'];
                    
                    const choicesHtml = choices.map((c, i) => {
                        const choiceText = q[`choice_${c}`];
                        if (!choiceText) return '';
                        const isCorrect = (q.correct_answer || '').toLowerCase().trim() === c.toLowerCase();
                        const bg = isCorrect ? 'var(--success-light)' : 'transparent';
                        const border = isCorrect ? '1px solid var(--success)' : '1px solid var(--border)';
                        const color = isCorrect ? 'var(--success)' : 'var(--text-secondary)';
                        const weight = isCorrect ? 'bold' : 'normal';
                        return `<div style="padding: 6px 10px; border-radius: 4px; background-color: ${bg}; border: ${border}; color: ${color}; font-weight: ${weight}; font-size: 0.95rem; display: flex; gap: 8px;">
                            <span>${letters[i]}.</span> <span>${choiceText}</span>
                        </div>`;
                    }).join('');
                    
                    html += `<div style="display:flex; flex-direction:column; gap:6px;">${choicesHtml}</div>`;
                    
                    // Actions
                    html += `<div style="margin-top:auto; padding-top:12px; border-top:1px dashed var(--border); display:flex; justify-content:flex-end; align-items:center;">
                        <button class="btn btn-secondary btn-sm" onclick="openQuestionDrawer(${q.id})">✏️ Détails</button>
                    </div>`;
                    
                    card.innerHTML = html;
                    cardsGrid.appendChild(card);
                });
                
                groupDiv.appendChild(groupTitle);
                groupDiv.appendChild(cardsGrid);
                container.appendChild(groupDiv);
            });
        }

        function renderQuestionsPagination(pagination) {

            const container = document.getElementById('questions-pagination');

            let html = '';

            if (pagination.total_pages > 1) {

                if (pagination.page > 1) {

                    html += `<button class="btn btn-secondary btn-sm" onclick="loadQuestions(${pagination.page - 1})">السابق</button>`;

                }

                html += `<span style="display:inline-block; margin: 0 10px; line-height: 32px;">صفحة ${pagination.page} من ${pagination.total_pages} (${pagination.total_count} سؤال)</span>`;

                if (pagination.page < pagination.total_pages) {

                    html += `<button class="btn btn-secondary btn-sm" onclick="loadQuestions(${pagination.page + 1})">التالي</button>`;

                }

            }

            container.innerHTML = html;

        }

        // ─── TRANSCRIPT FULL EDITOR ────────────────────────────────────────────

        let transcriptEditorLesson = null; // The lesson currently being edited

        function closeTranscriptDrawer() {

            document.getElementById('transcript-drawer-backdrop').classList.remove('show');

            document.getElementById('transcript-detail-drawer').classList.remove('open');

            transcriptEditorLesson = null;

        }

        function openTranscriptDrawer(subject, lessonNum) {

            // Find the lesson in state.transcripts

            const lesson = (state.transcripts || []).find(

                l => l.subject === subject && parseInt(l.lessonNum) === parseInt(lessonNum)

            );

            if (!lesson) {

                showNotification('لم يتم العثور على التفريغ لهذا الدرس', 'error');

                return;

            }

            transcriptEditorLesson = lesson;

            const drawer = document.getElementById('transcript-detail-drawer');

            drawer.innerHTML = renderTranscriptEditorHTML(lesson);

            document.getElementById('transcript-drawer-backdrop').classList.add('show');

            drawer.classList.add('open');

        }

        function renderTranscriptEditorHTML(lesson) {

            const blocks = [...(lesson.thematic_blocks || [])].sort((a, b) => (a.start_seconds || 0) - (b.start_seconds || 0));

            const segments = lesson.segments || [];

            const isSira = lesson.subject === 'sira';

            function getSegmentsForBlock(bIdx) {

                const startSec = blocks[bIdx].start_seconds || 0;

                const endSec   = bIdx + 1 < blocks.length ? (blocks[bIdx + 1].start_seconds || Infinity) : Infinity;

                return segments.map((seg, idx) => ({ seg, idx })).filter(({ seg }) => (seg.sec || 0) >= startSec && (seg.sec || 0) < endSec);

            }

            const firstBlockStart = blocks.length > 0 ? (blocks[0].start_seconds || 0) : 0;

            const introSegs = segments.map((seg, idx) => ({ seg, idx })).filter(({ seg }) => (seg.sec || 0) < firstBlockStart);

            let html = `

            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border); padding: 16px 24px; background:var(--bg); flex-shrink:0;">

                <div>

                    <h2 style="margin:0; font-size:1.3rem;">📝 تحرير التفريغ الكامل ${isSira ? '(نظام الأبيات مفعل)' : ''}</h2>

                    <div style="font-size:0.8rem; color:var(--text-secondary); margin-top:4px;">الدرس ${lesson.lessonNum} — ${lesson.subjectLabel || lesson.subject}</div>

                </div>

                <div style="display:flex; gap:8px; align-items:center;">

                    <button class="btn btn-primary" id="save-transcript-btn" onclick="saveFullTranscript()">💾 حفظ التغييرات</button>

                    <button class="btn btn-secondary" onclick="closeTranscriptDrawer()">✖ إغلاق</button>

                </div>

            </div>

            <div style="flex:1; overflow-y:auto; padding:20px 24px; display:flex; flex-direction:column; gap:15px;">

                                <div style="background: rgba(212, 175, 55, 0.08); border: 1px solid rgba(212, 175, 55, 0.25); border-radius: 12px; padding: 16px 20px; font-size: 0.9rem; color: var(--text-primary); direction: rtl; display: flex; justify-content: space-between; align-items: center; gap: 20px; margin-bottom: 10px; width: 100%;">
                    <div>
                        <strong style="color: var(--gold-light); font-size: 1.05rem; display: block; margin-bottom: 4px;">🖥️ لوحة تعديل المحاور الشاملة (100% Plein Écran)</strong>
                        <span style="font-size: 0.82rem; color: var(--text-secondary); line-height: 1.4;">
                            تتيح لك هذه اللوحة تعديل نصوص التفريغ الحرفي وتصحيح انقسامات العبارات، مع إمكانية تقسيم المحاور، نقل النصوص ونظم الشعر بشاشة كاملة وبسهولة فائقة.
                        </span>
                    </div>
                    <button class="btn btn-primary" style="background: var(--gold); color: #000; font-weight: bold; height: auto; padding: 10px 18px; white-space: nowrap;" onclick="closeTranscriptDrawer(); openAxesEditor('${lesson.subject}', ${lesson.lessonNum});">
                        📝 فتح لوحة التعديل الشاملة
                    </button>
                </div>

                <div id="transcript-editor-body" style="display:flex; flex-direction:column; gap:20px; direction:rtl;">`;

            if (introSegs.length > 0) {

                const fullText = introSegs.map(s => s.seg.text).join(' ');

                const firstSec = introSegs[0].seg.sec || 0;

                const firstTs  = introSegs[0].seg.ts  || '0:00';

                const lastSec  = introSegs[introSegs.length - 1].seg.sec || firstSec;

                const vLink    = introSegs[0].seg.video_link || '';

                const segIdxs  = introSegs.map(s => s.idx);

                html += renderOneBlockEditor('intro', 0, '📌 مقدمة الدرس', firstTs, firstSec, lastSec, vLink, fullText, segIdxs, '', isSira, false);

            }

            blocks.forEach((block, bIdx) => {

                const segs = getSegmentsForBlock(bIdx);

                const fullText = segs.map(s => s.seg.text).join(' ');

                const firstSec = segs.length > 0 ? (segs[0].seg.sec || 0) : (block.start_seconds || 0);

                const firstTs  = segs.length > 0 ? (segs[0].seg.ts  || block.timestamp) : block.timestamp;

                const lastSec  = segs.length > 0 ? (segs[segs.length - 1].seg.sec || firstSec) : firstSec;

                const vLink    = block.video_link || (segs.length > 0 ? segs[0].seg.video_link : '') || '';

                const segIdxs  = segs.map(s => s.idx);

                html += renderOneBlockEditor(bIdx, bIdx + 1, block.title, firstTs, firstSec, lastSec, vLink, fullText, segIdxs, block.explanation || '', isSira, !!block.is_sub_theme);

            });

            html += `

                    <div style="text-align: center; margin-top: 10px;">

                        <button class="btn btn-secondary" onclick="addThematicBlock()" style="width: 100%; border: 2px dashed var(--border); background: transparent; padding: 12px; font-weight: bold; color: var(--text-secondary);">+ إضافة محور جديد</button>

                    </div>

                </div>

            </div>

            <div style="display:flex; justify-content:flex-end; gap:8px; padding: 16px 24px; border-top:1px solid var(--border); background:var(--bg); flex-shrink:0;">

                <button class="btn btn-primary" onclick="saveFullTranscript()">💾 حفظ التغييرات</button>

                <button class="btn btn-secondary" onclick="closeTranscriptDrawer()">إلغاء</button>

            </div>`;

            return html;

        }

        function renderOneBlockEditor(blockId, blockNum, title, firstTs, firstSec, lastSec, vLink, rawText, segIdxs, explanation, isSira, isSubTheme) {

            const escapedText = rawText.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

            const safeExpl = (explanation || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');

            const safeTitle = (title || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');

            const hasSegs  = segIdxs.length > 0;

            const isIntro = blockId === 'intro';

            // Styling for sub-themes

            const marginRight = isSubTheme ? '40px' : '0';

            const borderRight = isSubTheme ? '4px solid #9ca3af' : '1px solid var(--border)';

            const bgHeader = isSubTheme ? 'rgba(0,0,0,0.02)' : 'var(--surface-hover, rgba(0,0,0,0.04))';

            const iconBadge = isIntro ? 'مقدمة' : (isSubTheme ? '↳ فرعي' : 'المحور ' + blockNum);

            let editorHtml = '';

            if (isSira) {

                const verses = rawText.split('\n').filter(l => l.trim());

                if (verses.length === 0) verses.push('');

                editorHtml = `<div class="sira-verses-container" data-block-id="${blockId}">`;

                verses.forEach((verse, i) => {

                    editorHtml += `<div class="sira-verse-row" style="display:flex; gap:8px; margin-bottom:8px; align-items:center;">

                        <span class="verse-number" style="font-size:0.8rem; color:var(--gold-light); font-weight:bold; min-width:20px; text-align:center;">${i+1}</span>

                        <textarea class="form-select sira-verse-input" style="flex:1; min-height:45px; padding:6px 10px; line-height:1.5; resize:vertical;">${verse.replace(/"/g, '&quot;')}</textarea>

                        <button class="btn btn-secondary btn-sm" onclick="removeVerseRow(this)" style="padding:4px 8px;">❌</button>

                    </div>`;

                });

                editorHtml += `<button class="btn btn-secondary btn-sm" onclick="addVerseToBlock(this)" style="margin-top:8px;">+ إضافة شطر/بيت</button></div>`;

                // Hidden textarea to keep compatibility with segment iteration logic

                editorHtml += `<textarea class="transcript-block-editor" style="display:none;" data-is-sira="true" data-block-id="${blockId}" data-first-sec="${firstSec}" data-last-sec="${lastSec}" data-first-ts="${firstTs}" data-video-link="${(vLink || '').replace(/"/g, '&quot;')}" data-seg-idxs='${JSON.stringify(segIdxs)}'>${escapedText}</textarea>`;

            } else {

                editorHtml = `<textarea class="settings-textarea transcript-block-editor" data-block-id="${blockId}" data-first-sec="${firstSec}" data-last-sec="${lastSec}" data-first-ts="${firstTs}" data-video-link="${(vLink || '').replace(/"/g, '&quot;')}" data-seg-idxs='${JSON.stringify(segIdxs)}' style="width:100%; min-height:${Math.max(120, Math.min(400, Math.round(rawText.length / 3)))}px; font-family:'Tajawal',sans-serif; font-size:0.92rem; line-height:1.85; resize:vertical; box-sizing:border-box;" placeholder="${hasSegs ? '' : 'لا توجد مقاطع تفريغ لهذا المحور'}" ${!hasSegs ? 'disabled' : ''}>${escapedText}</textarea>`;

            }

            return `

            <div class="transcript-block-section" style="border:1px solid var(--border); border-right:${borderRight}; border-radius:12px; overflow:hidden; background:var(--surface); margin-right:${marginRight}; transition: margin 0.2s, border 0.2s;">

                <div style="padding:14px 16px; background:${bgHeader}; display:flex; align-items:center; gap:10px; flex-wrap:wrap; border-bottom:1px solid var(--border); cursor:pointer;" onclick="toggleBlockBody(this)">

                    <span class="tb-toggle-icon" style="font-size:0.8rem; color:var(--text-secondary); width:16px; text-align:center;">◀</span>

                    <span style="font-size:0.72rem; font-weight:800; background:var(--primary-light, rgba(79,70,229,0.12)); color:var(--primary); padding:3px 8px; border-radius:6px; white-space:nowrap;">

                        ${iconBadge}

                    </span>

                    ${isIntro ? 

                        `<strong style="font-size:0.95rem; color:var(--text-primary); flex:1;">${title}</strong>` : 

                        `<input type="text" class="form-select tb-title-input" onclick="event.stopPropagation()" value="${safeTitle}" style="flex:1; padding: 4px 8px; font-weight: bold;" placeholder="عنوان المحور">`

                    }

                    ${!isIntro ? `

                        <label style="font-size:0.75rem; color:var(--text-secondary); margin-right:8px; display:flex; align-items:center; gap:4px; cursor:pointer;" onclick="event.stopPropagation()">

                            <input type="checkbox" class="tb-sub-theme-checkbox" ${isSubTheme ? 'checked' : ''} onchange="toggleSubThemeState(this)"> فرعي

                        </label>

                    ` : ''}

                    <span style="font-size:0.72rem; color:var(--text-secondary); white-space:nowrap;">⏱ ${firstTs}</span>

                    ${vLink ? `<a href="${vLink}" target="_blank" style="font-size:0.72rem; color:var(--primary); text-decoration:none; background:var(--primary-light, rgba(79,70,229,0.1)); padding:3px 10px; border-radius:6px; white-space:nowrap;" onclick="event.stopPropagation()">🎥</a>` : ''}

                    ${!isIntro ? `

                        <button class="btn btn-secondary btn-sm" onclick="event.stopPropagation(); moveThematicBlock(${blockId}, -1)" title="أعلى">⬆️</button>

                        <button class="btn btn-secondary btn-sm" onclick="event.stopPropagation(); moveThematicBlock(${blockId}, 1)" title="أسفل">⬇️</button>

                        <button class="btn btn-secondary btn-sm" onclick="event.stopPropagation(); deleteThematicBlock(${blockId})" style="color:#ef4444;" title="حذف">🗑</button>

                    ` : ''}

                </div>

                <div class="tb-body" style="padding:14px 16px; display:none; flex-direction:column; gap:10px;">

                    ${!isIntro ? `

                    <div>

                        <label style="font-size:0.72rem; font-weight:800; color:#b45309; display:block; margin-bottom:6px; direction:rtl;">💡 الشرح التوضيحي للمحور (سيظهر للطلاب كملخص)</label>

                        <textarea class="settings-textarea tb-expl-input" placeholder="شرح المحور..." style="width:100%; min-height:60px; font-size:0.85rem; line-height:1.6;">${safeExpl}</textarea>

                    </div>` : ''}

                    <div>

                        <label style="font-size:0.72rem; font-weight:800; color:var(--text-secondary); display:block; margin-bottom:6px; direction:rtl;">

                            📝 نص التفريغ ${isSira ? '(نظام الأبيات)' : 'الحرفي'} (${hasSegs ? segIdxs.length + ' مقطع صوتي' : 'لا توجد مقاطع'})

                        </label>

                        ${editorHtml}

                    </div>

                </div>

            </div>`;

        }

        window.toggleBlockBody = function(headerEl) {

            const body = headerEl.nextElementSibling;

            const icon = headerEl.querySelector('.tb-toggle-icon');

            if (body.style.display === 'none') {

                body.style.display = 'flex';

                if (icon) icon.textContent = '▼';

            } else {

                body.style.display = 'none';

                if (icon) icon.textContent = '◀';

            }

        };

        window.toggleSubThemeState = function(checkbox) {

            const section = checkbox.closest('.transcript-block-section');

            if (checkbox.checked) {

                section.style.marginRight = '40px';

                section.style.borderRight = '4px solid #9ca3af';

            } else {

                section.style.marginRight = '0';

                section.style.borderRight = '1px solid var(--border)';

            }

        };

        window.addThematicBlock = function() {

            if (!transcriptEditorLesson) return;

            if (!transcriptEditorLesson.thematic_blocks) transcriptEditorLesson.thematic_blocks = [];

            

            let lastSec = 0;

            if (transcriptEditorLesson.segments && transcriptEditorLesson.segments.length > 0) {

                lastSec = transcriptEditorLesson.segments[transcriptEditorLesson.segments.length - 1].sec || 0;

            }

            if (transcriptEditorLesson.thematic_blocks.length > 0) {

                const maxBlockSec = Math.max(...transcriptEditorLesson.thematic_blocks.map(b => b.start_seconds || 0));

                lastSec = Math.max(lastSec, maxBlockSec);

            }

            const newStartSec = lastSec + 10;

            

            function localSecToTs(s) {

                const mins = Math.floor(s / 60);

                const secs = Math.floor(s % 60);

                return `${mins}:${secs.toString().padStart(2, '0')}`;

            }

            

            transcriptEditorLesson.thematic_blocks.push({

                title: "محور جديد",

                explanation: "",

                start_seconds: newStartSec,

                timestamp: localSecToTs(newStartSec),

                video_link: ""

            });

            const drawer = document.getElementById('transcript-detail-drawer');

            drawer.innerHTML = renderTranscriptEditorHTML(transcriptEditorLesson);

        };

        window.moveThematicBlock = function(idx, dir) {

            if (!transcriptEditorLesson || !transcriptEditorLesson.thematic_blocks) return;

            const arr = transcriptEditorLesson.thematic_blocks;

            if (idx < 0 || idx >= arr.length) return;

            const newIdx = idx + dir;

            if (newIdx < 0 || newIdx >= arr.length) return;

            

            // Swap

            const temp = arr[idx];

            arr[idx] = arr[newIdx];

            arr[newIdx] = temp;

            

            const drawer = document.getElementById('transcript-detail-drawer');

            drawer.innerHTML = renderTranscriptEditorHTML(transcriptEditorLesson);

        };

        window.deleteThematicBlock = function(idx) {

            if (!transcriptEditorLesson || !transcriptEditorLesson.thematic_blocks) return;

            if (confirm("هل أنت متأكد من حذف هذا المحور؟ لن يتم حذف التفريغ الصوتي، لكن سيتم دمج نصوصه.")) {

                transcriptEditorLesson.thematic_blocks.splice(idx, 1);

                const drawer = document.getElementById('transcript-detail-drawer');

                drawer.innerHTML = renderTranscriptEditorHTML(transcriptEditorLesson);

            }

        };

        window.addVerseToBlock = function(btn) {

            const container = btn.parentElement;

            const rows = container.querySelectorAll('.sira-verse-row');

            const newNum = rows.length + 1;

            const newRow = document.createElement('div');

            newRow.className = 'sira-verse-row';

            newRow.style.cssText = 'display:flex; gap:8px; margin-bottom:8px; align-items:center;';

            newRow.innerHTML = `

                <span class="verse-number" style="font-size:0.8rem; color:var(--gold-light); font-weight:bold; min-width:20px; text-align:center;">${newNum}</span>

                <textarea class="form-select sira-verse-input" style="flex:1; min-height:45px; padding:6px 10px; line-height:1.5; resize:vertical;"></textarea>

                <button class="btn btn-secondary btn-sm" onclick="removeVerseRow(this)" style="padding:4px 8px;">❌</button>

            `;

            container.insertBefore(newRow, btn);

        };

        window.removeVerseRow = function(btn) {

            const container = btn.parentElement.parentElement;

            btn.parentElement.remove();

            // Re-number

            const rows = container.querySelectorAll('.sira-verse-row');

            rows.forEach((row, idx) => {

                row.querySelector('.verse-number').textContent = idx + 1;

            });

        };

        async function saveFullTranscript() {

            if (!transcriptEditorLesson) return;

            const saveBtn = document.getElementById('save-transcript-btn');

            if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = '⏳ جاري الحفظ...'; }

            const origSegments = JSON.parse(JSON.stringify(transcriptEditorLesson.segments || []));

            const sections = document.querySelectorAll('.transcript-block-section');

            

            const newThematicBlocks = [];

            sections.forEach(section => {

                const ta = section.querySelector('.transcript-block-editor');

                if (!ta || ta.disabled) return;

                // Update Sira text from inputs

                if (ta.dataset.isSira === 'true') {

                    const inputs = section.querySelectorAll('.sira-verse-input');

                    ta.value = Array.from(inputs).map(i => i.value).join('\n');

                }

                const segIdxs  = JSON.parse(ta.dataset.segIdxs || '[]');

                const newText  = ta.value.trim();

                const firstSec = parseFloat(ta.dataset.firstSec) || 0;

                const lastSec  = parseFloat(ta.dataset.lastSec)  || firstSec;

                const vLink    = ta.dataset.videoLink || '';

                const firstTs  = ta.dataset.firstTs || '0:00';

                

                // Construct thematic block

                if (ta.dataset.blockId !== 'intro') {

                    const titleInput = section.querySelector('.tb-title-input');

                    const explInput = section.querySelector('.tb-expl-input');

                    const subCheckbox = section.querySelector('.tb-sub-theme-checkbox');

                    newThematicBlocks.push({

                        title: titleInput ? titleInput.value.trim() : 'محور جديد',

                        explanation: explInput ? explInput.value.trim() : '',

                        start_seconds: firstSec,

                        timestamp: firstTs,

                        video_link: vLink,

                        is_sub_theme: subCheckbox ? subCheckbox.checked : false

                    });

                }

                const count = segIdxs.length;

                if (!count) return;

                const sentences = smartSplitSentences(newText);

                const secSpan   = Math.max(lastSec - firstSec, count * 4);

                segIdxs.forEach((sIdx, i) => {

                    const text      = sentences[i] !== undefined ? sentences[i].trim() : '';

                    const secOffset = Math.round((i / Math.max(count - 1, 1)) * secSpan);

                    const sec       = firstSec + secOffset;

                    origSegments[sIdx] = {

                        ts:         secToTs(sec),

                        sec:        sec,

                        text:       text,

                        video_link: vLink ? rebuildVideoLink(vLink, sec) : ''

                    };

                });

            });

            const cleanedSegments = origSegments.filter(s => (s.text || '').trim() !== '');

            try {

                const resp = await fetch('/admin/save-full-transcript', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({

                        userId:    state.state.userId,

                        subject:   transcriptEditorLesson.subject,

                        lessonNum: transcriptEditorLesson.lessonNum,

                        segments:  cleanedSegments,

                        thematicBlocks: newThematicBlocks

                    })

                });

                const result = await resp.json();

                if (result.success) {

                    const localLesson = (state.transcripts || []).find(

                        l => l.subject === transcriptEditorLesson.subject && l.lessonNum === transcriptEditorLesson.lessonNum

                    );

                    if (localLesson) {

                        localLesson.segments = cleanedSegments;

                        localLesson.thematic_blocks = newThematicBlocks;

                    }

                    transcriptEditorLesson.segments = cleanedSegments;

                    transcriptEditorLesson.thematic_blocks = newThematicBlocks;

                    showNotification('✅ تم حفظ التفريغ بنجاح وسيظهر في الواجهة الطلابية', 'success');

                    closeTranscriptDrawer();

                } else {

                    showNotification('❌ خطأ: ' + (result.error || 'فشل الحفظ'), 'error');

                }

            } catch(e) {

                showNotification('❌ خطأ في الاتصال بالخادم', 'error');

            } finally {

                if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = '💾 حفظ التغييرات'; }

            }

        }

        // Split text on Arabic/Latin sentence boundaries

        function smartSplitSentences(text) {

            const raw = text.split(/(?<=[.؟!؛،])\s+/);

            return raw.filter(s => s.trim().length > 0);

        }

        function secToTs(sec) {

            const m = Math.floor(sec / 60);

            const s = Math.floor(sec % 60);

            return `${m}:${String(s).padStart(2, '0')}`;

        }

        function rebuildVideoLink(baseLink, sec) {

            const base = baseLink.replace(/[&?]t=\d+s?/, '');

            if (base.includes('youtube.com') || base.includes('youtu.be')) {

                return base + (base.includes('?') ? '&' : '?') + `t=${sec}s`;

            }

            return baseLink;

        }

        // ─── END TRANSCRIPT EDITOR ──────────────────────────────────────────────

        function closeQuestionDrawer() {

            document.getElementById('question-drawer-backdrop').classList.remove('show');

            document.getElementById('question-detail-drawer').classList.remove('open');

        }

        async function openQuestionDrawer(questionId) {

            try {

                const response = await fetch('/admin/question', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({ userId: state.userId, questionId })

                });

                const data = await response.json();

                if (!data.success) {

                    showNotification('خطأ في تحميل السؤال: ' + data.error, 'error');

                    return;

                }

                const q = data.question;

                // Find matching reference video link

                let videoLink = '';

                if (state.transcripts && state.transcripts.length > 0) {

                    const lesson = state.transcripts.find(l => l.subject === q.subject && parseInt(l.lessonNum) === parseInt(q.course_number));

                    if (lesson && lesson.thematic_blocks) {

                        const block = lesson.thematic_blocks.find(b => b.video_link);

                        if (block) {

                            videoLink = block.video_link;

                        }

                    }

                }

                const drawer = document.getElementById('question-detail-drawer');

                

                let proposerInfoHtml = '';

                if (q.proposed_by) {

                    const usernameLink = q.proposed_by.username 

                        ? `<a href="https://t.me/${q.proposed_by.username}" target="_blank" style="color: var(--gold-light); font-weight: bold; text-decoration: none;">@${q.proposed_by.username}</a>`

                        : `<span style="color: var(--text-secondary);">لا يوجد pseudo</span>`;

                    proposerInfoHtml = `

                        <div style="margin-bottom: 12px; padding: 12px; background: rgba(217, 119, 6, 0.1); border: 1px dashed var(--gold); border-radius: 6px; font-size: 0.8rem; direction: rtl;">

                            <strong>💡 الطالب المقترح للمسألة:</strong> ${escapeHtml(q.proposed_by.first_name)} (${usernameLink})

                        </div>

                    `;

                }

                drawer.innerHTML = `

                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; border-bottom:1px solid var(--border); padding-bottom:16px;">

                        <h2 style="margin:0; font-size:1.5rem;">📝 تعديل السؤال #${q.id}</h2>

                        <button class="btn btn-secondary" onclick="closeQuestionDrawer()">✖ إغلاق</button>

                    </div>

                    <div class="question-editor-grid-wide" style="display: grid; grid-template-columns: 1fr 1.3fr; gap: 24px; direction: rtl;">

                        <!-- Left Column: Smartphone Preview Mockup -->

                        <div style="display: flex; flex-direction: column; align-items: center; justify-content: flex-start; gap: 10px;">

                            <label style="color: var(--text-secondary); font-size: 0.85rem; font-weight: 800; display: flex; align-items: center; gap: 6px; width: 100%; justify-content: center; margin-bottom: 4px;">

                                💬 معاينة تليجرام المباشرة للطلاب

                            </label>

                            <div class="tg-phone-mockup">

                                <div class="tg-phone-header">

                                    <div class="tg-phone-avatar">أ</div>

                                    <div class="tg-phone-title-container">

                                        <span class="tg-phone-title">أكاديمية الباجي 🎓</span>

                                        <span class="tg-phone-subtitle">سؤال وجواب</span>

                                    </div>

                                </div>

                                <div class="tg-phone-chat">

                                    <!-- The Poll/Quiz Bubble -->

                                    <div class="tg-quiz-bubble">

                                        <div class="tg-quiz-header">

                                            <span>📊 اختبار (Quiz)</span>

                                        </div>

                                        <div id="qb-preview-question" class="tg-quiz-question"></div>

                                        <div class="tg-quiz-options">

                                            <div id="qb-preview-opt-a" class="tg-quiz-option">

                                                <span id="qb-preview-opt-a-text" class="tg-quiz-option-text"></span>

                                                <div class="tg-quiz-option-circle"></div>

                                            </div>

                                            <div id="qb-preview-opt-b" class="tg-quiz-option">

                                                <span id="qb-preview-opt-b-text" class="tg-quiz-option-text"></span>

                                                <div class="tg-quiz-option-circle"></div>

                                            </div>

                                            <div id="qb-preview-opt-c" class="tg-quiz-option">

                                                <span id="qb-preview-opt-c-text" class="tg-quiz-option-text"></span>

                                                <div class="tg-quiz-option-circle"></div>

                                            </div>

                                            <div id="qb-preview-opt-d" class="tg-quiz-option">

                                                <span id="qb-preview-opt-d-text" class="tg-quiz-option-text"></span>

                                                <div class="tg-quiz-option-circle"></div>

                                            </div>

                                        </div>

                                    </div>

                                    

                                    <!-- The Feedback bubble -->

                                    <div class="tg-feedback-bubble" id="qb-preview-feedback-container">

                                        <div class="tg-feedback-title">

                                            <span>💡 شرح وتوضيح الأستاذ:</span>

                                        </div>

                                        <div id="qb-live-preview-content" class="tg-feedback-content"></div>

                                    </div>

                                </div>

                            </div>

                        </div>

                        <!-- Right Column: ALL inputs / Form -->

                        <div style="display: flex; flex-direction: column; gap: 14px; background-color: var(--surface-hover); border: 1px solid var(--border); padding: 20px; border-radius: var(--radius-md); width: 100%;">

                            <h3 style="margin: 0 0 8px 0; font-size: 1.1rem; border-bottom: 1px solid var(--border); padding-bottom: 8px; color: var(--text-primary); display: flex; align-items: center; gap: 8px;">

                                ⚙️ نموذج تعديل السؤال والخيارات

                            </h3>

                            

                            ${proposerInfoHtml}

                            

                            ${videoLink ? `

                            <div style="margin-bottom: 4px; padding: 10px; background: rgba(36, 129, 204, 0.1); border: 1px dashed var(--primary); border-radius: 6px; display: flex; align-items: center; justify-content: space-between;">

                                <span style="font-size: 0.8rem; font-weight: bold; color: var(--text-primary);">🎥 فيديو الدرس المرجعي:</span>

                                <a href="${videoLink}" target="_blank" class="btn btn-primary btn-sm" style="padding: 4px 10px; font-size: 0.75rem; text-decoration: none; display: inline-flex; align-items: center; gap: 4px; height: auto;">فتح الفيديو</a>

                            </div>

                            ` : ''}

                            <div>

                                <label style="display: block; margin-bottom: 6px; font-weight: 800; font-size: 0.85rem; color: var(--text-secondary);">نص السؤال الرئيسي</label>

                                <textarea id="qb-edit-q" class="reply-textarea" oninput="updateDrawerTelegramPreview()" style="min-height: 80px; font-size: 1rem; line-height: 1.4; font-family: inherit; width: 100%;" dir="rtl">${escapeHtml(q.question)}</textarea>

                            </div>

                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">

                                <div>

                                    <label style="font-weight: 800; font-size: 0.75rem; color: var(--text-secondary); display: block; margin-bottom: 4px;">الخيار أ (A)</label>

                                    <input type="text" id="qb-edit-a" class="form-select" oninput="updateDrawerTelegramPreview()" style="width:100%" value="${escapeHtml(q.choice_a || '')}" dir="rtl">

                                </div>

                                <div>

                                    <label style="font-weight: 800; font-size: 0.75rem; color: var(--text-secondary); display: block; margin-bottom: 4px;">الخيار ب (B)</label>

                                    <input type="text" id="qb-edit-b" class="form-select" oninput="updateDrawerTelegramPreview()" style="width:100%" value="${escapeHtml(q.choice_b || '')}" dir="rtl">

                                </div>

                            </div>

                            

                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">

                                <div>

                                    <label style="font-weight: 800; font-size: 0.75rem; color: var(--text-secondary); display: block; margin-bottom: 4px;">الخيار ج (C)</label>

                                    <input type="text" id="qb-edit-c" class="form-select" oninput="updateDrawerTelegramPreview()" style="width:100%" value="${escapeHtml(q.choice_c || '')}" dir="rtl">

                                </div>

                                <div>

                                    <label style="font-weight: 800; font-size: 0.75rem; color: var(--text-secondary); display: block; margin-bottom: 4px;">الخيار د (D)</label>

                                    <input type="text" id="qb-edit-d" class="form-select" oninput="updateDrawerTelegramPreview()" style="width:100%" value="${escapeHtml(q.choice_d || '')}" dir="rtl">

                                </div>

                            </div>

                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 4px;">

                                <div>

                                    <label style="font-weight: 800; font-size: 0.8rem; color: var(--gold-light); display: block; margin-bottom: 4px;">الجواب الصحيح</label>

                                    <select id="qb-edit-correct" class="form-select" onchange="updateDrawerTelegramPreview()" style="width:100%">

                                        <option value="a" ${q.correct_answer === 'a' ? 'selected' : ''}>أ (A)</option>

                                        <option value="b" ${q.correct_answer === 'b' ? 'selected' : ''}>ب (B)</option>

                                        <option value="c" ${q.correct_answer === 'c' ? 'selected' : ''}>ج (C)</option>

                                        <option value="d" ${q.correct_answer === 'd' ? 'selected' : ''}>د (D)</option>

                                    </select>

                                </div>

                                <div>

                                    <label style="font-weight: 800; font-size: 0.8rem; color: var(--text-secondary); display: block; margin-bottom: 4px;">حالة تفعيل السؤال</label>

                                    <div style="padding: 10px; background: rgba(255,255,255,0.02); border: 1px solid var(--border); border-radius: 6px; display: flex; align-items: center; height: 38px;">

                                        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; user-select: none; margin: 0; font-size: 0.8rem; color: var(--text-primary);">

                                            <input type="checkbox" id="qb-edit-active" ${q.is_active !== 0 ? 'checked' : ''} style="width: 16px; height: 16px;">

                                            <span>سؤال نشط (يظهر للطلاب)</span>

                                        </label>

                                    </div>

                                </div>

                            </div>

                            <!-- Theme/Category Selection Row -->
                            <div>
                                <label style="display: block; margin-bottom: 6px; font-weight: 800; font-size: 0.85rem; color: var(--gold-light);">🎯 تصنيف المحور (Thématique)</label>
                                ${(() => {
                                    const subj = q.subject ? q.subject.toLowerCase() : '';
                                    if (subj === 'fiqh') {
                                        return `
                                            <select id="qb-edit-theme" class="form-select" style="width:100%" onchange="handleThemeSelectChange(this)">
                                                <option value="" ${!q.theme ? 'selected' : ''}>-- غير محدد --</option>
                                                <option value="فرائض الصلاة" ${q.theme === 'فرائض الصلاة' ? 'selected' : ''}>فرائض الصلاة</option>
                                                <option value="شروط الصلاة" ${q.theme === 'شروط الصلاة' ? 'selected' : ''}>شروط الصلاة</option>
                                                <option value="سنن الصلاة" ${q.theme === 'سنن الصلاة' ? 'selected' : ''}>سنن الصلاة</option>
                                                <option value="مندوبات الصلاة" ${q.theme === 'مندوبات الصلاة' ? 'selected' : ''}>مندوبات الصلاة</option>
                                                <option value="مكروهات ومبطلات الصلاة" ${q.theme === 'مكروهات ومبطلات الصلاة' ? 'selected' : ''}>مكروهات ومبطلات الصلاة</option>
                                                <option value="صلاة الجمعة" ${q.theme === 'صلاة الجمعة' ? 'selected' : ''}>صلاة الجمعة</option>
                                                <option value="سجود السهو" ${q.theme === 'سجود السهو' ? 'selected' : ''}>سجود السهو</option>
                                                <option value="فرض عين / فرض كفاية" ${q.theme === 'فرض عين / فرض كفاية' ? 'selected' : ''}>فرض عين / فرض كفاية</option>
                                                <option value="شروط الإمام" ${q.theme === 'شروط الإمام' ? 'selected' : ''}>شروط الإمام</option>
                                                <option value="NEW_AXE">+ إضافة محور جديد...</option>
                                            </select>
                                        `;
                                    } else if (subj === 'sira') {
                                        return `
                                            <select id="qb-edit-theme" class="form-select" style="width:100%">
                                                <option value="" ${!q.theme ? 'selected' : ''}>-- غير محدد --</option>
                                                <option value="الغزوات والسرايا" ${q.theme === 'الغزوات والسرايا' ? 'selected' : ''}>الغزوات والسرايا</option>
                                                <option value="بيت النبوة والحياة الشخصية" ${q.theme === 'بيت النبوة والحياة الشخصية' ? 'selected' : ''}>بيت النبوة والحياة الشخصية</option>
                                                <option value="العبادات والمعاملات والتشريعات" ${q.theme === 'العبادات والمعاملات والتشريعات' ? 'selected' : ''}>العبادات والمعاملات والتشريعات</option>
                                                <option value="الصحابة والمجتمع المدني" ${q.theme === 'الصحابة والمجتمع المدني' ? 'selected' : ''}>الصحابة والمجتمع المدني</option>
                                                <option value="العهود والوفود والعلاقات الخارجية" ${q.theme === 'العهود والوفود والعلاقات الخارجية' ? 'selected' : ''}>العهود والوفود والعلاقات الخارجية</option>
                                                <option value="الشمائل والأخلاق النبوية" ${q.theme === 'الشمائل والأخلاق النبوية' ? 'selected' : ''}>الشمائل والأخلاق النبوية</option>
                                            </select>
                                        `;
                                    } else if (subj === 'aqeeda' || subj === 'aqida') {
                                        return `
                                            <select id="qb-edit-theme" class="form-select" style="width:100%">
                                                <option value="" ${!q.theme ? 'selected' : ''}>-- غير محدد --</option>
                                                <option value="tawhid" ${q.theme === 'tawhid' ? 'selected' : ''}>أصول العقيدة والتوحيد (tawhid)</option>
                                                <option value="firaq" ${q.theme === 'firaq' ? 'selected' : ''}>المذاهب والفرق والولاء والبراء (firaq)</option>
                                            </select>
                                        `;
                                    } else if (subj === 'nahw') {
                                        return `
                                            <select id="qb-edit-theme" class="form-select" style="width:100%">
                                                <option value="" ${!q.theme ? 'selected' : ''}>-- غير محدد --</option>
                                                <option value="marfouat" ${q.theme === 'marfouat' ? 'selected' : ''}>المرفوعات والمنصوبات (marfouat)</option>
                                                <option value="tawabi" ${q.theme === 'tawabi' ? 'selected' : ''}>التوابع والأساليب النحوية (tawabi)</option>
                                            </select>
                                        `;
                                    } else {
                                        return `
                                            <input type="text" id="qb-edit-theme" class="form-select" style="width:100%" value="${escapeHtml(q.theme || '')}" placeholder="اكتب تصنيف المحور يدوياً...">
                                        `;
                                    }
                                })()}
                            </div>

                            <!-- Sub-theme (Axe) and Hijra Year Fields -->
                            <div style="display: grid; grid-template-columns: 1.2fr 0.8fr; gap: 10px; margin-top: 8px;">
                                <div>
                                    <label style="display: block; margin-bottom: 6px; font-weight: 800; font-size: 0.8rem; color: var(--gold-light); display: flex; align-items: center; gap: 4px;">📌 الجزئية/الأخذ (Axe/Sub)</label>
                                    <div style="display: flex; gap: 6px;">
                                        <select id="qb-edit-subtheme" class="form-select" style="width:100%" onchange="handleSubThemeDropdownChange(this)">
                                            <option value="" ${!q.sub_theme ? 'selected' : ''}>-- اختر أو اكتب يدوياً --</option>
                                            ${(() => {
                                                const subj = q.subject ? (q.subject.toLowerCase() === 'aqeeda' ? 'aqida' : q.subject.toLowerCase()) : '';
                                                const courseNum = q.course_number;
                                                const subthemeOptions = [];
                                                if (state.questionsStats && state.questionsStats[subj] && state.questionsStats[subj][courseNum]) {
                                                    const chapters = state.questionsStats[subj][courseNum].chapters || [];
                                                    chapters.forEach(ch => {
                                                        subthemeOptions.push(ch.title);
                                                    });
                                                }
                                                // Add current sub_theme if it's not in the official chapters
                                                if (q.sub_theme && !subthemeOptions.includes(q.sub_theme)) {
                                                    subthemeOptions.push(q.sub_theme);
                                                }
                                                return subthemeOptions.map(opt => `<option value="${escapeHtml(opt)}" ${q.sub_theme === opt ? 'selected' : ''}>${escapeHtml(opt)}</option>`).join('');
                                            })()}
                                            <option value="NEW_SUB_THEME" style="color:var(--primary); font-weight:bold;">➕ إضافة محور فرعي جديد...</option>
                                        </select>
                                    </div>
                                </div>
                                <div>
                                    <label style="display: block; margin-bottom: 6px; font-weight: 800; font-size: 0.8rem; color: var(--text-secondary); display: flex; align-items: center; gap: 4px;">📅 السنة الهجرية (Sira)</label>
                                    <div style="position: relative; display: flex; align-items: center;">
                                        <span style="position: absolute; right: 10px; color: var(--text-secondary); font-size: 0.85rem;">H</span>
                                        <input type="number" id="qb-edit-hijrayear" class="form-select" style="width:100%; padding-right: 28px; text-align: center;" value="${q.hijra_year !== null && q.hijra_year !== undefined ? q.hijra_year : ''}" placeholder="لا يوجد">
                                    </div>
                                </div>
                            </div>

                            <div style="display: flex; flex-direction: column; gap: 6px; margin-top: 4px;">

                                <div style="display: flex; justify-content: space-between; align-items: center;">

                                    <label style="margin: 0; color: var(--text-secondary); font-size: 0.85rem; font-weight: 800;">الشرح والتوضيح العلمي (يدعم HTML)</label>

                                    <button type="button" class="btn btn-secondary btn-sm" onclick="openHybridTelegramEditor()" style="padding: 4px 8px; font-size: 0.75rem; display: flex; align-items: center; gap: 6px; height: auto; line-height: 1;">

                                        ✨ تنسيق تليجرام

                                    </button>

                                </div>

                                <textarea id="qb-edit-exp" class="reply-textarea" oninput="updateDrawerTelegramPreview()" style="min-height: 90px; font-size: 0.95rem; line-height: 1.4; font-family: inherit; width: 100%;" dir="rtl">${escapeHtml(q.explanation || '')}</textarea>

                            </div>

                            <button class="btn btn-primary" style="width: 100%; margin-top: 10px; padding: 12px; font-weight: bold; font-size: 1rem;" onclick="saveBankQuestionEdit(${q.id})">💾 حفظ التعديلات</button>

                        </div>

                    </div>

                `;

                document.getElementById('question-drawer-backdrop').classList.add('show');

                drawer.classList.add('open');

                updateDrawerTelegramPreview();

            } catch (err) {

                showNotification('خطأ في تحميل السؤال', 'error');

            }

        }

        function updateDrawerTelegramPreview() {

            // Update explanation preview

            const expText = document.getElementById('qb-edit-exp')?.value || '';

            const previewEl = document.getElementById('qb-live-preview-content');

            if (previewEl) {

                previewEl.innerHTML = renderTelegramPreview(expText) || '<span style="color:var(--text-secondary); font-style:italic;">لا يوجد شرح بعد...</span>';

            }

            

            // Show/hide feedback bubble depending on if explanation exists

            const feedbackContainer = document.getElementById('qb-preview-feedback-container');

            if (feedbackContainer) {

                feedbackContainer.style.display = expText.trim() ? 'block' : 'none';

            }

            // Update question text preview

            const qText = document.getElementById('qb-edit-q')?.value || '';

            const previewQ = document.getElementById('qb-preview-question');

            if (previewQ) {

                previewQ.textContent = qText || 'نص السؤال...';

            }

            // Update choices preview

            const choices = ['a', 'b', 'c', 'd'];

            const correctChoice = document.getElementById('qb-edit-correct')?.value || 'a';

            for (const choice of choices) {

                const choiceVal = document.getElementById(`qb-edit-${choice}`)?.value || '';

                const previewOptText = document.getElementById(`qb-preview-opt-${choice}-text`);

                const previewOptContainer = document.getElementById(`qb-preview-opt-${choice}`);

                

                if (previewOptContainer && previewOptText) {

                    if (choiceVal.trim()) {

                        previewOptText.textContent = choiceVal;

                        previewOptContainer.style.display = 'flex';

                        

                        // Highlight if correct answer

                        if (choice === correctChoice) {

                            previewOptContainer.classList.add('correct');

                        } else {

                            previewOptContainer.classList.remove('correct');

                        }

                    } else {

                        // Hide choices that are empty (like Choice C or D if only A & B are used)

                        previewOptContainer.style.display = 'none';

                    }

                }

            }

        }

        async function saveBankQuestionEdit(questionId) {

            const payload = {

                userId: state.userId,

                questionId,

                question: document.getElementById('qb-edit-q').value,

                choiceA: document.getElementById('qb-edit-a').value,

                choiceB: document.getElementById('qb-edit-b').value,

                choiceC: document.getElementById('qb-edit-c').value,

                choiceD: document.getElementById('qb-edit-d').value,

                correctAnswer: document.getElementById('qb-edit-correct').value,

                explanation: document.getElementById('qb-edit-exp').value,

                isActive: document.getElementById('qb-edit-active').checked,

                theme: document.getElementById('qb-edit-theme') ? document.getElementById('qb-edit-theme').value : "",

                subTheme: document.getElementById('qb-edit-subtheme') ? document.getElementById('qb-edit-subtheme').value : "",

                hijraYear: document.getElementById('qb-edit-hijrayear') ? document.getElementById('qb-edit-hijrayear').value : null

            };

            if (!payload.question || !payload.choiceA || !payload.choiceB) {

                showToast("السؤال والخيارات A و B إجبارية", "error");

                return;

            }

            try {

                const res = await fetch('/admin/update-question', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify(payload)

                });

                const data = await res.json();

                if (data.success) {

                    showToast("✅ تم حفظ التعديلات بنجاح", "success");

                    closeQuestionDrawer();

                    const activePageBtn = document.querySelector('#questions-pagination span');

                    let pageToLoad = 1;

                    if (activePageBtn) {

                        const m = activePageBtn.textContent.match(/صفحة (\d+)/);

                        if (m) pageToLoad = parseInt(m[1]);

                    }

                    loadQuestions(pageToLoad);

                } else {

                    showToast("❌ خطأ: " + data.error, "error");

                }

            } catch (err) {

                showToast("❌ خطأ في الاتصال", "error");

            }

        }

        function handleThemeSelectChange(selectEl) {
            if (selectEl.value === 'NEW_AXE') {
                const customAxe = prompt("أدخل اسم المحور الجديد:");
                if (customAxe && customAxe.trim() !== "") {
                    // Check if option already exists
                    let exists = false;
                    for (let i = 0; i < selectEl.options.length; i++) {
                        if (selectEl.options[i].value === customAxe.trim()) {
                            exists = true;
                            selectEl.selectedIndex = i;
                            break;
                        }
                    }
                    if (!exists) {
                        const newOpt = document.createElement('option');
                        newOpt.value = customAxe.trim();
                        newOpt.text = customAxe.trim();
                        newOpt.selected = true;
                        selectEl.insertBefore(newOpt, selectEl.options[selectEl.options.length - 1]);
                    }
                } else {
                    selectEl.value = "";
                }
            }
        }

        function handleSubThemeDropdownChange(selectEl) {
            if (selectEl.value === 'NEW_SUB_THEME') {
                const customSub = prompt("أدخل اسم الجزئية/المحور الفرعي الجديد:");
                if (customSub && customSub.trim() !== "") {
                    let exists = false;
                    for (let i = 0; i < selectEl.options.length; i++) {
                        if (selectEl.options[i].value === customSub.trim()) {
                            exists = true;
                            selectEl.selectedIndex = i;
                            break;
                        }
                    }
                    if (!exists) {
                        const newOpt = document.createElement('option');
                        newOpt.value = customSub.trim();
                        newOpt.text = customSub.trim();
                        newOpt.selected = true;
                        selectEl.insertBefore(newOpt, selectEl.options[selectEl.options.length - 1]);
                    }
                } else {
                    selectEl.value = "";
                }
            }
        }

        function exportCurrentTableAsCSV() {

            const items = state.currentItems || [];

            if (items.length === 0) { showToast("⚠️ لا توجد بيانات لتصديرها", "error"); return; }

            const headers = ["ID", "النوع", "الأولوية", "الحالة", "المادة", "الطالب", "الملخص", "التاريخ"];

            const rows = items.map(item => [

                item.id,

                item.type === 'report' ? 'بلاغ' : item.type === 'proposal' ? 'مقترح' : 'تذكرة',

                item.urgency || '',

                item.status || '',

                item.subject || '',

                item.firstName || '',

                (item.title || item.content || '').replace(/,/g, '،').replace(/\n/g, ' '),

                item.timestamp || ''

            ]);

            const csvContent = [headers, ...rows].map(row => row.map(c => `"${c}"`).join(",")).join("\n");

            const bom = "\uFEFF"; // UTF-8 BOM for Arabic in Excel

            const blob = new Blob([bom + csvContent], { type: 'text/csv;charset=utf-8;' });

            const url = URL.createObjectURL(blob);

            const a = document.createElement('a');

            a.href = url;

            a.download = `admin_export_${new Date().toISOString().slice(0,10)}.csv`;

            a.click();

            URL.revokeObjectURL(url);

            showToast("📥 تم تصدير الملف بنجاح", "success");

        }

        function onEditorSubjectChange() {

            const subject = document.getElementById('editor-subject').value;

            const lessonSelect = document.getElementById('editor-lesson');

            const chapterSelect = document.getElementById('editor-chapter');

            

            // Reset

            lessonSelect.innerHTML = '<option value="">-- اختر الدرس --</option>';

            chapterSelect.innerHTML = '<option value="">-- اختر المحور --</option>';

            lessonSelect.disabled = true;

            chapterSelect.disabled = true;

            document.getElementById('editor-content-area').style.display = 'none';

            if (!subject) return;

            // Load matching lessons from transcripts list

            const lessons = state.transcripts.filter(l => l.subject === subject);

            if (lessons.length === 0) {

                showToast("⚠️ لا توجد دروس مسجلة لهذه المادة", "error");

                return;

            }

            lessons.sort((a,b) => a.lessonNum - b.lessonNum);

            lessons.forEach(l => {

                const opt = document.createElement('option');

                opt.value = l.lessonNum;

                opt.textContent = `الدرس ${l.lessonNum} : ${l.title || 'بدون عنوان'}`;

                lessonSelect.appendChild(opt);

            });

            lessonSelect.disabled = false;

        }

        function onEditorLessonChange() {

            const subject = document.getElementById('editor-subject').value;

            const lessonNum = parseInt(document.getElementById('editor-lesson').value);

            const chapterSelect = document.getElementById('editor-chapter');

            // Reset

            chapterSelect.innerHTML = '<option value="">-- اختر المحور --</option>';

            chapterSelect.disabled = true;

            document.getElementById('editor-content-area').style.display = 'none';

            if (isNaN(lessonNum)) return;

            const lesson = state.transcripts.find(l => l.subject === subject && l.lessonNum === lessonNum);

            if (!lesson || !lesson.thematic_blocks || lesson.thematic_blocks.length === 0) {

                showToast("⚠️ لا توجد محاور أو نصوص في هذا الدرس", "error");

                return;

            }

            lesson.thematic_blocks.forEach((block, idx) => {

                const opt = document.createElement('option');

                opt.value = idx;

                opt.textContent = `المحور ${idx + 1} : ${block.title}`;

                chapterSelect.appendChild(opt);

            });

            chapterSelect.disabled = false;

        }

        function onEditorChapterChange() {

            const subject = document.getElementById('editor-subject').value;

            const lessonNum = parseInt(document.getElementById('editor-lesson').value);

            const chapterIdx = parseInt(document.getElementById('editor-chapter').value);

            

            if (isNaN(chapterIdx)) {

                document.getElementById('editor-content-area').style.display = 'none';

                return;

            }

            const lesson = state.transcripts.find(l => l.subject === subject && l.lessonNum === lessonNum);

            const block = lesson.thematic_blocks[chapterIdx];

            document.getElementById('editor-chapter-label').innerHTML = `محتوى المحور <b>${chapterIdx + 1}</b> : (<i>${block.title}</i>)`;

            document.getElementById('editor-textarea').value = block.content || "";

            document.getElementById('editor-content-area').style.display = 'block';

        }

        function openChapterInEditor(subject, lessonNum, chapterIdx) {

            // 1. Switch to courses sheet

            switchTab('inbox');

            switchSheet('courses');

            

            // 2. Select corresponding subject

            state.coursesSubTab = 'explorer';

            state.selectedCourseSubject = subject;

            

            // 3. Load panel

            loadCoursesPanel();

            

            // 4. Expand lesson details (wrapped in setTimeout to let DOM render)

            setTimeout(() => {

                const el = document.getElementById('lesson-details-' + subject + '_' + lessonNum);

                if (el) {

                    el.style.display = 'flex';

                    // Scroll to the edit block

                    const targetEl = document.getElementById(`edit-title-${subject}-${lessonNum}-${chapterIdx}`);

                    if (targetEl) {

                        targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });

                        targetEl.focus();

                    }

                }

            }, 250);

        }

        function resetEditor() {

            document.getElementById('editor-subject').value = "";

            onEditorSubjectChange();

        }

        async function saveEditorContent() {

            const subject = document.getElementById('editor-subject').value;

            const lessonNum = parseInt(document.getElementById('editor-lesson').value);

            const chapterIdx = parseInt(document.getElementById('editor-chapter').value);

            const contentText = document.getElementById('editor-textarea').value.trim();

            if (!contentText) {

                showToast("⚠️ لا يمكن حفظ محتوى فارغ", "error");

                return;

            }

            try {

                showToast("⏳ جاري نشر التعديلات في النظام ومزامنة خادم التطبيق...", "info");

                const res = await fetch('/admin/edit-chapter', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({

                        userId: state.userId,

                        subject: subject,

                        lessonNum: lessonNum,

                        chapterIdx: chapterIdx,

                        content: contentText

                    })

                });

                const data = await res.json();

                if (data.success) {

                    showToast("🚀 تم تحديث الدرس ونشر التعديلات بنجاح!", "success");

                    // Refresh data in background

                    loadDashboardData();

                } else {

                    showToast("❌ فشل حفظ التعديلات", "error");

                }

            } catch(e) {

                console.error(e);

                showToast("❌ فشل الاتصال بالخادم لنشر التعديل", "error");

            }

        }

        // ─── INITIALIZATION ───

        // Already handled at lines 3686-3689



        // ─── Bulk Actions System ───

        const bulkState = { selectedIndices: new Set() };

        function onRowCheckboxChange(checkbox) {

            const index = parseInt(checkbox.dataset.index);

            const row = document.getElementById(`helpdesk-row-${index}`);

            if (checkbox.checked) {

                bulkState.selectedIndices.add(index);

                if (row) row.style.background = 'rgba(212, 175, 55, 0.08)';

                if (row) row.style.outline = '1px solid rgba(212, 175, 55, 0.3)';

            } else {

                bulkState.selectedIndices.delete(index);

                if (row) row.style.background = '';

                if (row) row.style.outline = '';

            }

            syncSelectAllCheckbox();

            updateBulkBar();

        }

        function toggleSelectAll(checkbox) {

            const checkboxes = document.querySelectorAll('.row-checkbox');

            checkboxes.forEach(cb => {

                if (cb.checked !== checkbox.checked) {

                    cb.checked = checkbox.checked;

                    onRowCheckboxChange(cb);

                }

            });

        }

        function syncSelectAllCheckbox() {

            const all = document.querySelectorAll('.row-checkbox');

            const checked = document.querySelectorAll('.row-checkbox:checked');

            const selectAll = document.getElementById('bulk-select-all');

            if (!selectAll) return;

            if (all.length === 0) {

                selectAll.indeterminate = false;

                selectAll.checked = false;

            } else if (checked.length === all.length) {

                selectAll.indeterminate = false;

                selectAll.checked = true;

            } else if (checked.length === 0) {

                selectAll.indeterminate = false;

                selectAll.checked = false;

            } else {

                selectAll.indeterminate = true;

            }

        }

        function updateBulkBar() {

            const bar = document.getElementById('bulk-actions-bar');

            const countBadge = document.getElementById('bulk-selected-count');

            const count = bulkState.selectedIndices.size;

            if (bar) {

                bar.classList.toggle('show', count > 0);

            }

            if (countBadge) countBadge.textContent = count;

        }

        function deselectAllRows() {

            bulkState.selectedIndices.clear();

            document.querySelectorAll('.row-checkbox').forEach(cb => {

                cb.checked = false;

                const index = parseInt(cb.dataset.index);

                const row = document.getElementById(`helpdesk-row-${index}`);

                if (row) { row.style.background = ''; row.style.outline = ''; }

            });

            const selectAll = document.getElementById('bulk-select-all');

            if (selectAll) { selectAll.checked = false; selectAll.indeterminate = false; }

            updateBulkBar();

        }

        function getSelectedItems() {

            return [...bulkState.selectedIndices].map(i => state.currentItems[i]).filter(Boolean);

        }

        async function triggerBulkResolve() {

            const items = getSelectedItems();

            if (items.length === 0) return;

            if (!confirm(`هل تريد حل / قبول ${items.length} عنصر محدد؟`)) return;

            await executeBulkAction(items, 'resolved');

        }

        async function triggerBulkReject() {

            const items = getSelectedItems();

            if (items.length === 0) return;

            if (!confirm(`هل تريد رفض ${items.length} عنصر محدد؟`)) return;

            await executeBulkAction(items, 'rejected');

        }

        async function executeBulkAction(items, newStatus) {

            showToast(`⏳ جاري تطبيق الإجراء على ${items.length} عنصر...`, 'info');

            let success = 0;

            let failed = 0;

            for (const item of items) {

                try {

                    let endpoint = '';

                    let body = { userId: state.userId, status: newStatus, adminReply: '' };

                    if (item.type === 'report') {

                        endpoint = '/admin/resolve-report';

                        body.reportId = item.id;

                    } else if (item.type === 'proposal') {

                        endpoint = '/admin/resolve-proposal';

                        body.proposalId = item.id;

                    } else if (item.type === 'ticket') {

                        endpoint = '/admin/resolve-ticket';

                        body.ticketId = item.id;

                    } else {

                        failed++;

                        continue;

                    }

                    const res = await fetch(endpoint, {

                        method: 'POST',

                        headers: { 'Content-Type': 'application/json' },

                        body: JSON.stringify(body)

                    });

                    const data = await res.json();

                    if (data.success) success++;

                    else failed++;

                } catch (e) {

                    failed++;

                }

            }

            deselectAllRows();

            if (failed === 0) {

                showToast(`✅ تم تطبيق الإجراء على ${success} عنصر بنجاح!`, 'success');

            } else {

                showToast(`⚠️ نجح: ${success} | فشل: ${failed}`, 'error');

            }

            await loadDashboardData();

        }

        // ─── Student Directory Management (Refonte V2.0) ───

        async function loadStudentsData() {

            try {

                const res = await fetch('/admin/students', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({ userId: state.userId })

                });

                const data = await res.json();

                if (data.success) {

                    state.students = data.students || [];

                    renderStudents();

                } else {

                    showToast("❌ فشل تحميل دليل الطلاب: " + (data.error || "خطأ غير معروف"), "error");

                    const tbody = document.getElementById('students-table-body');

                    if (tbody) {

                        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:24px; color:var(--danger); font-weight:bold;">❌ فشل التحميل: ${data.error || 'خطأ غير معروف'}</td></tr>`;

                    }

                }

            } catch (err) {

                console.error("Error loading students data:", err);

                showToast("❌ خطأ في الاتصال بالخادم", "error");

                const tbody = document.getElementById('students-table-body');

                if (tbody) {

                    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:24px; color:var(--danger); font-weight:bold;">❌ خطأ في الشبكة أو الخادم: ${err.message}</td></tr>`;

                }

            }

        }

        function renderStudents() {

            const tbody = document.getElementById('students-table-body');

            if (!tbody) return;

            let filtered = [...state.students];

            const searchVal = (state.studentsFilters.search || '').trim().toLowerCase();

            if (searchVal) {

                filtered = filtered.filter(s => {

                    return (

                        s.telegramId.toString().includes(searchVal) ||

                        (s.username || '').toLowerCase().includes(searchVal) ||

                        (s.firstName || '').toLowerCase().includes(searchVal) ||

                        (s.preferredName || '').toLowerCase().includes(searchVal)

                    );

                });

            }

            if (filtered.length === 0) {

                tbody.innerHTML = `

                    <tr>

                        <td colspan="7" style="text-align: center; padding: 48px;">

                            <div class="empty-feed" style="border: none; background: transparent; padding: 0;">

                                <div class="empty-feed-icon">🔎</div>

                                <h3 style="color: var(--text-primary);">لا توجد نتائج تطابق خيارات التصفية!</h3>

                                <p style="margin-top: 8px; font-size: 0.85rem; color: var(--text-secondary);">يرجى كتابة كلمة بحث مختلفة.</p>

                            </div>

                        </td>

                    </tr>

                `;

                return;

            }

            tbody.innerHTML = filtered.map(s => {

                const genderIcon = s.gender === 'female' ? '🧕' : '👤';

                const genderLabel = s.gender === 'female' ? 'أنثى' : (s.gender === 'male' ? 'ذكر' : 'غير محدد');

                const usernameLink = s.username ? `<a href="https://t.me/${s.username}" target="_blank" onclick="event.stopPropagation()" style="color: var(--gold-light); font-weight: 700;">@${s.username}</a>` : '<span class="cell-muted">-</span>';

                

                return `

                    <tr onclick="selectStudent(${s.telegramId})">

                        <td><strong>#${s.telegramId}</strong></td>

                        <td>

                            <div style="display: flex; align-items: center; gap: 8px;">

                                <span>${genderIcon}</span>

                                <div style="display: flex; flex-direction: column;">

                                    <span style="font-weight: 700; color: var(--text-primary);">${s.firstName || 'طالب'}</span>

                                    <span>${usernameLink}</span>

                                </div>

                            </div>

                        </td>

                        <td><span class="cell-title">${genderLabel}</span></td>

                        <td data-sort-value="${Number(s.quizCount) || 0}"><span style="font-weight: 800; color: var(--gold-light);">${s.quizCount} اختبار</span></td>

                        <td data-sort-value="${Number(s.reportCount) || 0}"><span class="badge-count" style="background-color: ${s.reportCount > 0 ? 'var(--danger)' : 'rgba(255,255,255,0.05)'}; color: ${s.reportCount > 0 ? 'white' : 'var(--text-secondary)'}; padding: 2px 8px; border-radius: 50px;">${s.reportCount}</span></td>

                        <td data-sort-value="${Number(s.proposalCount) || 0}"><span class="badge-count" style="background-color: ${s.proposalCount > 0 ? 'var(--success)' : 'rgba(255,255,255,0.05)'}; color: ${s.proposalCount > 0 ? 'white' : 'var(--text-secondary)'}; padding: 2px 8px; border-radius: 50px;">${s.proposalCount}</span></td>

                        <td data-sort-value="${s.createdAt ? new Date(s.createdAt).getTime() : 0}"><span class="cell-muted">${formatTime(s.createdAt)}</span></td>

                    </tr>

                `;

            }).join('');

        }

        function onStudentsSearch() {

            state.studentsFilters.search = document.getElementById('students-search').value;

            renderStudents();

        }

        async function selectStudent(studentId) {

            const drawer = document.getElementById('student-detail-drawer');

            const backdrop = document.getElementById('student-drawer-backdrop');

            if (!drawer || !backdrop) return;

            drawer.innerHTML = `

                <button class="close-detail-btn" onclick="closeStudentDrawer()">×</button>

                <div class="empty-feed" style="margin-top: 100px;">

                    <div class="empty-feed-icon">⏳</div>

                    <h3>جاري تحميل سجل الطالب...</h3>

                </div>

            `;

            drawer.classList.add('open');

            backdrop.classList.add('open');

            try {

                const res = await fetch('/admin/student-details', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({ userId: state.userId, studentId: studentId })

                });

                const data = await res.json();

                if (!data.success) {

                    showToast("❌ فشل تحميل تفاصيل الطالب", "error");

                    return;

                }

                const s = state.students.find(x => x.telegramId === studentId) || {

                    telegramId: studentId,

                    firstName: "طالب مجهول",

                    username: "",

                    gender: "",

                    quizCount: 0,

                    reportCount: 0,

                    proposalCount: 0

                };

                const details = data.details;

                

                drawer.innerHTML = `

                    <button class="close-detail-btn" onclick="closeStudentDrawer()">×</button>

                    

                    <div style="text-align: center; margin-bottom: 24px; border-bottom: 1px solid var(--border); padding-bottom: 20px; margin-top: 20px;">

                        <span style="font-size: 3rem;">${s.gender === 'female' ? '🧕' : '👤'}</span>

                        <h2 style="font-size: 1.4rem; font-weight: 900; margin-top: 8px; color: var(--text-primary);">${s.firstName}</h2>

                        ${s.username ? `<p style="margin-top: 4px;"><a href="https://t.me/${s.username}" target="_blank" style="color: var(--gold-light); font-weight: 700; text-decoration: none;">@${s.username}</a></p>` : ''}

                        <p style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 6px;">Telegram ID: <b>#${s.telegramId}</b></p>

                    </div>

                    <!-- Quick stats summary in drawer -->

                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 24px;">

                        <div style="background: rgba(0,0,0,0.15); border: 1px solid var(--border); padding: 10px; border-radius: var(--radius-md); text-align: center;">

                            <span style="font-size: 0.7rem; color: var(--text-secondary); display: block; font-weight: 700;">الاختبارات</span>

                            <strong style="font-size: 1.1rem; color: var(--gold-light); font-weight: 800; display: block; margin-top: 4px;">${s.quizCount}</strong>

                        </div>

                        <div style="background: rgba(0,0,0,0.15); border: 1px solid var(--border); padding: 10px; border-radius: var(--radius-md); text-align: center;">

                            <span style="font-size: 0.7rem; color: var(--text-secondary); display: block; font-weight: 700;">البلاغات</span>

                            <strong style="font-size: 1.1rem; color: var(--danger); font-weight: 800; display: block; margin-top: 4px;">${s.reportCount}</strong>

                        </div>

                        <div style="background: rgba(0,0,0,0.15); border: 1px solid var(--border); padding: 10px; border-radius: var(--radius-md); text-align: center;">

                            <span style="font-size: 0.7rem; color: var(--text-secondary); display: block; font-weight: 700;">المقترحات</span>

                            <strong style="font-size: 1.1rem; color: var(--success); font-weight: 800; display: block; margin-top: 4px;">${s.proposalCount}</strong>

                        </div>

                    </div>

                    <div class="workbook-tabs" style="margin-bottom: 12px; gap: 4px; display: flex;">

                        <button class="workbook-tab active" onclick="switchDrawerTab('reports')" id="drawer-tab-reports" style="flex: 1; padding: 8px; font-size: 0.8rem;">🚩 بلاغات الطالب</button>

                        <button class="workbook-tab" onclick="switchDrawerTab('proposals')" id="drawer-tab-proposals" style="flex: 1; padding: 8px; font-size: 0.8rem;">💡 مقترحاته</button>

                        <button class="workbook-tab" onclick="switchDrawerTab('quizzes')" id="drawer-tab-quizzes" style="flex: 1; padding: 8px; font-size: 0.8rem;">📝 اختباراته</button>

                    </div>

                    <!-- Drawer content containers -->

                    <div id="drawer-content-reports" class="drawer-tab-content">

                        ${details.reports.length === 0 ? `

                            <p style="text-align: center; color: var(--text-secondary); padding: 20px; font-size: 0.85rem;">لم يرسل هذا الطالب أي بلاغات أخطاء حتى الآن.</p>

                        ` : details.reports.map(r => {

                            const title = r.type === 'chapter_report' ? `📖 بلاغ درس (${arabicSubject(r.subject)} - درس ${r.lessonNum})` : `❓ بلاغ سؤال (سؤال #${r.questionId} - ${r.reportType || 'محتوى'})`;

                            return `

                            <div class="ticket-bubble" style="margin-bottom: 10px;">

                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">

                                    <span style="font-size: 0.75rem; font-weight: 800; color: var(--gold-light);">${title}</span>

                                    <span style="font-size: 0.75rem;" class="cell-muted">${formatTime(r.timestamp)}</span>

                                </div>

                                <p style="font-size: 0.85rem; color: var(--text-primary); font-weight: 500;">${r.report}</p>

                                ${r.adminReply ? `

                                    <div style="background: rgba(217, 119, 6, 0.05); border-right: 3px solid var(--gold); padding: 8px; margin-top: 8px; border-radius: var(--radius-sm); font-size: 0.8rem;">

                                        <strong>رد الإدارة:</strong> ${r.adminReply}

                                    </div>

                                ` : ''}

                            </div>

                            `;

                        }).join('')}

                    </div>

                    <div id="drawer-content-proposals" class="drawer-tab-content" style="display: none;">

                        ${details.proposals.length === 0 ? `

                            <p style="text-align: center; color: var(--text-secondary); padding: 20px; font-size: 0.85rem;">لم يقترح هذا الطالب أي أسئلة QCM حتى الآن.</p>

                        ` : details.proposals.map(p => `

                            <div class="ticket-bubble" style="margin-bottom: 10px;">

                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">

                                    <span style="font-size: 0.75rem; font-weight: 800; color: var(--gold-light);">${arabicSubject(p.subject)} - درس ${p.courseNumber}</span>

                                    <span style="font-size: 0.75rem;" class="cell-muted">${formatTime(p.createdAt)}</span>

                                </div>

                                <p style="font-size: 0.85rem; color: var(--text-primary); font-weight: 700; margin-bottom: 4px;">السؤال: ${p.question}</p>

                                <span style="font-size: 0.75rem; background: ${p.status === 'resolved' ? 'var(--success-bg)' : (p.status === 'rejected' ? 'var(--danger-bg)' : 'rgba(255,255,255,0.05)')}; color: ${p.status === 'resolved' ? 'var(--success)' : (p.status === 'rejected' ? 'var(--danger)' : 'var(--text-secondary)')}; padding: 2px 8px; border-radius: 50px;">

                                    ${p.status === 'resolved' ? 'مقبول ✅' : (p.status === 'rejected' ? 'مرفوض ❌' : 'قيد المراجعة ⏳')}

                                </span>

                                ${p.adminReply ? `

                                    <div style="background: rgba(255,255,255,0.02); border-right: 3px solid var(--border); padding: 8px; margin-top: 8px; border-radius: var(--radius-sm); font-size: 0.8rem;">

                                        <strong>ملاحظات الإدارة:</strong> ${p.adminReply}

                                    </div>

                                ` : ''}

                            </div>

                        `).join('')}

                    </div>

                    <div id="drawer-content-quizzes" class="drawer-tab-content" style="display: none;">

                        ${details.quiz_logs.length === 0 ? `

                            <p style="text-align: center; color: var(--text-secondary); padding: 20px; font-size: 0.85rem;">لم يقم هذا الطالب بحل أي اختبار عبر البوت البديل حتى الآن.</p>

                        ` : `

                            <table style="width: 100%; border-collapse: collapse; font-size: 0.8rem;">

                                <thead>

                                    <tr style="border-bottom: 1px solid var(--border);">

                                        <th style="text-align: right; padding: 8px;">المادة</th>

                                        <th style="text-align: center; padding: 8px;">النتيجة</th>

                                        <th style="text-align: left; padding: 8px;">التاريخ</th>

                                    </tr>

                                </thead>

                                <tbody>

                                    ${details.quiz_logs.map(q => {

                                        const statusLabel = q.isCorrect ? 'إجابة صحيحة ✅' : 'إجابة خاطئة ❌';

                                        const statusColor = q.isCorrect ? 'var(--success)' : 'var(--danger)';

                                        return `

                                            <tr style="border-bottom: 1px solid rgba(255,255,255,0.03);">

                                                <td style="padding: 8px; font-weight: 700;">${arabicSubject(q.subject)}</td>

                                                <td style="padding: 8px; text-align: center; font-weight: 800; color: ${statusColor};">${statusLabel}</td>

                                                <td style="padding: 8px; text-align: left;" class="cell-muted">${formatTime(q.answeredAt)}</td>

                                            </tr>

                                        `;

                                    }).join('')}

                                </tbody>

                            </table>

                        `}

                    </div>

                `;

            } catch (err) {

                console.error("Error loading student details drawer:", err);

                showToast("❌ خطأ أثناء تحميل تفاصيل الطالب", "error");

            }

        }

        function switchDrawerTab(tabName) {

            document.querySelectorAll('.drawer-tab-content').forEach(el => el.style.display = 'none');

            const target = document.getElementById(`drawer-content-${tabName}`);

            if (target) target.style.display = 'block';

            document.querySelectorAll('#student-detail-drawer .workbook-tab').forEach(el => el.classList.remove('active'));

            const activeTab = document.getElementById(`drawer-tab-${tabName}`);

            if (activeTab) activeTab.classList.add('active');

        }

        function closeStudentDrawer() {

            const drawer = document.getElementById('student-detail-drawer');

            const backdrop = document.getElementById('student-drawer-backdrop');

            if (drawer) drawer.classList.remove('open');

            if (backdrop) backdrop.classList.remove('open');

        }

        // ─── UI Helper: Toast ───

        let toastTimeout = null;

        function showToast(text, type = "info") {

            const toast = document.getElementById('toast');

            const iconSpan = document.getElementById('toast-icon');

            const textSpan = document.getElementById('toast-text');

            let icon = "📢";

            if (type === "success") { 

                icon = "✅"; 

                toast.style.borderColor = 'var(--success)'; 

                toast.style.borderLeft = '4px solid var(--success)';

            }

            else if (type === "error") { 

                icon = "⚠️"; 

                toast.style.borderColor = 'var(--danger)'; 

                toast.style.borderLeft = '4px solid var(--danger)';

            }

            else { 

                toast.style.borderColor = 'var(--gold)'; 

                toast.style.borderLeft = '4px solid var(--gold)';

            }

            iconSpan.textContent = icon;

            textSpan.textContent = text;

            toast.classList.add('show');

            if (toastTimeout) clearTimeout(toastTimeout);

            const duration = type === "error" ? 3600 : (type === "info" ? 1400 : 1900);

            toastTimeout = setTimeout(() => {

                toast.classList.remove('show');

            }, duration);

        }

        function renderTelegramPreview(text) {

            if (!text) return '<span style="color:var(--text-secondary); font-style:italic;">محتوى فارغ...</span>';

            let escaped = escapeHtml(text);

            escaped = escaped

                .replace(/&lt;b&gt;([\s\S]*?)&lt;\/b&gt;/g, '<strong>$1</strong>')

                .replace(/&lt;i&gt;([\s\S]*?)&lt;\/i&gt;/g, '<em>$1</em>')

                .replace(/&lt;code&gt;([\s\S]*?)&lt;\/code&gt;/g, '<code style="background: rgba(255,255,255,0.12); padding: 2px 5px; border-radius: 4px; font-family: monospace; font-size: 0.9em; color: #f43f5e;">$1</code>')

                .replace(/&lt;blockquote&gt;([\s\S]*?)&lt;\/blockquote&gt;/g, '<blockquote style="border-right: 3px solid #5288c1; padding-right: 12px; margin: 8px 0; color: #a4c6eb; background: rgba(82, 136, 193, 0.08); border-left: none; padding-left: 0; display: block; border-top: none; border-bottom: none;">$1</blockquote>')

                .replace(/&lt;a\s+href=(?:&quot;|&#39;|')([\s\S]*?)(?:&quot;|&#39;|')&gt;([\s\S]*?)&lt;\/a&gt;/gi, '<a href="$1" target="_blank" style="color: #2481cc; text-decoration: underline; font-weight: 500;">$2</a>')

                .replace(/\n/g, '<br>');

            return escaped;

        }

        function openHybridTelegramEditor() {

            const expTextarea = document.getElementById('qb-edit-exp');

            if (!expTextarea) return;

            

            const modalTextarea = document.getElementById('tg-editor-textarea');

            modalTextarea.value = expTextarea.value;

            

            // Set current time for simulated bubble

            const now = new Date();

            const hrs = String(now.getHours()).padStart(2, '0');

            const mins = String(now.getMinutes()).padStart(2, '0');

            const timeEl = document.getElementById('tg-bubble-time-el');

            if (timeEl) timeEl.textContent = `${hrs}:${mins}`;

            

            updateLiveTelegramPreview();

            

            const overlay = document.getElementById('telegram-editor-overlay');

            overlay.style.display = 'flex';

            setTimeout(() => overlay.classList.add('show'), 10);

        }

        function closeHybridTelegramEditor() {

            const overlay = document.getElementById('telegram-editor-overlay');

            if (!overlay) return;

            overlay.classList.remove('show');

            setTimeout(() => overlay.style.display = 'none', 300);

        }

        function updateLiveTelegramPreview() {

            const text = document.getElementById('tg-editor-textarea').value;

            const previewContainer = document.getElementById('tg-live-preview-content');

            if (previewContainer) {

                previewContainer.innerHTML = renderTelegramPreview(text);

            }

        }

        function insertTelegramTag(tag) {

            const textarea = document.getElementById('tg-editor-textarea');

            if (!textarea) return;

            

            const start = textarea.selectionStart;

            const end = textarea.selectionEnd;

            const text = textarea.value;

            

            const selectedText = text.substring(start, end);

            const replacement = `<${tag}>${selectedText}</${tag}>`;

            

            textarea.value = text.substring(0, start) + replacement + text.substring(end);

            

            // Refocus and place selection

            textarea.focus();

            if (selectedText.length > 0) {

                textarea.setSelectionRange(start, start + replacement.length);

            } else {

                // place cursor inside tags

                const cursorPosition = start + tag.length + 2;

                textarea.setSelectionRange(cursorPosition, cursorPosition);

            }

            

            updateLiveTelegramPreview();

        }

        function clearSelectedTelegramTags() {

            const textarea = document.getElementById('tg-editor-textarea');

            if (!textarea) return;

            

            const start = textarea.selectionStart;

            const end = textarea.selectionEnd;

            const text = textarea.value;

            

            let targetText = text;

            let isSelectionOnly = start !== end;

            

            if (isSelectionOnly) {

                targetText = text.substring(start, end);

            }

            

            // Strip tags

            const cleaned = targetText

                .replace(/<\/?(b|i|code|blockquote)>/gi, '');

                

            if (isSelectionOnly) {

                textarea.value = text.substring(0, start) + cleaned + text.substring(end);

                textarea.focus();

                textarea.setSelectionRange(start, start + cleaned.length);

            } else {

                textarea.value = cleaned;

                textarea.focus();

            }

            

            updateLiveTelegramPreview();

        }

        function applyTelegramEditorChange() {

            const modalTextarea = document.getElementById('tg-editor-textarea');

            const expTextarea = document.getElementById('qb-edit-exp');

            if (modalTextarea && expTextarea) {

                expTextarea.value = modalTextarea.value;

                updateDrawerTelegramPreview();

            }

            closeHybridTelegramEditor();

            showToast("✨ تم تطبيق تنسيق تليجرام بنجاح! تذكر حفظ التغييرات للبطاقة.", "success");

        }

        // ─── Thematic Axes Fullscreen Dashboard Editor Logic ───
        let currentAxesEditing = null;
        let activeAxisIdx = 0;

        window.openAxesEditor = function(subject, lessonNum) {
            const lesson = state.transcripts.find(l => l.subject === subject && parseInt(l.lessonNum) === parseInt(lessonNum));
            if (!lesson) {
                showToast("⚠️ لم يتم العثور على الدرس المطلوب", "error");
                return;
            }

            // Create a deep copy of thematic blocks to edit locally
            const blocksCopy = (lesson.thematic_blocks || []).map((b, idx) => {
                // Fetch segments falling within the time boundaries of this block
                const startSec = b.start_seconds || 0;
                const nextBlock = lesson.thematic_blocks[idx + 1];
                const endSec = nextBlock ? (nextBlock.start_seconds || Infinity) : Infinity;
                const blockSegs = (lesson.segments || []).filter(seg => (seg.sec || 0) >= startSec && (seg.sec || 0) < endSec);
                const rawSegText = blockSegs.map(s => s.text).join('\n');

                return {
                    title: b.title || '',
                    explanation: b.explanation || '',
                    video_link: b.video_link || '',
                    poetry_verses: b.poetry_verses || '',
                    search_text: rawSegText || b.search_text || ''
                };
            });

            currentAxesEditing = {
                subject: subject,
                lessonNum: parseInt(lessonNum),
                blocks: blocksCopy
            };
            activeAxisIdx = 0;

            // Show Overlay
            const overlay = document.getElementById('axes-editor-overlay');
            if (overlay) {
                overlay.style.display = 'flex';
                setTimeout(() => overlay.classList.add('show'), 10);
            }

            window.renderAxesSidebar();
            window.loadActiveAxis();
        };

        window.closeAxesEditor = function() {
            const overlay = document.getElementById('axes-editor-overlay');
            if (!overlay) return;
            overlay.classList.remove('show');
            setTimeout(() => { overlay.style.display = 'none'; }, 300);
            currentAxesEditing = null;
        };

        window.renderAxesSidebar = function() {
            const listEl = document.getElementById('axes-sidebar-list');
            if (!listEl || !currentAxesEditing) return;

            listEl.innerHTML = '';
            if (currentAxesEditing.blocks.length === 0) {
                listEl.innerHTML = '<div style="color: var(--text-secondary); text-align: center; padding: 20px 0; font-size: 0.85rem;">لا توجد محاور. اضغط على الزر أدناه لإضافة محور.</div>';
                return;
            }

            currentAxesEditing.blocks.forEach((block, idx) => {
                const item = document.createElement('div');
                item.className = `axis-item ${idx === activeAxisIdx ? 'active' : ''}`;
                item.setAttribute('data-idx', idx);
                item.onclick = () => {
                    activeAxisIdx = idx;
                    window.renderAxesSidebar();
                    window.loadActiveAxis();
                };

                item.innerHTML = `
                    <span class="axis-item-title">${idx + 1}. ${escapeHtml(block.title || 'بدون عنوان')}</span>
                    <div class="axis-actions" onclick="event.stopPropagation();">
                        <button class="axis-action-btn" onclick="window.moveAxisUp(${idx})" title="نقل للأعلى">🔼</button>
                        <button class="axis-action-btn" onclick="window.moveAxisDown(${idx})" title="نقل للأسفل">🔽</button>
                        <button class="axis-action-btn" onclick="window.deleteAxis(${idx})" title="حذف المحور">❌</button>
                    </div>
                `;
                listEl.appendChild(item);
            });
        }

        window.loadActiveAxis = function() {
            const editorPanel = document.getElementById('axes-editor-panel-container');
            if (!editorPanel) return;

            if (!currentAxesEditing || currentAxesEditing.blocks.length === 0) {
                editorPanel.innerHTML = `
                    <div style="flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: var(--text-secondary); text-align: center; gap: 15px;">
                        <span style="font-size: 3rem;">📁</span>
                        <span>يرجى إضافة محور جديد للبدء في التحرير</span>
                        <button class="btn btn-primary" onclick="window.addNewAxis()">➕ إضافة محور جديد</button>
                    </div>
                `;
                return;
            }

            const block = currentAxesEditing.blocks[activeAxisIdx];
            editorPanel.innerHTML = `
                <div class="editor-card">
                    <div class="editor-card-title">📌 عنوان المحور</div>
                    <input type="text" class="axes-input" value="${escapeHtml(block.title)}" placeholder="اكتب عنوان المحور هنا..." oninput="currentAxesEditing.blocks[activeAxisIdx].title = this.value; window.updateAxisSidebarTitle(activeAxisIdx); window.updateLiveStudentPreview();">
                </div>

                <div class="editor-card">
                    <div class="editor-card-title">🎥 رابط الفيديو (مع أو بدون وسم زمني)</div>
                    <input type="text" class="axes-input" style="font-family: monospace; font-size: 0.95rem; font-weight: normal; direction: ltr; text-align: left;" value="${escapeHtml(block.video_link || '')}" placeholder="https://www.youtube.com/watch?v=..." oninput="currentAxesEditing.blocks[activeAxisIdx].video_link = this.value; window.updateLiveStudentPreview();">
                </div>

                <!-- Helper Toolbar -->
                <div class="axes-toolbar">
                    <span class="axes-toolbar-title">🛠️ أدوات تحديد ونقل نص التفريغ:</span>
                    <button class="axes-toolbar-btn" onclick="window.moveSelectionToPrev()" title="نقل النص المحدد إلى نهاية المحور السابق">➡️ السابق</button>
                    <button class="axes-toolbar-btn" onclick="window.moveSelectionToNext()" title="نقل النص المحدد إلى بداية المحور التالي">⬅️ التالي</button>
                    <button class="axes-toolbar-btn" onclick="window.splitAxisAtSelection()" title="تقسيم المحور عند تحديد النص أو موقع المؤشر">✂️ تقسيم المحور</button>
                    <button class="axes-toolbar-btn" onclick="window.moveSelectionToPoetry()" title="تحويل النص المحدد إلى أبيات شعرية">📜 إرسال للشعر</button>
                </div>

                <div style="display: grid; grid-template-columns: 1.2fr 1fr; gap: 20px; flex: 1; min-height: 400px; margin-bottom: 20px;">
                    <!-- Left: Transcription Text -->
                    <div class="editor-card" style="flex: 1; display: flex; flex-direction: column; border-color: var(--primary);">
                        <div class="editor-card-title" style="color: var(--primary);">📝 نص التفريغ</div>
                        <textarea id="axis-transcription-editor" class="axes-textarea" style="flex: 1; min-height: 250px;" placeholder="اكتب نص التفريغ الحرفي الكامل هنا..." oninput="currentAxesEditing.blocks[activeAxisIdx].search_text = this.value; window.updateLiveStudentPreview();">${escapeHtml(block.search_text || '')}</textarea>
                    </div>

                    <!-- Right: Explanation + Poetry stacked -->
                    <div style="display: flex; flex-direction: column; gap: 20px;">
                        <div class="editor-card gold-tint" style="flex: 1; display: flex; flex-direction: column;">
                            <div class="editor-card-title">💡 شرح وتلخيص المحور (شاشات العرض للطلاب)</div>
                            <textarea id="axis-explanation-editor" class="axes-textarea" style="flex: 1; min-height: 100px;" placeholder="اكتب الشرح التوضيحي للمحور هنا..." oninput="currentAxesEditing.blocks[activeAxisIdx].explanation = this.value; window.updateLiveStudentPreview();">${escapeHtml(block.explanation || '')}</textarea>
                        </div>

                        <div class="editor-card gold-tint" style="flex: 1; display: flex; flex-direction: column;">
                            <div class="editor-card-title">📜 أبيات الشعر / السيرة (تنسيق ممركز)</div>
                            <textarea id="axis-poetry-editor" class="axes-textarea" style="flex: 1; text-align: center; font-style: italic; min-height: 100px;" placeholder="أدخل أبيات الشعر هنا (كل بيت في سطر منفصل)..." oninput="currentAxesEditing.blocks[activeAxisIdx].poetry_verses = this.value; window.updateLiveStudentPreview();">${escapeHtml(block.poetry_verses || '')}</textarea>
                        </div>
                    </div>
                </div>

                <!-- Student Live Preview Card -->
                <div class="editor-card" style="border: 1px solid rgba(212, 175, 55, 0.35); background: rgba(212, 175, 55, 0.03); margin-top: 10px; margin-bottom: 20px;">
                    <div class="editor-card-title" style="color: var(--gold-light); display: flex; align-items: center; gap: 8px;">📱 معاينة عرض الطالب (Aperçu en direct pour l'étudiant)</div>
                    <div id="live-student-preview-container" style="margin-top: 10px;">
                        <!-- Rendered dynamically -->
                    </div>
                </div>
                
                <!-- Bottom Scroll Spacer to clear the absolute/fixed height overlay footer -->
                <div style="height: 120px; flex-shrink: 0;"></div>
            `;
            window.updateLiveStudentPreview();
        }

        window.updateAxisSidebarTitle = function(idx) {
            const item = document.querySelector(`.axis-item[data-idx="${idx}"] .axis-item-title`);
            if (item && currentAxesEditing && currentAxesEditing.blocks[idx]) {
                item.textContent = `${idx + 1}. ${currentAxesEditing.blocks[idx].title || 'بدون عنوان'}`;
            }
        };

        window.addNewAxis = function() {
            if (!currentAxesEditing) return;
            const newAx = {
                title: 'محور جديد',
                explanation: '',
                video_link: '',
                poetry_verses: '',
                search_text: ''
            };
            currentAxesEditing.blocks.splice(activeAxisIdx + 1, 0, newAx);
            activeAxisIdx = activeAxisIdx + 1;
            window.renderAxesSidebar();
            window.loadActiveAxis();
        };

        window.moveAxisUp = function(idx) {
            if (idx <= 0 || !currentAxesEditing) return;
            const temp = currentAxesEditing.blocks[idx];
            currentAxesEditing.blocks[idx] = currentAxesEditing.blocks[idx - 1];
            currentAxesEditing.blocks[idx - 1] = temp;
            activeAxisIdx = idx - 1;
            window.renderAxesSidebar();
            window.loadActiveAxis();
        };

        window.moveAxisDown = function(idx) {
            if (!currentAxesEditing || idx >= currentAxesEditing.blocks.length - 1) return;
            const temp = currentAxesEditing.blocks[idx];
            currentAxesEditing.blocks[idx] = currentAxesEditing.blocks[idx + 1];
            currentAxesEditing.blocks[idx + 1] = temp;
            activeAxisIdx = idx + 1;
            window.renderAxesSidebar();
            window.loadActiveAxis();
        };

        window.deleteAxis = function(idx) {
            if (!currentAxesEditing) return;
            if (confirm("⚠️ هل أنت متأكد من حذف هذا المحور نهائياً؟")) {
                currentAxesEditing.blocks.splice(idx, 1);
                if (activeAxisIdx >= currentAxesEditing.blocks.length) {
                    activeAxisIdx = Math.max(0, currentAxesEditing.blocks.length - 1);
                }
                window.renderAxesSidebar();
                window.loadActiveAxis();
            }
        };

        

        window.moveSelectionToPrev = function() {
            const txtArea = document.getElementById('axis-transcription-editor');
            if (!txtArea || !currentAxesEditing) return;
            const start = txtArea.selectionStart;
            const end = txtArea.selectionEnd;
            const selectedText = txtArea.value.substring(start, end).trim();
            if (!selectedText) {
                showToast("⚠️ يرجى تحديد جزء من نص التفريغ أولاً", "warning");
                return;
            }
            if (activeAxisIdx === 0) {
                showToast("⚠️ لا يوجد محور سابق لنقل النص إليه", "warning");
                return;
            }
            
            // Remove text from current transcription
            const val = txtArea.value;
            txtArea.value = val.substring(0, start) + val.substring(end);
            currentAxesEditing.blocks[activeAxisIdx].search_text = txtArea.value;

            // Prepend/append to previous transcription
            const prevAxis = currentAxesEditing.blocks[activeAxisIdx - 1];
            prevAxis.search_text = (prevAxis.search_text || '').trim() + "\n\n" + selectedText;

            showToast("➡️ تم نقل النص المحدد بنجاح لنهاية تفriغ المحور السابق", "success");
            window.renderAxesSidebar();
            window.loadActiveAxis();
        };

        window.moveSelectionToNext = function() {
            const txtArea = document.getElementById('axis-transcription-editor');
            if (!txtArea || !currentAxesEditing) return;
            const start = txtArea.selectionStart;
            const end = txtArea.selectionEnd;
            const selectedText = txtArea.value.substring(start, end).trim();
            if (!selectedText) {
                showToast("⚠️ يرجى تحديد جزء من نص التفريغ أولاً", "warning");
                return;
            }
            if (activeAxisIdx === currentAxesEditing.blocks.length - 1) {
                showToast("⚠️ لا يوجد محور تالي لنقل النص إليه", "warning");
                return;
            }

            // Remove text from current transcription
            const val = txtArea.value;
            txtArea.value = val.substring(0, start) + val.substring(end);
            currentAxesEditing.blocks[activeAxisIdx].search_text = txtArea.value;

            // Prepend to next transcription
            const nextAxis = currentAxesEditing.blocks[activeAxisIdx + 1];
            nextAxis.search_text = selectedText + "\n\n" + (nextAxis.search_text || '').trim();

            showToast("⬅️ تم نقل النص المحدد بنجاح لبداية تفريغ المحور التالي", "success");
            window.renderAxesSidebar();
            window.loadActiveAxis();
        };

        window.splitAxisAtSelection = function() {
            const txtArea = document.getElementById('axis-transcription-editor');
            if (!txtArea || !currentAxesEditing) return;
            const start = txtArea.selectionStart;
            const end = txtArea.selectionEnd;
            
            let splitText = "";
            const val = txtArea.value;
            if (start !== end) {
                // Split selected text
                splitText = val.substring(start, end).trim();
                txtArea.value = val.substring(0, start) + val.substring(end);
            } else {
                // Split from cursor to end
                txtArea.value = val.substring(0, start);
                splitText = val.substring(start).trim();
            }

            currentAxesEditing.blocks[activeAxisIdx].search_text = txtArea.value;

            const newAx = {
                title: `${currentAxesEditing.blocks[activeAxisIdx].title || 'المحور'} (تابع)`,
                explanation: '',
                video_link: currentAxesEditing.blocks[activeAxisIdx].video_link || '',
                poetry_verses: '',
                search_text: splitText
            };

            currentAxesEditing.blocks.splice(activeAxisIdx + 1, 0, newAx);
            activeAxisIdx = activeAxisIdx + 1;

            showToast("✂️ تم تقسيم المحور بنجاح وإنشاء محور جديد", "success");
            window.renderAxesSidebar();
            window.loadActiveAxis();
        };

        window.moveSelectionToPoetry = function() {
            const txtArea = document.getElementById('axis-transcription-editor');
            if (!txtArea || !currentAxesEditing) return;
            const start = txtArea.selectionStart;
            const end = txtArea.selectionEnd;
            const selectedText = txtArea.value.substring(start, end).trim();
            if (!selectedText) {
                showToast("⚠️ يرجى تحديد جزء من نص التفريغ أولاً", "warning");
                return;
            }

            // Remove text from current transcription
            const val = txtArea.value;
            txtArea.value = val.substring(0, start) + val.substring(end);
            currentAxesEditing.blocks[activeAxisIdx].search_text = txtArea.value;

            // Append to current poetry
            const block = currentAxesEditing.blocks[activeAxisIdx];
            block.poetry_verses = (block.poetry_verses || '').trim() + (block.poetry_verses ? '\n' : '') + selectedText;

            showToast("📜 تم إرسال النص المحدد لأبيات الشعر بنجاح", "success");
            window.loadActiveAxis();
        };

        window.saveAxesChanges = async function() {
            if (!currentAxesEditing) return;

            // Validate that all blocks have titles
            for (let i = 0; i < currentAxesEditing.blocks.length; i++) {
                if (!currentAxesEditing.blocks[i].title.trim()) {
                    showToast(`⚠️ يرجى إدخال عنوان للمحور رقم ${i + 1}`, "error");
                    return;
                }
            }

            const saveBtn = document.getElementById('save-axes-btn');
            if (saveBtn) {
                saveBtn.disabled = true;
                saveBtn.innerHTML = '⏳ جاري الحفظ ومزامنة البيانات...';
            }

            try {
                const res = await fetch('/admin/save-thematic-blocks', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        userId: state.userId,
                        subject: currentAxesEditing.subject,
                        lessonNum: currentAxesEditing.lessonNum,
                        thematicBlocks: currentAxesEditing.blocks
                    })
                });

                const data = await res.json();
                if (data.success) {
                    showToast("✅ تم حفظ وتحديث كافة المحاور بنجاح ومزامنتها للإنتاج وقاعدة البيانات", "success");
                    
                    // Sync locally
                    const lesson = state.transcripts.find(l => l.subject === currentAxesEditing.subject && parseInt(l.lessonNum) === currentAxesEditing.lessonNum);
                    if (lesson) {
                        lesson.thematic_blocks = currentAxesEditing.blocks;
                    }

                    window.closeAxesEditor();
                    
                    // Refresh view
                    if (typeof filterLessons === 'function') {
                        filterLessons();
                    } else {
                        location.reload();
                    }
                } else {
                    showToast(`❌ حدث خطأ أثناء حفظ التعديلات: ${data.error}`, "error");
                }
            } catch (err) {
                console.error("Error saving thematic blocks:", err);
                showToast(`❌ فشل الاتصال بالخادم لحفظ البيانات: ${err.message}`, "error");
            } finally {
                if (saveBtn) {
                    saveBtn.disabled = false;
                    saveBtn.innerHTML = '💾 حفظ كافة المحاور والمزامنة للإنتاج';
                }
            }
        };


        window.toggleFullTranscriptPanel = function() {
            const panel = document.getElementById('axes-full-transcript-panel');
            if (!panel) return;
            if (panel.style.display === 'none') {
                panel.style.display = 'flex';
                const txtArea = document.getElementById('full-transcript-textarea');
                if (txtArea && currentAxesEditing) {
                    const lesson = state.transcripts.find(l => l.subject === currentAxesEditing.subject && parseInt(l.lessonNum) === currentAxesEditing.lessonNum);
                    txtArea.value = lesson ? (lesson.full_text || '') : '';
                }
            } else {
                panel.style.display = 'none';
            }
        };

        window.importSelectionToCurrentAxis = function() {
            const fullTxtArea = document.getElementById('full-transcript-textarea');
            const axisTxtArea = document.getElementById('axis-transcription-editor');
            if (!fullTxtArea || !axisTxtArea || !currentAxesEditing) return;
            
            const start = fullTxtArea.selectionStart;
            const end = fullTxtArea.selectionEnd;
            const selectedText = fullTxtArea.value.substring(start, end).trim();
            if (!selectedText) {
                showToast("⚠️ يرجى تحديد جزء من نص التفريغ الكامل أولاً", "warning");
                return;
            }
            
            const val = axisTxtArea.value;
            const cursor = axisTxtArea.selectionStart;
            axisTxtArea.value = val.substring(0, cursor) + (val ? "\n\n" : "") + selectedText + val.substring(cursor);
            currentAxesEditing.blocks[activeAxisIdx].search_text = axisTxtArea.value;
            window.updateLiveStudentPreview();
            
            showToast("📥 تم إدراج النص المحدد في المحور النشط", "success");
        };

        window.importSelectionToNewAxis = function() {
            const fullTxtArea = document.getElementById('full-transcript-textarea');
            if (!fullTxtArea || !currentAxesEditing) return;
            
            const start = fullTxtArea.selectionStart;
            const end = fullTxtArea.selectionEnd;
            const selectedText = fullTxtArea.value.substring(start, end).trim();
            if (!selectedText) {
                showToast("⚠️ يرجى تحديد جزء من نص التفريغ الكامل أولاً", "warning");
                return;
            }
            
            const newAx = {
                title: 'محور جديد',
                explanation: '',
                video_link: '',
                poetry_verses: '',
                search_text: selectedText
            };
            
            currentAxesEditing.blocks.splice(activeAxisIdx + 1, 0, newAx);
            activeAxisIdx = activeAxisIdx + 1;
            window.renderAxesSidebar();
            window.loadActiveAxis();
            
            showToast("➕ تم إنشاء محور جديد بالنص المحدد", "success");
        };

        window.updateLiveStudentPreview = function() {
            const container = document.getElementById('live-student-preview-container');
            if (!container || !currentAxesEditing) return;
            const block = currentAxesEditing.blocks[activeAxisIdx];
            if (!block) return;

            const escapedTitle = escapeHtml(block.title || 'عنوان المحور');
            const escapedExpl = escapeHtml(block.explanation || 'لا يوجد شرح لهذا المحور حتى الآن. اكتب شرحاً في الأعلى للمعاينة...');
            const escapedPoetry = escapeHtml(block.poetry_verses || '');
            const escapedSearchText = escapeHtml(block.search_text || 'لا يوجد نص تفريغ لهذا المحور...');
            const hasPoetry = escapedPoetry.trim().length > 0;
            
            // Get timestamp from video url or default
            let timestamp = '0:00';
            if (block.video_link) {
                const m = block.video_link.match(/[?&]t=(\\d+)s?/);
                if (m) {
                    const sec = parseInt(m[1]);
                    const mins = Math.floor(sec / 60);
                    const secs = sec % 60;
                    timestamp = `${mins}:${secs < 10 ? '0' : ''}${secs}`;
                }
            }

            container.innerHTML = `
                <div style="background: var(--bg); border: 1px solid var(--border); border-radius: 10px; padding: 16px; display: flex; flex-direction: column; gap: 12px; direction: rtl; text-align: right;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <h4 style="margin: 0; font-size: 1.1rem; color: var(--primary);"><span style="color: var(--text-secondary); font-size: 0.9rem; margin-left: 8px;">محور ${activeAxisIdx + 1}:</span> ${escapedTitle}</h4>
                        <span style="font-size: 0.8rem; color: var(--text-secondary); background: var(--surface-hover); padding: 4px 8px; border-radius: 6px;">⏱ ${timestamp}</span>
                    </div>
                    
                    <div style="background: rgba(212, 175, 55, 0.06); border-right: 4px solid var(--gold); padding: 12px; border-radius: 6px; font-size: 0.95rem; color: var(--text-primary); line-height: 1.7; white-space: pre-line;">
                        <strong style="color: var(--gold); display: block; margin-bottom: 6px;">💡 الشرح التوضيحي (الملخص):</strong>
                        ${escapedExpl}
                    </div>

                    <div style="background: rgba(255,255,255,0.02); border-right: 4px solid var(--primary); padding: 12px; border-radius: 6px; font-size: 0.92rem; color: var(--text-secondary); line-height: 1.8; white-space: pre-line; margin-top: 10px;">
                        <strong style="color: var(--primary); display: block; margin-bottom: 6px;">📝 نص التفريغ:</strong>
                        ${escapedSearchText}
                    </div>

                    ${hasPoetry ? `
                        <div style="background: rgba(212, 175, 55, 0.04); border: 1px dashed rgba(212, 175, 55, 0.3); padding: 14px; border-radius: 6px; text-align: center; font-style: italic; font-size: 1.1rem; color: var(--text-primary); line-height: 1.8; white-space: pre-line;">
                            ${escapedPoetry}
                        </div>
                    ` : ''}
                </div>
            `;
        };


    

// --- Curriculum Mapping (Miller Columns) ---
let curriculumData = { programs: [], nodes: [], unassigned_questions: [] };
let selectedPath = { 1: null, 2: null, 3: null, 4: null };


async function toggleNodeVisibility(nodeId) {
    try {
        const response = await fetch('/admin/curriculum/toggle-visibility', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ userId: state.userId, node_id: nodeId })
        });
        const data = await response.json();
        if (data.success) {
            loadAdminThematics();
        } else {
            alert('خطأ: ' + data.error);
        }
    } catch (e) {
        console.error(e);
        alert('حدث خطأ أثناء الاتصال بالخادم.');
    }
}

function selectCurriculumNode(level, id) {
    selectedPath[level] = id;
    const maxKeys = Math.max(...Object.keys(selectedPath).map(Number), level);
    for (let l = level + 1; l <= maxKeys; l++) {
        delete selectedPath[l];
    }
    renderCurriculum();
}

async function loadAdminThematics() {
    const subject = document.getElementById('curriculum-subject-filter').value;
    const yearEl = document.getElementById('curriculum-year-filter');
    const year = yearEl ? yearEl.value : '';
    
    const container = document.getElementById('miller-columns-container');
    if (container) {
        container.className = 'miller-columns-container';
    }
    
    try {
        const response = await fetch('/admin/thematics', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ userId: state.userId, subject: subject, academic_year: year })
        });
        const data = await response.json();
        if (data.success) {
            curriculumData = data;
            selectedPath = {};
            renderCurriculum();
        } else {
            console.error("Failed to load thematics:", data.error);
        }
    } catch (e) {
        console.error("Error loading thematics:", e);
    }
}

function renderCurriculum() {
    const container = document.getElementById('miller-columns-container');
    if (!container) return;
    container.innerHTML = '';
    
    // Level 1: Root Nodes
    renderMillerColumn(1, null);
    
    // Recursively render child columns
    let level = 1;
    while(selectedPath[level] != null) {
        renderMillerColumn(level + 1, selectedPath[level]);
        level++;
    }
    
    renderMillerInbox();
}

function renderMillerColumn(level, parentId) {
    const container = document.getElementById('miller-columns-container');
    if (!container) return;
    
    // Remove any columns >= level
    const existingCols = container.querySelectorAll('.miller-column');
    existingCols.forEach(col => {
        if (parseInt(col.dataset.level) >= level) {
            col.remove();
        }
    });

    let items = [];
    if (level === 1) {
        // Level 1: Root nodes
        items = curriculumData.nodes.filter(n => n.parent_id == null);
    } else {
        items = curriculumData.nodes.filter(n => n.parent_id == parentId);
    }

    if (items.length === 0 && level > 1) return;

    const colDiv = document.createElement('div');
    colDiv.className = 'miller-column';
    colDiv.dataset.level = level;
    
    const depthTitles = ['المجلدات الرئيسية', 'المجلدات الفرعية', 'المحاور', 'الجزئيات', 'مستوى 5', 'مستوى 6'];
    const titleHeader = depthTitles[level - 1] || `مستوى ${level}`;
    
    let headerHtml = `
        <div class="miller-column-header">
            <span>${titleHeader}</span>
            <button class="btn btn-secondary" style="padding: 2px 8px; font-size: 0.8rem;" onclick="addCurriculumNode(${level}, ${parentId})">➕</button>
        </div>
        <div class="miller-column-body" id="miller-col-body-${level}" ondragover="allowDrop(event)" ondrop="dropQuestionToNode(event, ${level})">
    `;
    
    items.sort((a,b) => {
        const orderDiff = (a.order_index || 0) - (b.order_index || 0);
        if (orderDiff !== 0) return orderDiff;
        const titleA = (a.name || a.title || '').toString();
        const titleB = (b.name || b.title || '').toString();
        return titleA.localeCompare(titleB, 'ar');
    }).forEach(item => {
        const isSelected = selectedPath[level] === item.id;
        const title = item.title || item.name;
        const isHidden = item.is_active === 0;
        const eyeIcon = isHidden ? '🚫' : '👁️';
        const opacityStyle = isHidden ? 'opacity: 0.5;' : '';
        
        headerHtml += `
            <div class="miller-item ${isSelected ? 'selected' : ''}" onclick="selectCurriculumNode(${level}, ${item.id})" data-id="${item.id}" style="${opacityStyle}">
                <span class="miller-item-text">${title}</span>
                <span class="drag-handle" draggable="true" ondragstart="dragNode(event, ${level}, ${item.id})" ondragover="allowDrop(event)" ondragleave="dragLeaveNode(event)" ondrop="dropNode(event, ${level}, ${item.id})">⋮⋮</span>
                <div class="miller-item-actions">
                    <button class="miller-item-btn" title="تبديل الظهور" onclick="event.stopPropagation(); toggleNodeVisibility(${item.id})">${eyeIcon}</button>
                    <button class="miller-item-btn" title="عرض الأسئلة" onclick="event.stopPropagation(); viewNodeQuestions(${item.id}, '${title.replace(/'/g, "\'")}')">📂</button>
                    <button class="miller-item-btn" title="تعديل" onclick="event.stopPropagation(); editCurriculumNode(${level}, ${item.id}, '${title.replace(/'/g, "\'")}')">✏️</button>
                    <button class="miller-item-btn" title="حذف" onclick="event.stopPropagation(); deleteCurriculumNode(${level}, ${item.id})">🗑️</button>
                </div>
            </div>
        `;
    });
    
    headerHtml += '</div>';
    colDiv.innerHTML = headerHtml;
    container.appendChild(colDiv);
    
    setTimeout(() => {
        colDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'start' });
    }, 100);
}

function renderMillerInbox() {
    const list = document.getElementById('miller-inbox-list');
    list.innerHTML = '';
    
    if (!curriculumData.unassigned_questions || curriculumData.unassigned_questions.length === 0) {
        list.innerHTML = '<div style="text-align:center; color: var(--text-secondary); padding: 20px;">لا يوجد أسئلة غير مصنفة</div>';
        return;
    }
    
    let htmlContent = '';
    curriculumData.unassigned_questions.forEach(q => {
        const title = (q.subject || '') + ' - درس ' + (q.course_number || '?');
        const text = q.question || 'بدون نص';
        const sourceClass = q.source === 'IA' ? 'source-ai' : (q.source === 'USER' ? 'source-user' : 'source-official');
        htmlContent += `
            <div class="draggable-question ${sourceClass}">
                <span class="question-id-badge">#${q.id}</span>
                <div class="draggable-question-header">
                    <span class="drag-handle" draggable="true" ondragstart="dragQuestion(event, ${q.id})">⋮⋮</span>
                    <div style="font-size: 0.8rem; color: var(--text-secondary);">${title}</div>
                </div>
                <div class="draggable-question-text">${text}</div>
            </div>
        `;
    });
    list.innerHTML = htmlContent;
}

function switchMillerSideTab(tabName) {
    document.getElementById('miller-side-panel').style.display = 'flex';
    document.getElementById('btn-show-sidepanel').style.display = 'none';

    document.getElementById('miller-tab-inbox').style.display = 'none';
    document.getElementById('miller-tab-preview').style.display = 'none';
    
    document.getElementById('btn-tab-miller-inbox').classList.remove('btn-primary');
    document.getElementById('btn-tab-miller-inbox').classList.add('btn-secondary');
    
    document.getElementById('btn-tab-miller-preview').classList.remove('btn-primary');
    document.getElementById('btn-tab-miller-preview').classList.add('btn-secondary');
    
    document.getElementById('miller-tab-' + tabName).style.display = 'flex';
    document.getElementById('btn-tab-miller-' + tabName).classList.remove('btn-secondary');
    document.getElementById('btn-tab-miller-' + tabName).classList.add('btn-primary');
}

function dragQuestion(ev, questionId) {
    ev.dataTransfer.setData("questionId", questionId);
}

function allowDrop(ev) {
    ev.preventDefault();
    ev.currentTarget.classList.add('drag-over');
}

async function dropQuestionToNode(ev, level) {
    ev.preventDefault();
    ev.currentTarget.classList.remove('drag-over');
    
    const questionId = ev.dataTransfer.getData("questionId");
    if (!questionId) return;
    
    const nodeId = selectedPath[level];
    if (!nodeId && level > 1) {
        alert("الرجاء تحديد عنصر أولاً");
        return;
    }
    
    try {
        const response = await fetch('/admin/thematics/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                userId: state.userId, 
                action: 'assign_question',
                question_id: parseInt(questionId),
                node_id: level === 1 ? null : nodeId
            })
        });
        const data = await response.json();
        if (data.success) {
            loadAdminThematics();
        }
    } catch(e) { console.error(e); }
}

async function dropQuestionToInbox(ev) {
    ev.preventDefault();
    ev.currentTarget.classList.remove('drag-over');
    
    const questionId = ev.dataTransfer.getData("questionId");
    if (!questionId) return;
    
    try {
        const response = await fetch('/admin/thematics/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                userId: state.userId, 
                action: 'assign_question',
                question_id: parseInt(questionId),
                node_id: null
            })
        });
        const data = await response.json();
        if (data.success) {
            loadAdminThematics();
        }
    } catch(e) { console.error(e); }
}

async function addCurriculumNode(level, parentId) {
    let payload = { userId: state.userId };
    
    if (level === 1) {
        const subject = prompt("رمز المادة (مثال: fiqh):");
        if (!subject) return;
        const name = prompt("اسم البرنامج (مثال: الفقه الميسر):");
        if (!name) return;
        payload.action = 'add_program';
        payload.subject = subject;
        payload.name = name;
    } else {
        const title = prompt("عنوان العقدة:");
        if (!title) return;
        payload.action = 'add_node';
        payload.title = title;
        payload.level = level;
        if (level === 2) {
            payload.program_id = parentId;
            payload.parent_id = null;
        } else {
            const parent = curriculumData.nodes.find(n => n.id == parentId);
            payload.program_id = parent ? parent.program_id : null;
            payload.parent_id = parentId;
        }
    }
    
    try {
        const response = await fetch('/admin/thematics/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (data.success) {
            loadAdminThematics();
        } else {
            alert("خطأ: " + data.error);
        }
    } catch(e) { console.error(e); }
}

async function editCurriculumNode(level, id, oldTitle) {
    if (level === 1) {
        alert("تعديل البرامج غير متاح حالياً من الواجهة. يرجى إضافته كبرنامج جديد.");
        return;
    }
    const newTitle = prompt("عنوان العقدة:", oldTitle);
    if (!newTitle || newTitle === oldTitle) return;
    
    try {
        const response = await fetch('/admin/thematics/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                userId: state.userId, 
                action: 'update_node',
                node_id: id,
                title: newTitle
            })
        });
        const data = await response.json();
        if (data.success) {
            loadAdminThematics();
        }
    } catch(e) { console.error(e); }
}

async function deleteCurriculumNode(level, id) {
    if (!confirm("هل أنت متأكد من الحذف؟ سيتم حذف جميع العقد الفرعية المرتبطة!")) return;
    
    if (level === 1) {
        alert("حذف البرامج غير متاح حالياً للبرامج.");
        return;
    }
    
    try {
        const response = await fetch('/admin/thematics/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                userId: state.userId, 
                action: 'delete_node',
                node_id: id
            })
        });
        const data = await response.json();
        if (data.success) {
            loadAdminThematics();
        }
    } catch(e) { console.error(e); }
}

// Hook into tab switching to load data
const originalSwitchTab = window.switchTab;
window.switchTab = function(tabName) {
    if (originalSwitchTab) {
        originalSwitchTab(tabName);
    }
    if (tabName === 'curriculum') {
        loadAdminThematics();
    }
};

document.addEventListener('dragleave', (ev) => {
    if (ev.target.classList && (ev.target.classList.contains('miller-column-body') || ev.target.classList.contains('miller-inbox-list'))) {
        ev.target.classList.remove('drag-over');
    }
});

async function viewNodeQuestions(nodeId, nodeTitle) {
    switchMillerSideTab('preview');
    document.getElementById('miller-preview-title').innerText = "الأسئلة المصنفة في: " + nodeTitle;
    const list = document.getElementById('miller-preview-list');
    list.innerHTML = '<div style="text-align:center; padding:20px;">جاري التحميل...</div>';
    
    try {
        const response = await fetch('/admin/thematics/node_questions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ userId: state.userId, node_id: nodeId })
        });
        const data = await response.json();
        
        if (data.success) {
            if (!data.questions || data.questions.length === 0) {
                list.innerHTML = '<div style="text-align:center; color: var(--text-secondary); padding: 20px;">لا يوجد أسئلة مصنفة في هذه العقدة</div>';
            } else {
                let html = '';
                data.questions.forEach(q => {
                    const text = q.question || 'بدون نص';
                    const sourceClass = q.source === 'IA' ? 'source-ai' : (q.source === 'USER' ? 'source-user' : 'source-official');
                    html += `
                        <div class="draggable-question ${sourceClass}" style="background: var(--surface-hover);">
                            <span class="question-id-badge">#${q.id}</span>
                            <div class="draggable-question-header">
                                <span class="drag-handle" draggable="true" ondragstart="dragQuestion(event, ${q.id})">⋮⋮</span>
                                <span style="font-size: 0.8rem; color: var(--text-secondary);">${q.subject || ''} - درس ${q.course_number || '?'}</span>
                            </div>
                            <div class="draggable-question-text">${text}</div>
                        </div>
                    `;
                });
                list.innerHTML = html;
            }
        } else {
            list.innerHTML = `<div style="color: red; padding: 20px;">خطأ: ${data.error}</div>`;
        }
    } catch (e) {
        list.innerHTML = `<div style="color: red; padding: 20px;">خطأ في الاتصال</div>`;
    }
}


function dragNode(ev, level, nodeId) {
    ev.dataTransfer.setData("nodeId", nodeId);
    ev.dataTransfer.setData("nodeLevel", level);
    ev.dataTransfer.effectAllowed = "move";
}

function dragLeaveNode(ev) {
    ev.currentTarget.classList.remove('drag-over');
}

async function dropNode(ev, level, targetNodeId) {
    const questionId = ev.dataTransfer.getData("questionId");
    if (questionId) {
        // It's a question, let it bubble up, but we remove drag-over
        ev.currentTarget.classList.remove('drag-over');
        return; 
    }
    
    ev.preventDefault();
    ev.stopPropagation();
    ev.currentTarget.classList.remove('drag-over');
    
    const sourceNodeId = ev.dataTransfer.getData("nodeId");
    const sourceLevel = ev.dataTransfer.getData("nodeLevel");
    
    if (!sourceNodeId || sourceLevel != level || sourceNodeId == targetNodeId) return;
    
    try {
        const response = await fetch('/admin/thematics/reorder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                userId: state.userId,
                source_node_id: parseInt(sourceNodeId),
                target_node_id: parseInt(targetNodeId),
                level: parseInt(level)
            })
        });
        
        const data = await response.json();
        if (data.success) {
            loadCurriculum();
            if (!window.silent) showToast("تم تغيير الترتيب بنجاح", "success");
        } else {
            alert("Error: " + data.error);
        }
    } catch (err) {
        console.error("Reorder error:", err);
    }
}
