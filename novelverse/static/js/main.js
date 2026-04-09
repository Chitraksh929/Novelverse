/* ── NovelVerse · Main JS ──────────────────────────────────────────────────── */

// ── CSRF Token ────────────────────────────────────────────────────────────────
// Injected from a meta tag in base.html; sent as header with every AJAX request
function getCsrfToken() {
  return document.querySelector('meta[name="csrf-token"]')?.content || '';
}

// Wrapper around fetch that always includes the CSRF header
async function apiFetch(url, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    'X-CSRF-Token': getCsrfToken(),
    'X-Requested-With': 'XMLHttpRequest',
    ...(options.headers || {}),
  };
  return fetch(url, { ...options, headers });
}

// ── Toast ────────────────────────────────────────────────────────────────────
const Toast = {
  container: null,
  init() {
    this.container = document.getElementById('toast-container') || (() => {
      const el = document.createElement('div');
      el.id = 'toast-container';
      el.className = 'toast-container';
      document.body.appendChild(el);
      return el;
    })();
  },
  show(msg, type = 'info', duration = 3500) {
    if (!this.container) this.init();
    const icons = { success:'✓', error:'✕', info:'ℹ' };
    const t = document.createElement('div');
    t.className = `toast toast-${type}`;
    t.innerHTML = `<span style="color:var(--${type==='error'?'danger':type==='success'?'success':'info'})">${icons[type]||'•'}</span><span>${msg}</span>`;
    this.container.appendChild(t);
    setTimeout(() => { t.style.opacity='0'; t.style.transform='translateX(120%)'; t.style.transition='all 0.3s'; setTimeout(()=>t.remove(),300); }, duration);
  }
};
Toast.init();

// ── Follow Button ─────────────────────────────────────────────────────────────
document.addEventListener('click', async (e) => {
  const btn = e.target.closest('.btn-follow');
  if (!btn) return;
  const novelId = btn.dataset.novelId;
  btn.disabled = true;
  try {
    const res = await apiFetch(`/api/follow/${novelId}`, { method:'POST' });
    const data = await res.json();
    if (data.error) { Toast.show(data.error,'error'); return; }
    btn.classList.toggle('following', data.following);
    btn.textContent = data.following ? '✓ Following' : '+ Follow';
    const counter = document.querySelector(`[data-followers="${novelId}"]`);
    if (counter) counter.textContent = data.count;
    Toast.show(data.following ? 'Added to reading list!' : 'Removed from reading list', data.following ? 'success' : 'info');
  } finally { btn.disabled = false; }
});

// ── Star Rating ───────────────────────────────────────────────────────────────
function initStarRating(container) {
  const stars = container.querySelectorAll('.star');
  const input = container.querySelector('input[name="rating"]');
  let current = parseInt(input?.value) || 0;
  stars.forEach((s, i) => {
    s.addEventListener('mouseenter', () => stars.forEach((st,j) => st.classList.toggle('hover', j<=i)));
    s.addEventListener('mouseleave', () => stars.forEach(st => st.classList.remove('hover')));
    s.addEventListener('click', () => {
      current = i + 1;
      if (input) input.value = current;
      stars.forEach((st,j) => st.classList.toggle('filled', j<current));
    });
    if (i < current) s.classList.add('filled');
  });
}
document.querySelectorAll('.star-rating').forEach(initStarRating);

// ── Review Submit ─────────────────────────────────────────────────────────────
const reviewForm = document.getElementById('review-form');
if (reviewForm) {
  reviewForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const rating = reviewForm.querySelector('input[name="rating"]')?.value;
    const body   = reviewForm.querySelector('textarea[name="body"]')?.value;
    const novelId= reviewForm.dataset.novelId;
    if (!rating) { Toast.show('Please select a rating','error'); return; }
    const btn = reviewForm.querySelector('button[type="submit"]');
    btn.disabled = true; btn.textContent = 'Saving…';
    try {
      const res = await apiFetch('/api/review',{ method:'POST', body:JSON.stringify({novel_id:novelId,rating,body}) });
      const data = await res.json();
      if (data.success) {
        Toast.show('Review saved!','success');
        document.getElementById('avg-rating-display')?.querySelector('.rating-score') && (document.querySelector('.rating-score').textContent = data.avg_rating.toFixed(1));
        reviewForm.closest('.review-section')?.classList.add('reviewed');
      }
    } finally { btn.disabled=false; btn.textContent='Submit Review'; }
  });
}

// ── Comment Submit ────────────────────────────────────────────────────────────
document.querySelectorAll('.comment-form').forEach(form => {
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const textarea  = form.querySelector('textarea');
    const body      = textarea.value.trim();
    if (!body) return;
    const novelId   = form.dataset.novelId;
    const chapterId = form.dataset.chapterId;
    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    try {
      const res = await apiFetch('/api/comment',{ method:'POST', body:JSON.stringify({novel_id:novelId,chapter_id:chapterId,body}) });
      const data = await res.json();
      if (data.success) {
        textarea.value = '';
        const list = form.closest('.comments-section')?.querySelector('.comment-list');
        if (list) {
          const el = document.createElement('div');
          el.className = 'comment';
          el.innerHTML = `<div class="comment-header"><div class="comment-avatar">${data.username[0].toUpperCase()}</div><span class="comment-username">${data.username}</span><span class="comment-time">${data.time}</span></div><div class="comment-body">${escapeHtml(data.body)}</div>`;
          list.prepend(el);
        }
        Toast.show('Comment posted!','success');
      }
    } finally { btn.disabled=false; }
  });
});

// ── Comment Like ──────────────────────────────────────────────────────────────
document.addEventListener('click', async (e) => {
  const btn = e.target.closest('.comment-like-btn');
  if (!btn) return;
  const id = btn.dataset.commentId;
  const res = await apiFetch(`/api/like/comment/${id}`,{method:'POST'});
  const data = await res.json();
  btn.classList.toggle('liked', data.liked);
  const counter = btn.querySelector('.like-count');
  if (counter) counter.textContent = data.count;
});

// ── Reading Progress Bar ───────────────────────────────────────────────────────
const progressBar = document.getElementById('reading-progress-bar');
if (progressBar) {
  window.addEventListener('scroll', () => {
    const pct = window.scrollY / (document.body.scrollHeight - window.innerHeight) * 100;
    progressBar.style.width = Math.min(100, pct) + '%';
  });
}

// ── Font Size Control ─────────────────────────────────────────────────────────
const readingBody = document.querySelector('.reading-body');
let fontSize = parseInt(localStorage.getItem('nv-fontsize') || '18');
function applyFontSize() { if(readingBody) readingBody.style.fontSize = fontSize+'px'; }
applyFontSize();
document.getElementById('font-inc')?.addEventListener('click', () => { fontSize = Math.min(26, fontSize+1); applyFontSize(); localStorage.setItem('nv-fontsize',fontSize); });
document.getElementById('font-dec')?.addEventListener('click', () => { fontSize = Math.max(14, fontSize-1); applyFontSize(); localStorage.setItem('nv-fontsize',fontSize); });

// ── AI Writing Assistant ───────────────────────────────────────────────────────
const aiPanel = document.getElementById('ai-panel');
if (aiPanel) {
  aiPanel.querySelectorAll('[data-ai-action]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const action = btn.dataset.aiAction;
      const content = document.getElementById('chapter-content')?.value || '';
      const context = document.getElementById('novel-context')?.value || '';
      const resultEl = document.getElementById('ai-result');
      if (!resultEl) return;
      resultEl.textContent = 'Thinking…';
      resultEl.style.display = 'block';
      btn.disabled = true;
      try {
        const res = await apiFetch('/api/ai/writing-assist',{
          method:'POST',
          body: JSON.stringify({action,content:content.slice(-2000),context})
        });
        const data = await res.json();
        resultEl.textContent = data.result || data.error || 'Error';
        if (data.result) {
          const applyBtn = document.getElementById('ai-apply');
          if (applyBtn) {
            applyBtn.style.display = 'inline-flex';
            applyBtn.onclick = () => {
              const ta = document.getElementById('chapter-content');
              if (ta) { ta.value += '\n\n' + data.result; updateWordCount(); }
              applyBtn.style.display='none';
              Toast.show('Text appended to chapter!','success');
            };
          }
        }
      } finally { btn.disabled = false; }
    });
  });
}

// ── Word Count Live ───────────────────────────────────────────────────────────
function updateWordCount() {
  const ta = document.getElementById('chapter-content');
  const wc = document.getElementById('word-count-live');
  if (ta && wc) wc.textContent = ta.value.trim().split(/\s+/).filter(Boolean).length + ' words';
}
document.getElementById('chapter-content')?.addEventListener('input', updateWordCount);
updateWordCount();

// ── Analytics Charts ──────────────────────────────────────────────────────────
async function loadAnalytics(novelId) {
  const res = await fetch(`/api/analytics/${novelId}`);
  const data = await res.json();
  if (window.Chart) {
    // Views over time
    const viewsCtx = document.getElementById('views-chart')?.getContext('2d');
    if (viewsCtx) {
      new Chart(viewsCtx, {
        type: 'line',
        data: {
          labels: data.views_by_day.map(d=>d.day.slice(5)),
          datasets:[{ label:'Views', data:data.views_by_day.map(d=>d.cnt),
            borderColor:'#c9a84c', backgroundColor:'rgba(201,168,76,0.08)',
            tension:0.35, fill:true, pointRadius:3 }]
        },
        options: { responsive:true, plugins:{legend:{display:false}}, scales:{
          x:{grid:{color:'rgba(255,255,255,0.04)'},ticks:{color:'#6b6358',font:{size:11}}},
          y:{grid:{color:'rgba(255,255,255,0.04)'},ticks:{color:'#6b6358',font:{size:11}}}
        }}
      });
    }
    // Chapter views bar
    const chapCtx = document.getElementById('chapter-chart')?.getContext('2d');
    if (chapCtx) {
      new Chart(chapCtx, {
        type:'bar',
        data:{
          labels: data.chapter_stats.map(c=>`Ch.${c.num}`),
          datasets:[{label:'Views',data:data.chapter_stats.map(c=>c.views),
            backgroundColor:'rgba(123,104,238,0.6)',borderColor:'rgba(123,104,238,0.9)',borderWidth:1,borderRadius:4}]
        },
        options:{responsive:true,plugins:{legend:{display:false}},scales:{
          x:{grid:{color:'rgba(255,255,255,0.04)'},ticks:{color:'#6b6358',font:{size:11}}},
          y:{grid:{color:'rgba(255,255,255,0.04)'},ticks:{color:'#6b6358',font:{size:11}}}
        }}
      });
    }
    // Ratings
    const ratCtx = document.getElementById('ratings-chart')?.getContext('2d');
    if (ratCtx) {
      const counts = [1,2,3,4,5].map(r => (data.ratings_dist.find(d=>d.rating===r)||{cnt:0}).cnt);
      new Chart(ratCtx,{
        type:'bar',
        data:{labels:['★','★★','★★★','★★★★','★★★★★'],datasets:[{data:counts,
          backgroundColor:['#e05252','#e07852','#c9a84c','#82c44c','#4caf7d'],
          borderRadius:4}]},
        options:{responsive:true,plugins:{legend:{display:false}},scales:{
          x:{grid:{display:false},ticks:{color:'#c9a84c'}},
          y:{grid:{color:'rgba(255,255,255,0.04)'},ticks:{color:'#6b6358',stepSize:1}}
        }}
      });
    }
    // Word count
    const wordEl = document.getElementById('chapter-words-list');
    if (wordEl) {
      wordEl.innerHTML = data.chapter_stats.map(c=>`
        <div style="display:flex;justify-content:space-between;padding:0.5rem 0;border-bottom:1px solid var(--border);font-size:0.9rem">
          <span style="color:var(--text2)">Ch.${c.num} — ${c.title}</span>
          <span style="color:var(--text3);font-family:var(--font-mono)">${(c.words||0).toLocaleString()} w</span>
        </div>`).join('');
    }
  }
}

// ── Tabs ──────────────────────────────────────────────────────────────────────
// Scoped per .tabs container — no cross-tab bleed, smooth fade-in on switch
document.querySelectorAll('.tabs').forEach(tabBar => {
  const tabs = tabBar.querySelectorAll('.tab[data-tab]');
  const paneIds = Array.from(tabs).map(t => t.dataset.tab);

  // On load: enforce correct visibility based on which tab has .active class
  paneIds.forEach(id => {
    const pane = document.getElementById(id);
    if (!pane) return;
    const isActive = tabBar.querySelector('.tab[data-tab="' + id + '"]')?.classList.contains('active');
    pane.style.display  = isActive ? '' : 'none';
    pane.style.opacity  = isActive ? '1' : '0';
  });

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const target = tab.dataset.tab;
      // Deactivate all tabs in this bar
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      // Show/hide only panes belonging to this bar
      paneIds.forEach(id => {
        const pane = document.getElementById(id);
        if (!pane) return;
        if (id === target) {
          pane.style.display = '';
          pane.style.opacity = '0';
          pane.style.transition = '';
          requestAnimationFrame(() => {
            pane.style.transition = 'opacity 0.18s ease';
            pane.style.opacity = '1';
          });
        } else {
          pane.style.transition = '';
          pane.style.display    = 'none';
          pane.style.opacity    = '0';
        }
      });
    });
  });
});

// ── Utility ───────────────────────────────────────────────────────────────────
function escapeHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── Auto-dismiss flashes ───────────────────────────────────────────────────────
document.querySelectorAll('.flash').forEach(el => {
  setTimeout(()=>{ el.style.transition='opacity 0.5s'; el.style.opacity='0'; setTimeout(()=>el.remove(),500); }, 4000);
});

// ── Expose loadAnalytics for template inline call ─────────────────────────────
window.loadAnalytics = loadAnalytics;

// ── Cover Image Live Preview ───────────────────────────────────────────────────
const coverInput = document.getElementById('cover-file-input');
if (coverInput) {
  coverInput.addEventListener('change', () => {
    const file = coverInput.files[0];
    const preview    = document.getElementById('cover-preview');
    const previewImg = document.getElementById('cover-preview-img');
    if (file && preview && previewImg) {
      const reader = new FileReader();
      reader.onload = e => {
        previewImg.src  = e.target.result;
        preview.style.display = 'block';
      };
      reader.readAsDataURL(file);
      // Clear URL field when file is chosen — avoid ambiguity
      const urlField = document.querySelector('input[name="cover_url"]');
      if (urlField) urlField.value = '';
    }
  });
}
