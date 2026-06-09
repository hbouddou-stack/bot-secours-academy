let player; 
let currentLessonData = null;
let currentSubject = null;
let currentLessonNum = null;
let currentTabIndex = 0;
let thematicData = []; // Array of objects { title, startTime, endTime, htmlContent, questions: [] }
let DB = [];
let wordIndex = [];
let pendingSeekTime = null;
let syllabusCompletion = JSON.parse(localStorage.getItem('academy_syllabus_completions')) || {};
let syllabusMode = 'grid';
let isSeekingTab = false;

const SUBJECT_LABELS = {
    'sira': 'السيرة النبوية',
    'fiqh': 'الفقه',
    'tahawi': 'العقيدة الطحاوية',
    'adab': 'الأدب',
    'nahw': 'النحو'
};


// UI State
let currentTheme = localStorage.getItem('readerTheme') || 'sepia';
let fontSizeBase = parseInt(localStorage.getItem('readerFontSize')) || 18; 
if(currentTheme !== 'light') document.documentElement.setAttribute('data-theme', currentTheme);
document.documentElement.style.setProperty('--font-size-base', fontSizeBase + 'px');

document.addEventListener('DOMContentLoaded', async () => {
    initUIControls();

    try {
        const urlParams = new URLSearchParams(window.location.search);
        let lessonParam = urlParams.get('lesson'); 
        let subjectParam = urlParams.get('subject'); 

        const response = await fetch('transcripts.json?v=' + Date.now());
        DB = await response.json();

        buildSyllabusTab(DB);
        setTimeout(buildIndex, 100);

        if (lessonParam) {
            const found = DB.find(t => 
                (t.lessonNum == lessonParam || t.lesson.includes(lessonParam)) &&
                (!subjectParam || t.subject === subjectParam)
            );
            if (found) {
                openLesson(found);
                switchTab('reader');
            } else {
                switchTab('home');
            }
        } else {
            switchTab('home');
        }

    } catch (e) {
        console.error("Error loading reader data:", e);
    }
});

function loadLesson(lessonNum, subject, startSeconds = 0) {
    currentSubject = subject;
    currentLessonNum = lessonNum;
    
    document.getElementById('reader-empty-state').style.display = 'none';
    const activeState = document.getElementById('reader-active-state');
    if(activeState) activeState.style.display = 'block';
    
    document.getElementById('reader-content').style.display = 'block';
    const lesson = DB.find(t => t.lessonNum == lessonNum && t.subject === subject);
    if (lesson) {
        if (startSeconds > 0) {
            pendingSeekTime = startSeconds;
        }
        openLesson(lesson);
    }
}

window.openLessonFromList = function(subject, lessonNum, startSeconds = 0) {
    loadLesson(lessonNum, subject, startSeconds);
    switchTab('reader');
};

function openLesson(lesson) {
    const emptyState = document.getElementById('reader-empty-state');
    const activeState = document.getElementById('reader-active-state');
    if(emptyState) emptyState.style.display = 'none';
    if(activeState) activeState.style.display = 'block';
    
    document.getElementById('reader-content').style.display = 'block';
    currentLessonData = lesson;
    
    // Auto-seek logic
    if (!pendingSeekTime && lesson.thematic_blocks && lesson.thematic_blocks.length > 0) {
        pendingSeekTime = lesson.thematic_blocks[0].start_seconds;
    }
    
    prepareThematicData(lesson);
    renderLessonHeader(lesson);
    renderTabs();
    
    // Automatically set reader nav button visible
    document.getElementById('btn-nav-reader').style.display = 'flex';
    
    if(thematicData.length > 0) {
        switchThemeTab(0, false);
    }
    markLessonOpened(lesson.subject, lesson.lessonNum);
}



// Reading Progress Bar Logic

function updateDashboardProgress() {
    if (!thematicData || thematicData.length === 0) return;
    
    let currentTime = 0;
    let duration = 1;
    if (player && typeof player.getCurrentTime === 'function') {
        currentTime = player.getCurrentTime() || 0;
        duration = player.getDuration() || 1;
    }

    const numThemes = thematicData.length;
    let activeIdx = currentTabIndex;

    // Reverting to artificial evenly-spaced progress bar (N spaces for N themes)
    let totalFill = 0;
    
    if (numThemes <= 1) {
        totalFill = duration > 0 ? (currentTime / duration) * 100 : 0;
    } else {
        let blockIndex = 0;
        for (let i = 0; i < numThemes; i++) {
            if (currentTime >= thematicData[i].startTime && (i === numThemes - 1 || currentTime < thematicData[i+1].startTime)) {
                blockIndex = i;
                break;
            }
        }
        
        let blockStart = thematicData[blockIndex].startTime;
        let blockEnd = (blockIndex === numThemes - 1) ? duration : thematicData[blockIndex+1].startTime;
        let blockDuration = blockEnd - blockStart;
        if (blockDuration <= 0) blockDuration = 1;
        
        let fractionInBlock = (currentTime - blockStart) / blockDuration;
        fractionInBlock = Math.max(0, Math.min(1, fractionInBlock));
        
        let spacePerBlock = 100 / numThemes;
        totalFill = (blockIndex * spacePerBlock) + (fractionInBlock * spacePerBlock);
    }
    totalFill = Math.max(0, Math.min(100, totalFill));

    const titleEl = document.getElementById('current-theme-label');
    let currentTab = thematicData[activeIdx];
    if (titleEl && currentTab) titleEl.textContent = (activeIdx + 1) + ". " + currentTab.title;
    
    const dotsContainer = document.getElementById('progress-tracker-dots');
    if (!dotsContainer) return;
    
    if (dotsContainer.childElementCount <= 2 || dotsContainer.getAttribute('data-lesson') !== `${currentLessonData.subject}_${currentLessonData.lessonNum}`) {
        let dotsHtml = '';
        for(let i = 0; i <= numThemes; i++) {
            const isCompleted = currentLessonData && i < numThemes ? !!syllabusCompletion[`${currentLessonData.subject}_${currentLessonData.lessonNum}_${i}`] : false;
            const isCurrent = (i === activeIdx);
            const isPast = (i < activeIdx) || (i === numThemes && activeIdx === numThemes - 1 && totalFill >= 99);
            
            let bgClass = isPast || isCurrent || isCompleted ? 'var(--primary, var(--accent-color))' : 'var(--surface-2)';
            let borderColor = isPast || isCurrent || isCompleted ? 'var(--primary, var(--accent-color))' : 'var(--border-color)';
            
            const scale = isCurrent ? '1.4' : (isCompleted ? '1.1' : '1');
            const pos = numThemes === 0 ? 0 : (i / numThemes) * 100;
            
            let onclickAttr = i < numThemes ? `onclick="switchThemeTab(${i});"` : '';
            
            dotsHtml += `
            <div class="progress-dot-item" style="position: absolute; right: ${pos}%; top: 50%; transform: translate(-50%, -50%); display: flex; flex-direction: column; align-items: center; z-index: 2; transition: all 0.3s; cursor:pointer;" ${onclickAttr}>
                <div style="width: 12px; height: 12px; border-radius: 50%; background: ${bgClass}; border: 2px solid var(--surface); box-shadow: 0 0 0 1px ${borderColor}; transform: scale(${scale}); transition: all 0.3s;"></div>
            </div>`;
        }
        dotsHtml += `
        <div class="progress-line-bg" style="position: absolute; top: 50%; left: 0; right: 0; height: 4px; background: var(--surface-2); transform: translateY(-50%); border-radius: 2px; z-index: 0;"></div>
        <div class="progress-line-fill" id="progress-tracker-fill" style="position: absolute; top: 50%; right: 0; height: 3px; background: var(--primary); transform: translateY(-50%); border-radius: 2px; width: ${totalFill}%; transition: width 0.1s linear; z-index: 1;"></div>
        `;
        dotsContainer.innerHTML = dotsHtml;
        dotsContainer.setAttribute('data-lesson', `${currentLessonData.subject}_${currentLessonData.lessonNum}`);
    } else {
        const fillEl = document.getElementById('progress-tracker-fill');
        const dots = dotsContainer.querySelectorAll('.progress-dot-item');
        dots.forEach((dot, i) => {
            if (i > numThemes) return;
            const isCompleted = currentLessonData && i < numThemes ? !!syllabusCompletion[`${currentLessonData.subject}_${currentLessonData.lessonNum}_${i}`] : false;
            const isCurrent = (i === activeIdx);
            const isPast = (i < activeIdx) || (i === numThemes && activeIdx === numThemes - 1 && totalFill >= 99);
            
            let bgClass = isPast || isCurrent || isCompleted ? 'var(--primary, var(--accent-color))' : 'var(--surface-2)';
            let borderColor = isPast || isCurrent || isCompleted ? 'var(--primary, var(--accent-color))' : 'var(--border-color)';
            
            const scale = isCurrent ? '1.4' : (isCompleted ? '1.1' : '1');
            
            const dotCircle = dot.firstElementChild;
            dotCircle.style.background = bgClass;
            const pos = numThemes === 0 ? 0 : (i / numThemes) * 100;
            dot.style.right = `${pos}%`;
            dotCircle.style.boxShadow = `0 0 0 1px ${borderColor}`;
            dotCircle.style.transform = `scale(${scale})`;
        });
        
        if (fillEl) {
            fillEl.style.width = `${totalFill}%`;
            fillEl.style.background = 'var(--primary, var(--accent-color))';
        }
    }
}

function initUIControls() {
    // Sticky Video Toggle Logic
    const btnSticky = document.getElementById('btn-sticky-toggle');
    const videoWrapper = document.getElementById('video-wrapper');
    const sommaireWrapper = document.getElementById('sommaire-wrapper');
    
    if (btnSticky && videoWrapper && sommaireWrapper) {
        // Toggle pinned state
        btnSticky.addEventListener('click', () => {
            if (videoWrapper.classList.contains('pinned')) {
                // Unpin
                videoWrapper.classList.remove('pinned');
                videoWrapper.style.position = 'relative';
                btnSticky.style.opacity = '0.5';
                btnSticky.title = "Épingler la vidéo";
                sommaireWrapper.style.top = '0px';
            } else {
                // Pin
                videoWrapper.classList.add('pinned');
                videoWrapper.style.position = 'sticky';
                btnSticky.style.opacity = '1';
                btnSticky.title = "Désépingler la vidéo";
                sommaireWrapper.style.top = videoWrapper.offsetHeight + 'px';
            }
        });

        // Keep Sommaire right below the video dynamically
        new ResizeObserver(() => {
            if (videoWrapper.classList.contains('pinned')) {
                sommaireWrapper.style.top = videoWrapper.offsetHeight + 'px';
            }
        }).observe(videoWrapper);
    }

    const globalSidebar = document.getElementById('global-sidebar');
    const globalOverlay = document.getElementById('global-overlay');
    if (globalSidebar && globalOverlay) {
        const closeGlobal = () => {
            globalSidebar.classList.remove('open');
            globalOverlay.classList.remove('show');
        };
        document.getElementById('close-global-sidebar').addEventListener('click', closeGlobal);
        globalOverlay.addEventListener('click', closeGlobal);
    }

    // Sommaire Bottom Sheet
    const sommaireBtn = document.getElementById('open-sommaire-btn');
    const sommaireOverlay = document.getElementById('sommaire-overlay');
    const sommaireSheet = document.getElementById('sommaire-sheet');
    const closeSommaireBtn = document.getElementById('close-sommaire-btn');

    const openSommaire = () => {
        sommaireOverlay.classList.add('show');
        sommaireSheet.classList.add('open');
    };
    const closeSommaire = () => {
        sommaireOverlay.classList.remove('show');
        sommaireSheet.classList.remove('open');
    };

    if(sommaireBtn) sommaireBtn.addEventListener('click', openSommaire);
    if(closeSommaireBtn) closeSommaireBtn.addEventListener('click', closeSommaire);
    if(sommaireOverlay) sommaireOverlay.addEventListener('click', closeSommaire);

    // Text & Theme Controls
    // Initialize UI theme toggle button
    const themeBtn = document.getElementById('btn-theme-toggle');
    if(themeBtn) {
        if(currentTheme === 'dark') themeBtn.textContent = '☀️';
        else if(currentTheme === 'sepia') themeBtn.textContent = '📜';
        else themeBtn.textContent = '🌙';

        themeBtn.addEventListener('click', () => {
            if (currentTheme === 'light') currentTheme = 'sepia';
            else if (currentTheme === 'sepia') currentTheme = 'dark';
            else currentTheme = 'light';
            
            document.documentElement.setAttribute('data-theme', currentTheme);
            localStorage.setItem('readerTheme', currentTheme);
            
            if (currentTheme === 'dark') themeBtn.textContent = '☀️';
            else if (currentTheme === 'sepia') themeBtn.textContent = '📜';
            else themeBtn.textContent = '🌙';
        });
    }
    
    // ZEN MODE LOGIC
    const zenBtn = document.getElementById('btn-zen-toggle');
    if (zenBtn) {
        zenBtn.addEventListener('click', () => {
            document.body.classList.toggle('zen-mode');
            if (document.body.classList.contains('zen-mode')) {
                zenBtn.style.color = 'var(--primary, var(--accent-color))';
                // Block auto-scroll completely in zen mode
                lastUserScrollTime = Date.now() + 999999999;
            } else {
                zenBtn.style.color = '';
                // Re-enable auto-scroll with a 5s grace period
                lastUserScrollTime = Date.now();
            }
        });
    }

    document.getElementById('btn-text-plus').addEventListener('click', () => {
        if(fontSizeBase < 30) {
            fontSizeBase += 2;
            document.documentElement.style.setProperty('--font-size-base', fontSizeBase + 'px');
            localStorage.setItem('readerFontSize', fontSizeBase);
        }
    });

    document.getElementById('btn-text-minus').addEventListener('click', () => {
        if(fontSizeBase > 14) {
            fontSizeBase -= 2;
            document.documentElement.style.setProperty('--font-size-base', fontSizeBase + 'px');
            localStorage.setItem('readerFontSize', fontSizeBase);
        }
    });
}

function buildSyllabusTab(transcripts) {
    const subjectsMap = new Map();
    transcripts.forEach(t => {
        if (!subjectsMap.has(t.subject)) {
            subjectsMap.set(t.subject, {
                label: t.subjectLabel || t.subject,
                lessons: []
            });
        }
        subjectsMap.get(t.subject).lessons.push(t);
    });

    const listContainer = document.getElementById('subjects-list');
    if (!listContainer) return;
    listContainer.innerHTML = '';

    subjectsMap.forEach((data, subjectKey) => {
        data.lessons.sort((a,b) => a.lessonNum - b.lessonNum);
        
        let colorClass = 'subject-default';
        if (subjectKey.includes('sira') || subjectKey.includes('sirah')) colorClass = 'subject-sira';
        else if (subjectKey.includes('fiqh')) colorClass = 'subject-fiqh';
        else if (subjectKey.includes('tahawi') || subjectKey.includes('aqida') || subjectKey.includes('aqeeda')) colorClass = 'subject-tahawi';
        else if (subjectKey.includes('adab') || subjectKey.includes('nahw')) colorClass = 'subject-adab';
        else colorClass = 'subject-sira';
        
        // Calculate completion
        let totalBlocks = 0;
        let completedBlocks = 0;
        data.lessons.forEach(l => {
            if (l.thematic_blocks && l.thematic_blocks.length) {
                l.thematic_blocks.forEach((b, idx) => {
                    totalBlocks++;
                    if (syllabusCompletion[`${l.subject}_${l.lessonNum}_${idx}`]) {
                        completedBlocks++;
                    }
                });
            } else {
                totalBlocks++;
            }
        });
        let progressPercent = totalBlocks > 0 ? Math.round((completedBlocks / totalBlocks) * 100) : 0;
        let deg = (progressPercent / 100) * 360;
        
        if (syllabusMode === 'grid') {
            // IDEA 3: Dashboard Cards
            const card = document.createElement('div');
            card.className = `subject-dashboard-card ${colorClass}`;
            card.innerHTML = `
                <div class="card-info">
                    <h3>${data.label}</h3>
                    <p style="margin-bottom: 4px; font-weight: 600; color: var(--subject-color, var(--primary));">الدروس: ${data.lessons.length}</p>
                    <p style="color: var(--text-2); font-size: 13px;">المحاور المنجزة: ${completedBlocks}/${totalBlocks}</p>
                </div>
                <div class="card-progress">
                    <div class="circular-progress-wrap" style="background: conic-gradient(var(--subject-color, var(--primary, var(--accent-color))) ${deg}deg, var(--surface-2) 0deg);">
                        <span>${progressPercent}%</span>
                    </div>
                </div>
            `;
            
            card.onclick = () => {
                openSubjectDetail(data, colorClass);
            };
            
            listContainer.appendChild(card);
        } else {
            // Mode Programme (List) - Old Accordion
            const subjHeader = document.createElement('div');
            subjHeader.className = 'subject-header';
            subjHeader.innerHTML = `<h3>${data.label}</h3><span class="chev">▼</span>`;
            
            const subjContent = document.createElement('div');
            subjContent.className = 'subject-content subject-list';
            
            data.lessons.forEach(l => {
                let html = `<div style="background:var(--bg); border-radius:12px; margin-bottom:10px; overflow:hidden;">
                    <div style="padding:12px; background:var(--surface); border-bottom:1px solid var(--border-color); font-weight:bold; display:flex; justify-content:space-between; align-items:center;" onclick="openLessonFromList('${l.subject}', ${l.lessonNum})">
                        <span>الدرس ${l.lessonNum} - ${l.title || ''}</span>
                    </div>
                    <div style="padding:10px;">`;
                
                if (l.thematic_blocks && l.thematic_blocks.length) {
                    l.thematic_blocks.forEach((b, idx) => {
                        const compKey = `${l.subject}_${l.lessonNum}_${idx}`;
                        const isComp = !!syllabusCompletion[compKey];
                        html += `<div style="display:flex; justify-content:space-between; align-items:center; padding:8px; background:white; margin-bottom:6px; border-radius:8px; border:1px solid ${isComp ? 'var(--primary)' : 'var(--border-color)'};">
                            <button onclick="toggleChapterCompletion(event, '${l.subject}', ${l.lessonNum}, ${idx})" style="width:24px; height:24px; border-radius:50%; border:2px solid ${isComp ? 'var(--primary)' : '#cbd5e1'}; background:${isComp ? 'var(--primary)' : 'none'}; color:white; font-size:12px; cursor:pointer; display:flex; justify-content:center; align-items:center; flex-shrink:0;">${isComp ? '✓' : ''}</button>
                            <span onclick="openLessonFromList('${l.subject}', ${l.lessonNum}, ${b.start_seconds})" style="flex:1; margin-right:12px; font-size:13px; color:var(--text); cursor:pointer; text-align:right;">${b.title}</span>
                        </div>`;
                    });
                }
                html += `</div></div>`;
                subjContent.innerHTML += html;
            });
            
            subjHeader.onclick = () => {
                subjContent.classList.toggle('active');
                subjHeader.classList.toggle('active');
            };
            
            listContainer.appendChild(subjHeader);
            listContainer.appendChild(subjContent);
        }
    });
}

function openSubjectDetail(data, colorClass) {
    const listContainer = document.getElementById('subjects-list');
    listContainer.innerHTML = '';
    
    const header = document.createElement('div');
    header.className = `subject-detail-header ${colorClass}`;
    header.innerHTML = `
        <button class="back-btn" onclick="buildSyllabusTab(DB)">رجوع ➡️</button>
        <h2 style="color: var(--subject-color, var(--primary, var(--accent-color)));">${data.label}</h2>
    `;
    listContainer.appendChild(header);
    
    const grid = document.createElement('div');
    grid.className = 'smart-grid';
    
    data.lessons.forEach(l => {
        let total = 0, comp = 0;
        if (l.thematic_blocks && l.thematic_blocks.length) {
            l.thematic_blocks.forEach((b, idx) => {
                total++;
                if (syllabusCompletion[`${l.subject}_${l.lessonNum}_${idx}`]) comp++;
            });
        } else {
            total = 1;
            // No easy generic completion for now, assume 0
        }
        let p = total > 0 ? (comp / total) * 100 : 0;
        let deg = (p / 100) * 360;
        
        const btn = document.createElement('button');
        btn.className = `smart-lesson-btn ${colorClass} ${p === 100 ? 'completed' : ''}`;
        
        btn.innerHTML = `
            <div class="ring" style="background: conic-gradient(var(--subject-color, var(--primary, var(--accent-color))) ${deg}deg, var(--surface-2) 0deg);">
                <div class="inner">${l.lessonNum}</div>
            </div>
            <div class="lesson-title-label">الدرس ${l.lessonNum}</div>
        `;
        
        btn.onclick = () => {
            openLessonPreview(l);
        };
        grid.appendChild(btn);
    });
    
    listContainer.appendChild(grid);
}



// YouTube Player Setup
function onYouTubeIframeAPIReady() {
    // API ready
}

function initYouTubePlayer(videoId) {
    if (player && typeof player.loadVideoById === 'function') {
        let start = pendingSeekTime || 0;
        player.loadVideoById({'videoId': videoId, 'startSeconds': start});
        player.playVideo();
        pendingSeekTime = null;
    } else {
        player = new YT.Player('youtube-player', {
            height: '100%',
            width: '100%',
            videoId: videoId,
            playerVars: {
                'playsinline': 1,
                'rel': 0,
                'controls': 0,
                'modestbranding': 1,
                'showinfo': 0,
                'start': pendingSeekTime || 0
            },
            events: {
                'onReady': (e) => {
                    if (pendingSeekTime !== null) {
                        e.target.seekTo(pendingSeekTime, true);
                        e.target.playVideo();
                        pendingSeekTime = null;
                    } else {
                        e.target.playVideo();
                    }
                }
            }
        });
    }
}
function renderLessonHeader(lesson) {
    function extractYoutubeId(url) { if(!url) return null; let match = url.match(/(?:youtu\.be\/|youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=))([^&\n\?#]+)/); return (match && match[1]) || null; }
    const videoId = extractYoutubeId(lesson.video_url || lesson.videoLink || lesson.url);
    const videoWrapper = document.getElementById('video-wrapper');
    if (!videoId) {
        videoWrapper.innerHTML = '<div style="background:#1e293b; color:white; height:100%; display:flex; align-items:center; justify-content:center; flex-direction:column;"><span style="font-size:32px;margin-bottom:8px;">🎥</span><span style="font-size:14px;">الفيديو غير متوفر لهذا الدرس</span></div>';
    } else {
        if (!document.getElementById('youtube-player')) {
            videoWrapper.innerHTML = '<div id="youtube-player"></div>';
        }
        if (window.YT && window.YT.Player) {
            initYouTubePlayer(videoId);
        } else {
            // API non prête
            const interval = setInterval(() => {
                if (window.YT && window.YT.Player) {
                    initYouTubePlayer(videoId);
                    clearInterval(interval);
                }
            }, 500);
        }
    }
}

function prepareThematicData(lesson) {
    thematicData = [];
    if (!lesson.segments || lesson.segments.length === 0) {
        // Fallback if no segments
        thematicData.push({
            title: "Leçon complète",
            startTime: 0,
            endTime: 99999,
            htmlContent: `<div class="reader-paragraph">${lesson.full_text || lesson.summary}</div>`,
            questions: lesson.quiz || []
        });
        return;
    }

    let blocks = lesson.thematic_blocks || [];
    if(blocks.length === 0) {
        blocks = [{ title: "Partie 1", start_seconds: 0, end_seconds: 99999 }];
    }

    let questions = lesson.quiz ? [...lesson.quiz] : [];

    blocks.forEach((block, idx) => {
        // Determine end time securely
        let nextStart = (idx < blocks.length - 1) ? blocks[idx+1].start_seconds : 99999;
        
        // Find segments for this block
        let blockSegments = lesson.segments.filter(s => s.sec >= block.start_seconds && s.sec < nextStart);
        
        let htmlContent = "";

        // Extract tags [POEME:X] shatr 1 *** shatr 2 [/POEME] or just [POEME] shatr 1 *** shatr 2 [/POEME]
        const poetryRegex = /\[POEME(?::(\d+))?\](.*?)\[\/POEME\]/g;

        let parts = [];
        let lastIndex = 0;
        let match;

        let blockText = blockSegments.map(s => `[[TS:${s.sec}]]${s.text}`).join(' ');
        let lastTs = block.start_seconds || 0;
        
        function injectKaraokeSpans(htmlString) {
            let initialTs = lastTs;
            let res = htmlString.replace(/\[\[TS:(\d+(?:\.\d+)?)\]\]/g, (match, sec) => {
                lastTs = sec;
                return `</span><span class="karaoke-segment" data-start="${sec}">`;
            });
            if (res.startsWith('</span>')) {
                res = res.substring(7);
            } else {
                res = `<span class="karaoke-segment" data-start="${initialTs}">` + res;
            }
            res = res + `</span>`;
            // Clean up empty spans
            res = res.replace(/<span[^>]*>\s*<\/span>/g, '');
            return res;
        }

        while ((match = poetryRegex.exec(blockText)) !== null) {
            const prose = blockText.substring(lastIndex, match.index);
            if (prose) parts.push({ type: 'prose', content: prose });
            
            // Inside the tag, we expect *** to separate the two halves, but it's optional in case they write a 1 line quote.
            let innerText = match[2].trim();
            let s1 = innerText, s2 = '';
            if (innerText.includes('***')) {
                let split = innerText.split('***');
                s1 = split[0].trim();
                s2 = split[1].trim();
            }
            
            parts.push({
                type: 'poetry',
                num: match[1] || null,
                shatr1: s1,
                shatr2: s2
            });
            lastIndex = poetryRegex.lastIndex;
        }

        if (lastIndex < blockText.length) {
            parts.push({ type: 'prose', content: blockText.substring(lastIndex) });
        }
        if (parts.length === 0) {
            parts.push({ type: 'prose', content: blockText });
        }

        parts.forEach(part => {
            if (part.type === 'prose') {
                if (!part.content.trim()) return;
                
                // Group sentences into paragraphs of ~4 sentences for better readability
                let sentences = part.content.match(/[^.!?]+[.!?]*/g) || [part.content];
                let pText = "";
                let pCount = 0;
                
                sentences.forEach(sentence => {
                    pText += sentence.trim() + " ";
                    pCount++;
                    if (pCount >= 4) {
                        htmlContent += `<div class="reader-paragraph">${injectKaraokeSpans(formatProse(pText))}</div>`;
                        pText = "";
                        pCount = 0;
                    }
                });
                if (pText.trim() !== "") {
                    htmlContent += `<div class="reader-paragraph">${injectKaraokeSpans(formatProse(pText))}</div>`;
                }
            } else {
                const s1 = injectKaraokeSpans(formatProse(part.shatr1.trim()));
                const s2 = part.shatr2 ? injectKaraokeSpans(formatProse(part.shatr2.trim())) : '';
                const numBadge = part.num ? `<div style="position: absolute; top: -14px; right: 20px; background: var(--gold, #d4af37); color: white; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 0.9rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border: 2px solid white;">بيت ${part.num}</div>` : '';
                
                htmlContent += `
                <div class="poetry-verse-container" style="position: relative; margin: 28px auto 18px auto; max-width: 90%; direction: rtl; text-align: center;">
                    ${numBadge}
                    <div class="poetry-verse" style="background: #fffdf5; border: 1.1px solid #f2e7c9; border-radius: 14px; padding: 16px 16px 12px 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.02); font-family: 'Amiri', serif; line-height: 1.8; display: inline-block; width: 100%; box-sizing: border-box; margin-top: ${part.num ? '8px' : '0'};">
                        <div class="shatr" style="font-size: 16.5px; font-weight: 700; color: #854d0e; margin-bottom: ${s2 ? '6px' : '0'}; text-align: center;">${s1}</div>
                        ${s2 ? `<div class="shatr" style="font-size: 16.5px; font-weight: 700; color: #854d0e; text-align: center;">${s2}</div>` : ''}
                    </div>
                </div>`;
            }
        });

        if (block.explanation && block.explanation.trim() !== "") {
            htmlContent += `
            <div class="reader-chapter-explanation">
                <div class="explanation-header">
                    <span class="explanation-icon">💡</span>
                    <span class="explanation-title">توجيه وفائدة (Note du Professeur)</span>
                </div>
                <div class="explanation-content">${block.explanation}</div>
            </div>`;
        }

        // Find questions for this block
        let blockQuestions = [];
        for (let i = questions.length - 1; i >= 0; i--) {
            let q = questions[i];
            let qTimeSec = extractSecondsFromExplanation(q.explanation);
            
            // Assign question to this block if its time falls within, or if we couldn't parse time and it's the last block
            if ((qTimeSec >= block.start_seconds && qTimeSec < nextStart) || 
                (idx === blocks.length - 1 && qTimeSec === -1)) {
                blockQuestions.push(q);
                questions.splice(i, 1);
            }
        }

        thematicData.push({
            title: block.title,
            level: block.level || 1,
            startTime: block.start_seconds,
            endTime: nextStart,
            htmlContent: htmlContent,
            questions: blockQuestions.reverse()
        });
    });
}

function renderTabs() {
    renderSommaire();
}

function renderSommaire() {
    const listContainer = document.getElementById('sommaire-list');
    if (!listContainer) return;
    listContainer.innerHTML = '';
    
    const sheetTitle = document.querySelector('#sommaire-sheet .bottom-sheet-header h3');
    if (sheetTitle && currentLessonData) {
        sheetTitle.textContent = `محاور الدرس ${currentLessonData.lessonNum}`;
    }

    thematicData.forEach((data, index) => {
        let item = document.createElement('div');
        item.className = 'theme-item';
        if (data.level === 2) item.classList.add('level-2');
        
        item.style.display = 'flex';
        item.style.alignItems = 'center';
        item.style.justifyContent = 'space-between';
        
        const compKey = `${currentLessonData.subject}_${currentLessonData.lessonNum}_${index}`;
        let isComp = !!syllabusCompletion[compKey];
        
        item.innerHTML = `<span style="flex:1; text-align:right;">${index + 1}. ${data.title}</span>`;
        
        let checkBtn = document.createElement('button');
        checkBtn.className = 'sommaire-check-btn ' + (isComp ? 'completed' : '');
        checkBtn.innerHTML = isComp ? '✓' : '';
        checkBtn.onclick = (e) => {
            e.stopPropagation();
            isComp = !isComp;
            syllabusCompletion[compKey] = isComp;
            localStorage.setItem('academy_syllabus_completions', JSON.stringify(syllabusCompletion));
            checkBtn.className = 'sommaire-check-btn ' + (isComp ? 'completed' : '');
            checkBtn.innerHTML = isComp ? '✓' : '';
            
            updateDashboardProgress();
            
            if (currentTabIndex === index) {
                const vBtn = document.querySelector('.validate-chapter-btn');
                if (vBtn) {
                    vBtn.className = isComp ? 'validate-chapter-btn completed' : 'validate-chapter-btn';
                    vBtn.innerHTML = isComp ? '✓ تم إنجاز المحور' : 'تعليم كمقروء';
                }
            }
        };
        
        item.appendChild(checkBtn);
        
        item.onclick = (e) => {
            if (e.target === checkBtn) return;
            switchThemeTab(index, true);
            document.getElementById('sommaire-overlay').classList.remove('show');
            document.getElementById('sommaire-sheet').classList.remove('open');
        };
        listContainer.appendChild(item);
    });
}

function switchThemeTab(index, shouldSeek = true) {
    if (index < 0 || index >= thematicData.length) return;
    
    currentTabIndex = index;
    const data = thematicData[index];

    // Update bottom sheet label and active state
    const labelEl = document.getElementById('current-theme-label');
    if (labelEl) {
        labelEl.textContent = data.title;
    }

    const items = document.querySelectorAll('.theme-item');
    items.forEach((item, i) => {
        if (i === index) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    // Render Content
    const contentArea = document.getElementById('reader-content');
    contentArea.innerHTML = ''; // Clear

    let contentDiv = document.createElement('div');
    contentDiv.className = 'tab-content active';
    
    // Course Badge (Lesson X - Subject)
    if (currentSubject && currentLessonNum) {
        let courseBadge = document.createElement('div');
        courseBadge.style.fontSize = '12px';
        courseBadge.style.color = 'var(--text-3)';
        courseBadge.style.marginBottom = '6px';
        const subjLabel = SUBJECT_LABELS[currentSubject] || currentSubject;
        courseBadge.textContent = `${subjLabel} • الدرس ${currentLessonNum}`;
        contentDiv.appendChild(courseBadge);
    }

    // Title
    let titleEl = document.createElement('h2');
    if (data.level === 2) {
        titleEl.className = 'sub-theme-title';
    } else {
        titleEl.className = 'thematic-title';
    }
    titleEl.textContent = data.title;
    contentDiv.appendChild(titleEl);

    // Text
    let textWrapper = document.createElement('div');
    textWrapper.innerHTML = data.htmlContent;
    contentDiv.appendChild(textWrapper);

    // Questions
    data.questions.forEach(q => {
        contentDiv.appendChild(createQuizElement(q));
    });

    // Finish Thematic Button
    if (currentSubject && currentLessonNum) {
        let finishBtnWrapper = document.createElement('div');
        finishBtnWrapper.style.marginTop = '24px';
        finishBtnWrapper.style.marginBottom = '12px';
        let finishBtn = document.createElement('button');
        finishBtn.className = 'finish-theme-btn';
        finishBtn.innerHTML = '✅ أكملت هذا المحور';
        finishBtn.onclick = (e) => {
            toggleChapterCompletion(e, currentSubject, currentLessonNum, index);
            if (finishBtn.classList.contains('completed')) {
                finishBtn.classList.remove('completed');
                finishBtn.innerHTML = '✅ أكملت هذا المحور';
                finishBtn.style.background = 'var(--surface)';
                finishBtn.style.color = 'var(--text)';
            } else {
                finishBtn.classList.add('completed');
                finishBtn.innerHTML = '✔️ تم إنجاز المحور';
                finishBtn.style.background = 'var(--success, #10b981)';
                finishBtn.style.color = 'white';
            }
        };
        
        // Check if already completed
        const compKey = `${currentSubject}_${currentLessonNum}_${index}`;
        if (syllabusCompletion[compKey]) {
            finishBtn.classList.add('completed');
            finishBtn.innerHTML = '✔️ تم إنجاز المحور';
            finishBtn.style.background = 'var(--success, #10b981)';
            finishBtn.style.color = 'white';
        } else {
            finishBtn.style.background = 'var(--surface)';
            finishBtn.style.color = 'var(--text)';
            finishBtn.style.border = '1px solid var(--border-color)';
        }
        
        finishBtn.style.width = '100%';
        finishBtn.style.padding = '14px';
        finishBtn.style.borderRadius = '12px';
        finishBtn.style.fontWeight = 'bold';
        finishBtn.style.cursor = 'pointer';
        finishBtn.style.transition = 'all 0.3s';
        
        finishBtnWrapper.appendChild(finishBtn);
        contentDiv.appendChild(finishBtnWrapper);
    }

    // Next Button
    if (index < thematicData.length - 1) {
        let nextBtnWrapper = document.createElement('div');
        nextBtnWrapper.className = 'next-tab-wrapper';
        
        let nextBtn = document.createElement('button');
        nextBtn.className = 'next-tab-btn';
        nextBtn.innerHTML = `التالي: ${thematicData[index+1].title} ⬅️`;
        nextBtn.onclick = () => switchThemeTab(index + 1, true);
        
        nextBtnWrapper.appendChild(nextBtn);
        contentDiv.appendChild(nextBtnWrapper);
    }


    // Mark completed button
    let markBtnWrapper = document.createElement('div');
    markBtnWrapper.style.textAlign = 'center';
    markBtnWrapper.style.marginTop = '24px';
    markBtnWrapper.style.marginBottom = '24px';
    
    let isCompleted = false;
    if (currentLessonData) {
        const compKey = `${currentLessonData.subject}_${currentLessonData.lessonNum}_${index}`;
        isCompleted = !!syllabusCompletion[compKey];
    }
    
    let markBtn = document.createElement('button');
    markBtn.style.padding = '12px 24px';
    markBtn.style.borderRadius = '12px';
    markBtn.style.border = 'none';
    markBtn.style.fontSize = '14px';
    markBtn.style.fontWeight = 'bold';
    markBtn.style.cursor = 'pointer';
    markBtn.style.fontFamily = 'inherit';
    
    if (isCompleted) {
        markBtn.style.background = '#e2e8f0';
        markBtn.style.color = '#64748b';
        markBtn.textContent = '✓ مكتمل';
        markBtn.disabled = true;
    } else {
        markBtn.style.background = 'var(--primary)';
        markBtn.style.color = 'white';
        markBtn.textContent = '✅ إنهاء هذا المحور';
        markBtn.onclick = () => {
            if (currentLessonData) {
                toggleChapterCompletion(null, currentLessonData.subject, currentLessonData.lessonNum, index);
                markBtn.style.background = '#e2e8f0';
                markBtn.style.color = '#64748b';
                markBtn.textContent = '✓ مكتمل';
                markBtn.disabled = true;
                
                // Show completion toast or visual effect
                let tst = document.createElement('div');
                tst.textContent = 'تم تسجيل التقدم!';
                tst.style.position = 'fixed';
                tst.style.bottom = '80px';
                tst.style.left = '50%';
                tst.style.transform = 'translateX(-50%)';
                tst.style.background = '#10b981';
                tst.style.color = 'white';
                tst.style.padding = '8px 16px';
                tst.style.borderRadius = '20px';
                tst.style.zIndex = '9999';
                document.body.appendChild(tst);
                setTimeout(() => tst.remove(), 2000);
            }
        };
    }
    
    markBtnWrapper.appendChild(markBtn);
    contentDiv.appendChild(markBtnWrapper);

    contentArea.appendChild(contentDiv);

    // Video Seek
    if (shouldSeek && player && player.seekTo) {
        isSeekingTab = true;
        player.seekTo(data.startTime, true);
        player.playVideo();
        setTimeout(() => { isSeekingTab = false; }, 1500);
        // Scroll to video
        window.scrollTo({top: 0, behavior: 'smooth'});
    } else if (shouldSeek) {
        window.scrollTo({top: 0, behavior: 'smooth'});
    }
}

function createQuizElement(questionData) {
    const container = document.createElement('div');
    container.className = 'inline-quiz-container';

    let optionsHtml = '';
    let opts = Array.isArray(questionData.options) ? questionData.options : 
               (typeof questionData.options === 'string' ? questionData.options.split(/[.-]/).map(s=>s.trim()).filter(s=>s) : []);
    
    opts.forEach((opt, optIdx) => {
        optionsHtml += `<button class="quiz-option" data-idx="${optIdx}">${opt}</button>`;
    });

    let tempDiv = document.createElement('div');
    tempDiv.innerHTML = questionData.explanation || '';
    let cleanExplanation = tempDiv.textContent || tempDiv.innerText || '';
    // Parse explanation like Telegram
    let text = cleanExplanation.trim();
    let sourceText = "";
    if (text.includes("📍")) {
        let parts = text.split("📍");
        text = parts[0].trim();
        sourceText = "📍 " + parts[1].trim();
    } else if (text.includes("المصدر")) {
        let parts = text.split("المصدر");
        text = parts[0].trim();
        sourceText = "📍 المصدر " + parts[1].trim();
    }

    let profNote = "";
    const profPatterns = ["توجيه وفائدة :", "ملاحظة الأستاذ :", "فائدة :"];
    for (let p of profPatterns) {
        if (text.includes(p)) {
            let parts = text.split(p);
            text = parts[0].trim();
            profNote = parts[1].trim();
            break;
        }
    }

    let parsedHtml = '';
    if (text) {
        parsedHtml += `<div class="exp-main" style="margin-bottom:12px; font-size:14px;"><strong>التوضيح:</strong><br>${text}</div>`;
    }
    if (profNote) {
        parsedHtml += `<div class="exp-prof" style="margin-bottom:12px; background:var(--surface-2); padding:12px; border-radius:8px; border-right:3px solid var(--primary); font-size:13.5px;"><span style="font-size:16px;">💡</span> <strong>توجيه وفائدة:</strong><br>${profNote}</div>`;
    }
    if (sourceText) {
        parsedHtml += `<div class="exp-source" style="font-size:12px; color:var(--text-3); margin-top:8px;">${sourceText}</div>`;
    }

    container.innerHTML = `
        <div class="quiz-header">سؤال تفاعلي</div>
        <div class="quiz-question">${questionData.question}</div>
        <div class="quiz-options">
            ${optionsHtml}
        </div>
        <div class="quiz-explanation">
            ${parsedHtml}
        </div>
    `;

    const buttons = container.querySelectorAll('.quiz-option');
    const expDiv = container.querySelector('.quiz-explanation');

    buttons.forEach(btn => {
        btn.addEventListener('click', () => {
            if (container.classList.contains('answered')) return;
            container.classList.add('answered');

            let correctIdx = questionData.answerIndex; 
            if (correctIdx === undefined && questionData.correct) {
                correctIdx = questionData.correct - 1;
            }

            buttons.forEach(b => {
                const bIdx = parseInt(b.getAttribute('data-idx'));
                if (bIdx === correctIdx) {
                    b.classList.add('correct');
                } else if (bIdx === parseInt(btn.getAttribute('data-idx'))) {
                    b.classList.add('wrong');
                }
            });

            expDiv.classList.add('show');
        });
    });

    return container;
}

function extractVideoID(url) {
    let match = url.match(/[?&]v=([^&]+)/);
    if (match) return match[1];
    match = url.match(/youtu\.be\/([^?]+)/);
    if (match) return match[1];
    return null;
}

function extractSecondsFromExplanation(html) {
    if (!html) return -1;
    let match = html.match(/&t=(\d+)s/);
    if (match) {
        return parseInt(match[1]);
    }
    return -1;
}

// ── RICH TEXT PARSERS ──
function formatProse(text) {
    if (!text) return '';
    let result = text;
    // Quranic verses inside {}
    result = result.replace(/\{([^{}]+)\}/g, (match, verse) => {
        const cleanVerse = verse.trim();
        return `<span class="quran-verse">﴿ ${cleanVerse} ﴾</span>`;
    });
    result = highlightGlossary(result);
    return result;
}

function highlightGlossary(text) {
    let result = text;
    
    // Order matters: longer/more specific patterns first to avoid partial matches
    const GLOSSARY_MATCHERS = [
        // ── نساء (rose/pink) ──
        { term: "خديجة بنت خويلد",         pattern: "خديج[ةه] بنت خويلد|خديج[ةه] رضي الله عنها|خديج[ةه]" },
        { term: "عائشة بنت أبي بكر",        pattern: "عائش[ةه] بنت [أا]بي بكر|عائش[ةه] رضي الله عنها|عائش[ةه]|السيدة عائش[ةه]" },
        { term: "فاطمة الزهراء",            pattern: "فاطم[ةه] الزهراء|فاطم[ةه] بنت محمد|فاطم[ةه]" },
        { term: "زينب بنت جحش",            pattern: "زينب بنت جحش|السيدة زينب" },
        { term: "زينب بنت محمد",            pattern: "زينب بنت محمد|زينب بنت النبي|زينب" },
        { term: "أم سلمة",                 pattern: "[أا]م سلم[ةه]|هند بنت [أا]بي [أا]مي[ةه]" },
        { term: "صفية بنت حيي",            pattern: "صفي[ةه] بنت حيي|صفي[ةه]" },
        { term: "حفصة بنت عمر",            pattern: "حفص[ةه] بنت عمر|حفص[ةه]" },
        { term: "رقية بنت محمد",            pattern: "رقي[ةه] بنت محمد|رقي[ةه]" },
        { term: "أم كلثوم بنت محمد",        pattern: "[أا]م كلثوم بنت محمد|[أا]م كلثوم" },
        { term: "هند بنت عتبة",             pattern: "هند بنت عتب[ةه]|هند" },
        { term: "أسماء بنت أبي بكر",        pattern: "[أا]سماء بنت [أا]بي بكر|[أا]سماء|ذات النطاقين" },
        { term: "ماريا القبطية",            pattern: "ماري[ةا] القبطي[ةه]|ماري[ةا]" },
        // ── رجال (bleu) ──
        { term: "أبو بكر الصديق",           pattern: "[أا]بو بكر الصديق|الصديق|[أا]بو بكر" },
        { term: "عمر بن الخطاب",            pattern: "عمر بن الخطاب|الفاروق عمر|عمر بن الخطاب|عمر" },
        { term: "عثمان بن عفان",            pattern: "عثمان بن عفان|ذو النورين|عثمان" },
        { term: "علي بن أبي طالب",          pattern: "علي بن [أا]بي طالب|علي رضي الله عنه|علي" },
        { term: "خالد بن الوليد",           pattern: "خالد بن الوليد|سيف الله المسلول|خالد" },
        { term: "بلال بن رباح",             pattern: "بلال بن رباح|بلال" },
        { term: "أبو هريرة",               pattern: "[أا]بو هرير[ةه]" },
        { term: "عبد الله بن مسعود",        pattern: "عبد الله بن مسعود|ابن مسعود" },
        { term: "حمزة بن عبد المطلب",       pattern: "حمز[ةه] بن عبد المطلب|حمز[ةه]" },
        { term: "مصعب بن عمير",            pattern: "مصعب بن عمير|مصعب" },
        { term: "عمرو بن العاص",            pattern: "عمرو بن العاص|عمرو" },
        { term: "طلحة بن عبيد الله",        pattern: "طلح[ةه] بن عبيد الله|طلح[ةه]" },
        { term: "الزبير بن العوام",          pattern: "الزبير بن العوام|الزبير" },
        { term: "كعب بن الأشرف",           pattern: "كعب بن الأشرف|كعب" },
        { term: "سعد بن عبادة",            pattern: "سعد بن عباد[ةه]" },
        { term: "زيد بن حارثة",            pattern: "زيد بن حارث[ةه]|زيد" },
        { term: "سلمان الفارسي",           pattern: "سلمان الفارسي|سلمان" },
        { term: "سعد بن معاذ",             pattern: "سعد بن معاذ|سعد" },
        { term: "حيي بن أخطب",             pattern: "حيي بن [أا]خطب|حيي" },
        { term: "نعيم بن مسعود",           pattern: "نعيم بن مسعود|نعيم" },
        { term: "عبد الله بن سلام",         pattern: "عبد الله بن سلام|ابن سلام" },
        { term: "عبد الله بن أبي بن سلول",  pattern: "عبد الله بن [أا]بي بن سلول|ابن سلول|عبد الله بن [أا]بي" },
        { term: "صفوان بن المعطل",          pattern: "صفوان بن المعطل|صفوان" },
        { term: "وحشي بن حرب",             pattern: "وحشي بن حرب|وحشي" },
        { term: "أبو جهل",                 pattern: "[أا]بو جهل|فرعون [أا]مة" },
        { term: "أبو لهب",                 pattern: "[أا]بو لهب" },
        { term: "أبو سفيان",               pattern: "[أا]بو سفيان|[أا]بي سفيان|[أا]با سفيان" },
        { term: "أمية بن خلف",             pattern: "[أا]مي[ةه] بن خلف" },
        { term: "الحسن بن علي",            pattern: "الحسن بن علي|السبط الحسن|الحسن" },
        { term: "الحسين بن علي",           pattern: "الحسين بن علي|السبط الحسين|الحسين" },
        { term: "النجاشي",                 pattern: "النجاشي|نجاشي الحبش[ةه]" },
        // ── قبائل وأحداث ──
        { term: "بنو قريظة",               pattern: "بنو قريظ[ةه]|بني قريظ[ةه]" },
        { term: "بنو قينقاع",              pattern: "بنو قينقاع|بني قينقاع" },
        { term: "بنو النضير",              pattern: "بنو النضير|بني النضير" },
        { term: "غزوة الأحزاب",            pattern: "غزو[ةه] الأحزاب|الأحزاب" },
        { term: "بدر الموعد",              pattern: "بدر الموعد" },
        { term: "ذات الرقاع",              pattern: "ذات الرقاع" },
        { term: "دومة الجندل",             pattern: "دوم[ةه] الجندل" },
        { term: "غزوة بني المصطلق",        pattern: "غزو[ةه] بني المصطلق|بني المصطلق|المريسيع" }
    ];
    
    GLOSSARY_MATCHERS.forEach((item, idx) => {
        let isFemale = idx < 13;
        let cssClass = isFemale ? 'glossary-female' : 'glossary-male';
        // Removed lookbehind for iOS/Safari compatibility. Captured the preceding char in $1, the pattern in $2.
        try {
            const regex = new RegExp(`(^|[^أ-ي])(${item.pattern})(?=$|[^أ-ي])(?![^<>]*>)`, 'g');
            result = result.replace(regex, `$1<span class="glossary-badge ${cssClass}" onclick="showGlossaryPopup(event, '${item.term}')">$2</span>`);
        } catch (e) {
            console.error("Regex error on term", item.term, e);
        }
    });
    return result;
}

// ── GLOSSARY & MINDMAP POPUPS ──
const GLOSSARY = {
    // رجال الصحابة والمعاصرون
    "زيد بن حارثة": { def: "صحابي جليل، كان يدعى زيد بن محمد بالتبني قبل تحريمه، وهو الصحابي الوحيد الذي ذُكر اسمه صراحة في القرآن الكريم.", type: "person", gender: "male" },
    "أبو سفيان": { def: "زعيم مشركي قريش وقائد قوافلهم وجيوشهم في غزو أحد والأحزاب قبل إسلامه يوم فتح مكة.", type: "person", gender: "male" },
    "سلمان الفارسي": { def: "صحابي جليل من بلاد فارس، وهو صاحب فكرة حفر الخندق لحماية المدينة في غزوة الأحزاب.", type: "person", gender: "male" },
    "سعد بن معاذ": { def: "سيد الأوس وصحابي جليل اهتز لوفاته عرش الرحمن، وهو الذي حكم في بني قريظة بحكم الله ورسوله.", type: "person", gender: "male" },
    "حيي بن أخطب": { def: "زعيم بني النضير وأحد ألد أعداء الإسلام، حرّض الأحزاب ضد المدينة وغدر بالعهد ثم قُتل مع بني قريظة.", type: "person", gender: "male" },
    "نعيم بن مسعود": { def: "صحابي جليل أسلم سرّاً يوم الأحزاب ونجح بدهائه في خذل المشركين وإيقاع الخلاف بين قريش وبني قريظة.", type: "person", gender: "male" },
    "عبد الله بن أبي بن سلول": { def: "رأس النفاق في المدينة، استغل غزوة بني المصطلق لإثارة الفتن وتولى كِبر حادثة الإفك طعناً في أم المؤمنين عائشة.", type: "person", gender: "male" },
    "صفوان بن المعطل": { def: "صحابي جليل من خيرة الصحابة، اتهمه المنافقون ظلماً وزوراً في حادثة الإفك وبرأه الله عز وجل بآيات سورة النور.", type: "person", gender: "male" },
    "أمية بن خلف": { def: "أحد أئمة الكفر بمكة، كان يعذب بلال بن رباح، وقُتل في معركة بدر الكبرى على يد المسلمين.", type: "person", gender: "male" },
    "حمزة بن عبد المطلب": { def: "أسد الله ورسوله وعم النبي ﷺ، استشهد في غزوة أحد على يد وحشي ومثل المشركون بجسده الشريف.", type: "person", gender: "male" },
    "مصعب بن عمير": { def: "أول سفير في الإسلام، حمل راية المسلمين في غزو أُحد واستشهد مقبلاً غير مدبر رضي الله عنه.", type: "person", gender: "male" },
    "عبد الله بن سلام": { def: "حبر من أحبار يهود بني قينقاع بالمدينة، أسلم مع بداية هجرة النبي ﷺ وشهد بصدق نبوته وهو من كبار الصحابة.", type: "person", gender: "male" },
    "أبو بكر الصديق": { def: "أول الخلفاء الراشدين وأقرب الصحابة إلى النبي ﷺ، رفيقه في الهجرة وصاحب الغار، وأول من صدّق بالإسراء والمعراج.", type: "person", gender: "male" },
    "عمر بن الخطاب": { def: "ثاني الخلفاء الراشدين، الفاروق الذي أعز الله به الإسلام، عُرف بشدته في الحق وعدله الذي ضرب به الأمثال في كل مكان.", type: "person", gender: "male" },
    "عثمان بن عفان": { def: "ثالث الخلفاء الراشدين وذو النورين، زوج رقية ثم أم كلثوم بنتَي النبي ﷺ، جهّز جيش العسرة من ماله وجمع القرآن.", type: "person", gender: "male" },
    "علي بن أبي طالب": { def: "رابع الخلفاء الراشدين وابن عم النبي ﷺ وزوج فاطمة الزهراء، أسلم وهو صغير وكان من أشجع فرسان الإسلام.", type: "person", gender: "male" },
    "خالد بن الوليد": { def: "سيف الله المسلول، أسلم قُبيل فتح مكة وقاد معارك حاسمة في اليمامة والشام والعراق ولم يُهزم في حرب قط.", type: "person", gender: "male" },
    "بلال بن رباح": { def: "أول مؤذن في الإسلام، عبد حبشي كان يعذبه أمية بن خلف بالرمضاء ليترك دينه، حتى اشتراه أبو بكر وأعتقه.", type: "person", gender: "male" },
    "أبو هريرة": { def: "أكثر الصحابة رواية للحديث النبوي، أسلم عام خيبر وظل ملازماً للنبي ﷺ حتى وفاته وروى أكثر من خمسة آلاف حديث.", type: "person", gender: "male" },
    "عبد الله بن مسعود": { def: "صحابي من أوائل المسلمين، خادم النبي ﷺ وأعلم الصحابة بالقرآن الكريم والتفسير، قال عنه النبي ﷺ: من سره أن يقرأ القرآن غضاً فليقرأ على قراءة ابن أم عبد.", type: "person", gender: "male" },
    "وحشي بن حرب": { def: "الحبشي الذي قتل حمزة بن عبد المطلب بأمر هند يوم أحد، ثم أسلم بعد فتح مكة وقتل مسيلمة الكذاب في حروب الردة.", type: "person", gender: "male" },
    "عمرو بن العاص": { def: "صحابي وقائد عسكري بارع، أسلم قُبيل فتح مكة وفتح مصر في عهد عمر بن الخطاب رضي الله عنه.", type: "person", gender: "male" },
    "الحسن بن علي": { def: "سبط النبي ﷺ وريحانته، ابن علي وفاطمة، قال فيه النبي: الحسن والحسين سيدا شباب أهل الجنة.", type: "person", gender: "male" },
    "الحسين بن علي": { def: "سبط النبي ﷺ وريحانته، أُولد في السنة الرابعة للهجرة، وقال فيه النبي: الحسين مني وأنا من الحسين.", type: "person", gender: "male" },
    "النجاشي": { def: "ملك الحبشة الذي أجار المهاجرين الأولين وأنصفهم، أسلم في قلبه وصلى عليه النبي ﷺ صلاة الغائب لما مات.", type: "person", gender: "male" },
    "أبو جهل": { def: "فرعون هذه الأمة واسمه عمرو بن هشام، من أشد أعداء الإسلام وأكثرهم إيذاءً للمسلمين، قُتل في غزوة بدر الكبرى.", type: "person", gender: "male" },
    "أبو لهب": { def: "عم النبي ﷺ وعدوه اللدود، نزلت فيه وزوجته سورة المسد، لعنه الله لشدة عدائه للإسلام ورسوله.", type: "person", gender: "male" },
    "سعد بن عبادة": { def: "سيد الخزرج وزعيم الأنصار، كان ينافس سعد بن معاذ على إمارة الأنصار وشهد غزوات كثيرة مع النبي ﷺ.", type: "person", gender: "male" },
    "طلحة بن عبيد الله": { def: "أحد العشرة المبشرين بالجنة، وقف يوم أُحد درعاً للنبي ﷺ وأصيبت يده حين أنقذه، فقال النبي: أوجب طلحة.", type: "person", gender: "male" },
    "الزبير بن العوام": { def: "أحد العشرة المبشرين بالجنة وحواري رسول الله ﷺ وابن عمته صفية، كان فارساً شجاعاً لا يُبارى في ميادين القتال.", type: "person", gender: "male" },
    "كعب بن الأشرف": { def: "زعيم يهودي من بني النضير، حرّض المشركين ضد المسلمين وهجا النبي ﷺ بشعره، فأذن النبي بقتله فنفذ الأمر محمد بن مسلمة.", type: "person", gender: "male" },
    // نساء الصحابة وأمهات المؤمنين
    "زينب بنت جحش": { def: "أم المؤمنين، زوجة النبي ﷺ، تزوجها بأمر من الله لإبطال حكم التبني عملياً، وكانت تفخر بأن الله زوّجها من فوق سبع سماوات.", type: "person", gender: "female" },
    "عائشة بنت أبي بكر": { def: "أم المؤمنين وحبيبة رسول الله ﷺ، أكثر الصحابة رواية للحديث بعد أبي هريرة، برأها الله في القرآن من حادثة الإفك.", type: "person", gender: "female" },
    "خديجة بنت خويلد": { def: "أول أمهات المؤمنين وأول من آمن بالنبي ﷺ، وهبت مالها ونفسها للدعوة، وبشّرها النبي ﷺ ببيت في الجنة من قصب لا صخب فيه ولا نصب.", type: "person", gender: "female" },
    "فاطمة الزهراء": { def: "سيدة نساء العالمين وابنة النبي ﷺ وزوجة علي بن أبي طالب، قال عنها النبي: فاطمة بضعة مني فمن آذاها فقد آذاني.", type: "person", gender: "female" },
    "أم سلمة": { def: "أم المؤمنين هند بنت أبي أمية، هاجرت إلى الحبشة ثم المدينة، اشتُهرت بحكمتها ونصحها للنبي ﷺ يوم الحديبية.", type: "person", gender: "female" },
    "صفية بنت حيي": { def: "أم المؤمنين، بنت زعيم بني النضير حيي بن أخطب، تزوجها النبي ﷺ بعد غزوة خيبر، وكانت تدافع عن شرف النبي ﷺ بلسانها.", type: "person", gender: "female" },
    "حفصة بنت عمر": { def: "أم المؤمنين وابنة عمر بن الخطاب، اشتهرت بالصيام والقيام، وعندها حُفظت المصحف الأول الذي جمعه أبو بكر رضي الله عنه.", type: "person", gender: "female" },
    "رقية بنت محمد": { def: "بنت النبي ﷺ وزوجة عثمان بن عفان، هاجرت معه إلى الحبشة ثم المدينة، وتوفيت يوم غزوة بدر وهو في المعركة.", type: "person", gender: "female" },
    "أم كلثوم بنت محمد": { def: "بنت النبي ﷺ وزوجة عثمان بن عفان بعد وفاة أختها رقية، ولهذا سُمي عثمان بذي النورين.", type: "person", gender: "female" },
    "زينب بنت محمد": { def: "أكبر بنات النبي ﷺ، تزوجت أبا العاص بن الربيع قبل الإسلام، وهاجرت إلى المدينة بعد غزوة بدر وتوفيت في السنة الثامنة.", type: "person", gender: "female" },
    "هند بنت عتبة": { def: "زوجة أبي سفيان وأم معاوية، أمرت بقتل حمزة يوم أُحد وشقت صدره، أسلمت يوم فتح مكة وحسن إسلامها.", type: "person", gender: "female" },
    "أسماء بنت أبي بكر": { def: "ذات النطاقين وأخت عائشة، أعانت أباها وزوج أختها النبي ﷺ في الهجرة بحمل الزاد، وأنجبت أول مولود في الإسلام بالمدينة.", type: "person", gender: "female" },
    "ماريا القبطية": { def: "أم إبراهيم ابن النبي ﷺ، أهداها المقوقس ملك مصر إلى النبي ﷺ، وتوفي ابنها إبراهيم صغيراً فبكى النبي وقال: إن العين تدمع والقلب يحزن.", type: "person", gender: "female" },
    // الأحداث والغزوات
    "بنو قينقاع": { def: "أول قبائل اليهود بالمدينة نقضاً للعهد مع النبي ﷺ بعد غزوة بدر، فتم حصارهم وإجلاؤهم عن المدينة.", type: "tribe" },
    "بنو قريظة": { def: "إحدى قبائل اليهود بالمدينة الذين تحالفوا مع الأحزاب ونقضوا عهدهم مع المسلمين، فحُوصروا وحكم فيهم سعد بن معاذ.", type: "tribe" },
    "بنو النضير": { def: "قبيلة يهودية بالمدينة تآمرت على قتل النبي ﷺ بلقاء صخرة، فحاصرهم وأجلاهم إلى خيبر والشام.", type: "tribe" },
    "بدر الموعد": { def: "غزوة بدر الصغرى أو الثانية، خرج فيها المسلمون للقاء قريش في السنة الرابعة للهجرة وتراجع المشركون رعباً.", type: "event" },
    "زكاة الفطر": { def: "صدقة تجب على كل مسلم قبل صلاة عيد الفطر طهرة للصائم وطعمة للمساكين، فرضت في شعبان من السنة الثانية للهجرة.", type: "concept" },
    "التبني": { def: "ادعاء بنوة طفل لغير أبيه الحقيقي، وقد أبطله الإسلام عملياً ونظرياً لصيانة الأنساب من الضياع.", type: "concept" },
    "ذات الرقاع": { def: "غزوة سُميت بذلك لأن الصحابة رضي الله عنهم لفوا الخرق على أقدامهم من شدة الحر والمشي، ونزلت فيها رخص كصلاة الخوف والتيمم.", type: "event" },
    "غزوة الأحزاب": { def: "غزوة الخندق (السنة الخامسة للهجرة) حيث تجمعت قبائل المشركين واليهود لمحاصرة المسلمين، فهزمهم الله بالريح والجنود.", type: "event" },
    "غزوة بني المصطلق": { def: "غزوة المريسيع (السنة السادسة للهجرة) هزم فيها المسلمون بني المصطلق وحدثت فيها حادثة الإفك المفترية.", type: "event" },
    "دومة الجندل": { def: "غزوة قادها النبي ﷺ في السنة الخامسة للهجرة لتأمين الحدود الشمالية وتفريق قبائل هناك كانت تتهيأ لغزو المدينة.", type: "event" }
};

function showGlossaryPopup(event, term) {
    if (event) event.stopPropagation();
    const item = GLOSSARY[term];
    if (!item) return;
    
    let icon = '📌';
    let color = '#4f46e5';
    let termColor = 'var(--primary)';
    
    if (item.type === 'person') {
        if (item.gender === 'female') {
            icon = '♀️'; color = '#ec4899'; termColor = '#be185d';
        } else {
            icon = '♂️'; color = '#3b82f6'; termColor = '#1d4ed8';
        }
    } else if (item.type === 'event') {
        icon = '⚔️'; color = '#10b981'; termColor = '#047857';
    } else if (item.type === 'tribe') {
        icon = '🏹'; color = '#7c3aed'; termColor = '#6d28d9';
    } else if (item.type === 'concept') {
        icon = '💡'; color = '#f59e0b'; termColor = '#b45309';
    }
    
    const termEl = document.getElementById('glossary-popup-term');
    if(termEl) termEl.innerHTML = `<span style="margin-left: 6px; font-size: 15px;">${icon}</span><span style="color:${termColor}; font-weight:800;">${term}</span>`;
    
    const defEl = document.getElementById('glossary-popup-def');
    if(defEl) defEl.textContent = item.def;
    
    const popup = document.getElementById('glossary-popup');
    if(popup) {
        popup.style.borderRightColor = color;
        popup.style.display = 'block';
    }
}

function closeGlossaryPopup() {
    const popup = document.getElementById('glossary-popup');
    if (popup) popup.style.display = 'none';
}

document.addEventListener('click', () => { closeGlossaryPopup(); });

// ── MIND MAP POPUP ──
function openMindMap() {
    const mindmapOverlay = document.getElementById('mindmap-overlay');
    const mindmapImg = document.getElementById('mindmap-image');
    if (!mindmapOverlay || !mindmapImg) return;
    
    // Lazy loading
    if (!mindmapImg.src || mindmapImg.src.endsWith('placeholder.png')) {
        // e.g. /assets/mindmaps/sira_14.png (We just use a demo or derived from URL)
        mindmapImg.src = `assets/mindmaps/sira_${urlLesson}.png`; // Adapt according to real paths
    }
    mindmapOverlay.style.display = 'flex';
}

function closeMindMap() {
    const mindmapOverlay = document.getElementById('mindmap-overlay');
    if (mindmapOverlay) mindmapOverlay.style.display = 'none';
}

// ─── SPA TAB LOGIC ───
function switchTab(name, btn) {

    
    document.querySelectorAll('.tab-panel').forEach(p=>p.classList.remove('active'));
    document.querySelectorAll('.bottom-nav .nav-btn').forEach(b=>b.classList.remove('active'));
    
    const panel = document.getElementById('tab-'+name);
    if(panel) panel.classList.add('active');
    
    if (btn) {
        btn.classList.add('active');
    } else {
        const targetBtn = document.querySelector(`.nav-btn[onclick*="switchTab('${name}'"]`);
        if(targetBtn) targetBtn.classList.add('active');
    }
    
    if(name === 'home') {
        renderHomeProgress();
    }
    
    if(name === 'search') {
        setTimeout(() => document.getElementById('search-input').focus(), 100);
    }
}

// ─── PROGRESS LOGIC ───
function markLessonOpened(subject, lessonNum) {
    try {
        let opened = JSON.parse(localStorage.getItem('openedLessons') || '{}');
        const key = `${subject}_${lessonNum}`;
        opened[key] = true;
        localStorage.setItem('openedLessons', JSON.stringify(opened));
        
        // Also track recent
        let recent = JSON.parse(localStorage.getItem('recentLessons') || '[]');
        recent = recent.filter(r => r.key !== key);
        recent.unshift({ key, subject, lessonNum, time: Date.now() });
        if(recent.length > 5) recent.pop();
        localStorage.setItem('recentLessons', JSON.stringify(recent));
    } catch(e){}
}

function renderHomeProgress() {
    let opened = {};
    let recent = [];
    try {
        opened = JSON.parse(localStorage.getItem('openedLessons') || '{}');
        recent = JSON.parse(localStorage.getItem('recentLessons') || '[]');
    } catch(e){}

    const totalLessons = DB.length;
    const openedCount = Object.keys(opened).length;
    let percentage = 0;
    if (totalLessons > 0) {
        percentage = Math.round((openedCount / totalLessons) * 100);
    }

    const circle = document.getElementById('progress-circle');
    const text = document.getElementById('progress-text');
    const subtitle = document.getElementById('progress-subtitle');
    
    if (circle) circle.style.strokeDasharray = `${percentage}, 100`;
    if (text) text.textContent = `${percentage}%`;
    if (subtitle) subtitle.textContent = `${openedCount} / ${totalLessons} درس`;

    const recentContainer = document.getElementById('recent-lessons-container');
    if (recentContainer) {
        if (recent.length === 0) {
            recentContainer.innerHTML = '<p style="color:var(--text-3); font-size:14px;">لم تفتح أي درس بعد.</p>';
        } else {
            recentContainer.innerHTML = '';
            recent.forEach(r => {
                const lessonObj = DB.find(l => l.subject === r.subject && l.lessonNum == r.lessonNum);
                if (lessonObj) {
                    const btn = document.createElement('div');
                    btn.style.padding = '12px';
                    btn.style.background = 'var(--surface)';
                    btn.style.border = '1px solid var(--border-color)';
                    btn.style.borderRadius = '12px';
                    btn.style.marginBottom = '8px';
                    btn.style.cursor = 'pointer';
                    btn.style.display = 'flex';
                    btn.style.alignItems = 'center';
                    btn.style.gap = '12px';
                    btn.innerHTML = `<span style="font-size:20px;">📘</span> <div><h4 style="margin:0; font-size:15px;">${lessonObj.title}</h4><span style="font-size:12px; color:var(--text-2);">${lessonObj.subjectLabel}</span></div>`;
                    btn.onclick = () => {
                        openLesson(lessonObj);
                        switchTab('reader');
                    };
                    recentContainer.appendChild(btn);
                }
            });
        }
    }
}

// ─── SEARCH LOGIC ───
function buildIndex() {
    const stop = new Set(["في","من","على","إلى","عن","هذا","هذه","التي","الذي","أن","إن","لا","ما","مع","كان","كانت","ثم","أو","أم","كل","يوم","بعد","قبل","عند","هو","هي","وقد","قد","فقد","وهو","وهي","وكان"]);
    const seen = new Set();
    DB.forEach(item => {
        ((item.full_text||'')+' '+(item.blocks_search_text||'')).split(/[\s،.؟!():؛]+/).forEach(w=>{
            const c=w.trim();
            if(c.length>=3&&c.length<=10&&!stop.has(c)&&!seen.has(c)){
                seen.add(c);
                wordIndex.push({text:c,subjectLabel:item.subjectLabel,cls:'badge-'+item.subject});
            }
        });
    });
}

function strip(html){return new DOMParser().parseFromString(html,'text/html').body.textContent||'';}
function esc(str){return str.replace(/[.*+?^${}()|[\]\\]/g,'\$&');}
function hl(t,q){const reg=new RegExp(`(${esc(q)})`,'gi');return t.replace(reg,'<mark>$1</mark>');}

function getQ(q){
    const words = q.split(/\s+/).filter(w => w.length > 0);
    return words;
}

const si = document.getElementById('search-input');
const cb = document.getElementById('clear-btn');
const ac = document.getElementById('autocomplete');

if (si) {
    si.addEventListener('input', () => {
        const q=si.value.trim();
        cb.style.display=q?'block':'none';
        if(q.length>=2){showAc(q);doSearch(q);} else{ac.style.display='none';resetSearch();}
    });
    
    si.addEventListener('keydown',(e)=>{
        if (e.key === 'Enter') {
            const q=si.value.trim();
            if(q.length>=2){
                ac.style.display='none';
                doSearch(q);
                si.blur();
            }
        }
    });
    
    cb.addEventListener('click',()=>{
        si.value='';
        cb.style.display='none';
        ac.style.display='none';
        resetSearch();
        si.focus();
    });
    
    document.addEventListener('click',e=>{
        if(ac && !e.target.closest('.search-wrap')) ac.style.display='none';
    });
}

function showAc(q) {
    const ql=q.toLowerCase();
    const matches=wordIndex.filter(w=>w.text.toLowerCase().includes(ql)).slice(0,5);
    if(!matches.length){ac.style.display='none';return;}
    ac.innerHTML=matches.map(m=>`<div class="autocomplete-item" onclick="document.getElementById('search-input').value='${m.text}';document.getElementById('autocomplete').style.display='none';document.getElementById('clear-btn').style.display='block';doSearch('${m.text}')"><span>${hl(m.text,q)}</span><span class="badge ${m.cls}">${m.subjectLabel}</span></div>`).join('');
    ac.style.display='block';
}

function doSearch(queryText) {
    if(ac) ac.style.display = 'none';
    const queries = getQ(queryText);
    const results = [];
    const resContainer = document.getElementById('search-results');
    
    DB.forEach(item => {
        if (item.thematic_blocks && item.thematic_blocks.length) {
            item.thematic_blocks.forEach(b => {
                let sc = 0;
                let matchTitle = false;
                queries.forEach(q2 => {
                    const titleLower = b.title.toLowerCase();
                    const textLower = (b.search_text || '').toLowerCase();
                    if (titleLower.includes(q2)) { sc += 2000; matchTitle = true; }
                    sc += (textLower.match(new RegExp(esc(q2),'g'))||[]).length * 10;
                });
                if(sc > 0) results.push({item, block:b, score:sc, matchTitle});
            });
        }
    });
    
    results.sort((a,b) => b.score - a.score);
    const top = results.slice(0,30);
    
    if(!top.length) {
        resContainer.innerHTML = `<div class="empty-state"><p style="color:var(--text-3);">لا توجد نتائج</p></div>`;
        return;
    }
    
    let html = '';
    top.forEach(r => {
        const item = r.item;
        const b = r.block;
        html += `<div class="result-card" onclick="openSearchResult('${item.subject}', ${item.lessonNum}, ${b.start_seconds})">
            <div style="padding:14px;">
                <div style="display:flex; justify-content:space-between; margin-bottom:8px; align-items:flex-start;">
                    <h4 style="margin:0; font-size:14.5px; color:var(--text); line-height:1.4;">${hl(b.title, queries[0])}</h4>
                    <span class="badge badge-${item.subject}" style="flex-shrink:0; margin-right:10px;">${item.subjectLabel} ${item.lessonNum}</span>
                </div>
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div style="font-size:12px; color:var(--primary); font-weight:600; background:var(--primary-light, rgba(79, 70, 229, 0.1)); padding:4px 8px; border-radius:6px;">
                        ⏱ ${formatSeconds(b.start_seconds)}
                    </div>
                </div>
            </div>
        </div>`;
    });
    resContainer.innerHTML = html;
}

function resetSearch() {
    const res = document.getElementById('search-results');
    if(res) res.innerHTML = `<div class="empty-state"><p style="color:var(--text-3);">اكتب كلمة للبحث</p></div>`;
}

function openSearchResult(subject, lessonNum, startTime) {
    const lesson = DB.find(l => l.subject === subject && l.lessonNum === lessonNum);
    if(lesson) {
        if (startTime !== null) pendingSeekTime = startTime;
        openLesson(lesson);
        switchTab('reader');
        
        const idx = thematicData.findIndex(t => t.startTime <= startTime && t.endTime > startTime);
        if(idx !== -1) {
            switchThemeTab(idx, false);
        }
    }
}
function formatSeconds(s) { const m = Math.floor(s/60); const ss = Math.floor(s%60); return m + ":" + (ss<10?"0":"")+ss; }

function setSyllabusMode(mode) {
    syllabusMode = mode;
    const gridBtn = document.getElementById('toggle-grid-btn');
    const listBtn = document.getElementById('toggle-list-btn');
    if (mode === 'grid') {
        gridBtn.style.background = 'var(--primary)';
        gridBtn.style.color = 'white';
        listBtn.style.background = 'transparent';
        listBtn.style.color = 'var(--text-2)';
    } else {
        listBtn.style.background = 'var(--primary)';
        listBtn.style.color = 'white';
        gridBtn.style.background = 'transparent';
        gridBtn.style.color = 'var(--text-2)';
    }
    buildSyllabusTab(DB);
}

function toggleChapterCompletion(event, subject, lessonNum, chapterIdx) {
    if (event) event.stopPropagation();
    const key = `${subject}_${lessonNum}_${chapterIdx}`;
    syllabusCompletion[key] = !syllabusCompletion[key];
    localStorage.setItem('academy_syllabus_completions', JSON.stringify(syllabusCompletion));
    
    updateGlobalProgress();
    
    // Only re-render the list view to show checks
    if(syllabusMode === 'list') {
        buildSyllabusTab(DB);
    }
}

function updateGlobalProgress() {
    let total = 0;
    let completed = 0;
    DB.forEach(l => {
        if (l.thematic_blocks) {
            l.thematic_blocks.forEach((b, idx) => {
                total++;
                if (syllabusCompletion[`${l.subject}_${l.lessonNum}_${idx}`]) {
                    completed++;
                }
            });
        }
    });
    const percent = total > 0 ? Math.round((completed / total) * 100) : 0;
    const txt = document.getElementById('syllabus-progress-text');
    const bar = document.getElementById('syllabus-progress-bar');
    if(txt) txt.textContent = percent + '%';
    if(bar) bar.style.width = percent + '%';
}


// --- KARAOKE ENGINE ---
let lastUserScrollTime = 0;
let isProgrammaticScroll = false;

let isTouching = false;
window.addEventListener('scroll', () => { 
    if (!isProgrammaticScroll) lastUserScrollTime = Date.now(); 
}, { passive: true, capture: true });
window.addEventListener('touchstart', () => { 
    if (!isProgrammaticScroll) {
        isTouching = true;
        lastUserScrollTime = Date.now(); 
    }
}, { passive: true, capture: true });
window.addEventListener('touchend', () => { 
    isTouching = false;
    if (!isProgrammaticScroll) lastUserScrollTime = Date.now(); 
}, { passive: true, capture: true });
window.addEventListener('wheel', () => { 
    if (!isProgrammaticScroll) lastUserScrollTime = Date.now(); 
}, { passive: true, capture: true });

setInterval(() => {
    if (!player || !player.getPlayerState || player.getPlayerState() !== YT.PlayerState.PLAYING) return;
    if (isSeekingTab) return;
    
    let currentTime = player.getCurrentTime();
    updateDashboardProgress();
    
    // --- SMART AUTO TAB SWITCHING ---
    if (thematicData && thematicData[currentTabIndex]) {
        let tabStart = thematicData[currentTabIndex].startTime;
        let tabEnd = thematicData[currentTabIndex].endTime;
        
        if (currentTime >= tabEnd && currentTabIndex < thematicData.length - 1) {
            // Video moved past current tab, find correct tab
            let correctIndex = thematicData.findIndex(t => currentTime >= t.startTime && currentTime < t.endTime);
            if (correctIndex !== -1 && correctIndex !== currentTabIndex) {
                switchThemeTab(correctIndex, false);
                return; // Let next tick handle highlighting
            }
        } else if (currentTime < tabStart && currentTabIndex > 0) {
            // Video scrubbed backwards
            let correctIndex = thematicData.findIndex(t => currentTime >= t.startTime && currentTime < t.endTime);
            if (correctIndex !== -1 && correctIndex !== currentTabIndex) {
                switchThemeTab(correctIndex, false);
                return;
            }
        }
    }
    
    const segments = document.querySelectorAll('.karaoke-segment');
    if (segments.length === 0) return;
    
    let activeStart = -1;
    let nextStart = 999999;
    
    for (let i = 0; i < segments.length; i++) {
        let start = parseFloat(segments[i].getAttribute('data-start'));
        if (isNaN(start)) continue;
        
        if (start <= currentTime) {
            activeStart = start;
        } else {
            nextStart = start;
            break;
        }
    }
    
    let firstActiveSeg = null;
    
    segments.forEach(seg => {
        let start = parseFloat(seg.getAttribute('data-start'));
        if (start === activeStart && currentTime < nextStart) {
            if (!seg.classList.contains('active-karaoke')) {
                seg.classList.add('active-karaoke');
            }
            if (!firstActiveSeg) firstActiveSeg = seg;
        } else {
            seg.classList.remove('active-karaoke');
        }
    });
    
    if (firstActiveSeg) {
        // Don't auto-scroll if: (1) user just scrolled manually within 8s, (2) Zen Mode is active,
        // or (3) user is near the bottom of page (near the validation button)
        const scrolledNearBottom = (window.scrollY + window.innerHeight) >= (document.documentElement.scrollHeight - 150);
        const isZenMode = document.body.classList.contains('zen-mode');
        if (Date.now() - lastUserScrollTime > 8000 && !isTouching && !isZenMode && !scrolledNearBottom) {
            const rect = firstActiveSeg.getBoundingClientRect();
            
            // Calculate sticky headers total height
            const stickyContainer = document.getElementById('sticky-header-container');
            let offsetHeight = 0;
            
            if (stickyContainer) {
                const style = window.getComputedStyle(stickyContainer);
                if (style.position === 'sticky' || style.position === 'fixed') {
                    offsetHeight += stickyContainer.offsetHeight;
                }
            }
            
            // Add a padding of 40px so the text is not squeezed against the menu
            const targetOffset = offsetHeight + 40;
            
            let needsScroll = false;
            
            if (readerSettings.scrollMode === 'teleprompter') {
                // Teleprompter: Must always be EXACTLY at targetOffset
                // Increase tolerance to 15px to avoid jitter with large fonts
                if (Math.abs(rect.top - targetOffset) > 15) {
                    needsScroll = true;
                }
            } else {
                // Zone: Only scroll if too high (hidden under header) or too low
                if (rect.top < targetOffset || rect.top > window.innerHeight * 0.70) {
                    needsScroll = true;
                }
            }
            
            if (needsScroll) {
                isProgrammaticScroll = true;
                
                // Calculate absolute scroll position
                const absoluteTop = window.scrollY + rect.top;
                
                window.scrollTo({
                    top: absoluteTop - targetOffset,
                    behavior: 'smooth'
                });
                
                setTimeout(() => { isProgrammaticScroll = false; }, 1200);
            }
        }
    }
}, 300);
// --- END KARAOKE ENGINE ---

// --- SETTINGS STATE ---
let readerSettings = {
    scrollMode: 'zone',
    focusMode: false,
    spacingAere: false,
    fontFamily: "'Tajawal', sans-serif"
};

function loadSettings() {
    try {
        let saved = localStorage.getItem('academie_reader_settings');
        if (saved) {
            let parsed = JSON.parse(saved);
            readerSettings = { ...readerSettings, ...parsed };
            if (parsed.spacingAere !== undefined) readerSettings.spacingAere = parsed.spacingAere;
            if (parsed.fontFamily !== undefined) readerSettings.fontFamily = parsed.fontFamily;
        }
    } catch (e) { console.error(e); }
    
    // Apply UI
    const radios = document.getElementsByName('scrollMode');
    radios.forEach(r => {
        if (r.value === readerSettings.scrollMode) r.checked = true;
        r.addEventListener('change', (e) => {
            readerSettings.scrollMode = e.target.value;
            saveSettings();
        });
    });

    const focusToggle = document.getElementById('focus-mode-toggle');
    if (focusToggle) {
        focusToggle.checked = readerSettings.focusMode;
        focusToggle.addEventListener('change', (e) => {
            readerSettings.focusMode = e.target.checked;
            saveSettings();
            applyFocusMode();
        });
    }

    const spacingToggle = document.getElementById('spacing-toggle');
    if (spacingToggle) {
        spacingToggle.checked = readerSettings.spacingAere;
        spacingToggle.addEventListener('change', (e) => {
            readerSettings.spacingAere = e.target.checked;
            saveSettings();
            applySpacing();
        });
    }

    applyFocusMode();
    applySpacing();
    applyFontFamily();
    initFontButtons();
}

function saveSettings() {
    localStorage.setItem('academie_reader_settings', JSON.stringify(readerSettings));
}

function applyFocusMode() {
    const content = document.getElementById('reader-content');
    if (content) {
        if (readerSettings.focusMode) {
            content.classList.add('focus-mode-active');
        } else {
            content.classList.remove('focus-mode-active');
        }
    }
}

// --- SETTINGS MODAL LOGIC ---
document.addEventListener('DOMContentLoaded', () => {
    const btnSettings = document.getElementById('btn-settings-toggle');
    const settingsSheet = document.getElementById('settings-sheet');
    const settingsOverlay = document.getElementById('settings-overlay');
    const closeSettingsBtn = document.getElementById('close-settings-btn');
    
    function openSettings() {
        settingsSheet.classList.add('open');
        settingsOverlay.classList.add('show');
        document.body.style.overflow = 'hidden';
    }
    
    function closeSettings() {
        settingsSheet.classList.remove('open');
        settingsOverlay.classList.remove('show');
        document.body.style.overflow = '';
    }
    
    if (btnSettings) btnSettings.addEventListener('click', openSettings);
    if (closeSettingsBtn) closeSettingsBtn.addEventListener('click', closeSettings);
    if (settingsOverlay) settingsOverlay.addEventListener('click', closeSettings);
    
    loadSettings();
});

document.addEventListener('DOMContentLoaded', () => {
    const prevBtn = document.getElementById('prev-theme-btn');
    const nextBtn = document.getElementById('next-theme-btn');
    
    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            if (currentTabIndex > 0) switchThemeTab(currentTabIndex - 1, true);
        });
    }
    
    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            if (thematicData && currentTabIndex < thematicData.length - 1) {
                switchThemeTab(currentTabIndex + 1, true);
            }
        });
    }
});




document.addEventListener('DOMContentLoaded', () => {
    const stickyToggleBtn = document.getElementById('btn-sticky-toggle');
    const stickyContainer = document.getElementById('sticky-header-container');
    const videoWrapper = document.getElementById('video-wrapper');
    
    if (stickyToggleBtn && stickyContainer && videoWrapper) {
        stickyToggleBtn.addEventListener('click', () => {
            if (videoWrapper.style.display === 'none') {
                videoWrapper.style.display = 'flex';
                stickyToggleBtn.style.background = 'var(--surface)';
                stickyToggleBtn.style.color = 'var(--text)';
                stickyToggleBtn.setAttribute('title', 'Désépingler la vidéo');
            } else {
                videoWrapper.style.display = 'none';
                stickyToggleBtn.style.background = 'var(--primary)';
                stickyToggleBtn.style.color = 'white';
                stickyToggleBtn.setAttribute('title', 'Épingler la vidéo');
            }
        });
    }
});

function applySpacing() {
    const rc = document.getElementById('reader-content');
    if (rc) {
        if (readerSettings.spacingAere) {
            rc.classList.add('spacing-aere');
        } else {
            rc.classList.remove('spacing-aere');
        }
    }
}

function applyFontFamily() {
    document.documentElement.style.setProperty('--main-font', readerSettings.fontFamily);
    
    // Update active button state
    document.querySelectorAll('.font-select-btn').forEach(btn => {
        if (btn.getAttribute('data-font') === readerSettings.fontFamily) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
}

function initFontButtons() {
    document.querySelectorAll('.font-select-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            readerSettings.fontFamily = e.target.getAttribute('data-font');
            saveSettings();
            applyFontFamily();
        });
    });
}

let currentPlaybackRate = 1;
function updateSpeedUI() {
    const quickSpeedBtn = document.getElementById('btn-speed-toggle');
    if (quickSpeedBtn) {
        quickSpeedBtn.textContent = currentPlaybackRate + 'x';
    }
    document.querySelectorAll('.speed-select-btn').forEach(b => {
        if (parseFloat(b.getAttribute('data-speed')) === currentPlaybackRate) {
            b.classList.add('active');
        } else {
            b.classList.remove('active');
        }
    });
}

function setPlaybackSpeed(rate) {
    currentPlaybackRate = rate;
    updateSpeedUI();
    if (player && typeof player.setPlaybackRate === 'function') {
        player.setPlaybackRate(currentPlaybackRate);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const speedBtns = document.querySelectorAll('.speed-select-btn');
    speedBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            setPlaybackSpeed(parseFloat(e.target.getAttribute('data-speed')));
        });
    });
    
    const quickSpeedBtn = document.getElementById('btn-speed-toggle');
    if (quickSpeedBtn) {
        quickSpeedBtn.addEventListener('click', () => {
            let newRate = 1;
            if (currentPlaybackRate === 1) newRate = 1.25;
            else if (currentPlaybackRate === 1.25) newRate = 1.5;
            else if (currentPlaybackRate === 1.5) newRate = 2;
            else if (currentPlaybackRate === 2) newRate = 0.75;
            else newRate = 1;
            setPlaybackSpeed(newRate);
        });
    }
    
    updateSpeedUI();
});

function openLessonPreview(l) {
    const sheet = document.getElementById('lesson-preview-sheet');
    const overlay = document.getElementById('lesson-preview-overlay');
    const title = document.getElementById('lesson-preview-title');
    const list = document.getElementById('lesson-preview-list');
    const startBtn = document.getElementById('start-reading-btn');

    title.textContent = 'الدرس ' + l.lessonNum + ' - ' + (l.subjectLabel || l.subject);

    let html = '';
    if (l.thematic_blocks && l.thematic_blocks.length > 0) {
        l.thematic_blocks.forEach((b, idx) => {
            const key = l.subject + '_' + l.lessonNum + '_' + idx;
            const isComp = !!syllabusCompletion[key];
            html += `<div class="preview-chapter-item" onclick="togglePreviewChapter(event, '${l.subject}', ${l.lessonNum}, ${idx}, this)">
                <div class="preview-checkbox ${isComp ? 'checked' : ''}">${isComp ? '✓' : ''}</div>
                <div class="preview-chapter-info" style="margin-right: 12px; text-align: right;">
                    <div class="preview-chapter-title">${idx + 1}. ${b.title}</div>
                </div>
            </div>`;
        });
    } else {
        html = '<div style="text-align:center; color:var(--text-2); padding: 20px;">لا توجد محاور متاحة</div>';
    }
    list.innerHTML = html;

    startBtn.onclick = () => {
        closeLessonPreview();
        switchTab('reader');
        let startSec = 0;
        if (l.thematic_blocks && l.thematic_blocks.length > 0) {
            startSec = l.thematic_blocks[0].start_seconds;
        }
        loadLesson(l.lessonNum, l.subject, startSec);
    };

    sheet.classList.add('open');
    overlay.classList.add('show');
}

function closeLessonPreview() {
    document.getElementById('lesson-preview-sheet').classList.remove('open');
    document.getElementById('lesson-preview-overlay').classList.remove('show');
}

function togglePreviewChapter(e, subject, lessonNum, chapterIdx, el) {
    if (e) e.stopPropagation();
    const key = subject + '_' + lessonNum + '_' + chapterIdx;
    const isComp = !syllabusCompletion[key];
    syllabusCompletion[key] = isComp;
    localStorage.setItem('academy_syllabus_completions', JSON.stringify(syllabusCompletion));

    updateGlobalProgress();
    buildSyllabusTab(DB);

    const cb = el.querySelector('.preview-checkbox');
    if (isComp) {
        cb.classList.add('checked');
        cb.textContent = '✓';
    } else {
        cb.classList.remove('checked');
        cb.textContent = '';
    }
}

document.getElementById('close-preview-btn').onclick = closeLessonPreview;
document.getElementById('lesson-preview-overlay').onclick = closeLessonPreview;
