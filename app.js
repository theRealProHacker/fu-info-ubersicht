/**
 * FU Berlin Informatik Institut - Interactive Diagram
 * Loads data from JSON and populates the HTML containers
 */

// SVG Icons for links and institutions
const ICONS = {
    // Universities
    'fu-berlin': '<img src="assets/fu-berlin-icon.png" alt="FU Berlin" style="width: 1.1em; height: 1.1em; vertical-align: text-bottom; margin-right: 2px;">',
    'tu-berlin': '<svg viewBox="0 0 1000 1000" fill="currentColor"><path d="M893,124v208h-63V223H698v522h61v92H485v-92h62V554H334v191h62v92H123v-92h61V223H52v109H0V124H893z M435,502V223H334v279H435z M544,136H343v33h201V136z"/></svg>',
    'tu-dresden': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M2.5,21.5h19v-19h-19V21.5z M4.5,4.5h15v15h-15V4.5z M6.5,11.5h11v1h-11V11.5z M6.5,14.5h11v1h-11V14.5z"/></svg>', // Placeholder or simple shape
    'hu-berlin': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 3L1 9l4 2.18v6L12 21l7-3.82v-6l2-1.09V17h2V9L12 3z"/></svg>',
    'kit': '<svg viewBox="0 0 263.69 119.5" fill="currentColor"><rect x="0" y="0" width="107.12" height="119.5" fill="#009682"/><path fill="#fff" d="M88.42,88.76L67,61.94L87.26,38h-27l-8.49,12.7L43.89,38h-26l19.59,24.1L16.29,88.76h27l10.32-15.1l10.15,15.1 H88.42z"/><rect x="114.71" y="0" width="37.81" height="119.5" /><polygon points="263.69,0 160.05,0 160.05,30.34 192.42,30.34 192.42,119.5 231.22,119.5 231.22,30.34 263.69,30.34 "/></svg>', // Using KIT green color roughly or currentcolor
    'fraunhofer': '<svg viewBox="0 0 200 60" fill="currentColor"><path d="M27.8 7.3h10v6.4h-10v5.8h8.8v6.4h-8.8v10h-7.6v-28.6zM46.8 19.4c0-2.3 1.2-3.3 4.1-3.3h0.7v6.6h-0.7c-2.7 0-4.1-0.9-4.1-3.3zM46.8 32.1h6.6v3.8h-6.6v-3.8zM66.4 25.1c0 2.4-1.2 3.3-4.1 3.3h-0.7v-6.6h0.7c2.9 0 4.1 1.1 4.1 3.3zM66.4 12.3h-6.6v-3.8h6.6v3.8zM96.7 32.2c0 2.4-1.4 3.7-4.4 3.7h-9.9v-13h9.6c3.1 0 4.7 1.2 4.7 3.6v5.7zM90.3 26.5h-2v3.6h2c0.8 0 1.2-0.3 1.2-1.7v-0.1c0-1.5-0.4-1.8-1.2-1.8zM113.8 32.2c0 2.4-1.4 3.7-4.4 3.7h-9.9v-13h9.6c3.1 0 4.7 1.2 4.7 3.6v5.7zM107.4 26.5h-2v3.6h2c0.8 0 1.2-0.3 1.2-1.7v-0.1c0-1.5-0.4-1.8-1.2-1.8zM130.9 32.2c0 2.4-1.4 3.7-4.4 3.7h-9.9v-13h9.6c3.1 0 4.7 1.2 4.7 3.6v5.7zM124.5 26.5h-2v3.6h2c0.8 0 1.2-0.3 1.2-1.7v-0.1c0-1.5-0.4-1.8-1.2-1.8zM148 32.2c0 2.4-1.4 3.7-4.4 3.7h-9.9v-13h9.6c3.1 0 4.7 1.2 4.7 3.6v5.7zM141.6 26.5h-2v3.6h2c0.8 0 1.2-0.3 1.2-1.7v-0.1c0-1.5-0.4-1.8-1.2-1.8zM153.2 25.1c0 2.4-1.2 3.3-4.1 3.3h-0.7v-6.6h0.7c2.9 0 4.1 1.1 4.1 3.3zM153.2 12.3h-6.6v-3.8h6.6v3.8zM167.3 35.9h-6.6v-28.6h6.6v28.6z"/></svg>', // Simplified Fraunhofer wordmark
    'bundesdruckerei': '<svg viewBox="0 0 283.46 283.46" fill="currentColor"><path d="M141.73,0C63.44,0,0,63.44,0,141.73s63.44,141.73,141.73,141.73s141.73-63.44,141.73-141.73S220.02,0,141.73,0z M193.36,204.09H90.1V79.37h103.26V204.09z"/></svg>', // Placeholder based on generic shape if exact path too complex, or need full path logic. 
    'cmu': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M5 13.18v4L12 21l7-3.82v-4L12 17l-7-3.82zM12 3L1 9l11 6 9-4.91V17h2V9L12 3z"/></svg>',

    // Social & Professional
    'github': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>',
    'linkedin': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z"/></svg>',
    'x': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>',
    'mastodon': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M23.268 5.313c-.35-2.578-2.617-4.61-5.304-5.004C17.51.242 15.792 0 11.813 0h-.03c-3.98 0-4.835.242-5.288.309C3.882.692 1.496 2.518.917 5.127.64 6.412.61 7.837.661 9.143c.074 1.874.088 3.745.26 5.611.118 1.24.325 2.47.62 3.68.55 2.237 2.777 4.098 4.96 4.857 2.336.792 4.849.923 7.256.38.265-.061.527-.132.786-.213.585-.184 1.27-.39 1.774-.753a.057.057 0 0 0 .023-.043v-1.809a.052.052 0 0 0-.02-.041.053.053 0 0 0-.046-.01 20.282 20.282 0 0 1-4.709.545c-2.73 0-3.463-1.284-3.674-1.818a5.593 5.593 0 0 1-.319-1.433.053.053 0 0 1 .066-.054c1.517.363 3.072.546 4.632.546.376 0 .75 0 1.125-.01 1.57-.044 3.224-.124 4.768-.422.038-.008.077-.015.11-.024 2.435-.464 4.753-1.92 4.989-5.604.008-.145.03-1.52.03-1.67.002-.512.167-3.63-.024-5.545zm-3.748 9.195h-2.561V8.29c0-1.309-.55-1.976-1.67-1.976-1.23 0-1.846.79-1.846 2.35v3.403h-2.546V8.663c0-1.56-.617-2.35-1.848-2.35-1.112 0-1.668.668-1.668 1.977v6.218H4.822V8.102c0-1.31.337-2.35 1.011-3.12.696-.77 1.608-1.164 2.74-1.164 1.311 0 2.302.5 2.962 1.498l.638 1.06.638-1.06c.66-.999 1.65-1.498 2.96-1.498 1.13 0 2.043.395 2.74 1.164.675.77 1.012 1.81 1.012 3.12z"/></svg>',
    'xing': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M18.188 0c-.517 0-.741.325-.927.66 0 0-7.455 13.224-7.702 13.657.015.024 4.919 9.023 4.919 9.023.17.308.436.66.967.66h3.454c.211 0 .375-.078.463-.22.089-.151.089-.346-.009-.536l-4.879-8.916c-.004-.006-.004-.016 0-.022L22.139.756c.095-.191.097-.387.006-.535C22.056.078 21.894 0 21.686 0h-3.498zM3.648 4.74c-.211 0-.385.074-.473.216-.09.149-.078.339.02.531l2.34 4.05c.004.01.004.016 0 .021L1.86 16.026c-.099.188-.093.381 0 .529.085.142.239.234.45.234h3.461c.518 0 .766-.348.945-.667l3.734-6.609-2.378-4.155c-.172-.315-.434-.659-.962-.659H3.648v.041z"/></svg>',

    // Academic
    'orcid': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.372 0 0 5.372 0 12s5.372 12 12 12 12-5.372 12-12S18.628 0 12 0zM7.369 4.378c.525 0 .947.431.947.947s-.422.947-.947.947a.95.95 0 0 1-.947-.947c0-.525.422-.947.947-.947zm-.722 3.038h1.444v10.041H6.647V7.416zm3.562 0h3.9c3.712 0 5.344 2.653 5.344 5.025 0 2.578-2.016 5.025-5.325 5.025h-3.919V7.416zm1.444 1.303v7.444h2.297c3.272 0 4.022-2.484 4.022-3.722 0-2.016-1.284-3.722-4.097-3.722h-2.222z"/></svg>',
    'google-scholar': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M5.242 13.769L0 9.5 12 0l12 9.5-5.242 4.269C17.548 11.249 14.978 9.5 12 9.5c-2.977 0-5.548 1.748-6.758 4.269zM12 10a7 7 0 1 0 0 14 7 7 0 0 0 0-14z"/></svg>',
    'researchgate': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M19.586 0c-.818 0-1.508.19-2.073.565-.563.377-.97.936-1.213 1.68a3.193 3.193 0 0 0-.112.437 8.365 8.365 0 0 0-.078.53 9 9 0 0 0-.046.627c-.008.224-.013.46-.013.707v.442a29.97 29.97 0 0 0 .014.566c.007.146.014.284.023.418a7.862 7.862 0 0 0 .054.477c.025.167.054.317.088.453.13.534.327.945.59 1.234.264.288.613.433 1.049.433.251 0 .478-.048.68-.143a1.48 1.48 0 0 0 .523-.4c.142-.169.254-.369.336-.599.081-.23.123-.478.123-.748s-.04-.524-.123-.748a1.701 1.701 0 0 0-.336-.605 1.567 1.567 0 0 0-.523-.405 1.518 1.518 0 0 0-.68-.149c-.151 0-.298.027-.44.08a1.175 1.175 0 0 0-.373.224 1.046 1.046 0 0 0-.263.35 1.084 1.084 0 0 0-.097.448h-1.647c0-.353.077-.667.232-.942.155-.276.36-.508.614-.695.255-.188.548-.33.88-.427.332-.096.683-.144 1.052-.144.501 0 .956.084 1.364.25.408.167.754.4 1.038.697.284.298.502.648.653 1.052.152.403.227.844.227 1.323 0 .574-.098 1.084-.293 1.529-.195.445-.453.82-.774 1.123a3.324 3.324 0 0 1-1.11.703 3.627 3.627 0 0 1-1.295.236c-.323 0-.632-.034-.926-.102a2.882 2.882 0 0 1-.785-.298 2.632 2.632 0 0 1-.627-.488 3.068 3.068 0 0 1-.455-.662 12.97 12.97 0 0 1-.303-.896 16.366 16.366 0 0 1-.217-.97 23.2 23.2 0 0 1-.135-.949 23.84 23.84 0 0 1-.057-.844v-1.91c0-.264.006-.541.017-.829.012-.287.03-.572.054-.853a9.9 9.9 0 0 1 .109-.823 5.372 5.372 0 0 1 .181-.76 3.356 3.356 0 0 1 .276-.648c.1-.18.213-.342.34-.486a1.63 1.63 0 0 1 .428-.358c.169-.099.361-.173.575-.222a3.24 3.24 0 0 1 .718-.074c.501 0 .957.084 1.367.25.41.167.759.4 1.045.697.286.298.506.648.66 1.052.153.403.23.844.23 1.323 0 .574-.082 1.082-.246 1.524-.164.443-.402.82-.713 1.129a3.256 3.256 0 0 1-1.092.715 3.505 3.505 0 0 1-1.39.25 3.488 3.488 0 0 1-.948-.126 2.772 2.772 0 0 1-.78-.355 2.413 2.413 0 0 1-.574-.546 1.879 1.879 0 0 1-.32-.694h-.016zM4.92 17.401H2.88V24h2.04v-6.599zM3.9 12.6c.668 0 1.21.542 1.21 1.21 0 .668-.542 1.21-1.21 1.21-.668 0-1.21-.542-1.21-1.21 0-.668.542-1.21 1.21-1.21z"/></svg>',

    // Documents & Media
    'cv-pdf': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/></svg>',
    'publikationen': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M18 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zM6 4h5v8l-2.5-1.5L6 12V4z"/></svg>',
    'bibliographie': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm16-4H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-1 9H9V9h10v2zm-4 4H9v-2h6v2zm4-8H9V5h10v2z"/></svg>',

    // Other
    'persoenlich': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>',
    'mpi': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>',
    'default': '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M3.9 12c0-1.71 1.39-3.1 3.1-3.1h4V7H7c-2.76 0-5 2.24-5 5s2.24 5 5 5h4v-1.9H7c-1.71 0-3.1-1.39-3.1-3.1zM8 13h8v-2H8v2zm9-6h-4v1.9h4c1.71 0 3.1 1.39 3.1 3.1s-1.39 3.1-3.1 3.1h-4V17h4c2.76 0 5-2.24 5-5s-2.24-5-5-5z"/></svg>'
};

// Profile picture URLs
const PROFILE_PICS = {
    'mueller-birn-claudia': 'https://www.clmb.de/images/clmb-sq.png',
    'prechelt-lutz': 'https://www.mi.fu-berlin.de/en/inf/groups/ag-se/members/_bilder/prechelt.jpg',
    'roth-volker': 'http://www.volkerroth.com/volkerroth-200x200.jpg',
    'reinert-knut': 'https://www.mi.fu-berlin.de/en/inf/groups/abi/members/Professors/_bilder/reinert.jpg',
    'wolter-katinka': 'https://www.mi.fu-berlin.de/en/inf/groups/ag-dds/staff/_bilder/wolter.jpg',
    'landgraf-tim': 'https://www.mi.fu-berlin.de/inf/groups/ag-ki/members/Professoren/_bilder/landgraf.jpg',
    'schiller-jochen': 'https://www.mi.fu-berlin.de/inf/groups/ag-tech/staff/0Current/_bilder/schiller.jpg'
};

// Display labels for links
const LINK_LABELS = {
    'fu-berlin': 'FU Berlin',
    'tu-berlin': 'TU Berlin',
    'hu-berlin': 'HU Berlin',
    'tu-dresden': 'TU Dresden',
    'kit': 'KIT',
    'cmu': 'CMU',
    'github': 'GitHub',
    'linkedin': 'LinkedIn',
    'orcid': 'ORCID',
    'researchgate': 'ResearchGate',
    'cv-pdf': 'CV (PDF)',
    'mpi': 'MPI',
    'persoenlich': 'Persönlich',
    'google-scholar': 'Google Scholar',
    'xing': 'Xing',
    'mastodon': 'Mastodon',
    'x': 'X (Twitter)'
};

class InstitutDiagram {
    constructor() {
        this.data = null;
        this.modal = document.getElementById('detail-modal');
        this.init();
    }

    async init() {
        try {
            await this.loadData();
            this.renderGroups();
            this.setupEventListeners();
            this.drawConnections();
        } catch (error) {
            console.error('Error initializing diagram:', error);
        }
    }

    async loadData() {
        const response = await fetch('research/fu-informatik-data.json');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        this.data = await response.json();
        console.log('Data loaded:', this.data);
    }

    getIcon(key, url) {
        if (ICONS[key]) return ICONS[key];

        // Specific fix for "website" key which isn't in ICONS map but should trigger URL check
        if (url) {
            const lowerUrl = url.toLowerCase();
            if (lowerUrl.includes('fu-berlin.de')) return ICONS['fu-berlin'];
            if (lowerUrl.includes('tu-berlin.de')) return ICONS['tu-berlin'];
            if (lowerUrl.includes('tu-dresden')) return ICONS['tu-dresden'];
            if (lowerUrl.includes('kit.edu')) return ICONS['kit'];
            if (lowerUrl.includes('fraunhofer')) return ICONS['fraunhofer'];
            if (lowerUrl.includes('bundesdruckerei.de')) return ICONS['bundesdruckerei'];
            if (lowerUrl.includes('mpg.de')) return ICONS['mpi'];
        }

        return ICONS['default'];
    }

    renderGroups() {
        const gridContainer = document.getElementById('ag-grid');
        if (!gridContainer) return;

        // Filter only AG groups (not extern)
        const ags = this.data.gruppen.filter(g => g.type === 'ag');

        // Calculate professor count for each AG
        const agsWithCount = ags.map(gruppe => {
            const professors = this.data.personen.filter(p =>
                p.gruppen?.includes(gruppe.id) &&
                p.rolle?.toLowerCase().includes('professor')
            );
            return { gruppe, professorCount: professors.length, professors };
        });

        // Helper to check if AG is inactive
        const isInactive = (g) => g.status === 'unbesetzt' || g.status === 'professor-gewechselt';

        // Sort by active status (active first) then professor count (descending)
        agsWithCount.sort((a, b) => {
            const aInactive = isInactive(a.gruppe);
            const bInactive = isInactive(b.gruppe);

            if (aInactive && !bInactive) return 1;
            if (!aInactive && bInactive) return -1;

            return b.professorCount - a.professorCount;
        });

        // Render each AG card
        agsWithCount.forEach(({ gruppe, professors }) => {
            const card = document.createElement('div');
            card.id = gruppe.id;
            card.className = 'card ag-card';
            card.dataset.groupId = gruppe.id;

            // Mark inactive/vacant AGs
            if (gruppe.status === 'unbesetzt' || gruppe.status === 'professor-gewechselt') {
                card.classList.add('inactive');
            }

            card.innerHTML = `
                <div class="card-header">
                    <h3 class="card-title" title="${gruppe['name-en'] || gruppe.name}">${gruppe.type === 'ag' ? 'AG ' : ''}${gruppe.name}</h3>
                    ${gruppe.abkuerzung ? `<span class="card-abbr">${gruppe.abkuerzung}</span>` : ''}
                </div>
                <div class="card-content">
                    <ul class="member-list">
                        ${professors.map(prof => {
                const simpleTitle = prof.titel && prof.titel.includes('Prof') ? 'Prof.' : prof.titel;
                return `
                            <li class="professor" data-person-id="${prof.id}">
                                ${simpleTitle} ${prof.name}
                            </li>
                            `;
            }).join('')}
                    </ul>
                </div>
            `;

            gridContainer.appendChild(card);
        });
    }

    setupEventListeners() {
        document.querySelectorAll('.card').forEach(card => {
            card.addEventListener('click', (e) => {
                const groupId = card.dataset.groupId;
                if (groupId) {
                    this.showGroupDetail(groupId);
                }
            });
        });

        document.querySelectorAll('.member-list li').forEach(li => {
            li.addEventListener('click', (e) => {
                e.stopPropagation();
                const personId = li.dataset.personId;
                if (personId) {
                    this.showPersonDetail(personId);
                }
            });
        });

        this.modal.querySelector('.modal-close').addEventListener('click', () => {
            this.closeModal();
        });

        this.modal.querySelector('.modal-backdrop').addEventListener('click', () => {
            this.closeModal();
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeModal();
            }
        });
    }

    showGroupDetail(groupId) {
        const gruppe = this.data.gruppen.find(g => g.id === groupId);
        if (!gruppe) return;

        const members = this.data.personen.filter(p => p.gruppen?.includes(groupId));

        // Categorize members
        const professors = members.filter(m => m.rolle?.toLowerCase().includes('professor'));
        const sekretariat = members.filter(m =>
            m.rolle?.toLowerCase().includes('sekret') ||
            m.rolle?.toLowerCase().includes('assistant') ||
            m.rolle?.toLowerCase().includes('projektassist')
        );
        const wimis = members.filter(m =>
            m.rolle?.toLowerCase().includes('wissenschaftl') ||
            m.rolle?.toLowerCase().includes('mitarbeiter') ||
            m.rolle?.toLowerCase().includes('doktorand')
        ).filter(m => !professors.includes(m) && !sekretariat.includes(m));

        const modalTitle = this.modal.querySelector('.modal-title');
        const modalSubtitle = this.modal.querySelector('.modal-subtitle');
        const modalAvatar = this.modal.querySelector('.modal-avatar');
        const modalGroups = this.modal.querySelector('.modal-groups');
        const modalBody = this.modal.querySelector('.modal-body');

        modalTitle.textContent = gruppe.name;

        // Compact Subtitle with Website
        let subtitleHtml = gruppe['name-en'] || '';
        if (gruppe.website) {
            const icon = this.getIcon('website', gruppe.website);
            subtitleHtml += ` <span style="opacity:0.5">|</span> <a href="${gruppe.website}" target="_blank" style="display:inline-flex;align-items:center;gap:4px;">${icon} Website</a>`;
        }
        modalSubtitle.innerHTML = subtitleHtml;

        modalAvatar.style.display = 'none';
        modalGroups.innerHTML = '';

        let html = '';

        // Website - REMOVED (Moved to Header)

        // Member grid
        html += '<div class="ag-modal-grid">';

        // Professors (left)
        html += '<div class="professors"><h4>Professoren</h4>';
        professors.forEach(prof => {
            const pic = prof.profilbild;
            html += `
                <div class="member-card" data-person-id="${prof.id}">
                    ${pic ? `<img class="member-avatar" src="${pic}" alt="${prof.name}">` : `<div class="member-avatar placeholder">${prof.name.charAt(0)}</div>`}
                    <div class="member-info">
                        <div class="member-name">${prof.titel} ${prof.name}</div>
                        <div class="member-role">${prof.rolle || 'Professor'}</div>
                    </div>
                </div>
            `;
        });
        html += '</div>';

        // Sekretariat (right)
        html += '<div class="sekretariat"><h4>Sekretariat</h4>';
        if (sekretariat.length > 0) {
            sekretariat.forEach(sek => {
                const pic = sek.profilbild;
                html += `
                    <div class="member-card" data-person-id="${sek.id}">
                         ${pic ? `<img class="member-avatar" src="${pic}" alt="${sek.name}">` : `<div class="member-avatar placeholder">${sek.name.charAt(0)}</div>`}
                        <div class="member-info">
                            <div class="member-name">${sek.titel || ''} ${sek.name}</div>
                            <div class="member-role">${sek.rolle || 'Sekretariat'}</div>
                        </div>
                    </div>
                `;
            });
        } else {
            html += '<p style="color: var(--text-muted); font-size: 0.875rem;">Keine Daten</p>';
        }
        html += '</div>';

        // WiMis (bottom)
        if (wimis.length > 0) {
            html += '<div class="wimis"><h4>Wissenschaftliche Mitarbeiter</h4><div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">';
            wimis.forEach(wimi => {
                const pic = wimi.profilbild;
                html += `
                    <div class="member-card" data-person-id="${wimi.id}" style="flex: 1; min-width: 220px;">
                        ${pic ? `<img class="member-avatar" src="${pic}" alt="${wimi.name}">` : `<div class="member-avatar placeholder">${wimi.name.charAt(0)}</div>`}
                        <div class="member-info">
                            <div class="member-name">${wimi.titel || ''} ${wimi.name}</div>
                            <div class="member-role">${wimi.rolle || 'WiMi'}</div>
                        </div>
                    </div>
                `;
            });
            html += '</div></div>';
        }

        html += '</div>'; // close ag-modal-grid

        // External connections
        if (gruppe.verbindungen?.length > 0) {
            html += '<h4>Kooperationen</h4><div class="link-list">';
            gruppe.verbindungen.forEach(vid => {
                const partner = this.data.gruppen.find(g => g.id === vid);
                if (partner) {
                    html += `<a href="${partner.website || '#'}" target="_blank">${this.getIcon('mpi')} ${partner.name}</a>`;
                }
            });
            html += '</div>';
        }

        modalBody.innerHTML = html;

        modalBody.querySelectorAll('[data-person-id]').forEach(el => {
            el.addEventListener('click', (e) => {
                e.stopPropagation();
                this.showPersonDetail(el.dataset.personId);
            });
        });

        this.openModal();
    }

    showPersonDetail(personId) {
        const person = this.data.personen.find(p => p.id === personId);
        if (!person) return;

        const modalTitle = this.modal.querySelector('.modal-title');
        const modalSubtitle = this.modal.querySelector('.modal-subtitle');
        const modalAvatar = this.modal.querySelector('.modal-avatar');
        const modalAvatarPlaceholder = this.modal.querySelector('.modal-avatar-placeholder');
        const modalGroups = this.modal.querySelector('.modal-groups');
        const modalBody = this.modal.querySelector('.modal-body');

        const agNames = [];
        if (person.gruppen?.length > 0) {
            person.gruppen.forEach(gid => {
                const gruppe = this.data.gruppen.find(g => g.id === gid);
                if (gruppe) {
                    agNames.push(gruppe.type === 'ag' ? `AG ${gruppe.name}` : gruppe.name);
                }
            });
        }

        modalTitle.textContent = `${person.titel} ${person.name}`;
        modalSubtitle.textContent = person.rolle ? `${person.rolle}${agNames.length > 0 ? ', ' + agNames.join(', ') : ''}` : '';

        // Avatar
        if (person.profilbild) {
            modalAvatar.src = person.profilbild;
            modalAvatar.style.display = 'block';
            if (modalAvatarPlaceholder) modalAvatarPlaceholder.style.display = 'none';
        } else {
            modalAvatar.style.display = 'none';
            if (modalAvatarPlaceholder) {
                modalAvatarPlaceholder.textContent = person.name.charAt(0);
                modalAvatarPlaceholder.style.display = 'flex';
            }
        }

        // Groups under name - CLEARED
        modalGroups.innerHTML = '';

        let html = '';

        // Contact
        if (person.kontakt) {
            html += '<h4>Kontakt</h4>';
            if (person.kontakt.email) {
                html += `<p>📧 <a href="mailto:${person.kontakt.email}">${person.kontakt.email}</a></p>`;
            }
            if (person.kontakt.telefon) {
                html += `<p>📞 ${person.kontakt.telefon}</p>`;
            }
            if (person.kontakt.sprechstunde) {
                if (person.kontakt.sprechstunde.startsWith('http')) {
                    html += `<p>🕐 <a href="${person.kontakt.sprechstunde}" target="_blank">Sprechstunde buchen</a></p>`;
                } else {
                    html += `<p>🕐 ${person.kontakt.sprechstunde}</p>`;
                }
            }
        }

        // Links with SVG icons
        if (person.links) {
            html += '<h4>Links</h4><div class="link-list">';
            for (const [key, url] of Object.entries(person.links)) {
                const icon = this.getIcon(key, url);
                const label = LINK_LABELS[key] || key.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                html += `<a href="${url}" target="_blank">${icon} ${label}</a>`;
            }
            html += '</div>';
        }

        // Research
        if (person.forschung?.interessen?.length > 0) {
            html += '<h4>Forschungsinteressen</h4><p>';
            html += person.forschung.interessen.join(', ');
            html += '</p>';
        }

        // Vita with icons
        if (person.vita?.positionen?.length > 0) {
            html += '<h4>Werdegang</h4><ul class="vita-list">';
            person.vita.positionen.forEach(pos => {
                let icon = this.getIcon('fu-berlin');
                if (pos.toLowerCase().includes('tu ')) icon = this.getIcon('tu-berlin');
                if (pos.toLowerCase().includes('cmu') || pos.toLowerCase().includes('carnegie')) icon = this.getIcon('cmu');
                if (pos.toLowerCase().includes('kit') || pos.toLowerCase().includes('karlsruhe')) icon = this.getIcon('kit');
                html += `<li>${icon} ${pos}</li>`;
            });
            html += '</ul>';
        }

        // Awards
        if (person.auszeichnungen?.length > 0) {
            html += '<h4>Auszeichnungen</h4><ul style="color: var(--text-secondary); font-size: 0.875rem;">';
            person.auszeichnungen.forEach(award => {
                html += `<li style="margin: 4px 0;">🏆 ${award.jahr}: ${award.name}</li>`;
            });
            html += '</ul>';
        }

        // Teaching
        if (person.lehre?.kurse?.length > 0) {
            html += '<h4>Lehrveranstaltungen</h4><ul style="color: var(--text-secondary); font-size: 0.875rem;">';
            person.lehre.kurse.slice(0, 5).forEach(kurs => {
                html += `<li style="margin: 4px 0;">📚 ${kurs.name} (${kurs.semester})</li>`;
            });
            if (person.lehre.kurse.length > 5) {
                html += `<li style="color: var(--text-muted);">... und ${person.lehre.kurse.length - 5} weitere</li>`;
            }
            html += '</ul>';
        }

        modalBody.innerHTML = html;
        this.openModal();
    }

    openModal() {
        this.modal.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    }

    closeModal() {
        this.modal.classList.add('hidden');
        document.body.style.overflow = '';
    }

    drawConnections() {
        const svg = document.getElementById('connection-lines');
        if (!svg) return;
        svg.innerHTML = '';

        this.data.verbindungen?.forEach(conn => {
            const fromEl = document.getElementById(conn.von);
            const toEl = document.getElementById(conn.zu);

            if (fromEl && toEl) {
                const fromRect = fromEl.getBoundingClientRect();
                const toRect = toEl.getBoundingClientRect();
                const containerRect = document.querySelector('.diagram-container').getBoundingClientRect();

                const x1 = fromRect.left + fromRect.width / 2 - containerRect.left;
                const y1 = fromRect.top + fromRect.height / 2 - containerRect.top;
                const x2 = toRect.left + toRect.width / 2 - containerRect.left;
                const y2 = toRect.top + toRect.height / 2 - containerRect.top;

                const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                line.setAttribute('x1', x1);
                line.setAttribute('y1', y1);
                line.setAttribute('x2', x2);
                line.setAttribute('y2', y2);
                svg.appendChild(line);
            }
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.diagram = new InstitutDiagram();
});

window.addEventListener('resize', () => {
    clearTimeout(window.resizeTimeout);
    window.resizeTimeout = setTimeout(() => {
        window.diagram?.drawConnections();
    }, 250);
});
