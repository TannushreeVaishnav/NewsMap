// Initialize the Leaflet Map
// Set default view to focus on India!
const map = L.map('map').setView([20.5937, 78.9629], 5);

// Use CARTO Voyager Tiles for the base map appearance (Forces English labels globally)
L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 20
}).addTo(map);

// Layer Group to hold all our news markers
const newsMarkers = L.layerGroup().addTo(map);

// Configuration for Categories (Colors and Icons)
const categoryConfig = {
    general: { color: "#3498db", icon: "fa-globe" },
    politics: { color: "#e74c3c", icon: "fa-landmark" },
    sports: { color: "#f39c12", icon: "fa-futbol" },
    technology: { color: "#8e44ad", icon: "fa-microchip" },
    entertainment: { color: "#f1c40f", icon: "fa-film" },
    health: { color: "#1abc9c", icon: "fa-heartbeat" },
    business: { color: "#27ae60", icon: "fa-briefcase" }
};

// SVG Generator to create custom colored Google-Maps style pins
function createCustomMarker(category) {
    const config = categoryConfig[category] || categoryConfig['general'];

    const svgIcon = `
        <svg viewBox="0 0 24 36" width="35" height="45" xmlns="http://www.w3.org/2000/svg">
            <!-- Pin Body -->
            <path d="M12 0C5.373 0 0 5.373 0 12c0 8.4 12 24 12 24s12-15.6 12-24c0-6.627-5.373-12-12-12z" 
                  fill="${config.color}" 
                  stroke="#ffffff" 
                  stroke-width="2"/>
            <!-- White Dot inside -->
            <circle cx="12" cy="12" r="4.5" fill="#ffffff"/>
        </svg>
    `;

    return L.divIcon({
        className: 'custom-leaflet-marker',
        html: svgIcon,
        iconSize: [35, 45],
        iconAnchor: [17.5, 45],
        popupAnchor: [0, -40]
    });
}

// Fetch Data from our Flask API
function fetchNewsData(category) {
    // Show Loading Spinner
    document.getElementById('loading').classList.remove('hidden');
    // Clear old map markers
    newsMarkers.clearLayers();

    console.log(`Fetching news for category: ${category}`);

    // Call our Python API
    fetch(`/api/news?category=${category}`)
        .then(response => response.json())
        .then(data => {
            // Hide Loading Spinner
            document.getElementById('loading').classList.add('hidden');

            if (data.status === 'success') {
                let markersAdded = 0;

                data.articles.forEach(article => {
                    // Only add a marker IF the Python script successfully found geographic coordinates
                    if (article.location) {
                        markersAdded++;

                        // Create the colored pin
                        const icon = createCustomMarker(category);
                        const marker = L.marker([article.location.lat, article.location.lon], { icon: icon });

                        // Build the beautiful Popup Card (HTML string)
                        let imageHtml = '';
                        if (article.image_url) {
                            imageHtml = `<img src="${article.image_url}" class="popup-image" alt="Article Thumbnail" onerror="this.style.display='none'">`;
                        }

                        // Grab the correct icon class for the footer
                        const categoryIconClass = categoryConfig[category] ? categoryConfig[category].icon : 'fa-newspaper';

                        let timeHtml = '';
                        if (article.published_at) {
                            const dateObj = new Date(article.published_at);
                            const options = { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' };
                            timeHtml = `<div style="font-size: 0.85em; color: #a8b2d1; margin-top: 5px;"><i class="far fa-clock"></i> ${dateObj.toLocaleString(undefined, options)}</div>`;
                        }

                        const popupContent = `
                            <div class="popup-header-container">
                                <a href="${article.url}" target="_blank" style="color:white; text-decoration:none; display: block;">
                                    ${article.title}
                                </a>
                                ${timeHtml}
                            </div>
                            ${imageHtml}
                            <div class="popup-summary">
                                ${article.summary ? article.summary : '<i>No summary available.</i>'}
                            </div>
                            <div class="popup-footer">
                                <i class="fas ${categoryIconClass}" style="color:${categoryConfig[category].color}"></i> 
                                ${category} News
                            </div>
                        `;


                        marker.bindPopup(popupContent);
                        newsMarkers.addLayer(marker);
                    }
                });

                console.log(`Placed ${markersAdded} map pins successfully.`);

            } else {
                alert('API Error: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            document.getElementById('loading').classList.add('hidden');
            console.error('Error fetching Data:', error);
            alert('Failed to connect to the Flask Python API.');
        });
}

// Handle Button Clicks on the Category Menu
document.querySelectorAll('.filter-btn').forEach(button => {
    button.addEventListener('click', (event) => {
        // Remove Active color from all buttons
        document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));

        // Add Active color to clicked button
        event.target.classList.add('active');

        // Fetch new data
        const selectedCategory = event.target.getAttribute('data-category');
        fetchNewsData(selectedCategory);
    });
});

// Run Initial Data Fetch on Page Load
window.addEventListener('load', () => {
    fetchNewsData('general');
});
