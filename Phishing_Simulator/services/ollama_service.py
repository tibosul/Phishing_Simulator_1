import logging
import requests
import json
from datetime import datetime
from flask import current_app
from jinja2 import Template

from models.campaign import Campaign
from models.target import Target
from models.template import Template as EmailTemplate
from utils.helpers import sanitize_input, get_client_ip, log_security_event
from utils.validators import ValidationError


class OllamaService:
    """
    Service pentru personalizarea conținutului cu AI folosind Ollama
    
    Features:
    - Generarea automată de template-uri de phishing
    - Personalizarea conținutului pe baza profilului țintei
    - Adaptarea tonului și stilului în funcție de context
    - Generarea de subiecte persuasive
    - Optimizarea pentru rate de conversie mai mari
    - Support pentru multiple limbi
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.base_url = current_app.config.get('OLLAMA_BASE_URL', 'http://localhost:11434')
        self.model = current_app.config.get('OLLAMA_MODEL', 'llama2')
        self.timeout = current_app.config.get('OLLAMA_TIMEOUT', 30)
        
        # Template-uri de prompt pentru diferite tipuri de conținut
        self.prompt_templates = {
            'email_generation': """
You are an expert in creating realistic email templates for security awareness training. 
Create a professional email template that appears to be from {company} with the following characteristics:

Context: {context}
Target Profile: {target_profile}
Email Type: {email_type}
Language: {language}
Urgency Level: {urgency_level}

The email should:
- Sound authentic and professional
- Include appropriate branding elements
- Have a compelling subject line
- Include a call-to-action
- Use placeholder variables like {{target_name}}, {{tracking_link}}
- Be convincing but educational in nature

Return the response in JSON format with:
- subject: Email subject line
- content: Full HTML email content
- tone: Description of the tone used
- persuasion_techniques: List of techniques employed

Remember: This is for security awareness training purposes only.
""",
            
            'personalization': """
You are an AI assistant that personalizes phishing simulation emails for security training.

Original Template: {template_content}
Target Information:
- Name: {target_name}
- Company: {target_company}
- Position: {target_position}
- Industry: {target_industry}
- Location: {target_location}

Personalize this template to be more relevant and engaging for this specific target while maintaining the educational purpose. Make it feel like it was written specifically for them.

Return the personalized content with the same structure as the original.
""",
            
            'subject_optimization': """
Generate 5 compelling email subject lines for a security awareness training email with these characteristics:

Email Type: {email_type}
Company: {company}
Context: {context}
Target Role: {target_role}
Urgency: {urgency}

Each subject should:
- Be under 50 characters
- Create urgency or curiosity
- Sound professional
- Be relevant to the target's role
- Avoid spam trigger words

Return as a JSON array of subject lines with effectiveness scores (1-10).
""",
            
            'sms_generation': """
Create a realistic SMS template for security awareness training:

Context: {context}
Character Limit: 160
Company: {company}
Urgency: {urgency_level}

The SMS should:
- Include {{tracking_link}} placeholder
- Sound urgent but professional
- Be concise and action-oriented
- Appear to be from a legitimate source

Return the SMS content only.
""",
            
            'content_analysis': """
Analyze this phishing simulation template and provide feedback:

Template: {content}
Type: {template_type}

Evaluate:
1. Realism and authenticity
2. Persuasion techniques used
3. Potential effectiveness
4. Areas for improvement
5. Risk level for training

Return analysis in JSON format with scores and recommendations.
"""
        }
    
    def _make_ollama_request(self, prompt, model=None, stream=False):
        """
        Face un request către Ollama API
        
        Args:
            prompt: Prompt-ul pentru AI
            model: Modelul de folosit (default: self.model)
            stream: Dacă să folosească streaming
            
        Returns:
            dict: Răspunsul de la Ollama
        """
        try:
            url = f"{self.base_url}/api/generate"
            
            payload = {
                "model": model or self.model,
                "prompt": prompt,
                "stream": stream,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "top_k": 40,
                    "num_predict": 1000
                }
            }
            
            response = requests.post(
                url, 
                json=payload, 
                timeout=self.timeout,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    'success': True,
                    'content': result.get('response', ''),
                    'model': result.get('model', model),
                    'done': result.get('done', True)
                }
            else:
                self.logger.error(f"Ollama API error: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': f"API error: {response.status_code}"
                }
                
        except requests.exceptions.Timeout:
            self.logger.error("Ollama request timeout")
            return {
                'success': False,
                'error': "Request timeout"
            }
        except requests.exceptions.ConnectionError:
            self.logger.error("Cannot connect to Ollama service")
            return {
                'success': False,
                'error': "Connection error"
            }
        except Exception as e:
            self.logger.error(f"Ollama request failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def generate_email_template(self, email_type, company="Revolut", context="", 
                              target_profile=None, language="en", urgency_level="medium"):
        """
        Generează un template de email cu AI
        
        Args:
            email_type: Tipul email-ului (security, promotion, update, etc.)
            company: Compania de la care pare să vină email-ul
            context: Contextul specific al email-ului
            target_profile: Profilul țintei (rol, industrie, etc.)
            language: Limba pentru template
            urgency_level: Nivelul de urgență (low, medium, high)
            
        Returns:
            dict: Template-ul generat cu subject și content
        """
        try:
            # Construiește prompt-ul
            prompt = self.prompt_templates['email_generation'].format(
                company=company,
                context=context or f"A {email_type} email notification",
                target_profile=target_profile or "General business professional",
                email_type=email_type,
                language=language,
                urgency_level=urgency_level
            )
            
            # Face request către Ollama
            response = self._make_ollama_request(prompt)
            
            if not response['success']:
                raise Exception(f"AI generation failed: {response['error']}")
            
            # Încearcă să parseze răspunsul ca JSON
            try:
                content = response['content'].strip()
                # Găsește JSON-ul în răspuns
                json_start = content.find('{')
                json_end = content.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_content = content[json_start:json_end]
                    result = json.loads(json_content)
                else:
                    # Fallback dacă nu găsește JSON
                    result = {
                        'subject': f'{email_type.title()} Notification from {company}',
                        'content': content,
                        'tone': 'professional',
                        'persuasion_techniques': ['authority', 'urgency']
                    }
            except json.JSONDecodeError:
                # Fallback pentru răspunsuri care nu sunt JSON
                lines = response['content'].split('\n')
                subject = next((line for line in lines if 'subject' in line.lower()), 
                              f'{email_type.title()} from {company}')
                
                result = {
                    'subject': subject.split(':', 1)[-1].strip() if ':' in subject else subject,
                    'content': response['content'],
                    'tone': 'professional',
                    'persuasion_techniques': ['authority']
                }
            
            # Validează și sanitizează rezultatul
            result['subject'] = sanitize_input(result.get('subject', ''))
            result['content'] = result.get('content', '')
            
            # Asigură-te că template-ul conține placeholder-urile necesare
            if '{{tracking_link}}' not in result['content']:
                result['content'] += '\n\n<a href="{{tracking_link}}">Click here to verify</a>'
            
            if '{{target_name}}' not in result['content']:
                result['content'] = result['content'].replace('Dear user', 'Dear {{target_name}}', 1)
            
            self.logger.info(f"Generated {email_type} email template using AI")
            log_security_event('ai_template_generated', f'AI generated {email_type} template')
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error generating email template: {str(e)}")
            return self._get_fallback_template(email_type, company)
    
    def personalize_content(self, template_content, target, campaign=None):
        """
        Personalizează conținutul pentru o țintă specifică folosind AI
        
        Args:
            template_content: Conținutul template-ului original
            target: Obiectul Target cu informații despre țintă
            campaign: Campania asociată (opțional)
            
        Returns:
            str: Conținutul personalizat
        """
        try:
            # Construiește profilul țintei
            target_profile = {
                'target_name': target.display_name or target.email,
                'target_company': target.company or 'Unknown Company',
                'target_position': target.position or 'Employee',
                'target_industry': self._guess_industry_from_email(target.email),
                'target_location': self._guess_location_from_domain(target.email)
            }
            
            # Construiește prompt-ul pentru personalizare
            prompt = self.prompt_templates['personalization'].format(
                template_content=template_content,
                **target_profile
            )
            
            # Face request către Ollama
            response = self._make_ollama_request(prompt)
            
            if response['success']:
                personalized_content = response['content'].strip()
                
                # Sanitizează conținutul
                personalized_content = sanitize_input(personalized_content)
                
                self.logger.info(f"Personalized content for target {target.email}")
                
                return personalized_content
            else:
                self.logger.warning(f"AI personalization failed: {response['error']}")
                return template_content
                
        except Exception as e:
            self.logger.error(f"Error personalizing content: {str(e)}")
            return template_content
    
    def generate_subject_lines(self, email_type, company="Revolut", context="", 
                             target_role="employee", urgency="medium", count=5):
        """
        Generează multiple variante de subject pentru A/B testing
        
        Args:
            email_type: Tipul email-ului
            company: Compania
            context: Contextul
            target_role: Rolul țintei
            urgency: Nivelul de urgență
            count: Numărul de variante de generat
            
        Returns:
            list: Lista cu subject lines și scorurile lor
        """
        try:
            prompt = self.prompt_templates['subject_optimization'].format(
                email_type=email_type,
                company=company,
                context=context,
                target_role=target_role,
                urgency=urgency
            )
            
            response = self._make_ollama_request(prompt)
            
            if response['success']:
                try:
                    # Încearcă să parseze JSON
                    content = response['content'].strip()
                    json_start = content.find('[')
                    json_end = content.rfind(']') + 1
                    
                    if json_start >= 0 and json_end > json_start:
                        json_content = content[json_start:json_end]
                        subjects = json.loads(json_content)
                    else:
                        # Fallback - ia liniile ca subject-uri
                        lines = [line.strip() for line in response['content'].split('\n') if line.strip()]
                        subjects = [{'subject': line, 'score': 7} for line in lines[:count]]
                    
                    # Sanitizează subject-urile
                    for item in subjects:
                        if isinstance(item, dict):
                            item['subject'] = sanitize_input(item.get('subject', ''))
                        elif isinstance(item, str):
                            item = {'subject': sanitize_input(item), 'score': 7}
                    
                    return subjects[:count]
                    
                except (json.JSONDecodeError, KeyError):
                    # Fallback cu subject-uri generate manual
                    return self._get_fallback_subjects(email_type, company, count)
            else:
                return self._get_fallback_subjects(email_type, company, count)
                
        except Exception as e:
            self.logger.error(f"Error generating subject lines: {str(e)}")
            return self._get_fallback_subjects(email_type, company, count)
    
    def generate_sms_template(self, context, company="Revolut", urgency_level="high"):
        """
        Generează un template SMS cu AI
        
        Args:
            context: Contextul SMS-ului
            company: Compania
            urgency_level: Nivelul de urgență
            
        Returns:
            str: Template-ul SMS generat
        """
        try:
            prompt = self.prompt_templates['sms_generation'].format(
                context=context,
                company=company,
                urgency_level=urgency_level
            )
            
            response = self._make_ollama_request(prompt)
            
            if response['success']:
                sms_content = response['content'].strip()
                
                # Asigură-te că SMS-ul conține tracking link
                if '{{tracking_link}}' not in sms_content:
                    sms_content += ' {{tracking_link}}'
                
                # Verifică lungimea (max 160 caractere pentru SMS standard)
                if len(sms_content) > 160:
                    # Scurtează conținutul
                    sms_content = sms_content[:140] + '... {{tracking_link}}'
                
                return sanitize_input(sms_content)
            else:
                return self._get_fallback_sms(company)
                
        except Exception as e:
            self.logger.error(f"Error generating SMS template: {str(e)}")
            return self._get_fallback_sms(company)
    
    def analyze_template_effectiveness(self, content, template_type):
        """
        Analizează eficacitatea unui template folosind AI
        
        Args:
            content: Conținutul template-ului
            template_type: Tipul template-ului (email/sms)
            
        Returns:
            dict: Analiza cu scoruri și recomandări
        """
        try:
            prompt = self.prompt_templates['content_analysis'].format(
                content=content,
                template_type=template_type
            )
            
            response = self._make_ollama_request(prompt)
            
            if response['success']:
                try:
                    # Încearcă să parseze JSON
                    content_text = response['content'].strip()
                    json_start = content_text.find('{')
                    json_end = content_text.rfind('}') + 1
                    
                    if json_start >= 0 and json_end > json_start:
                        json_content = content_text[json_start:json_end]
                        analysis = json.loads(json_content)
                    else:
                        # Fallback analysis
                        analysis = {
                            'realism_score': 7,
                            'persuasion_score': 6,
                            'effectiveness_score': 7,
                            'recommendations': ['Consider adding more urgency', 'Improve call-to-action'],
                            'risk_level': 'medium'
                        }
                    
                    return analysis
                    
                except json.JSONDecodeError:
                    return self._get_fallback_analysis()
            else:
                return self._get_fallback_analysis()
                
        except Exception as e:
            self.logger.error(f"Error analyzing template: {str(e)}")
            return self._get_fallback_analysis()
    
    def optimize_for_target_role(self, template_content, target_role):
        """
        Optimizează template-ul pentru un anumit rol organizațional
        
        Args:
            template_content: Conținutul original
            target_role: Rolul țintei (CEO, IT, HR, etc.)
            
        Returns:
            str: Conținutul optimizat pentru rol
        """
        try:
            role_specific_prompts = {
                'ceo': 'Focus on high-level business impact and board-level concerns',
                'cfo': 'Emphasize financial implications and compliance requirements',
                'it': 'Use technical language and focus on system security',
                'hr': 'Frame around employee policies and company procedures',
                'employee': 'Use simple language and focus on personal account security'
            }
            
            role_context = role_specific_prompts.get(target_role.lower(), 
                                                   role_specific_prompts['employee'])
            
            prompt = f"""
Adapt this email template for someone in a {target_role} role:

{template_content}

Adaptation guidance: {role_context}

Make the language, concerns, and call-to-action appropriate for this role while maintaining the core message.
"""
            
            response = self._make_ollama_request(prompt)
            
            if response['success']:
                return sanitize_input(response['content'].strip())
            else:
                return template_content
                
        except Exception as e:
            self.logger.error(f"Error optimizing for role {target_role}: {str(e)}")
            return template_content
    
    def generate_multilingual_template(self, template_content, target_language):
        """
        Traduce și adaptează un template pentru o altă limbă
        
        Args:
            template_content: Template-ul în limba originală
            target_language: Limba țintă (ro, fr, de, etc.)
            
        Returns:
            str: Template-ul tradus și adaptat cultural
        """
        try:
            language_names = {
                'ro': 'Romanian',
                'fr': 'French', 
                'de': 'German',
                'es': 'Spanish',
                'it': 'Italian'
            }
            
            language_name = language_names.get(target_language, target_language)
            
            prompt = f"""
Translate and culturally adapt this email template to {language_name}:

{template_content}

Make sure to:
- Translate accurately while maintaining the persuasive tone
- Adapt cultural references appropriately
- Keep all placeholder variables ({{...}}) unchanged
- Maintain professional business language
- Consider local business customs and communication styles

Return only the translated template.
"""
            
            response = self._make_ollama_request(prompt)
            
            if response['success']:
                return response['content'].strip()
            else:
                return template_content
                
        except Exception as e:
            self.logger.error(f"Error translating to {target_language}: {str(e)}")
            return template_content
    
    # === HELPER METHODS ===
    
    def _guess_industry_from_email(self, email):
        """Ghicește industria pe baza domeniului email-ului"""
        domain = email.split('@')[-1].lower()
        
        industry_domains = {
            'bank': 'banking',
            'finance': 'financial services',
            'hospital': 'healthcare', 
            'medical': 'healthcare',
            'edu': 'education',
            'gov': 'government',
            'tech': 'technology',
            'consulting': 'consulting'
        }
        
        for keyword, industry in industry_domains.items():
            if keyword in domain:
                return industry
        
        return 'business'
    
    def _guess_location_from_domain(self, email):
        """Ghicește locația pe baza domeniului email-ului"""
        domain = email.split('@')[-1].lower()
        
        if domain.endswith('.ro'):
            return 'Romania'
        elif domain.endswith('.uk'):
            return 'United Kingdom'
        elif domain.endswith('.de'):
            return 'Germany'
        elif domain.endswith('.fr'):
            return 'France'
        
        return 'International'
    
    def _get_fallback_template(self, email_type, company):
        """Returnează un template de fallback dacă AI-ul nu funcționează"""
        fallback_templates = {
            'security': {
                'subject': f'Security Alert from {company}',
                'content': f'''
                <div style="font-family: Arial, sans-serif;">
                    <h2>Security Alert</h2>
                    <p>Dear {{{{target_name}}}},</p>
                    <p>We detected suspicious activity on your {company} account.</p>
                    <a href="{{{{tracking_link}}}}">Verify Account</a>
                    <p>— {company} Security Team</p>
                </div>
                ''',
                'tone': 'urgent',
                'persuasion_techniques': ['authority', 'urgency']
            },
            'promotion': {
                'subject': f'Special Offer from {company}',
                'content': f'''
                <div style="font-family: Arial, sans-serif;">
                    <h2>Exclusive Offer</h2>
                    <p>Hi {{{{target_name}}}},</p>
                    <p>Limited time offer just for you!</p>
                    <a href="{{{{tracking_link}}}}">Claim Offer</a>
                    <p>— {company} Team</p>
                </div>
                ''',
                'tone': 'friendly',
                'persuasion_techniques': ['scarcity', 'personalization']
            }
        }
        
        return fallback_templates.get(email_type, fallback_templates['security'])
    
    def _get_fallback_subjects(self, email_type, company, count):
        """Returnează subject-uri de fallback"""
        subjects = {
            'security': [
                f'Security Alert: Action Required - {company}',
                f'Suspicious Activity Detected on Your {company} Account',
                f'Immediate Verification Required - {company} Security',
                f'Your {company} Account Has Been Compromised',
                f'Urgent: Confirm Your {company} Account Details'
            ],
            'promotion': [
                f'Exclusive Offer Just for You - {company}',
                f'Limited Time: Special {company} Benefits',
                f'Your {company} Rewards Are Waiting',
                f'Claim Your {company} Bonus Today',
                f'Last Chance: {company} Premium Upgrade'
            ]
        }
        
        subject_list = subjects.get(email_type, subjects['security'])
        return [{'subject': subj, 'score': 7} for subj in subject_list[:count]]
    
    def _get_fallback_sms(self, company):
        """Returnează SMS de fallback"""
        return f'{company} ALERT: Suspicious activity. Verify: {{{{tracking_link}}}}'
    
    def _get_fallback_analysis(self):
        """Returnează analiză de fallback"""
        return {
            'realism_score': 7,
            'persuasion_score': 6,
            'effectiveness_score': 7,
            'recommendations': ['Template appears functional for training purposes'],
            'risk_level': 'medium',
            'analysis_note': 'Fallback analysis - AI analysis unavailable'
        }
    
    def health_check(self):
        """
        Verifică dacă serviciul Ollama este disponibil
        
        Returns:
            dict: Statusul serviciului
        """
        try:
            # Testează conectivitatea cu un prompt simplu
            test_response = self._make_ollama_request("Hello", model=self.model)
            
            if test_response['success']:
                return {
                    'status': 'healthy',
                    'model': self.model,
                    'base_url': self.base_url,
                    'response_time': 'normal'
                }
            else:
                return {
                    'status': 'unhealthy',
                    'error': test_response['error']
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    @staticmethod
    def is_available():
        """
        Verifică rapid dacă serviciul Ollama este configurat și disponibil
        
        Returns:
            bool: True dacă serviciul este disponibil
        """
        try:
            base_url = current_app.config.get('OLLAMA_BASE_URL')
            if not base_url:
                return False
            
            # Testează conectivitatea rapidă
            response = requests.get(f"{base_url}/api/tags", timeout=5)
            return response.status_code == 200
            
        except:
            return False