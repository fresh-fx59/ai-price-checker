"""
Flask application with mTLS security for the price monitoring system.
"""
from flask import Flask, request, jsonify, g
import logging
import ssl
from typing import Optional
from datetime import datetime

from .security import SecurityService
from .security.auth_middleware import setup_mtls_authentication, require_authentication
from .services.config_service import ConfigService
from .services.product_service import ProductService
from .services.parser_service import ParserService
from .services.web_scraping_service import WebScrapingService
from .services.price_monitor_service import PriceMonitorService
from .services.email_service import EmailService
from .models.database import DatabaseManager


class SecureFlaskApp:
    """Flask application with mTLS authentication."""
    
    def __init__(self, config_service: ConfigService, logging_service: Optional['LoggingService'] = None):
        """Initialize the secure Flask application."""
        self.app = Flask(__name__, static_folder='../static', static_url_path='/static')
        self.config_service = config_service
        self.config = config_service.get_config()
        self.security_service = SecurityService(self.config)
        self.logging_service = logging_service
        self.logger = logging.getLogger(__name__)
        
        # Initialize database and services
        # Convert file path to SQLAlchemy URL if needed
        database_url = self.config.database_path
        if not database_url.startswith(('sqlite://', 'postgresql://', 'mysql://')):
            # Assume it's a file path for SQLite
            database_url = f"sqlite:///{database_url}"
        
        self.db_manager = DatabaseManager(database_url)
        self.product_service = ProductService(self.db_manager)
        self.web_scraping_service = WebScrapingService(
            timeout=self.config.request_timeout_seconds,
            max_retries=self.config.max_retry_attempts
        )
        self.parser_service = ParserService(
            ai_api_key=getattr(self.config, 'ai_api_key', None),
            ai_api_endpoint=getattr(self.config, 'ai_api_endpoint', None),
            enable_ai_parsing=getattr(self.config, 'enable_ai_parsing', False)
        )
        self.email_service = EmailService(self.config)
        self.price_monitor_service = PriceMonitorService(
            self.product_service,
            self.parser_service,
            self.web_scraping_service,
            self.email_service,
            self.logging_service
        )
        
        # Load certificates
        self.security_service.load_certificates()
        
        # Set up mTLS authentication
        setup_mtls_authentication(self.app, self.security_service, self.config)
        
        # Set up routes
        self._setup_routes()
        self._setup_error_handlers()
        self._setup_security_headers()
    
    def _setup_routes(self):
        """Set up API routes."""
        
        @self.app.route('/', methods=['GET'])
        def index():
            """Serve the main dashboard page."""
            return self.app.send_static_file('index.html')
        
        @self.app.route('/health', methods=['GET'])
        def health_check():
            """Enhanced health check endpoint with logging system status."""
            health_status = {
                'status': 'healthy',
                'service': 'price-monitor',
                'mtls_enabled': self.config.enable_mtls,
                'client_id': getattr(g, 'client_id', 'anonymous'),
                'timestamp': datetime.now().isoformat()
            }
            
            # Add logging service health if available
            if self.logging_service:
                logging_health = self.logging_service.get_health_status()
                health_status['logging'] = logging_health
            
            return jsonify(health_status)
        
        @self.app.route('/api/monitoring/metrics', methods=['GET'])
        @require_authentication
        def get_performance_metrics():
            """Get performance metrics."""
            if not self.logging_service:
                return jsonify({'error': 'Logging service not available'}), 503
            
            try:
                operation = request.args.get('operation')
                metrics = self.logging_service.get_performance_stats(operation)
                
                return jsonify({
                    'metrics': metrics,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                self.logger.error(f"Error retrieving performance metrics: {str(e)}")
                return jsonify({'error': 'Failed to retrieve metrics'}), 500
        
        @self.app.route('/api/monitoring/errors', methods=['GET'])
        @require_authentication
        def get_error_summary():
            """Get error summary."""
            if not self.logging_service:
                return jsonify({'error': 'Logging service not available'}), 503
            
            try:
                since_hours = int(request.args.get('since_hours', 24))
                error_summary = self.logging_service.get_error_summary(since_hours)
                
                return jsonify({
                    'error_summary': error_summary,
                    'since_hours': since_hours,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                self.logger.error(f"Error retrieving error summary: {str(e)}")
                return jsonify({'error': 'Failed to retrieve error summary'}), 500
        
        @self.app.route('/api/products', methods=['GET'])
        @require_authentication
        def get_products():
            """Get all monitored products with filtering and sorting."""
            try:
                # Get query parameters for filtering
                active_only = request.args.get('active_only', 'true').lower() == 'true'
                sort_by = request.args.get('sort_by', 'created_at')  # name, current_price, lowest_price, created_at, last_checked
                sort_order = request.args.get('sort_order', 'desc').lower()  # asc, desc
                search = request.args.get('search', '').strip()
                limit = request.args.get('limit', type=int)
                offset = request.args.get('offset', 0, type=int)
                
                # Validate sort parameters
                valid_sort_fields = ['name', 'current_price', 'previous_price', 'lowest_price', 'created_at', 'last_checked']
                if sort_by not in valid_sort_fields:
                    return jsonify({
                        'error': 'Invalid sort field',
                        'message': f'sort_by must be one of: {", ".join(valid_sort_fields)}'
                    }), 400
                
                if sort_order not in ['asc', 'desc']:
                    return jsonify({
                        'error': 'Invalid sort order',
                        'message': 'sort_order must be "asc" or "desc"'
                    }), 400
                
                if limit is not None and limit <= 0:
                    return jsonify({
                        'error': 'Invalid limit',
                        'message': 'limit must be a positive number'
                    }), 400
                
                if offset < 0:
                    return jsonify({
                        'error': 'Invalid offset',
                        'message': 'offset must be non-negative'
                    }), 400
                
                # Get products from service
                products = self.product_service.get_all_products(active_only=active_only)
                
                # Apply search filter
                if search:
                    search_lower = search.lower()
                    products = [p for p in products if 
                              search_lower in p.name.lower() or 
                              search_lower in p.url.lower()]
                
                # Apply sorting
                reverse = sort_order == 'desc'
                if sort_by == 'name':
                    products.sort(key=lambda p: p.name.lower(), reverse=reverse)
                elif sort_by == 'current_price':
                    products.sort(key=lambda p: p.current_price, reverse=reverse)
                elif sort_by == 'previous_price':
                    products.sort(key=lambda p: p.previous_price or 0, reverse=reverse)
                elif sort_by == 'lowest_price':
                    products.sort(key=lambda p: p.lowest_price, reverse=reverse)
                elif sort_by == 'created_at':
                    products.sort(key=lambda p: p.created_at or datetime.min, reverse=reverse)
                elif sort_by == 'last_checked':
                    products.sort(key=lambda p: p.last_checked or datetime.min, reverse=reverse)
                
                # Get total count before pagination
                total_count = len(products)
                
                # Apply pagination
                if limit is not None:
                    end_index = offset + limit
                    products = products[offset:end_index]
                elif offset > 0:
                    products = products[offset:]
                
                # Convert products to JSON-serializable format
                products_data = []
                for product in products:
                    # Calculate price change information
                    price_change = None
                    if product.previous_price and product.previous_price != product.current_price:
                        change_amount = product.current_price - product.previous_price
                        change_percentage = (change_amount / product.previous_price) * 100
                        price_change = {
                            'amount': change_amount,
                            'percentage': change_percentage,
                            'direction': 'drop' if change_amount < 0 else 'rise'
                        }
                    
                    product_data = {
                        'id': product.id,
                        'url': product.url,
                        'name': product.name,
                        'current_price': product.current_price,
                        'previous_price': product.previous_price,
                        'lowest_price': product.lowest_price,
                        'image_url': product.image_url,
                        'created_at': product.created_at.isoformat() if product.created_at else None,
                        'last_checked': product.last_checked.isoformat() if product.last_checked else None,
                        'is_active': product.is_active,
                        'price_change': price_change
                    }
                    products_data.append(product_data)
                
                return jsonify({
                    'products': products_data,
                    'count': len(products_data),
                    'total_count': total_count,
                    'offset': offset,
                    'limit': limit,
                    'filters': {
                        'active_only': active_only,
                        'search': search,
                        'sort_by': sort_by,
                        'sort_order': sort_order
                    },
                    'client_id': g.client_id
                })
                
            except Exception as e:
                self.logger.error(f"Error getting products: {str(e)}")
                return jsonify({
                    'error': 'Internal server error',
                    'message': 'Failed to retrieve products'
                }), 500
        
        @self.app.route('/api/products', methods=['POST'])
        @require_authentication
        def add_product():
            """Add a new product to monitor."""
            try:
                data = request.get_json()
                
                if not data or 'url' not in data:
                    return jsonify({
                        'error': 'Invalid request',
                        'message': 'URL is required'
                    }), 400
                
                url = data['url'].strip()
                if not url:
                    return jsonify({
                        'error': 'Invalid request',
                        'message': 'URL cannot be empty'
                    }), 400
                
                # Check if product already exists
                existing_product = self.product_service.get_product_by_url(url)
                if existing_product:
                    return jsonify({
                        'error': 'Product already exists',
                        'message': f'Product with URL {url} is already being monitored',
                        'product_id': existing_product.id
                    }), 409
                
                # Fetch and parse product information
                self.logger.info(f"Adding new product: {url}")
                
                # Fetch page content
                scraping_result = self.web_scraping_service.fetch_page_content(url)
                if not scraping_result.success:
                    return jsonify({
                        'error': 'Failed to fetch product page',
                        'message': scraping_result.error_message
                    }), 400
                
                # Parse product information
                parsing_result = self.parser_service.parse_product(url, scraping_result.page_content)
                if not parsing_result.success:
                    return jsonify({
                        'error': 'Failed to parse product information',
                        'message': parsing_result.error_message
                    }), 400
                
                product_info = parsing_result.product_info
                if not product_info or product_info.price is None:
                    return jsonify({
                        'error': 'Invalid product information',
                        'message': 'Could not extract price information from the page'
                    }), 400
                
                # Add product to database
                product = self.product_service.add_product(
                    url=url,
                    name=product_info.name or 'Unknown Product',
                    price=product_info.price,
                    image_url=product_info.image_url
                )
                
                if not product:
                    return jsonify({
                        'error': 'Failed to add product',
                        'message': 'Could not save product to database'
                    }), 500
                
                # Return product data
                product_data = {
                    'id': product.id,
                    'url': product.url,
                    'name': product.name,
                    'current_price': product.current_price,
                    'previous_price': product.previous_price,
                    'lowest_price': product.lowest_price,
                    'image_url': product.image_url,
                    'created_at': product.created_at.isoformat() if product.created_at else None,
                    'last_checked': product.last_checked.isoformat() if product.last_checked else None,
                    'is_active': product.is_active
                }
                
                self.logger.info(f"Successfully added product: {product.name} (ID: {product.id})")
                
                return jsonify({
                    'message': 'Product added successfully',
                    'product': product_data,
                    'client_id': g.client_id
                }), 201
                
            except Exception as e:
                self.logger.error(f"Error adding product: {str(e)}")
                return jsonify({
                    'error': 'Internal server error',
                    'message': 'Failed to add product'
                }), 500
        
        @self.app.route('/api/products/<int:product_id>', methods=['DELETE'])
        @require_authentication
        def delete_product(product_id):
            """Delete a monitored product."""
            try:
                self.logger.info(f"DELETE request for product {product_id}, args: {request.args}")
                
                # Check for confirmation parameter
                confirm = request.args.get('confirm', 'false').lower() == 'true'
                self.logger.info(f"Confirmation parameter: {confirm}")
                
                # Check if product exists
                product = self.product_service.get_product(product_id)
                if not product:
                    self.logger.warning(f"Product {product_id} not found")
                    return jsonify({
                        'error': 'Product not found',
                        'message': f'Product with ID {product_id} does not exist'
                    }), 404
                
                # If no confirmation, return product info for confirmation dialog
                if not confirm:
                    self.logger.info(f"No confirmation, returning product info for {product_id}")
                    return jsonify({
                        'requires_confirmation': True,
                        'product': {
                            'id': product.id,
                            'name': product.name,
                            'url': product.url,
                            'current_price': product.current_price
                        },
                        'message': 'Deletion requires confirmation. Add ?confirm=true to proceed.',
                        'client_id': g.client_id
                    }), 200
                
                # Delete the product
                self.logger.info(f"Attempting to delete product {product_id}: {product.name}")
                success = self.product_service.delete_product(product_id)
                
                if not success:
                    self.logger.error(f"Failed to delete product {product_id} from database")
                    return jsonify({
                        'error': 'Failed to delete product',
                        'message': 'Could not delete product from database'
                    }), 500
                
                self.logger.info(f"Successfully deleted product: {product.name} (ID: {product_id})")
                
                return jsonify({
                    'message': 'Product deleted successfully',
                    'product_id': product_id,
                    'product_name': product.name,
                    'client_id': g.client_id
                })
                
            except Exception as e:
                self.logger.error(f"Error deleting product {product_id}: {str(e)}", exc_info=True)
                return jsonify({
                    'error': 'Internal server error',
                    'message': f'Failed to delete product: {str(e)}'
                }), 500
        
        @self.app.route('/api/products/<int:product_id>/price', methods=['PUT'])
        @require_authentication
        def update_product_price(product_id):
            """Manually update a product's price."""
            try:
                data = request.get_json()
                
                if not data or 'price' not in data:
                    return jsonify({
                        'error': 'Invalid request',
                        'message': 'Price is required'
                    }), 400
                
                try:
                    price = float(data['price'])
                    if price < 0:
                        raise ValueError("Price cannot be negative")
                except (ValueError, TypeError):
                    return jsonify({
                        'error': 'Invalid price',
                        'message': 'Price must be a positive number'
                    }), 400
                
                # Check if product exists
                product = self.product_service.get_product(product_id)
                if not product:
                    return jsonify({
                        'error': 'Product not found',
                        'message': f'Product with ID {product_id} does not exist'
                    }), 404
                
                if not product.is_active:
                    return jsonify({
                        'error': 'Product not active',
                        'message': 'Cannot update price for inactive product'
                    }), 400
                
                # Use the price monitor service for manual updates (includes email notifications)
                result = self.price_monitor_service.update_product_price_manually(product_id, price)
                
                if not result.success:
                    return jsonify({
                        'error': 'Failed to update price',
                        'message': result.error_message
                    }), 500
                
                # Get updated product data
                updated_product = self.product_service.get_product(product_id)
                product_data = {
                    'id': updated_product.id,
                    'url': updated_product.url,
                    'name': updated_product.name,
                    'current_price': updated_product.current_price,
                    'previous_price': updated_product.previous_price,
                    'lowest_price': updated_product.lowest_price,
                    'image_url': updated_product.image_url,
                    'created_at': updated_product.created_at.isoformat() if updated_product.created_at else None,
                    'last_checked': updated_product.last_checked.isoformat() if updated_product.last_checked else None,
                    'is_active': updated_product.is_active
                }
                
                response_data = {
                    'message': 'Price updated successfully',
                    'product': product_data,
                    'price_change': {
                        'old_price': result.old_price,
                        'new_price': result.new_price,
                        'price_dropped': result.price_dropped,
                        'is_new_lowest': result.is_new_lowest
                    },
                    'notification': {
                        'sent': result.notification_sent,
                        'error': result.notification_error
                    },
                    'client_id': g.client_id
                }
                
                self.logger.info(f"Successfully updated price for product {product_id}: ${result.old_price:.2f} -> ${result.new_price:.2f}")
                
                return jsonify(response_data)
                
            except Exception as e:
                self.logger.error(f"Error updating price for product {product_id}: {str(e)}")
                return jsonify({
                    'error': 'Internal server error',
                    'message': 'Failed to update product price'
                }), 500
        
        @self.app.route('/api/products/<int:product_id>/history', methods=['GET'])
        @require_authentication
        def get_price_history(product_id):
            """Get price history for a product."""
            try:
                # Check if product exists
                product = self.product_service.get_product(product_id)
                if not product:
                    return jsonify({
                        'error': 'Product not found',
                        'message': f'Product with ID {product_id} does not exist'
                    }), 404
                
                # Get query parameters
                limit = request.args.get('limit', type=int)
                if limit is not None and limit <= 0:
                    return jsonify({
                        'error': 'Invalid limit',
                        'message': 'Limit must be a positive number'
                    }), 400
                
                # Get price history
                history = self.product_service.get_price_history(product_id, limit=limit)
                
                # Convert to JSON-serializable format
                history_data = []
                for entry in history:
                    entry_data = {
                        'id': entry.id,
                        'price': entry.price,
                        'recorded_at': entry.recorded_at.isoformat() if entry.recorded_at else None,
                        'source': entry.source
                    }
                    history_data.append(entry_data)
                
                # Get product summary
                product_data = {
                    'id': product.id,
                    'name': product.name,
                    'url': product.url,
                    'current_price': product.current_price,
                    'previous_price': product.previous_price,
                    'lowest_price': product.lowest_price,
                    'created_at': product.created_at.isoformat() if product.created_at else None,
                    'last_checked': product.last_checked.isoformat() if product.last_checked else None
                }
                
                return jsonify({
                    'product': product_data,
                    'history': history_data,
                    'count': len(history_data),
                    'client_id': g.client_id
                })
                
            except Exception as e:
                self.logger.error(f"Error getting price history for product {product_id}: {str(e)}")
                return jsonify({
                    'error': 'Internal server error',
                    'message': 'Failed to retrieve price history'
                }), 500
        
        @self.app.route('/api/products/<int:product_id>', methods=['GET'])
        @require_authentication
        def get_product_details(product_id):
            """Get detailed information for a specific product."""
            try:
                # Get product
                product = self.product_service.get_product(product_id)
                if not product:
                    return jsonify({
                        'error': 'Product not found',
                        'message': f'Product with ID {product_id} does not exist'
                    }), 404
                
                # Get recent price history (last 10 entries)
                recent_history = self.product_service.get_price_history(product_id, limit=10)
                
                # Convert to JSON-serializable format
                product_data = {
                    'id': product.id,
                    'url': product.url,
                    'name': product.name,
                    'current_price': product.current_price,
                    'previous_price': product.previous_price,
                    'lowest_price': product.lowest_price,
                    'image_url': product.image_url,
                    'created_at': product.created_at.isoformat() if product.created_at else None,
                    'last_checked': product.last_checked.isoformat() if product.last_checked else None,
                    'is_active': product.is_active
                }
                
                history_data = []
                for entry in recent_history:
                    entry_data = {
                        'id': entry.id,
                        'price': entry.price,
                        'recorded_at': entry.recorded_at.isoformat() if entry.recorded_at else None,
                        'source': entry.source
                    }
                    history_data.append(entry_data)
                
                return jsonify({
                    'product': product_data,
                    'recent_history': history_data,
                    'client_id': g.client_id
                })
                
            except Exception as e:
                self.logger.error(f"Error getting product details for {product_id}: {str(e)}")
                return jsonify({
                    'error': 'Internal server error',
                    'message': 'Failed to retrieve product details'
                }), 500
        
        @self.app.route('/api/stats', methods=['GET'])
        @require_authentication
        def get_statistics():
            """Get system statistics."""
            try:
                # Get product statistics
                product_stats = self.product_service.get_product_statistics()
                
                # Get monitoring statistics
                monitoring_stats = self.price_monitor_service.get_monitoring_stats()
                
                # Get next scheduled run
                next_run = self.price_monitor_service.get_next_scheduled_run()
                
                return jsonify({
                    'products': product_stats,
                    'monitoring': monitoring_stats,
                    'next_scheduled_run': next_run.isoformat() if next_run else None,
                    'client_id': g.client_id
                })
                
            except Exception as e:
                self.logger.error(f"Error getting statistics: {str(e)}")
                return jsonify({
                    'error': 'Internal server error',
                    'message': 'Failed to retrieve statistics'
                }), 500
    

    
    def _setup_error_handlers(self):
        """Set up error handlers."""
        
        @self.app.errorhandler(404)
        def not_found(error):
            return jsonify({
                'error': 'Not found',
                'message': 'The requested endpoint does not exist'
            }), 404
        
        @self.app.errorhandler(405)
        def method_not_allowed(error):
            return jsonify({
                'error': 'Method not allowed',
                'message': 'The requested method is not allowed for this endpoint'
            }), 405
        
        @self.app.errorhandler(500)
        def internal_error(error):
            self.logger.error(f"Internal server error: {error}")
            return jsonify({
                'error': 'Internal server error',
                'message': 'An unexpected error occurred'
            }), 500
    
    def _setup_security_headers(self):
        """Set up security headers for all responses."""
        
        @self.app.after_request
        def add_security_headers(response):
            """Add security headers to all responses."""
            # HTTPS-only headers
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            
            # Content security policy
            response.headers['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
                "img-src 'self' data: https: http:; "
                "connect-src 'self'; "
                "font-src 'self' https://cdnjs.cloudflare.com; "
                "object-src 'none'; "
                "media-src 'self'; "
                "frame-src 'none';"
            )
            
            # Other security headers
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            
            # Remove server information
            response.headers.pop('Server', None)
            
            return response
    
    def create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context for HTTPS with mTLS."""
        return self.security_service.setup_mtls_context()
    
    def run(self, host: str = '0.0.0.0', port: Optional[int] = None, debug: bool = False):
        """Run the Flask application with HTTPS and mTLS."""
        if port is None:
            port = self.config.api_port
        
        if self.config.enable_mtls:
            # Run with HTTPS and mTLS
            ssl_context = self.create_ssl_context()
            self.logger.info(f"Starting secure server with mTLS on https://{host}:{port}")
            self.app.run(
                host=host,
                port=port,
                debug=debug,
                ssl_context=ssl_context
            )
        else:
            # Run without HTTPS (for development/testing only)
            self.logger.warning("Running without mTLS - this should only be used for development")
            self.app.run(
                host=host,
                port=port,
                debug=debug
            )
    
    def get_app(self) -> Flask:
        """Get the Flask application instance."""
        return self.app