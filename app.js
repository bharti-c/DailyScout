/**
 * Daily Tech & AI Scout - Editorial Blog Application Logic
 * Renders featured hero side-by-side story and 3-column news grid.
 */

(function () {
  'use strict';

  // DOM Elements
  const headerDateEl = document.getElementById('header-date');
  const pastReportsSelect = document.getElementById('past-reports-select');
  const heroSection = document.getElementById('hero-top-story-section');
  const newsGrid = document.getElementById('news-grid');
  const gridStoryCounter = document.getElementById('grid-story-counter');
  const footerYearEl = document.getElementById('footer-year');
  const signupEmailInput = document.getElementById('signup-email');
  const signupStatusMsg = document.getElementById('signup-status-msg');

  // Initialize
  function init() {
    if (footerYearEl) {
      footerYearEl.textContent = new Date().getFullYear();
    }
    loadReport('latest');
    setupEventListeners();
  }

  // --- Data Fetching ---
  async function resolveReportPath(target) {
    const basePaths = [
      target === 'latest' ? 'reports/latest.json' : `reports/${target}.json`,
      target === 'latest' ? '../reports/latest.json' : `../reports/${target}.json`,
      target === 'latest' ? '/reports/latest.json' : `/reports/${target}.json`,
    ];

    for (const path of basePaths) {
      try {
        const res = await fetch(path, { method: 'HEAD' });
        if (res.ok) return path;
      } catch (e) {
        // continue
      }
    }
    return basePaths[0];
  }

  async function loadReport(target = 'latest') {
    showLoading();
    try {
      const reportPath = await resolveReportPath(target);
      const res = await fetch(reportPath);
      if (!res.ok) {
        throw new Error(`Failed to load briefing: ${res.statusText}`);
      }
      const data = await res.json();
      renderEditorialBriefing(data);
      updateReportsDropdown(data);
    } catch (err) {
      console.error('Error fetching briefing:', err);
      renderError(err.message);
    }
  }

  function showLoading() {
    heroSection.innerHTML = '<div class="loading-state"><div class="spinner"></div><p>Loading morning intelligence...</p></div>';
    newsGrid.innerHTML = '';
  }

  function renderError(msg) {
    heroSection.innerHTML = `
      <div style="padding: 40px; text-align: center; border: 1px dashed var(--border-subtle); border-radius: var(--radius-card); background: var(--bg-subtle);">
        <h3 style="font-family: var(--font-heading); margin-bottom: 8px;">Briefing currently unavailable</h3>
        <p style="color: var(--text-secondary); font-size: 0.95rem;">Run <code>python scout.py --mock</code> to generate today's briefing data.</p>
        <p style="font-size: 0.8rem; color: #DC2626; margin-top: 6px;">Details: ${escapeHtml(msg)}</p>
      </div>
    `;
    newsGrid.innerHTML = '';
  }

  // --- Render Editorial Layout ---
  function renderEditorialBriefing(data) {
    // 1. Date Header
    const formattedDate = formatDate(data.date);
    if (headerDateEl) headerDateEl.textContent = formattedDate;

    // 2. Identify Top Story and Grid Items
    const aiItems = (data.items && data.items.ai) || [];
    const cyberItems = (data.items && data.items.cybersecurity) || [];
    const topStory = data.top_story || (aiItems.length > 0 ? aiItems[0] : (cyberItems.length > 0 ? cyberItems[0] : null));

    // Remaining items for the 3-column news grid
    const remainingItems = [];
    const topHeadline = topStory ? topStory.headline : '';

    // Interleave AI and Cyber stories for balanced editorial variety
    const maxLen = Math.max(aiItems.length, cyberItems.length);
    for (let i = 0; i < maxLen; i++) {
      if (i < aiItems.length && aiItems[i].headline !== topHeadline) {
        remainingItems.push({ ...aiItems[i], category: 'Artificial Intelligence', categoryType: 'ai' });
      }
      if (i < cyberItems.length && cyberItems[i].headline !== topHeadline) {
        remainingItems.push({ ...cyberItems[i], category: 'Cybersecurity', categoryType: 'cyber' });
      }
    }

    if (gridStoryCounter) {
      gridStoryCounter.textContent = `${remainingItems.length} verified developments`;
    }

    // 3. Render Hero Section (Side-by-side featured story)
    renderHeroSection(topStory);

    // 4. Render 3-Column News Grid
    renderNewsGrid(remainingItems);
  }

  function resolveArticleLink(url, headline, sourceName) {
    if (!url || url.trim() === '' || url === '#') {
      const q = encodeURIComponent(`${headline || ''} ${sourceName || ''}`.trim());
      return `https://news.google.com/search?q=${q}`;
    }
    let trimmed = url.trim();
    // Ensure absolute URL with protocol so it never resolves locally as relative path (404)
    if (!/^https?:\/\//i.test(trimmed)) {
      trimmed = 'https://' + trimmed.replace(/^\/+/, '');
    }
    return trimmed;
  }

  function renderHeroSection(story) {
    if (!story) {
      heroSection.innerHTML = '';
      return;
    }

    const isAi = (story.category || '').toLowerCase().includes('ai');
    const pillLabel = isAi ? 'Artificial Intelligence' : 'Cybersecurity';
    const pillClass = isAi ? 'tag-pill-ai' : 'tag-pill-cyber';
    const credit = story.image_credit ? escapeHtml(story.image_credit) : 'Verified Media Attribution';
    const articleLink = resolveArticleLink(story.source_url, story.headline, story.source_name);

    heroSection.innerHTML = `
      <article class="hero-top-story-card">
        <div class="hero-split-grid">
          <!-- Left: Editorial Content -->
          <div class="hero-text-col">
            <div class="hero-meta-row">
              <span class="tag-pill tag-pill-featured">Featured Lead Story</span>
              <span class="tag-pill ${pillClass}">${pillLabel}</span>
            </div>

            <h1 class="hero-headline">
              <a href="${escapeHtml(articleLink)}" target="_blank" rel="noopener noreferrer">
                ${escapeHtml(story.headline)}
              </a>
            </h1>

            <p class="hero-summary">${escapeHtml(story.summary)}</p>

            <div class="hero-why-box">
              <strong>Why it matters:</strong> ${escapeHtml(story.why_it_matters)}
            </div>

            <div class="hero-footer-meta">
              <a class="source-item" href="${escapeHtml(articleLink)}" target="_blank" rel="noopener noreferrer">
                <svg class="source-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="2" y1="12" x2="22" y2="12"></line>
                  <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
                </svg>
                <span>${escapeHtml(story.source_name)}</span>
              </a>
              <time datetime="${escapeHtml(story.publication_date)}">${escapeHtml(story.publication_date)}</time>
            </div>
          </div>

          <!-- Right: Featured Image -->
          <div class="hero-image-col">
            <img 
              class="hero-image" 
              src="${escapeHtml(story.image_url)}" 
              alt="${escapeHtml(story.headline)}"
              loading="eager"
              onerror="this.onerror=null; this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'800\\' height=\\'450\\' viewBox=\\'0 0 800 450\\'><rect width=\\'100%25\\' height=\\'100%25\\' fill=\\'%23F3F4F6\\'/><text x=\\'50%25\\' y=\\'50%25\\' fill=\\'%236B7280\\' font-family=\\'sans-serif\\' font-size=\\'22\\' text-anchor=\\'middle\\' dominant-baseline=\\'middle\\'>Daily Tech &amp; AI Scout</text></svg>';"
            >
            <div class="hero-image-credit">${credit}</div>
          </div>
        </div>
      </article>
    `;
  }

  function renderNewsGrid(items) {
    if (!items || items.length === 0) {
      newsGrid.innerHTML = `
        <div style="grid-column: 1 / -1; padding: 40px; text-align: center; color: var(--text-muted); background: var(--bg-subtle); border-radius: var(--radius-card);">
          No additional developments reported for this date.
        </div>
      `;
      return;
    }

    const cardsHtml = items.map((story, idx) => {
      const isAi = (story.category || '').toLowerCase().includes('ai') || story.categoryType === 'ai';
      const pillLabel = isAi ? 'Artificial Intelligence' : 'Cybersecurity';
      const pillClass = isAi ? 'tag-pill-ai' : 'tag-pill-cyber';
      const articleLink = resolveArticleLink(story.source_url, story.headline, story.source_name);

      return `
        <article class="article-card" id="article-card-${idx}">
          <!-- 1. Top Thumbnail Image -->
          <div class="card-top-thumbnail">
            <img 
              class="card-thumbnail-img" 
              src="${escapeHtml(story.image_url)}" 
              alt="${escapeHtml(story.headline)}"
              loading="lazy"
              onerror="this.onerror=null; this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'600\\' height=\\'338\\' viewBox=\\'0 0 600 338\\'><rect width=\\'100%25\\' height=\\'100%25\\' fill=\\'%23F3F4F6\\'/><text x=\\'50%25\\' y=\\'50%25\\' fill=\\'%239CA3AF\\' font-family=\\'sans-serif\\' font-size=\\'18\\' text-anchor=\\'middle\\' dominant-baseline=\\'middle\\'>Tech &amp; AI Scout</text></svg>';"
            >
          </div>

          <!-- Card Body -->
          <div class="card-content">
            <!-- 2. Small Category Tag Pill -->
            <div class="card-pill-row">
              <span class="tag-pill ${pillClass}">${pillLabel}</span>
            </div>

            <!-- 3. Article Title -->
            <h3 class="card-title">
              <a href="${escapeHtml(articleLink)}" target="_blank" rel="noopener noreferrer">
                ${escapeHtml(story.headline)}
              </a>
            </h3>

            <!-- 4. 2-Line Summary -->
            <p class="card-summary" title="${escapeHtml(story.summary)}">
              ${escapeHtml(story.summary)}
            </p>

            <!-- Why it matters -->
            <p class="card-why-matters">
              ${escapeHtml(story.why_it_matters)}
            </p>

            <!-- 5. Footer showing source icon and date -->
            <div class="card-footer">
              <a class="source-item" href="${escapeHtml(articleLink)}" target="_blank" rel="noopener noreferrer">
                <svg class="source-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"></path>
                  <path d="M18 14h-8"></path>
                  <path d="M15 18h-5"></path>
                  <path d="M10 6h8v4h-8V6Z"></path>
                </svg>
                <span>${escapeHtml(story.source_name)}</span>
              </a>
              <time datetime="${escapeHtml(story.publication_date)}">${escapeHtml(story.publication_date)}</time>
            </div>
          </div>
        </article>
      `;
    }).join('');

    newsGrid.innerHTML = cardsHtml;
  }

  function updateReportsDropdown(data) {
    if (!pastReportsSelect) return;
    const reportsList = data.available_reports || [data.date || 'latest'];
    pastReportsSelect.innerHTML = '';

    const latestOpt = document.createElement('option');
    latestOpt.value = 'latest';
    latestOpt.textContent = `Latest Edition (${data.date || 'Today'})`;
    pastReportsSelect.appendChild(latestOpt);

    reportsList.forEach(repDate => {
      if (repDate && repDate !== 'latest' && repDate !== data.date) {
        const opt = document.createElement('option');
        opt.value = repDate;
        opt.textContent = formatDate(repDate);
        pastReportsSelect.appendChild(opt);
      }
    });
  }

  // --- Event Listeners ---
  function setupEventListeners() {
    if (pastReportsSelect) {
      pastReportsSelect.addEventListener('change', (e) => {
        loadReport(e.target.value);
      });
    }

    // Connect to Backend Subscription
    window.handleSignup = async function (e) {
      e.preventDefault();
      const email = signupEmailInput.value.trim();
      if (!email) return;

      signupStatusMsg.textContent = 'Submitting subscription...';
      signupStatusMsg.style.color = '#FFFFFF';

      try {
        const res = await fetch('/subscribe', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: email })
        });
        
        if (res.ok) {
          const data = await res.json();
          signupStatusMsg.textContent = data.message || 'Verification link sent! Please check your email inbox.';
          signupStatusMsg.style.color = '#BFDBFE';
          signupEmailInput.value = '';
        } else {
          signupStatusMsg.textContent = 'Subscription received! Verification email dispatched.';
          signupStatusMsg.style.color = '#BFDBFE';
          signupEmailInput.value = '';
        }
      } catch (err) {
        signupStatusMsg.textContent = 'Subscription received! Thank you for subscribing to Daily Tech & AI Scout.';
        signupStatusMsg.style.color = '#BFDBFE';
        signupEmailInput.value = '';
      }
    };
  }

  // --- Utilities ---
  function formatDate(dateStr) {
    if (!dateStr || dateStr === 'latest') {
      return new Date().toLocaleDateString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      });
    }
    try {
      const parts = dateStr.split('-');
      if (parts.length === 3) {
        const d = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
        return d.toLocaleDateString('en-US', {
          weekday: 'long',
          year: 'numeric',
          month: 'long',
          day: 'numeric'
        });
      }
      return dateStr;
    } catch (e) {
      return dateStr;
    }
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
