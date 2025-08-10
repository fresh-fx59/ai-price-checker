/**
 * Price Monitor Dashboard JavaScript
 * Handles client-side functionality including mTLS certificate handling
 */

class PriceMonitorApp {
    constructor() {
        this.apiBaseUrl = window.location.origin + '/api';
        this.products = [];
        this.currentProduct = null;
        this.showInactive = false;
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.loadInitialData();
    }
    
    setupEventListeners() {
        // Add product form
        document.getElementById('add-product-btn').addEventListener('click', () => this.addProduct());
        document.getElementById('product-url').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.addProduct();
        });
        
        // Refresh button
        document.getElementById('refresh-btn').addEventListener('click', () => this.loadProducts());
        
        // Show inactive toggle
        document.getElementById('show-inactive').addEventListener('change', (e) => {
            this.showInactive = e.target.checked;
            this.renderProducts();
        });
        
        // Modal controls
        document.getElementById('modal-close').addEventListener('click', () => this.closeModal());
        document.getElementById('update-price-btn').addEventListener('click', () => this.updatePrice());
        document.getElementById('delete-product-btn').addEventListener('click', () => this.deleteProduct());
        
        // Manual price input
        document.getElementById('manual-price').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.updatePrice();
        });
        
        // Toast close
        document.getElementById('toast-close').addEventListener('click', () => this.hideToast());
        
        // Modal backdrop click
        document.getElementById('product-modal').addEventListener('click', (e) => {
            if (e.target.id === 'product-modal') this.closeModal();
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') this.closeModal();
        });
    }
    
    async loadInitialData() {
        await Promise.all([
            this.loadProducts(),
            this.loadStatistics()
        ]);
    }
    
    async makeRequest(url, options = {}) {
        try {
            // Configure request for mTLS if needed
            const requestOptions = {
                ...options,
                credentials: 'include', // Include client certificates
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                }
            };
            
            const response = await fetch(url, requestOptions);
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.message || `HTTP ${response.status}: ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('Request failed:', error);
            
            // Handle specific mTLS errors
            if (error.message.includes('certificate') || error.message.includes('SSL')) {
                this.showToast('Certificate authentication failed. Please ensure your client certificate is properly configured.', 'error');
            } else if (error.message.includes('Network')) {
                this.showToast('Network error. Please check your connection.', 'error');
            } else {
                this.showToast(error.message || 'Request failed', 'error');
            }
            
            throw error;
        }
    }
    
    async loadProducts() {
        try {
            this.showLoading('products-container');
            
            const data = await this.makeRequest(`${this.apiBaseUrl}/products`);
            this.products = data.products || [];
            this.renderProducts();
            
        } catch (error) {
            this.showError('products-container', 'Failed to load products');
        }
    }
    
    async loadStatistics() {
        try {
            const data = await this.makeRequest(`${this.apiBaseUrl}/stats`);
            this.updateStatistics(data);
        } catch (error) {
            console.error('Failed to load statistics:', error);
            // Don't show error toast for statistics as it's not critical
        }
    }
    
    updateStatistics(data) {
        const productStats = data.products || {};
        
        document.getElementById('total-products').textContent = productStats.total_products || 0;
        document.getElementById('active-products').textContent = productStats.active_products || 0;
        document.getElementById('recent-drops').textContent = productStats.recent_price_drops || 0;
    }
    
    renderProducts() {
        const container = document.getElementById('products-container');
        
        // Filter products based on show inactive setting
        const filteredProducts = this.products.filter(product => 
            this.showInactive || product.is_active
        );
        
        if (filteredProducts.length === 0) {
            container.innerHTML = this.getEmptyState();
            return;
        }
        
        const productsHtml = filteredProducts.map(product => this.createProductCard(product)).join('');
        container.innerHTML = productsHtml;
        
        // Add click listeners to product cards
        container.querySelectorAll('.product-card').forEach(card => {
            card.addEventListener('click', () => {
                const productId = parseInt(card.dataset.productId);
                this.showProductDetails(productId);
            });
        });
    }
    
    createProductCard(product) {
        const priceChange = this.calculatePriceChange(product);
        const priceChangeClass = priceChange.type === 'drop' ? 'drop' : 'rise';
        const priceChangeIcon = priceChange.type === 'drop' ? 'fa-arrow-down' : 'fa-arrow-up';
        
        return `
            <div class="product-card ${product.is_active ? '' : 'inactive'}" data-product-id="${product.id}">
                <div class="product-header">
                    <div class="product-image">
                        ${product.image_url 
                            ? `<img src="${product.image_url}" alt="${product.name}" onerror="this.parentElement.innerHTML='<i class=\\'fas fa-image placeholder\\'></i>'">`
                            : '<i class="fas fa-image placeholder"></i>'
                        }
                    </div>
                    <div class="product-info">
                        <div class="product-name" title="${product.name}">${product.name}</div>
                        <a href="${product.url}" class="product-url" target="_blank" onclick="event.stopPropagation()" title="${product.url}">
                            ${this.truncateUrl(product.url)}
                        </a>
                    </div>
                </div>
                
                <div class="product-prices">
                    <div>
                        <span class="price current">$${product.current_price.toFixed(2)}</span>
                        ${product.previous_price ? `<span class="price previous">$${product.previous_price.toFixed(2)}</span>` : ''}
                    </div>
                    <div>
                        <span class="price lowest">Lowest: $${product.lowest_price.toFixed(2)}</span>
                    </div>
                </div>
                
                ${priceChange.amount > 0 ? `
                    <div class="price-change ${priceChangeClass}">
                        <i class="fas ${priceChangeIcon}"></i>
                        $${priceChange.amount.toFixed(2)} (${priceChange.percentage.toFixed(1)}%)
                    </div>
                ` : ''}
                
                <div class="product-meta">
                    <span>Last checked: ${this.formatDate(product.last_checked)}</span>
                    <span class="status-badge ${product.is_active ? 'active' : 'inactive'}">
                        ${product.is_active ? 'Active' : 'Inactive'}
                    </span>
                </div>
            </div>
        `;
    }
    
    calculatePriceChange(product) {
        if (!product.previous_price || product.previous_price === product.current_price) {
            return { type: 'none', amount: 0, percentage: 0 };
        }
        
        const amount = Math.abs(product.current_price - product.previous_price);
        const percentage = (amount / product.previous_price) * 100;
        const type = product.current_price < product.previous_price ? 'drop' : 'rise';
        
        return { type, amount, percentage };
    }
    
    truncateUrl(url) {
        try {
            const urlObj = new URL(url);
            const domain = urlObj.hostname.replace('www.', '');
            const path = urlObj.pathname;
            
            if (path.length > 30) {
                return `${domain}${path.substring(0, 27)}...`;
            }
            return `${domain}${path}`;
        } catch {
            return url.length > 40 ? url.substring(0, 37) + '...' : url;
        }
    }
    
    formatDate(dateString) {
        if (!dateString) return 'Never';
        
        try {
            const date = new Date(dateString);
            const now = new Date();
            const diffMs = now - date;
            const diffMins = Math.floor(diffMs / 60000);
            const diffHours = Math.floor(diffMs / 3600000);
            const diffDays = Math.floor(diffMs / 86400000);
            
            if (diffMins < 1) return 'Just now';
            if (diffMins < 60) return `${diffMins}m ago`;
            if (diffHours < 24) return `${diffHours}h ago`;
            if (diffDays < 7) return `${diffDays}d ago`;
            
            return date.toLocaleDateString();
        } catch {
            return 'Unknown';
        }
    }
    
    getEmptyState() {
        return `
            <div class="empty-state">
                <i class="fas fa-shopping-cart"></i>
                <h3>No products found</h3>
                <p>${this.showInactive ? 'No products are being monitored.' : 'No active products found. Toggle "Show Inactive" to see all products.'}</p>
            </div>
        `;
    }
    
    async addProduct() {
        const urlInput = document.getElementById('product-url');
        const url = urlInput.value.trim();
        
        if (!url) {
            this.showToast('Please enter a product URL', 'error');
            return;
        }
        
        if (!this.isValidUrl(url)) {
            this.showToast('Please enter a valid URL', 'error');
            return;
        }
        
        const addButton = document.getElementById('add-product-btn');
        const originalText = addButton.innerHTML;
        
        try {
            addButton.disabled = true;
            addButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Adding...';
            
            await this.makeRequest(`${this.apiBaseUrl}/products`, {
                method: 'POST',
                body: JSON.stringify({ url })
            });
            
            urlInput.value = '';
            this.showToast('Product added successfully!', 'success');
            
            // Reload data
            await Promise.all([
                this.loadProducts(),
                this.loadStatistics()
            ]);
            
        } catch (error) {
            // Error already handled in makeRequest
        } finally {
            addButton.disabled = false;
            addButton.innerHTML = originalText;
        }
    }
    
    isValidUrl(string) {
        try {
            const url = new URL(string);
            return url.protocol === 'http:' || url.protocol === 'https:';
        } catch {
            return false;
        }
    }
    
    async showProductDetails(productId) {
        const product = this.products.find(p => p.id === productId);
        if (!product) return;
        
        this.currentProduct = product;
        
        // Update modal content
        document.getElementById('modal-product-name').textContent = product.name;
        document.getElementById('modal-product-url').href = product.url;
        document.getElementById('modal-product-url').textContent = 'View Product';
        document.getElementById('modal-current-price').textContent = `$${product.current_price.toFixed(2)}`;
        document.getElementById('modal-previous-price').textContent = product.previous_price 
            ? `$${product.previous_price.toFixed(2)}` : 'N/A';
        document.getElementById('modal-lowest-price').textContent = `$${product.lowest_price.toFixed(2)}`;
        document.getElementById('modal-last-checked').textContent = this.formatDate(product.last_checked);
        
        // Update product image
        const imageElement = document.getElementById('modal-product-image');
        if (product.image_url) {
            imageElement.src = product.image_url;
            imageElement.style.display = 'block';
            imageElement.onerror = () => {
                imageElement.style.display = 'none';
            };
        } else {
            imageElement.style.display = 'none';
        }
        
        // Clear manual price input
        document.getElementById('manual-price').value = '';
        
        // Load price history
        await this.loadPriceHistory(productId);
        
        // Show modal
        document.getElementById('product-modal').style.display = 'block';
        document.body.style.overflow = 'hidden';
    }
    
    async loadPriceHistory(productId) {
        const container = document.getElementById('price-history-container');
        
        try {
            container.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Loading history...</div>';
            
            const data = await this.makeRequest(`${this.apiBaseUrl}/products/${productId}/history?limit=20`);
            const history = data.history || [];
            
            if (history.length === 0) {
                container.innerHTML = '<p style="text-align: center; color: #718096;">No price history available</p>';
                return;
            }
            
            const historyHtml = history.map(entry => `
                <div class="history-item">
                    <div>
                        <span class="history-price">$${entry.price.toFixed(2)}</span>
                        <span class="history-source ${entry.source}">${entry.source}</span>
                    </div>
                    <span class="history-date">${this.formatDate(entry.recorded_at)}</span>
                </div>
            `).join('');
            
            container.innerHTML = historyHtml;
            
        } catch (error) {
            container.innerHTML = '<p style="text-align: center; color: #e53e3e;">Failed to load price history</p>';
        }
    }
    
    async updatePrice() {
        if (!this.currentProduct) return;
        
        const priceInput = document.getElementById('manual-price');
        const price = parseFloat(priceInput.value);
        
        if (!price || price <= 0) {
            this.showToast('Please enter a valid price', 'error');
            return;
        }
        
        const updateButton = document.getElementById('update-price-btn');
        const originalText = updateButton.innerHTML;
        
        try {
            updateButton.disabled = true;
            updateButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Updating...';
            
            await this.makeRequest(`${this.apiBaseUrl}/products/${this.currentProduct.id}/price`, {
                method: 'PUT',
                body: JSON.stringify({ price })
            });
            
            priceInput.value = '';
            this.showToast('Price updated successfully!', 'success');
            
            // Reload data
            await Promise.all([
                this.loadProducts(),
                this.loadStatistics(),
                this.loadPriceHistory(this.currentProduct.id)
            ]);
            
            // Update current product reference
            this.currentProduct = this.products.find(p => p.id === this.currentProduct.id);
            if (this.currentProduct) {
                // Update modal display
                document.getElementById('modal-current-price').textContent = `$${this.currentProduct.current_price.toFixed(2)}`;
                document.getElementById('modal-previous-price').textContent = this.currentProduct.previous_price 
                    ? `$${this.currentProduct.previous_price.toFixed(2)}` : 'N/A';
                document.getElementById('modal-lowest-price').textContent = `$${this.currentProduct.lowest_price.toFixed(2)}`;
            }
            
        } catch (error) {
            // Error already handled in makeRequest
        } finally {
            updateButton.disabled = false;
            updateButton.innerHTML = originalText;
        }
    }
    
    async deleteProduct() {
        if (!this.currentProduct) return;
        
        if (!confirm(`Are you sure you want to delete "${this.currentProduct.name}"? This action cannot be undone.`)) {
            return;
        }
        
        const deleteButton = document.getElementById('delete-product-btn');
        const originalText = deleteButton.innerHTML;
        
        try {
            deleteButton.disabled = true;
            deleteButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Deleting...';
            
            await this.makeRequest(`${this.apiBaseUrl}/products/${this.currentProduct.id}`, {
                method: 'DELETE'
            });
            
            this.showToast('Product deleted successfully!', 'success');
            this.closeModal();
            
            // Reload data
            await Promise.all([
                this.loadProducts(),
                this.loadStatistics()
            ]);
            
        } catch (error) {
            // Error already handled in makeRequest
        } finally {
            deleteButton.disabled = false;
            deleteButton.innerHTML = originalText;
        }
    }
    
    closeModal() {
        document.getElementById('product-modal').style.display = 'none';
        document.body.style.overflow = 'auto';
        this.currentProduct = null;
    }
    
    showLoading(containerId) {
        const container = document.getElementById(containerId);
        container.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Loading...</div>';
    }
    
    showError(containerId, message) {
        const container = document.getElementById(containerId);
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-triangle"></i>
                <h3>Error</h3>
                <p>${message}</p>
                <button class="btn btn-primary" onclick="location.reload()">
                    <i class="fas fa-sync-alt"></i> Retry
                </button>
            </div>
        `;
    }
    
    showToast(message, type = 'info') {
        const toast = document.getElementById('toast');
        const messageElement = document.getElementById('toast-message');
        
        messageElement.textContent = message;
        toast.className = `toast ${type}`;
        toast.classList.add('show');
        
        // Auto-hide after 5 seconds
        setTimeout(() => this.hideToast(), 5000);
    }
    
    hideToast() {
        const toast = document.getElementById('toast');
        toast.classList.remove('show');
    }
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.priceMonitorApp = new PriceMonitorApp();
});

// Global functions for modal control (called from HTML)
function closeModal() {
    if (window.priceMonitorApp) {
        window.priceMonitorApp.closeModal();
    }
}

// Handle client certificate setup instructions
function showCertificateInstructions() {
    const instructions = `
        <div style="max-width: 600px; margin: 20px auto; padding: 20px; background: #f8f9fa; border-radius: 8px; font-family: Arial, sans-serif;">
            <h3 style="color: #2d3748; margin-bottom: 15px;">
                <i class="fas fa-certificate"></i> Client Certificate Setup
            </h3>
            <p style="margin-bottom: 15px;">This application uses mutual TLS (mTLS) for secure authentication. To access the API, you need to configure your client certificate:</p>
            
            <h4 style="color: #4a5568; margin: 15px 0 10px 0;">For Browsers:</h4>
            <ol style="margin-left: 20px; margin-bottom: 15px;">
                <li>Install your client certificate (.p12 or .pfx file) in your browser's certificate store</li>
                <li>When prompted, select your client certificate for authentication</li>
                <li>Ensure the certificate is valid and trusted by the server's CA</li>
            </ol>
            
            <h4 style="color: #4a5568; margin: 15px 0 10px 0;">For Development:</h4>
            <ul style="margin-left: 20px; margin-bottom: 15px;">
                <li>Place your client certificate files in the <code>certs/</code> directory</li>
                <li>Update the configuration to reference your certificate files</li>
                <li>Restart the application after certificate changes</li>
            </ul>
            
            <p style="margin-top: 15px; padding: 10px; background: #e6fffa; border-left: 4px solid #38a169; border-radius: 4px;">
                <strong>Note:</strong> If you're seeing certificate errors, contact your administrator for the correct client certificate files.
            </p>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', instructions);
}

// Check if we need to show certificate instructions
if (window.location.protocol === 'https:') {
    // Test API connectivity
    fetch('/health', { credentials: 'include' })
        .then(response => {
            if (!response.ok && response.status === 403) {
                console.warn('mTLS authentication may be required');
            }
        })
        .catch(error => {
            if (error.message.includes('certificate') || error.message.includes('SSL')) {
                console.warn('Client certificate authentication failed');
            }
        });
}