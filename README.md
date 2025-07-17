# Phishing Simulator

A comprehensive phishing simulation platform designed for security training and awareness testing. This tool helps organizations evaluate their security posture by simulating phishing attacks in a controlled environment.

## ⚠️ Legal Disclaimer

**This tool is intended for authorized security testing and educational purposes only.** Users must:

- Have explicit written permission before testing any systems
- Only use this tool on systems you own or have authorization to test
- Comply with all applicable local, state, and federal laws
- Use responsibly and ethically for defensive security purposes

Unauthorized use of this tool may violate computer crime laws. The developers assume no liability for misuse.

## 🚀 Features

### Campaign Management
- Create and manage phishing campaigns
- Support for email and SMS phishing vectors
- Campaign lifecycle management (draft → active → completed)
- Real-time campaign monitoring and control

### Template System
- Pre-built phishing email templates
- Custom template creation with variable substitution
- Template testing and preview functionality
- Support for multiple languages and categories

### Target Management
- Bulk target import via CSV
- Individual target management
- Target segmentation and grouping
- Engagement scoring and tracking

### Analytics & Reporting
- Real-time tracking and analytics
- Conversion funnel analysis
- Detailed reporting with export capabilities
- Device and browser analytics
- Geographic tracking

### Security Features
- CSRF protection
- Input sanitization and XSS prevention
- Rate limiting
- Security event logging
- Secure file upload handling

## 📋 Requirements

### System Requirements
- Python 3.8 or higher
- 4GB RAM minimum (8GB recommended)
- 10GB free disk space
- Linux/Windows/macOS

### Dependencies
- Flask 2.3.3
- SQLAlchemy (via Flask-SQLAlchemy)
- Email server (SMTP) for sending emails
- Optional: SMS API for SMS campaigns

## 🛠️ Installation

### Quick Start (Development)

1. **Clone the repository**
   ```bash
   git clone https://github.com/tibosul/Phishing_Simulator_1.git
   cd Phishing_Simulator_1/Phishing_Simulator
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   
   # On Linux/macOS:
   source venv/bin/activate
   
   # On Windows:
   venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   # Copy example configuration
   cp .env.example .env
   
   # Edit .env with your settings
   nano .env
   ```

5. **Initialize database**
   ```bash
   python -c "from app import create_app; from utils.database import db; app = create_app(); app.app_context().push(); db.create_all()"
   ```

6. **Run the application**
   ```bash
   python app.py
   ```

7. **Access the application**
   - Open your browser to: http://localhost:5000
   - Default admin interface: http://localhost:5000/admin/

### Production Installation

For production deployment, additional steps are required:

1. **Use a production WSGI server**
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```

2. **Set up reverse proxy (nginx example)**
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;
       
       location / {
           proxy_pass http://127.0.0.1:5000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       }
   }
   ```

3. **Use production database**
   ```bash
   # PostgreSQL example
   pip install psycopg2-binary
   
   # Update DATABASE_URL in .env
   DATABASE_URL=postgresql://user:password@localhost/phishing_sim
   ```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file with the following configuration:

```bash
# Flask Configuration
SECRET_KEY=your-secret-key-here
FLASK_ENV=production
DEBUG=False

# Database Configuration
DATABASE_URL=sqlite:///phishing_simulator.db

# Email Configuration (Required for email campaigns)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=your-email@gmail.com

# SMS Configuration (Optional)
SMS_API_KEY=your-sms-api-key
SMS_API_SECRET=your-sms-api-secret
SMS_FROM_NUMBER=+1234567890

# Application Settings
BASE_URL=https://your-domain.com
APP_NAME=Phishing Simulator
LOG_LEVEL=INFO

# Security Settings
WTF_CSRF_ENABLED=True
BCRYPT_LOG_ROUNDS=12

# Rate Limiting
RATELIMIT_DEFAULT=100 per hour
```

### Email Configuration

#### Gmail Setup
1. Enable 2-factor authentication
2. Generate an app-specific password
3. Use the app password in `MAIL_PASSWORD`

#### Other SMTP Providers
- **Outlook/Hotmail**: smtp-mail.outlook.com:587
- **Yahoo**: smtp.mail.yahoo.com:587
- **Custom SMTP**: Configure according to your provider

### Database Configuration

#### SQLite (Development)
```bash
DATABASE_URL=sqlite:///phishing_simulator.db
```

#### PostgreSQL (Production)
```bash
DATABASE_URL=postgresql://username:password@localhost:5432/phishing_sim
```

#### MySQL (Production)
```bash
DATABASE_URL=mysql://username:password@localhost:3306/phishing_sim
```

## 📘 Usage Guide

### Creating Your First Campaign

1. **Access Admin Panel**
   - Navigate to http://localhost:5000/admin/
   - Go to "Campaigns" → "Create Campaign"

2. **Configure Campaign**
   - **Name**: Give your campaign a descriptive name
   - **Type**: Choose Email, SMS, or Both
   - **Description**: Add campaign details
   - **Settings**: Configure tracking options

3. **Create or Select Template**
   - Go to "Templates" → "Create Template"
   - Choose template type (Email/SMS)
   - Design your phishing content
   - Use variables like `{{target_name}}`, `{{tracking_link}}`

4. **Add Targets**
   - Go to your campaign → "Upload Targets"
   - Upload CSV file with target information
   - Required columns: `email`, `first_name`, `last_name`
   - Optional: `company`, `position`, `phone`

5. **Test Template**
   - Go to "Templates" → Select template → "Test"
   - Send test email to yourself
   - Verify appearance and functionality

6. **Launch Campaign**
   - Return to campaign view
   - Click "Start Campaign"
   - Monitor progress in real-time

### Template Variables

Use these variables in your templates for personalization:

- `{{target_name}}` - Full name
- `{{target_first_name}}` - First name only
- `{{target_last_name}}` - Last name only
- `{{target_email}}` - Email address
- `{{target_company}}` - Company name
- `{{target_position}}` - Job title
- `{{tracking_link}}` - **Required** - Tracking URL
- `{{tracking_pixel}}` - Email open tracking pixel
- `{{current_date}}` - Current date
- `{{current_year}}` - Current year

### CSV Target Format

```csv
email,first_name,last_name,company,position
john.doe@example.com,John,Doe,Acme Corp,Manager
jane.smith@example.com,Jane,Smith,Tech Inc,Developer
```

### Analytics and Reporting

1. **Real-time Dashboard**
   - Campaign overview
   - Success rates
   - Recent activity

2. **Detailed Analytics**
   - Conversion funnel
   - Time-to-click analysis
   - Device and browser breakdown
   - Geographic distribution

3. **Export Options**
   - Campaign results (CSV)
   - Detailed reports
   - Credential captures (if applicable)

## 🧪 Testing

### Running Tests

```bash
# Run all tests
python -m unittest discover tests -v

# Run specific test module
python -m unittest tests.test_core_functionality -v

# Run integration tests
python -m unittest tests.test_integration -v
```

### Test Coverage

The test suite includes:
- Unit tests for all models
- Service layer testing
- Integration tests for API endpoints
- Security feature validation
- Campaign workflow testing

### Creating Test Data

```bash
# Create test campaign
python -c "
from app import create_app
from services.campaign_service import CampaignService
app = create_app()
with app.app_context():
    campaign = CampaignService.create_campaign('Test Campaign', 'email', 'Test description')
    print(f'Created campaign: {campaign.id}')
"
```

## 🔒 Security Considerations

### Security Features

1. **Input Validation**
   - All user input is sanitized
   - XSS prevention
   - SQL injection protection

2. **CSRF Protection**
   - Enabled by default in production
   - All forms include CSRF tokens

3. **Rate Limiting**
   - API endpoints are rate-limited
   - Prevents abuse and DoS attacks

4. **Security Headers**
   - X-Frame-Options: DENY
   - X-Content-Type-Options: nosniff
   - Content Security Policy
   - Strict Transport Security (HTTPS)

5. **Logging**
   - Security events are logged
   - Failed authentication attempts
   - Suspicious activity detection

### Best Practices

1. **Use HTTPS in Production**
   ```bash
   # Generate SSL certificate (Let's Encrypt)
   certbot --nginx -d your-domain.com
   ```

2. **Secure Database**
   - Use strong passwords
   - Restrict database access
   - Regular backups

3. **Regular Updates**
   ```bash
   pip list --outdated
   pip install --upgrade package-name
   ```

4. **Monitor Logs**
   ```bash
   tail -f phishing_simulator.log
   ```

### Compliance Considerations

- **GDPR**: Ensure proper data handling for EU targets
- **CCPA**: Comply with California privacy laws
- **SOX**: Financial institutions have specific requirements
- **Internal Policies**: Align with your organization's policies

## 🚀 Deployment

### Docker Deployment

1. **Create Dockerfile**
   ```dockerfile
   FROM python:3.11-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install -r requirements.txt
   COPY . .
   EXPOSE 5000
   CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
   ```

2. **Build and run**
   ```bash
   docker build -t phishing-simulator .
   docker run -p 5000:5000 --env-file .env phishing-simulator
   ```

### Docker Compose

```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "5000:5000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/phishing_sim
    depends_on:
      - db
  
  db:
    image: postgres:13
    environment:
      - POSTGRES_DB=phishing_sim
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### Cloud Deployment

#### AWS (Example)
1. Use Elastic Beanstalk for easy deployment
2. RDS for managed database
3. SES for email sending
4. CloudFront for CDN

#### Google Cloud Platform
1. App Engine for hosting
2. Cloud SQL for database
3. SendGrid for email

## 🐛 Troubleshooting

### Common Issues

1. **Email not sending**
   ```bash
   # Check SMTP configuration
   python -c "
   from services.email_service import EmailService
   is_valid, message = EmailService.validate_email_config()
   print(f'Valid: {is_valid}, Message: {message}')
   "
   ```

2. **Database connection errors**
   ```bash
   # Test database connection
   python -c "
   from utils.database import db
   from app import create_app
   app = create_app()
   with app.app_context():
       db.engine.execute('SELECT 1')
       print('Database connection successful')
   "
   ```

3. **Template rendering issues**
   - Check for missing required variables
   - Ensure `{{tracking_link}}` is included
   - Validate HTML syntax

4. **Permission errors**
   ```bash
   # Fix file permissions
   chmod +x app.py
   chown -R www-data:www-data /path/to/app
   ```

### Logs and Debugging

1. **Enable debug mode**
   ```bash
   export FLASK_ENV=development
   export DEBUG=True
   ```

2. **Check application logs**
   ```bash
   tail -f phishing_simulator.log
   ```

3. **Database debugging**
   ```bash
   export SQLALCHEMY_ECHO=True
   ```

## 🤝 Contributing

We welcome contributions to improve the Phishing Simulator!

### How to Contribute

1. **Fork the repository**
   ```bash
   git clone https://github.com/your-username/Phishing_Simulator_1.git
   ```

2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes**
   - Follow the existing code style
   - Add tests for new functionality
   - Update documentation

4. **Run tests**
   ```bash
   python -m unittest discover tests -v
   ```

5. **Submit a pull request**
   - Describe your changes
   - Include test results
   - Reference any related issues

### Development Guidelines

1. **Code Style**
   - Follow PEP 8
   - Use meaningful variable names
   - Add docstrings to functions

2. **Testing**
   - Write tests for new features
   - Maintain test coverage above 80%
   - Test both success and failure cases

3. **Documentation**
   - Update README for new features
   - Add inline comments for complex logic
   - Update API documentation

4. **Security**
   - Follow secure coding practices
   - Validate all user input
   - Never commit secrets or credentials

### Reporting Issues

When reporting bugs or requesting features:

1. Use the GitHub issue tracker
2. Provide detailed reproduction steps
3. Include system information and logs
4. Check for existing similar issues

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

### Getting Help

1. **Documentation**: Check this README and inline documentation
2. **Issues**: Search existing GitHub issues
3. **Community**: Join our discussions on GitHub

### Commercial Support

For enterprise deployments and commercial support, please contact the development team.

## 🙏 Acknowledgments

- Flask and the Python web development community
- Security researchers who contribute to defensive security
- Organizations that prioritize security awareness training

## 📞 Contact

- **Project Repository**: https://github.com/tibosul/Phishing_Simulator_1
- **Issues**: https://github.com/tibosul/Phishing_Simulator_1/issues

---

**Remember**: This tool is for authorized testing only. Use responsibly and ethically.