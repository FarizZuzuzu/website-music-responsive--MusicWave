// === GLOBAL VARIABLES ===
const toggleBtn = document.getElementById("toggleBtn");
const sidebar = document.getElementById("sidebar");
const overlay = document.getElementById("overlay");
const profileBtn = document.getElementById("profileBtn");
const profileDropdown = document.getElementById("profileDropdown");

// Music Player Variables - GLOBAL PERSISTENT
let globalAudio = null;
let currentTrack = null;
let isPlaying = false;
let currentTime = 0;
let duration = 0;
let playQueue = [];
let playQueueIndex = -1;

function updatePlayerControls() {
  const playing = Boolean(globalAudio && !globalAudio.paused && !globalAudio.ended);
  const icon = playing ? 'fa-pause' : 'fa-play';
  ['playPauseBtn', 'detailPlayPauseBtn'].forEach((id) => {
    const button = document.getElementById(id);
    if (button) button.innerHTML = `<i class="fa-solid ${icon}"></i>`;
  });
}

function syncFullPlayerView(track) {
  const songPage = document.getElementById('songPage');
  if (!songPage || !track || !track.id) return;
  if (String(songPage.dataset.songId) === String(track.id)) return;

  const songUrl = `/song/${encodeURIComponent(track.id)}`;
  if (typeof loadPageViaAjax === 'function') {
    loadPageViaAjax(songUrl);
  }
}

function playTrackData(track) {
  if (!globalAudio || !track || !track.audio) return;

  currentTrack = track;
  globalAudio.src = track.audio;
  globalAudio.currentTime = 0;

  const playerBar = document.getElementById('musicPlayer');
  const playerCover = document.getElementById('playerCover');
  const playerTitle = document.getElementById('playerTitle');
  const playerArtist = document.getElementById('playerArtist');
  if (playerBar) playerBar.classList.add('active');
  if (playerCover) playerCover.src = track.cover;
  if (playerTitle) playerTitle.textContent = track.title;
  if (playerArtist) playerArtist.textContent = track.artist;
  syncFullPlayerView(track);

  globalAudio.play().catch(() => {
    isPlaying = false;
    updatePlayerControls();
  });
  isPlaying = true;
  updatePlayerControls();
  savePlayerState();
}

function getTrackData(trackElement) {
  const titleEl = trackElement.querySelector('h4, h3, .track-title, .search-track-title');
  const artistEl = trackElement.querySelector('p:not(.small), .track-artist, .search-track-artist');
  const coverEl = trackElement.querySelector('img');
  return {
    id: trackElement.getAttribute('data-id'),
    title: titleEl ? titleEl.textContent.trim() : 'Unknown',
    artist: artistEl ? artistEl.textContent.trim() : 'Unknown',
    cover: coverEl ? coverEl.src : '/static/assets/img/default_cover.jpg',
    audio: trackElement.getAttribute('data-audio')
  };
}

// Initialize global audio on page load
function initGlobalAudio() {
  globalAudio = document.getElementById('globalAudioPlayer');
  console.log('🎵 initGlobalAudio called');
  console.log('🎵 globalAudio element found:', !!globalAudio);
  
  if (!globalAudio) {
    console.warn('🎵 globalAudioPlayer not found, creating fallback...');
    // Fallback: create if doesn't exist
    globalAudio = new Audio();
    globalAudio.id = 'globalAudioPlayer';
    globalAudio.crossOrigin = 'anonymous';
    document.body.appendChild(globalAudio);
  }
  restorePlayerState();
}

// Save player state to localStorage
function savePlayerState() {
  if (currentTrack && globalAudio) {
    const state = {
      track: currentTrack,
      position: globalAudio.currentTime || 0,
      isPlaying: !globalAudio.paused
    };
    try {
      localStorage.setItem('musicwave_player', JSON.stringify(state));
    } catch (e) {
      console.log('localStorage error:', e);
    }
  }
}

// Restore player state from localStorage
function restorePlayerState() {
  if (!globalAudio) return;
  try {
    const saved = localStorage.getItem('musicwave_player');
    if (saved) {
      const state = JSON.parse(saved);
      currentTrack = state.track;
      
      if (currentTrack && currentTrack.audio) {
        globalAudio.src = currentTrack.audio;
        globalAudio.currentTime = state.position || 0;
        
        // Update UI
        const playerBar = document.getElementById('musicPlayer');
        const playerCover = document.getElementById('playerCover');
        const playerTitle = document.getElementById('playerTitle');
        const playerArtist = document.getElementById('playerArtist');
        const playPauseBtn = document.getElementById('playPauseBtn');
        
        if (playerCover) playerCover.src = currentTrack.cover;
        if (playerTitle) playerTitle.textContent = currentTrack.title;
        if (playerArtist) playerArtist.textContent = currentTrack.artist;
        
        // Auto-resume if was playing
        if (state.isPlaying) {
          globalAudio.play().catch(() => {
            console.log('Auto-play blocked - user interaction required');
          });
          if (playPauseBtn) playPauseBtn.innerHTML = '<i class="fa-solid fa-pause"></i>';
          isPlaying = true;
        }
      }
    }
  } catch (e) {
    console.error('Error restoring state:', e);
  }
}

// Format time display
function formatTime(seconds) {
  if (!seconds || isNaN(seconds)) return '0:00';
  const min = Math.floor(seconds / 60);
  const sec = Math.floor(seconds % 60);
  return `${min}:${sec < 10 ? '0' : ''}${sec}`;
}

// Global play function - main entry point for playing music
function playTrackGlobal(trackElement) {
  console.log('🎵 playTrackGlobal called');
  
  if (!trackElement || !globalAudio) {
    console.error('🎵 Missing trackElement or globalAudio');
    return;
  }
  
  // Get track info and preserve the visible list as the playback queue.
  const track = getTrackData(trackElement);
  const audioSrc = track.audio;
  const trackId = track.id;
  
  if (!audioSrc) {
    alert('Audio tidak tersedia untuk lagu ini');
    return;
  }

  const isSameTrack = currentTrack
    && String(currentTrack.id) === String(trackId)
    && globalAudio.src === new URL(audioSrc, window.location.href).href;

  if (isSameTrack) {
    if (globalAudio.paused) {
      globalAudio.play().catch(() => {});
    }
    isPlaying = true;
    updatePlayerControls();
    return;
  }
  
  const title = track.title;
  const artist = track.artist;
  const cover = track.cover;

  const queueElements = Array.from(document.querySelectorAll('.music-item[data-audio], .track-item[data-audio], .music-card[data-audio]'));
  playQueue = queueElements.map(getTrackData).filter(queueTrack => queueTrack.audio);
  playQueueIndex = playQueue.findIndex(queueTrack => String(queueTrack.id) === String(trackId));
  currentTrack = track;
  
  // Set global audio source and play
  globalAudio.src = audioSrc;
  globalAudio.currentTime = 0;
  
  globalAudio.play().catch(e => {
    console.error('Play error:', e);
    isPlaying = false;
    updatePlayerControls();
  });
  
  // Update UI
  const playerBar = document.getElementById('musicPlayer');
  const playerCover = document.getElementById('playerCover');
  const playerTitle = document.getElementById('playerTitle');
  const playerArtist = document.getElementById('playerArtist');
  const playPauseBtn = document.getElementById('playPauseBtn');
  
  if (playerBar) playerBar.classList.add('active');
  if (playerCover) playerCover.src = cover;
  if (playerTitle) playerTitle.textContent = title;
  if (playerArtist) playerArtist.textContent = artist;
  syncFullPlayerView(track);
  isPlaying = true;
  updatePlayerControls();
  
  // Track play count
  if (trackId) {
    const isPodcast = trackElement.getAttribute('data-type') === 'podcast';
    fetch(`/play/${isPodcast ? 'podcast' : 'song'}/${trackId}`).catch(() => {});
  }
  
  savePlayerState();
}

// Attach click handlers to music items
function attachMusicListeners() {
  document.querySelectorAll('.music-item, .music-card, .track-item').forEach(item => {
    // Remove existing listener by cloning
    if (item.dataset.listenerAttached) return;
    
    item.addEventListener('click', function(e) {
      // Skip if clicking buttons
      if (e.target.closest('button, .music-actions, .track-actions, .context-menu, .add-track-btn, .profile-song-actions')) return;
      playTrackGlobal(item);
    });
    
    item.dataset.listenerAttached = 'true';
  });
}

document.addEventListener('click', function(e) {
  const menuToggle = e.target.closest('.profile-song-menu-toggle');
  if (menuToggle) {
    e.preventDefault();
    e.stopPropagation();
    document.querySelectorAll('.profile-song-menu-wrapper.open').forEach((menu) => {
      if (menu !== menuToggle.parentElement) menu.classList.remove('open');
    });
    menuToggle.parentElement.classList.toggle('open');
    return;
  }

  if (!e.target.closest('.profile-song-menu-wrapper')) {
    document.querySelectorAll('.profile-song-menu-wrapper.open').forEach((menu) => {
      menu.classList.remove('open');
    });
  }
});

document.addEventListener('click', function(e) {
  const playLikedSongsButton = e.target.closest('#playLikedSongs');
  if (!playLikedSongsButton) return;

  e.preventDefault();
  e.stopPropagation();
  const firstTrack = document.querySelector('#likedTracksList .music-item[data-audio]');
  if (firstTrack) playTrackGlobal(firstTrack);
}, true);

// === LIKE SONG FUNCTIONALITY ===
async function toggleLikeSong(songId) {
  try {
    const response = await fetch(`/api/like-song/${songId}`, {
      method: 'POST'
    });
    
    const data = await response.json();
    
    if (data.success) {
      // Update UI - toggle like button
      const likeBtn = document.querySelector(`[data-song-id="${songId}"] .like-btn, 
                                            [data-id="${songId}"] .like-btn,
                                            .music-detail-modal .like-btn,
                                            #songPageLike`);
      
      if (likeBtn) {
        if (data.liked) {
          likeBtn.classList.add('active');
          likeBtn.innerHTML = '<i class="fa-solid fa-heart"></i>';
        } else {
          likeBtn.classList.remove('active');
          likeBtn.innerHTML = '<i class="fa-regular fa-heart"></i>';
        }
      }
      
      showNotification(data.message, 'success');
      return data;
    } else {
      showNotification('Gagal mengubah status like', 'error');
    }
  } catch (error) {
    console.error('Like error:', error);
    showNotification('Gagal mengubah status like', 'error');
    return null;
  }
}

// Check if song is liked
async function checkIfLiked(songId) {
  try {
    const response = await fetch(`/api/is-liked/${songId}`);
    const data = await response.json();
    return data.liked;
  } catch (error) {
    console.error('Check like error:', error);
    return false;
  }
}

// === ADD TO PLAYLIST FUNCTIONALITY ===
async function showAddToPlaylistModal(songId) {
  try {
    // Fetch playlists
    const response = await fetch(`/api/playlists`);
    const data = await response.json();
    
    if (!data.playlists || data.playlists.length === 0) {
      showNotification('Anda belum memiliki playlist. Buat playlist terlebih dahulu!', 'warning');
      return;
    }
    
    // Create modal
    const modal = document.createElement('div');
    modal.className = 'add-to-playlist-modal modal-overlay';
    modal.innerHTML = `
      <div class="modal-content">
        <h3>Tambah ke Playlist</h3>
        <div class="playlist-list">
          ${data.playlists.map(p => `
            <div class="playlist-item" data-playlist-id="${p.id}">
              <img src="${p.cover_file || '/static/assets/img/default_cover.jpg'}" alt="${p.name}">
              <div class="playlist-info">
                <h4>${p.name}</h4>
                <p>${p.song_count || 0} lagu</p>
              </div>
            </div>
          `).join('')}
        </div>
        <button class="close-btn">✕</button>
      </div>
    `;
    
    document.body.appendChild(modal);
    
    // Handle clicks
    modal.querySelectorAll('.playlist-item').forEach(item => {
      item.addEventListener('click', async () => {
        const playlistId = item.dataset.playlistId;
        await addSongToPlaylist(songId, playlistId);
        modal.remove();
      });
    });
    
    modal.querySelector('.close-btn').addEventListener('click', () => modal.remove());
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.remove();
    });
    
  } catch (error) {
    console.error('Add to playlist error:', error);
    showNotification('Gagal memuat playlist', 'error');
  }
}

// Add song to playlist
async function addSongToPlaylist(songId, playlistId) {
  try {
    const response = await fetch(`/api/playlist/${playlistId}/add-song/${songId}`, {
      method: 'POST'
    });
    
    const data = await response.json();
    
    if (data.success) {
      showNotification(data.message || '✅ Lagu ditambahkan ke playlist', 'success');
    } else {
      showNotification(data.message || 'Gagal menambahkan lagu', 'error');
    }
  } catch (error) {
    console.error('Add song error:', error);
    showNotification('Gagal menambahkan lagu', 'error');
  }
}

// Show notification
function showNotification(message, type = 'info') {
  const notification = document.createElement('div');
  notification.className = `notification notification-${type}`;
  notification.textContent = message;
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    background: ${type === 'success' ? '#22c55e' : type === 'error' ? '#ef4444' : '#3b82f6'};
    color: white;
    padding: 12px 24px;
    border-radius: 8px;
    z-index: 10000;
    animation: slideIn 0.3s ease;
  `;
  
  document.body.appendChild(notification);
  
  setTimeout(() => {
    notification.style.animation = 'slideOut 0.3s ease';
    setTimeout(() => notification.remove(), 300);
  }, 3000);
}

// Setup global audio event listeners
function setupGlobalAudioListeners() {
  if (!globalAudio) return;

  const syncSongPagePlayButton = () => {
    const page = document.getElementById('songPage');
    const playButton = document.getElementById('songPagePlay');
    if (!page || !playButton) return;

    const isCurrentSong = currentTrack && String(currentTrack.id) === String(page.dataset.songId);
    const playing = isCurrentSong && !globalAudio.paused && !globalAudio.ended;
    playButton.innerHTML = playing
      ? '<i class="fa-solid fa-pause"></i><span>Jeda lagu</span>'
      : '<i class="fa-solid fa-play"></i><span>Putar lagu</span>';
  };

  globalAudio.addEventListener('play', () => {
    isPlaying = true;
    updatePlayerControls();
    syncSongPagePlayButton();
  });

  globalAudio.addEventListener('pause', () => {
    isPlaying = false;
    updatePlayerControls();
    syncSongPagePlayButton();
  });
  
  // Time update
  globalAudio.addEventListener('timeupdate', () => {
    duration = globalAudio.duration || 0;
    const progressFill = document.querySelector('.progress-fill');
    if (progressFill) {
      const percent = duration > 0
        ? (globalAudio.currentTime / duration) * 100
        : 0;
      progressFill.style.width = `${Math.min(100, Math.max(0, percent))}%`;
    }
    updateTimeDisplay();
    syncLyricsToAudio();
  });
  
  // When song ends
  globalAudio.addEventListener('ended', () => {
    isPlaying = false;
    updatePlayerControls();
    syncSongPagePlayButton();
    playNextTrack();
  });
  
  // Auto-save state every 2 seconds
  setInterval(() => {
    if (isPlaying && currentTrack) {
      savePlayerState();
    }
  }, 2000);
  
  // Save before leaving page
  window.addEventListener('beforeunload', () => {
    if (currentTrack && globalAudio) {
      savePlayerState();
    }
  });
}

function initializeSyncedLyrics() {
  const lyricsContainer = document.querySelector('.song-page-lyrics');
  if (!lyricsContainer || lyricsContainer.dataset.synced === 'true') return;

  const timestampPattern = /\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]/g;
  const sourceLines = Array.from(lyricsContainer.querySelectorAll('p'));
  const timedLines = [];

  sourceLines.forEach((line) => {
    const text = line.textContent.trim();
    const timestamps = [...text.matchAll(timestampPattern)];
    if (!timestamps.length) return;

    const lyricText = text.replace(timestampPattern, '').trim();
    timestamps.forEach((match) => {
      const fraction = match[3] ? Number(`0.${match[3]}`) : 0;
      const lyricLine = document.createElement('p');
      lyricLine.dataset.time = String(Number(match[1]) * 60 + Number(match[2]) + fraction);
      lyricLine.textContent = lyricText;
      timedLines.push(lyricLine);
    });
  });

  if (!timedLines.length) return;

  timedLines.sort((firstLine, secondLine) => Number(firstLine.dataset.time) - Number(secondLine.dataset.time));

  lyricsContainer.replaceChildren(...timedLines);
  lyricsContainer.dataset.synced = 'true';
  syncLyricsToAudio();
}

function syncLyricsToAudio() {
  const lyricsContainer = document.querySelector('.song-page-lyrics[data-synced="true"]');
  if (!lyricsContainer || !globalAudio) return;

  const lines = Array.from(lyricsContainer.querySelectorAll('p[data-time]'));
  let activeIndex = -1;
  lines.forEach((line, index) => {
    if (globalAudio.currentTime >= Number(line.dataset.time)) activeIndex = index;
  });

  if (activeIndex === Number(lyricsContainer.dataset.activeIndex)) return;
  lines.forEach((line, index) => line.classList.toggle('active', index === activeIndex));
  lyricsContainer.dataset.activeIndex = String(activeIndex);

  if (activeIndex >= 0) {
    lines[activeIndex].scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

// === AJAX NAVIGATION TO PREVENT AUDIO ELEMENT RECREATION ===
function initAjaxNavigation() {
  // Add click handlers ke semua navigation links
  document.addEventListener('click', function(e) {
    const link = e.target.closest('a[href*="/"]');
    
    // Skip jika: external link, #anchor, download, atau special attributes
    if (!link || link.target === '_blank' || link.hostname !== window.location.hostname) return;
    if (link.getAttribute('href').startsWith('#')) return;
    if (link.download) return;
    
    // Skip jika ada special data attributes yang require full reload
    if (link.getAttribute('data-no-ajax') === 'true') return;
    
    // Skip auth pages - mereka handle login/redirect
    const href = link.getAttribute('href');
    if (href.includes('/login') || href.includes('/register') || href.includes('/logout')) {
      return; // Let normal navigation happen
    }
    
    // Check jika link adalah navigation (bukan action buttons)
    if (link.closest('.music-actions, .add-track-btn, .action-btn, .like, .play')) return;
    
    // Semua link lainnya pakai AJAX
    e.preventDefault();
    loadPageViaAjax(href);
  });
  
  // Handle form submissions via AJAX (untuk add playlist, add podcast, etc)
  document.addEventListener('submit', function(e) {
    const form = e.target;
    
    // Skip jika form punya data-no-ajax
    if (form.getAttribute('data-no-ajax') === 'true') return;
    
    // Handle ALL POST forms via AJAX (including file uploads)
    if (form.method.toUpperCase() === 'POST' || form.method === '') {
      e.preventDefault();
      submitFormViaAjax(form);
    }
  });
}

// Submit form via AJAX
async function submitFormViaAjax(form) {
  try {
    document.body.classList.add('page-loading');
    
    const formData = new FormData(form);
    const response = await fetch(form.action || window.location.href, {
      method: form.method || 'POST',
      body: formData,
      headers: {
        'X-Requested-With': 'XMLHttpRequest'
      }
    });
    
    const html = await response.text();
    
    // Parse response
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    const newMain = doc.querySelector('main');
    const oldMain = document.querySelector('main');
    
    if (newMain && oldMain) {
      oldMain.innerHTML = newMain.innerHTML;
      document.title = doc.title;
      
      // Re-attach listeners
      attachMusicListeners();
      initializeSearch();
      if (document.querySelector('.playlist-hero')) {
        initializePlaylistFeatures();
      }
      
      // Update URL jika response redirected
      window.history.pushState({ path: form.action }, '', form.action || window.location.href);
      window.scrollTo(0, 0);
      
      console.log('✅ Form submitted via AJAX');
    }
  } catch (error) {
    console.error('❌ Form submission error:', error);
    form.submit(); // Fallback
  } finally {
    document.body.classList.remove('page-loading');
  }
}

// Load halaman via AJAX tanpa full reload
async function loadPageViaAjax(url) {
  try {
    document.body.classList.add('page-loading');
    
    // Fetch halaman
    const response = await fetch(url);
    const html = await response.text();
    
    // Parse HTML
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    
    // Extract konten utama
    const newMain = doc.querySelector('main');
    const oldMain = document.querySelector('main');
    
    if (newMain && oldMain) {
      document.body.classList.remove('song-detail-active');
      // Replace main content (audio element stays in body)
      oldMain.innerHTML = newMain.innerHTML;
      
      // Update page title
      document.title = doc.title;
      
      // Update sidebar active state
      updateSidebarActiveState(url);
      initializeProfilePage();
      initializeSongPage();
      
      // Re-attach music listeners ke content baru
      attachMusicListeners();
      
      // Re-initialize features jika ada
      if (document.querySelector('.playlist-hero')) {
        initializePlaylistFeatures();
      }
      
      // Re-initialize explore tabs jika ada
      if (document.querySelector('.tab-button')) {
        initializeExploreTabs();
      }
      
      // Re-initialize search jika ada
      initializeSearch();
      
      // Dispatch event untuk liked songs handlers
      if (url.includes('/liked-songs')) {
        setTimeout(() => {
          document.dispatchEvent(new Event('likedSongsLoaded'));
        }, 100);
      }
      
      // Update browser history
      window.history.pushState({ path: url }, '', url);
      
      // Scroll ke top
      window.scrollTo(0, 0);
      
      console.log('✅ Page loaded via AJAX - audio element preserved!');
    }
  } catch (error) {
    console.error('❌ AJAX navigation error:', error);
    // Fallback ke normal navigation
    window.location.href = url;
  } finally {
    document.body.classList.remove('page-loading');
  }
}

// Update sidebar active state based on current URL
function updateSidebarActiveState(url) {
  // Remove active dari semua menu items
  document.querySelectorAll('.sidebar .menu li').forEach(li => {
    li.classList.remove('active');
  });
  
  // Map URL patterns to menu item IDs
  const urlPatterns = {
    'menu-dashboard': ['/', '/index'],
    'menu-library': ['/library', '/playlists', '/liked-songs'],
    'menu-explore': ['/explore', '/genre'],
    'menu-settings': ['/settings'],
    'menu-admin-songs': ['/admin/songs'],
    'menu-admin-podcasts': ['/admin/podcasts'],
    'menu-admin-artists': ['/admin/artists']
  };
  
  // Main pages list
  const mainPages = ['/', '/index', '/library', '/playlists', '/liked-songs', '/explore', '/genre', '/settings', '/admin/songs', '/admin/podcasts', '/admin/artists'];
  
  // Get current path
  const urlObj = new URL(url, window.location.origin);
  const pathname = urlObj.pathname;
  
  // Check if current page is a main page or secondary page
  const isMainPage = mainPages.some(page => {
    if (page === '/') {
      return pathname === '/' || pathname === '/index.html';
    }
    return pathname.includes(page);
  });
  
  const sidebar = document.querySelector('.sidebar');
  if (isMainPage) {
    sidebar.classList.remove('secondary-page');
  } else {
    sidebar.classList.add('secondary-page');
  }
  
  // Find matching menu item
  Object.entries(urlPatterns).forEach(([menuId, patterns]) => {
    const menuItem = document.getElementById(menuId);
    if (!menuItem) return;
    
    const matches = patterns.some(pattern => {
      if (pattern === '/') {
        return pathname === '/' || pathname === '/index.html';
      }
      return pathname.includes(pattern);
    });
    
    if (matches) {
      menuItem.classList.add('active');
      console.log(`✅ Sidebar active state updated to: ${menuId}`);
    }
  });
}

function initializeProfilePage() {
  const editProfileBtn = document.getElementById('editProfileBtn');
  const editProfileModal = document.getElementById('editProfileModal');
  const editProfileForm = document.getElementById('editProfileForm');

  if (!editProfileBtn || !editProfileModal || editProfileBtn.dataset.initialized) return;
  editProfileBtn.dataset.initialized = 'true';

  const closeModal = (resetForm = true) => {
    if (resetForm) {
      editProfileForm.reset();
      document.getElementById('removeAvatar').value = '0';
      document.querySelector('.file-upload-label span').textContent = 'Pilih Foto';
    }
    editProfileModal.style.display = 'none';
  };
  editProfileBtn.addEventListener('click', () => { editProfileModal.style.display = 'flex'; });
  document.getElementById('modalClose')?.addEventListener('click', closeModal);
  document.getElementById('cancelEdit')?.addEventListener('click', closeModal);
  editProfileModal.addEventListener('click', (event) => {
    if (event.target === editProfileModal) closeModal();
  });

  document.getElementById('avatar')?.addEventListener('change', (event) => {
    const file = event.target.files[0];
    const label = document.querySelector('.file-upload-label span');
    if (file && label) {
      label.textContent = file.name;
      document.getElementById('removeAvatar').value = '0';
    }
  });

  document.getElementById('removeAvatarBtn')?.addEventListener('click', () => {
    document.getElementById('removeAvatar').value = '1';
    document.getElementById('avatar').value = '';
    document.querySelector('.file-upload-label span').textContent = 'Foto akan dihapus';
  });

  editProfileForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
      const response = await fetch(editProfileForm.action, {
        method: 'POST',
        body: new FormData(editProfileForm)
      });
      const data = await response.json();
      if (!response.ok || !data.success) {
        showNotification(data.message || 'Gagal menyimpan profile', 'error');
        return;
      }

      showNotification(data.message, 'success');
      document.querySelector('.user-profile__name').textContent = data.user.full_name;
      document.querySelector('.user-profile__username').textContent = '@' + data.user.username;
      const bioElement = document.querySelector('.user-profile__bio');
      if (data.user.bio) {
        if (bioElement) bioElement.textContent = data.user.bio;
        else {
          const newBioElement = document.createElement('p');
          newBioElement.className = 'user-profile__bio';
          newBioElement.textContent = data.user.bio;
          document.querySelector('.user-profile__username').after(newBioElement);
        }
      } else if (bioElement) {
        bioElement.remove();
      }
      if (data.user.avatar) {
        const avatarUrl = data.user.avatar.startsWith('/static/') ? data.user.avatar : '/static/uploads/avatars/' + data.user.avatar;
        const avatarElement = document.querySelector('.user-profile__avatar');
        if (avatarElement.tagName === 'IMG') avatarElement.src = avatarUrl;
        else avatarElement.outerHTML = `<img src="${avatarUrl}" alt="User Profile" class="user-profile__avatar">`;
      }
      setTimeout(() => { closeModal(false); window.location.reload(); }, 800);
    } catch (error) {
      console.error('Profile update error:', error);
      showNotification('Gagal menyimpan profile', 'error');
    }
  });
}

// === HANDLE SIDEBAR ===
if (toggleBtn) {
  toggleBtn.addEventListener("click", () => {
    if (window.innerWidth <= 768) {
      sidebar.classList.toggle("active");
      overlay.classList.toggle("show");
    } else {
      sidebar.classList.toggle("closed");
    }
  });
}

// Klik luar area sidebar -> tutup (untuk HP)
if (overlay) {
  overlay.addEventListener("click", () => {
    sidebar.classList.remove("active");
    overlay.classList.remove("show");
  });
}

// === HANDLE DROPDOWN PROFIL ===
if (profileBtn) {
  profileBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    profileDropdown.style.display =
      profileDropdown.style.display === "block" ? "none" : "block";
  });
}

// Klik di luar dropdown -> tutup
document.addEventListener("click", () => {
  if (profileDropdown) profileDropdown.style.display = "none";
});

// === HANDLE LIKE BUTTONS ===
document.querySelectorAll(".music-actions .like").forEach(btn => {
  btn.addEventListener("click", () => {
    btn.classList.toggle("active");
    const icon = btn.querySelector("i");
    icon.classList.toggle("fa-regular");
    icon.classList.toggle("fa-solid");
  });
});

// === HANDLE EXPLORE TABS ===
function initializeExploreTabs() {
  const exploreTabs = document.querySelectorAll(".tab-button");
  const exploreContents = document.querySelectorAll(".tab-content");

  exploreTabs.forEach(btn => {
    btn.addEventListener("click", () => {
      exploreTabs.forEach(b => b.classList.remove("active"));
      exploreContents.forEach(c => c.classList.remove("active"));
      btn.classList.add("active");
      const tabId = btn.getAttribute('data-tab');
      const tabContent = document.getElementById(tabId);
      if (tabContent) {
        tabContent.classList.add("active");
      }
    });
  });
  
  console.log('✅ Explore tabs initialized');
}

// === MODERN MUSIC PLAYER FUNCTIONALITY ===
function initializeModernPlayer() {
    const progressBar = document.querySelector('.progress-bar');
    const currentTimeEl = document.getElementById('currentTime');
    const totalTimeEl = document.getElementById('totalTime');
    const detailPrevBtn = document.getElementById('detailPrevBtn');
    const detailNextBtn = document.getElementById('detailNextBtn');
    const detailPlayPauseBtn = document.getElementById('detailPlayPauseBtn');
    const playPauseBtn = document.getElementById('playPauseBtn');
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const closeModal = document.getElementById('closeModal');
    const closeMusicPlayer = document.getElementById('closeMusicPlayer');
    const playerContent = document.querySelector('.player-content');

    if (closeMusicPlayer) {
      closeMusicPlayer.addEventListener('click', (e) => {
        e.stopPropagation();
        globalAudio?.pause();
        isPlaying = false;
        currentTrack = null;
        document.getElementById('musicPlayer')?.classList.remove('active');
        try {
          localStorage.removeItem('musicwave_player');
        } catch (error) {
          console.log('localStorage error:', error);
        }
      });
    }

    // Player content click untuk buka modal
    if (playerContent) {
        playerContent.addEventListener('click', (e) => {
            e.stopPropagation();
            openMusicDetail();
        });
    }

    // Close modal
    if (closeModal) {
        closeModal.addEventListener('click', closeMusicDetail);
    }

    // Play/pause in mini player
    if (playPauseBtn) {
        playPauseBtn.addEventListener('click', togglePlayPause);
    }

    // Play/pause in detail modal
    if (detailPlayPauseBtn) {
        detailPlayPauseBtn.addEventListener('click', togglePlayPause);
    }

    // Previous/Next in mini player
    if (prevBtn) {
        prevBtn.addEventListener('click', playPreviousTrack);
    }

    if (nextBtn) {
        nextBtn.addEventListener('click', playNextTrack);
    }

    // Previous/Next in detail modal
    if (detailPrevBtn) {
        detailPrevBtn.addEventListener('click', playPreviousTrack);
    }
    
    if (detailNextBtn) {
        detailNextBtn.addEventListener('click', playNextTrack);
    }

    // Progress bar click
    if (progressBar) {
        progressBar.addEventListener('click', (e) => {
            if (!globalAudio) return;
            
            const rect = progressBar.getBoundingClientRect();
            const percent = (e.clientX - rect.left) / rect.width;
            globalAudio.currentTime = percent * duration;
        });
    }

    // Like button in modal
    const likeDetailBtn = document.getElementById('likeDetailBtn');
    if (likeDetailBtn) {
        likeDetailBtn.addEventListener('click', async () => {
            if (!currentTrack || !currentTrack.id) return;
            await toggleLikeSong(currentTrack.id);
        });
    }

    // Add to playlist button
    const addToPlaylistBtn = document.getElementById('addToPlaylistBtn');
    if (addToPlaylistBtn) {
        addToPlaylistBtn.addEventListener('click', () => {
            if (!currentTrack || !currentTrack.id) return;
            showAddToPlaylistModal(currentTrack.id);
        });
    }

    // Update time display every second
    setInterval(updateTimeDisplay, 1000);
}

// Open the full song page without recreating the persistent audio player.
function openMusicDetail() {
    if (!currentTrack || !currentTrack.id) return;
    const songUrl = `/song/${encodeURIComponent(currentTrack.id)}`;
    if (typeof loadPageViaAjax === 'function') {
      loadPageViaAjax(songUrl);
    } else {
      window.location.href = songUrl;
    }
}

function initializeSongPage() {
    const page = document.getElementById('songPage');
    if (!page || page.dataset.initialized) return;
    page.dataset.initialized = 'true';
  document.body.classList.add('song-detail-active');

    const songId = page.dataset.songId;
    const song = {
      id: songId,
      title: page.dataset.title,
      artist: page.dataset.artist,
      cover: page.dataset.cover,
      audio: page.dataset.audio
    };
    const playButton = document.getElementById('songPagePlay');
    const likeButton = document.getElementById('songPageLike');
    const addButton = document.getElementById('songPageAdd');
    const closeButton = document.getElementById('songPageClose');

    initializeSyncedLyrics();

    const syncPlayButton = () => {
      if (!playButton) return;
      const playing = currentTrack && String(currentTrack.id) === String(songId) && globalAudio && !globalAudio.paused && !globalAudio.ended;
      playButton.innerHTML = playing
        ? '<i class="fa-solid fa-pause"></i><span>Jeda lagu</span>'
        : '<i class="fa-solid fa-play"></i><span>Putar lagu</span>';
    };

    closeButton?.addEventListener('click', () => {
      loadPageViaAjax('/explore');
    });

    checkIfLiked(songId).then((liked) => {
      likeButton?.classList.toggle('active', liked);
      if (likeButton) likeButton.innerHTML = liked
        ? '<i class="fa-solid fa-heart"></i>'
        : '<i class="fa-regular fa-heart"></i>';
    });

    playButton?.addEventListener('click', () => {
      if (currentTrack && String(currentTrack.id) === String(songId)) {
        togglePlayPause();
      } else {
        currentTrack = song;
        globalAudio.src = song.audio;
        globalAudio.currentTime = 0;
        globalAudio.play().catch(() => {
          isPlaying = false;
          syncPlayButton();
        });
        isPlaying = true;
        document.getElementById('musicPlayer')?.classList.add('active');
        document.getElementById('playerCover').src = song.cover;
        document.getElementById('playerTitle').textContent = song.title;
        document.getElementById('playerArtist').textContent = song.artist;
      }
      syncPlayButton();
    });

    likeButton?.addEventListener('click', async () => {
      const data = await toggleLikeSong(songId);
      if (data) {
        likeButton.classList.toggle('active', data.liked);
        likeButton.innerHTML = data.liked
          ? '<i class="fa-solid fa-heart"></i>'
          : '<i class="fa-regular fa-heart"></i>';
      }
    });

    addButton?.addEventListener('click', () => showAddToPlaylistModal(songId));
    syncPlayButton();
}

// Legacy modal loader retained only for compatibility with older markup.
async function loadLegacyMusicDetailModal() {
    if (!currentTrack) return;
    
    const modal = document.getElementById('musicDetailModal');
    const detailCover = document.getElementById('detailCover');
    const detailTitle = document.getElementById('detailTitle');
    const detailArtist = document.getElementById('detailArtist');
    const detailAlbum = document.getElementById('detailAlbum');
    const detailPlayPauseBtn = document.getElementById('detailPlayPauseBtn');
    const lyricsContent = document.getElementById('lyricsContent');
    const infoGenre = document.getElementById('infoGenre');
    const infoPlays = document.getElementById('infoPlays');
    const infoUploader = document.getElementById('infoUploader');
    const infoUploadDate = document.getElementById('infoUploadDate');

    // currentTrack adalah object dari playTrackGlobal
    const songId = currentTrack.id;
    
    // Update basic info dari currentTrack object
    if (detailCover) detailCover.src = currentTrack.cover;
    if (detailTitle) detailTitle.textContent = currentTrack.title;
    if (detailArtist) detailArtist.textContent = currentTrack.artist;
    if (detailAlbum) detailAlbum.textContent = 'Single';

    // Update play/pause button
    if (detailPlayPauseBtn) {
        detailPlayPauseBtn.innerHTML = isPlaying ? 
            '<i class="fa-solid fa-pause"></i>' : 
            '<i class="fa-solid fa-play"></i>';
    }

    const likeDetailBtn = document.getElementById('likeDetailBtn');
    if (likeDetailBtn) {
      const liked = await checkIfLiked(songId);
      likeDetailBtn.classList.toggle('active', liked);
      likeDetailBtn.innerHTML = liked
        ? '<i class="fa-solid fa-heart"></i>'
        : '<i class="fa-regular fa-heart"></i>';
    }

    // Tampilkan loading state
    if (lyricsContent) {
        lyricsContent.innerHTML = '<p><i class="fa-solid fa-spinner fa-spin"></i> Memuat lirik...</p>';
    }

    // Fetch detailed song info dari API
    try {
        const response = await fetch(`/api/song/${songId}`);
        const songData = await response.json();
        
        if (songData.error) {
            throw new Error(songData.error);
        }

        // Update lyrics
        if (lyricsContent) {
            // Format lirik dengan line breaks
            const formattedLyrics = songData.lyrics ? songData.lyrics.replace(/\n/g, '</p><p>') : 'Lirik tidak tersedia';
            lyricsContent.innerHTML = `<p>${formattedLyrics}</p>`;
        }

        // Update song info
        if (infoGenre) infoGenre.textContent = songData.genre || 'Tidak ada genre';
        if (infoPlays) infoPlays.textContent = `${songData.plays || 0} kali`;
        if (infoUploader) infoUploader.textContent = songData.artist || 'Unknown';
        if (infoUploadDate) {
            const uploadDate = new Date(songData.uploaded_at);
            infoUploadDate.textContent = uploadDate.toLocaleDateString('id-ID');
        }

    } catch (error) {
        console.error('Error fetching song details:', error);
        if (lyricsContent) {
            lyricsContent.innerHTML = '<p>Gagal memuat lirik. Silakan coba lagi.</p>';
        }
    }

    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
}

// Close music detail modal
function closeMusicDetail() {
    const modal = document.getElementById('musicDetailModal');
    modal.classList.remove('active');
    document.body.style.overflow = 'auto';
}

// Update time display
function updateTimeDisplay() {
    if (!globalAudio) return;

    const currentTimeEl = document.getElementById('currentTime');
    const totalTimeEl = document.getElementById('totalTime');
    const progressFill = document.querySelector('.progress-fill');

    currentTime = globalAudio.currentTime;
    duration = globalAudio.duration || 0;

    // Update progress bars
    const progressPercent = duration ? (currentTime / duration) * 100 : 0;
    
    if (progressFill) progressFill.style.width = `${progressPercent}%`;

    // Update time displays
    if (currentTimeEl) currentTimeEl.textContent = formatTime(currentTime);
    if (totalTimeEl) totalTimeEl.textContent = formatTime(duration);
}

// Format time (seconds to MM:SS)
function formatTime(seconds) {
    if (!seconds || isNaN(seconds)) return '0:00';
    
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// Toggle play/pause
function togglePlayPause() {
    if (!globalAudio) return;

    const playPauseBtn = document.getElementById('playPauseBtn');
    const detailPlayPauseBtn = document.getElementById('detailPlayPauseBtn');

  if (!globalAudio.paused && !globalAudio.ended) {
        globalAudio.pause();
        if (playPauseBtn) playPauseBtn.innerHTML = '<i class="fa-solid fa-play"></i>';
        if (detailPlayPauseBtn) detailPlayPauseBtn.innerHTML = '<i class="fa-solid fa-play"></i>';
    } else {
    globalAudio.play().catch(() => {});
    }
}

// Enhanced playTrack function - delegates to global player
window.playTrack = function(trackElement) {
    playTrackGlobal(trackElement);
}

// Play next track
function playNextTrack() {
  if (!currentTrack || playQueueIndex < 0) return;
  const nextTrack = playQueue[playQueueIndex + 1];
  if (!nextTrack) return;
  playQueueIndex += 1;
  playTrackData(nextTrack);
}

// Play previous track
function playPreviousTrack() {
  if (!currentTrack || playQueueIndex <= 0) return;
  const prevTrack = playQueue[playQueueIndex - 1];
  playQueueIndex -= 1;
  playTrackData(prevTrack);
}

// === HANDLE ADD PODCAST SELECTION ===
const addPodcastBtn = document.querySelector(".add-podcast-btn");
const podcastCards = document.querySelectorAll(".podcast-card");

if (podcastCards.length > 0) {
  podcastCards.forEach(card => {
    card.addEventListener("click", (e) => {
      const checkbox = card.querySelector("input[type='checkbox']");
      checkbox.checked = !checkbox.checked;
      card.classList.toggle("selected", checkbox.checked);
    });
  });
}

if (addPodcastBtn) {
  addPodcastBtn.addEventListener("click", () => {
    const selected = Array.from(document.querySelectorAll("input[name='selected_podcast']:checked"))
      .map(cb => cb.value);

    if (selected.length === 0) {
      alert("Pilih setidaknya satu podcast untuk ditambahkan.");
      return;
    }

    // Kirim POST ke backend Flask
    fetch("/add_podcast", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams(selected.map(id => ["podcast_ids", id]))
    })
      .then(res => {
        if (res.redirected) {
          window.location.href = res.url;
        } else {
          alert("Podcast berhasil ditambahkan ke Library!");
          window.location.href = "/library";
        }
      })
      .catch(err => {
        console.error(err);
        alert("Terjadi kesalahan saat menambahkan podcast.");
      });
  });
}

// === SEARCH FUNCTIONALITY ===
function initializeSearch() {
    const searchForm = document.querySelector('.search-bar form');
    const searchInput = document.querySelector('.search-bar input[name="q"]');
    
    if (searchForm && searchInput) {
        // Real-time search untuk popup
        if (document.getElementById('trackSearch')) {
            document.getElementById('trackSearch').addEventListener('input', function(e) {
                const query = e.target.value.toLowerCase();
                performSearch(query, true);
            });
        }
        
        // Form search utama
        searchForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const query = searchInput.value.trim();
            if (query) {
                window.location.href = `/search?q=${encodeURIComponent(query)}`;
            }
        });
    }
}

function performSearch(query, isPopup = false) {
    if (isPopup) {
        // Search untuk popup tambah lagu
        const availableSongs = window.availableSongs || [];
        const filtered = availableSongs.filter(song => 
            song.title.toLowerCase().includes(query) || 
            song.artist.toLowerCase().includes(query)
        );
        displaySearchResults(filtered);
    } else {
        // Search global - redirect ke explore page
        if (query) {
            window.location.href = `/search?q=${encodeURIComponent(query)}`;
        }
    }
}

// === IMPROVED PLAYLIST FUNCTIONALITY ===
function initializePlaylistFeatures() {
    const editPlaylistBtn = document.getElementById('editPlaylistBtn');
    const editMode = document.getElementById('editMode');
    const cancelEdit = document.getElementById('cancelEdit');
    const addTrackBtn = document.getElementById('addTrackBtn');
    const addFirstTrackBtn = document.getElementById('addFirstTrackBtn');
    const addTrackPopup = document.getElementById('addTrackPopup');
    const closePopup = document.getElementById('closePopup');
    const playPlaylistBtn = document.getElementById('playPlaylist');

    // Edit playlist toggle
    if (editPlaylistBtn && editMode) {
        editPlaylistBtn.addEventListener('click', () => {
            editMode.style.display = editMode.style.display === 'none' ? 'block' : 'none';
        });
    }

    if (cancelEdit && editMode) {
        cancelEdit.addEventListener('click', () => {
            editMode.style.display = 'none';
        });
    }

    // Add track popup
    function openAddTrackPopup() {
        if (addTrackPopup) {
            addTrackPopup.classList.add('active');
            const trackSearch = document.getElementById('trackSearch');
            if (trackSearch) {
                trackSearch.focus();
                trackSearch.value = '';
            }
            loadAvailableSongs();
        }
    }

    if (addTrackBtn) {
        addTrackBtn.addEventListener('click', openAddTrackPopup);
    }

    if (addFirstTrackBtn) {
        addFirstTrackBtn.addEventListener('click', openAddTrackPopup);
    }

    if (closePopup && addTrackPopup) {
        closePopup.addEventListener('click', () => {
            addTrackPopup.classList.remove('active');
        });
    }

    // Close popup on overlay click
    if (addTrackPopup) {
        addTrackPopup.addEventListener('click', (e) => {
            if (e.target === addTrackPopup) {
                addTrackPopup.classList.remove('active');
            }
        });
    }

    // Load available songs dengan AJAX
    function loadAvailableSongs() {
        const playlistId = window.currentPlaylistId;
        if (!playlistId) return;

        fetch(`/api/search_songs?playlist_id=${playlistId}`)
            .then(response => response.json())
            .then(songs => {
                window.availableSongs = songs;
                displaySearchResults(songs);
            })
            .catch(error => {
                console.error('Error loading songs:', error);
                const availableSongs = window.availableSongs || [];
                displaySearchResults(availableSongs);
            });
    }

    function displaySearchResults(songs) {
        const searchResults = document.getElementById('searchResults');
        if (!searchResults) return;
        
        searchResults.innerHTML = '';
        
        if (songs.length === 0) {
            searchResults.innerHTML = `
                <div style="text-align: center; padding: 40px; color: #666;">
                    <i class="fa-solid fa-music" style="font-size: 48px; margin-bottom: 16px; opacity: 0.5;"></i>
                    <p>Tidak ada lagu tersedia</p>
                </div>
            `;
            return;
        }

        songs.forEach(song => {
            const trackElement = document.createElement('div');
            trackElement.className = 'search-track';
            trackElement.innerHTML = `
                <img src="${song.cover}" alt="${song.title}" class="search-track-cover">
                <div class="search-track-info">
                    <div class="search-track-title">${song.title}</div>
                    <div class="search-track-artist">${song.artist}</div>
                </div>
                <div class="search-track-duration">${song.duration || '3:45'}</div>
                <button class="add-track-btn" data-song-id="${song.id}" title="Tambah ke playlist">
                    <i class="fa-solid fa-plus"></i>
                </button>
            `;
            
            searchResults.appendChild(trackElement);
            
            // Add event listener untuk tombol tambah
            const addBtn = trackElement.querySelector('.add-track-btn');
            if (addBtn) {
                addBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    addSongToPlaylist(song.id);
                });
            }
            
            // Preview lagu on click
            trackElement.addEventListener('click', () => {
                previewSong(song);
            });
        });
    }

    function addSongToPlaylist(songId) {
        const playlistId = window.currentPlaylistId;
        if (!playlistId) return;

        fetch(`/playlist/${playlistId}/add_song`, {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body: `song_id=${songId}`
        })
        .then(response => {
            if (response.ok) {
                addTrackPopup.classList.remove('active');
                location.reload();
            } else {
                alert('Gagal menambahkan lagu');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Terjadi kesalahan saat menambahkan lagu');
        });
    }

    function previewSong(song) {
        const audioPreview = document.getElementById('audioPreview');
        if (audioPreview && song.audio_url) {
            audioPreview.src = song.audio_url;
            audioPreview.play().catch(e => console.log('Audio preview failed:', e));
        }
    }

    // Delete song dari playlist
    document.querySelectorAll('.delete-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const songId = btn.getAttribute('data-song-id');
            const playlistId = window.currentPlaylistId;
            
            if (confirm('Hapus lagu dari playlist?')) {
                fetch(`/playlist/${playlistId}/remove_song`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    body: `song_id=${songId}`
                })
                .then(response => {
                    if (response.ok) {
                        location.reload();
                    } else {
                        alert('Gagal menghapus lagu');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Terjadi kesalahan saat menghapus lagu');
                });
            }
        });
    });

    // Play playlist
    if (playPlaylistBtn) {
        playPlaylistBtn.addEventListener('click', () => {
            const firstTrack = document.querySelector('.track-item');
            if (firstTrack) {
                firstTrack.click();
            }
        });
    }

    // Set current playlist ID
    const urlParts = window.location.pathname.split('/');
    const playlistId = urlParts[urlParts.length - 1];
    window.currentPlaylistId = playlistId;
}

// Close modal when clicking outside
document.addEventListener('click', function(e) {
    const modal = document.getElementById('musicDetailModal');
    if (e.target === modal) {
        closeMusicDetail();
    }
});

// === INITIALIZE WHEN DOM LOADED ===
document.addEventListener('DOMContentLoaded', function() {
    console.log('🎵 MusicWave loaded successfully');
    
    // Initialize global audio player FIRST
    initGlobalAudio();
    setupGlobalAudioListeners();
    
    // Initialize AJAX navigation (no full page reloads)
    initAjaxNavigation();
    
    // Update sidebar state on initial load
    updateSidebarActiveState(window.location.href);
    initializeProfilePage();
    initializeSongPage();
    
    initializeSearch();
    initializeModernPlayer();
    attachMusicListeners();
    
    // Initialize explore tabs jika ada
    if (document.querySelector('.tab-button')) {
        initializeExploreTabs();
    }
    
    // Check jika di playlist detail page
    if (document.querySelector('.playlist-hero')) {
        initializePlaylistFeatures();
    }

    // Debug: Cek apakah ada music-card di halaman
    const musicCards = document.querySelectorAll('.music-card');
    console.log(`🎵 Found ${musicCards.length} music cards`);
    
    musicCards.forEach((card, index) => {
        const audioUrl = card.getAttribute('data-audio');
        console.log(`🎵 Card ${index + 1}:`, {
            title: card.querySelector('.music-info h4')?.textContent,
            audioUrl: audioUrl,
            hasAudio: !!audioUrl
        });
    });
});

// Function to apply theme to dynamically loaded content
function applyThemeToDynamicContent() {
  const theme = document.body.classList.contains('theme-dark') ? 'dark' : 'light';
  
  // Apply theme to modals
  document.querySelectorAll('.modal-content').forEach(modal => {
    if (theme === 'dark') {
      modal.classList.add('theme-dark');
    } else {
      modal.classList.remove('theme-dark');
    }
  });
  
  // Apply theme to music detail modal
  const musicModal = document.getElementById('musicDetailModal');
  if (musicModal) {
    if (theme === 'dark') {
      musicModal.classList.add('theme-dark');
    } else {
      musicModal.classList.remove('theme-dark');
    }
  }
}

// Call this function when theme changes or modals open
document.addEventListener('DOMContentLoaded', function() {
  applyThemeToDynamicContent();
  
  // Re-apply theme when modals are opened
  const observer = new MutationObserver(function(mutations) {
    mutations.forEach(function(mutation) {
      if (mutation.type === 'attributes' && mutation.attributeName === 'style') {
        if (mutation.target.style.display === 'flex' || mutation.target.style.display === 'block') {
          setTimeout(applyThemeToDynamicContent, 100);
        }
      }
    });
  });
  
  // Observe all modals
  document.querySelectorAll('.modal').forEach(modal => {
    observer.observe(modal, { attributes: true });
  });
});