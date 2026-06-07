const DistributorsMap = {
    map: null,
    markers: [],
    infoWindow: null,
    distributors: [],
    mapId: null,
    
    init(config) {
        this.distributors = config.distributors;
        this.mapId = config.mapId;
        this.initMap(config);
        this.initListInteractions();
    },
    
    async initMap(config) {
        // Wait for Google Maps API with better async handling
        const waitForGoogleMaps = () => {
            return new Promise((resolve) => {
                const checkGoogleMaps = () => {
                    if (typeof google !== 'undefined' && google.maps && google.maps.Map) {
                        resolve();
                    } else {
                        setTimeout(checkGoogleMaps, 100);
                    }
                };
                checkGoogleMaps();
            });
        };

        await waitForGoogleMaps();
        
        this.map = new google.maps.Map(document.getElementById(config.mapId), {
            zoom: parseInt(config.zoom),
            center: { lat: 20, lng: 0 },
            mapTypeId: google.maps.MapTypeId.ROADMAP,
            mapId: '6d78e7a359bbe3b4ab6c0175', // Required for Advanced Markers
            restriction: {
                latLngBounds: {
                    north: 85,
                    south: -85,
                    west: -180,
                    east: 180
                },
                strictBounds: false
            },
            minZoom: 2,
            maxZoom: 18,
            gestureHandling: 'greedy',
            mapTypeControl: true,
            mapTypeControlOptions: {
                style: google.maps.MapTypeControlStyle.HORIZONTAL_BAR,
                position: google.maps.ControlPosition.TOP_RIGHT,
                mapTypeIds: [
                    google.maps.MapTypeId.ROADMAP,
                    google.maps.MapTypeId.TERRAIN
                ]
            },
            streetViewControl: false
        });
        
        this.infoWindow = new google.maps.InfoWindow();
        
        // Import the Advanced Marker library
        try {
            const { AdvancedMarkerElement } = await google.maps.importLibrary("marker");
            this.AdvancedMarkerElement = AdvancedMarkerElement;
            this.createMarkers(this.distributors);
            this.adjustMapBounds(this.distributors);
        } catch (error) {
            console.error('Error loading marker library:', error);
        }
    },
    
    initListInteractions() {
        const self = this;
        
        // Add click handlers for list items
        jQuery(document).on('click', '.distributor-item', function(e) {
            e.preventDefault();
            const $item = jQuery(this);
            const lat = parseFloat($item.data('lat'));
            const lng = parseFloat($item.data('lng'));
            const index = parseInt($item.data('index'));
            
            // Remove active class from all items
            jQuery('.distributor-item').removeClass('active');
            // Add active class to clicked item
            $item.addClass('active');
            
            // Center map on this distributor
            self.map.setCenter({ lat: lat, lng: lng });
            self.map.setZoom(12);
            
            // Show info window for this marker
            if (self.markers[index]) {
                self.showInfoWindow(self.markers[index], self.distributors[index]);
            }
            
            // Scroll map into view
            document.getElementById(self.mapId).scrollIntoView({ 
                behavior: 'smooth', 
                block: 'center' 
            });
        });
        
        // Handle action buttons
        jQuery(document).on('click', '.action-button', function(e) {
            e.stopPropagation();
            const action = jQuery(this).data('action');
            const $item = jQuery(this).closest('.distributor-item');
            
            if (action === 'view-map') {
                $item.trigger('click');
            }
        });
    },
    
    createMarkers(distributors) {
        this.clearMarkers();
        
        distributors.forEach((distributor, index) => {
            if (!distributor || !distributor.lat || !distributor.lng) return;
            
            // Use Advanced Marker instead of legacy Marker
            const marker = new this.AdvancedMarkerElement({
                position: { lat: distributor.lat, lng: distributor.lng },
                map: this.map,
                title: distributor.title,
                content: this.createMarkerContent()
            });
            
            marker.addListener('click', () => {
                this.showInfoWindow(marker, distributor);
                this.highlightListItemByData(distributor);
            });
            
            marker.distributorData = distributor;
            this.markers.push(marker);
        });
    },
    
    createMarkerContent() {
        // Create custom marker content for Advanced Markers
        const markerContent = document.createElement('div');
        markerContent.innerHTML = `
            <svg width="24" height="32" viewBox="0 0 24 32" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 0C5.4 0 0 5.4 0 12c0 12 12 20 12 20s12-8 12-20c0-6.6-5.4-12-12-12z" fill="#004470"/>
                <circle cx="12" cy="12" r="6" fill="white"/>
                <text x="12" y="16" text-anchor="middle" font-family="Arial" font-size="10" fill="#004470">H</text>
            </svg>
        `;
        return markerContent;
    },
    
    // Add this new method to find list items by distributor data
    highlightListItemByData(distributor) {
        // Remove active class from all items
        jQuery('.distributor-item').removeClass('active');
        
        // Find the list item by matching lat/lng coordinates
        const $item = jQuery('.distributor-item').filter(function() {
            const itemLat = parseFloat(jQuery(this).data('lat'));
            const itemLng = parseFloat(jQuery(this).data('lng'));
            
            // Use small tolerance for floating point comparison
            return Math.abs(itemLat - distributor.lat) < 0.0001 && 
                   Math.abs(itemLng - distributor.lng) < 0.0001;
        }).first();
        
        if ($item.length && $item.is(':visible')) {
            // Add active class to found item
            $item.addClass('active');
            
            // Scroll to the item in the list
            const listContainer = jQuery('.distributors-list-content');
            
            // Use offset() instead of position() for more accurate positioning
            const itemOffset = $item.offset().top;
            const containerOffset = listContainer.offset().top;
            const containerScrollTop = listContainer.scrollTop();
            const containerHeight = listContainer.height();
            
            // Calculate the item's position relative to the container's visible area
            const itemRelativeTop = itemOffset - containerOffset + containerScrollTop;
            
            // Check if item is outside visible area
            const isAboveView = itemRelativeTop < containerScrollTop;
            const isBelowView = itemRelativeTop > (containerScrollTop + containerHeight - $item.outerHeight());
            
            if (isAboveView || isBelowView) {
                // Center the item in the container
                const targetScrollTop = itemRelativeTop - (containerHeight / 2) + ($item.outerHeight() / 2);
                
                listContainer.animate({
                    scrollTop: Math.max(0, targetScrollTop)
                }, 300);
            }
        }
    },
    
    clearMarkers() {
        this.markers.forEach(marker => {
            if (marker.map) {
                marker.map = null; // For Advanced Markers, set map to null to remove
            }
        });
        this.markers = [];
    },
    
    filterByCountry(selectedCountry) {
        const filteredDistributors = selectedCountry 
            ? this.distributors.filter(d => d.country === selectedCountry)
            : this.distributors;
        
        this.createMarkers(filteredDistributors);
        this.adjustMapBounds(filteredDistributors);
        this.updateList(filteredDistributors);
    },
    
    updateList(filteredDistributors) {
        const listContent = jQuery('.distributors-list-content');
        const header = jQuery('.distributors-list-header .count');
        
        // Update count
        header.text(`${filteredDistributors.length} distributors found`);
        
        // Show/hide list items based on filter
        jQuery('.distributor-item').each(function() {
            const $item = jQuery(this);
            const lat = parseFloat($item.data('lat'));
            const lng = parseFloat($item.data('lng'));
            
            const isVisible = filteredDistributors.some(d => 
                Math.abs(d.lat - lat) < 0.0001 && Math.abs(d.lng - lng) < 0.0001
            );
            
            $item.toggle(isVisible);
        });
    },
    
    adjustMapBounds(distributors) {
        if (distributors.length === 0) {
            this.map.setCenter({ lat: 20, lng: 0 });
            this.map.setZoom(2);
            return;
        }
        
        const bounds = new google.maps.LatLngBounds();
        distributors.forEach(distributor => {
            bounds.extend(new google.maps.LatLng(distributor.lat, distributor.lng));
        });
        
        // Add padding to bounds to prevent edge cases
        this.map.fitBounds(bounds, {
            top: 50,
            right: 50,
            bottom: 50,
            left: 50
        });
        
        // Ensure reasonable zoom level and prevent too much zoom out
        setTimeout(() => {
            const currentZoom = this.map.getZoom();
            if (currentZoom > 12) {
                this.map.setZoom(12);
            } else if (currentZoom < 2) {
                this.map.setZoom(2);
            }
        }, 500);
    },
    
    showInfoWindow(marker, distributor) {
        const content = this.generateInfoWindowContent(distributor);
        this.infoWindow.setContent(content);
        this.infoWindow.open(this.map, marker);
    },
    
    generateInfoWindowContent(distributor) {
        let content = `<div class="distributor-popup">
            <h4>${distributor.title}</h4>`;
        
        if (distributor.editor) {
            content += `<div>${distributor.editor}</div>`;
        }
        
        content += '</div>';
        return content;
    }
};