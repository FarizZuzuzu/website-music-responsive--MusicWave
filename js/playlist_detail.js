// === PLAYLIST DETAIL FUNCTIONALITY ===
document.addEventListener('DOMContentLoaded', function() {
    // Get playlist data from HTML
    const playlistDataElement = document.getElementById('playlistData');
    const playlistId = playlistDataElement ? playlistDataElement.getAttribute('data-playlist-id') : null;

    // Elements
    const editPlaylistBtn = document.getElementById('editPlaylistBtn');
    const editMode = document.getElementById('editMode');
    const cancelEdit = document.getElementById('cancelEdit');
    const addTrackBtn = document.getElementById('addTrackBtn');
    const addFirstTrackBtn = document.getElementById('addFirstTrackBtn');
    const addTrackPopup = document.getElementById('addTrackPopup');
    const closePopup = document.getElementById('closePopup');
    const trackSearch = document.getElementById('trackSearch');
    const searchResults = document.getElementById('searchResults');
    const playPlaylistBtn = document.getElementById('playPlaylist');

    // Edit playlist toggle
    if (editPlaylistBtn && editMode) {
        editPlaylistBtn.addEventListener('click', () => {
            const isVisible = editMode.style.display === 'block';
            editMode.style.display = isVisible ? 'none' : 'block';
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
            if (trackSearch) {
                trackSearch.focus();
                trackSearch.value = '';
            }
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

    // Search functionality
    if (trackSearch) {
        trackSearch.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase();
            filterSongs(query);
        });
    }

    function filterSongs(query) {
        const allSearchTracks = document.querySelectorAll('.search-track');
        
        allSearchTracks.forEach(track => {
            const title = track.querySelector('.search-track-title').textContent.toLowerCase();
            const artist = track.querySelector('.search-track-artist').textContent.toLowerCase();
            
            if (title.includes(query) || artist.includes(query)) {
                track.style.display = 'flex';
            } else {
                track.style.display = 'none';
            }
        });

        // Show/hide no results message
        const visibleTracks = Array.from(allSearchTracks).filter(track => 
            track.style.display !== 'none'
        );
        
        const noResultsMsg = searchResults.querySelector('.no-results');
        if (visibleTracks.length === 0 && !noResultsMsg) {
            const noResultsElement = document.createElement('div');
            noResultsElement.className = 'no-results';
            noResultsElement.style.textAlign = 'center';
            noResultsElement.style.padding = '40px';
            noResultsElement.style.color = '#666';
            noResultsElement.innerHTML = `
                <i class="fa-solid fa-search" style="font-size: 48px; margin-bottom: 16px; opacity: 0.5;"></i>
                <p>Tidak ada hasil untuk "${query}"</p>
            `;
            searchResults.appendChild(noResultsElement);
        } else if (noResultsMsg && visibleTracks.length > 0) {
            noResultsMsg.remove();
        }
    }

    // Add song to playlist
    document.querySelectorAll('.add-track-btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const songId = this.getAttribute('data-song-id');
            addSongToPlaylist(songId);
        });
    });

    function addSongToPlaylist(songId) {
        if (!playlistId) {
            alert('Playlist ID tidak ditemukan');
            return;
        }

        fetch(`/playlist/${playlistId}/add_song`, {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body: `song_id=${songId}`
        })
        .then(response => {
            if (response.ok) {
                if (addTrackPopup) {
                    addTrackPopup.classList.remove('active');
                }
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

    // Delete song dari playlist
    document.querySelectorAll('.delete-btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const songId = this.getAttribute('data-song-id');
            
            if (confirm('Hapus lagu dari playlist?')) {
                deleteSongFromPlaylist(songId);
            }
        });
    });

    function deleteSongFromPlaylist(songId) {
        if (!playlistId) {
            alert('Playlist ID tidak ditemukan');
            return;
        }

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

    // Play playlist (play first track)
    if (playPlaylistBtn) {
        playPlaylistBtn.addEventListener('click', () => {
            const firstTrack = document.querySelector('.track-item');
            if (firstTrack) {
                // Use the global music player functionality
                if (typeof window.playTrack === 'function') {
                    window.playTrack(firstTrack);
                } else {
                    // Fallback: trigger click event
                    firstTrack.click();
                }
            }
        });
    }

    console.log('Playlist detail functionality loaded');
});